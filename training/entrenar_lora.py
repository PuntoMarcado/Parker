#!/usr/bin/env python3
"""
training/entrenar_lora.py
=========================
Entrena un LoRA de PERSONALIDAD (texto) sobre Qwen2.5-3B-Instruct con QLoRA.

No se puede ejecutar en la Orange Pi ni en este PC sin GPU: necesita CUDA y
unos 6-8 GB de VRAM (3B en 4 bits). Para probar el dataset sin GPU:
    python training/entrenar_lora.py --dry-run

Instalación (máquina con GPU, Python 3.10/3.11):
    pip install -r training/requirements-lora.txt

Uso típico:
    python training/entrenar_lora.py
    python training/entrenar_lora.py --epocas 2 --max-seq 1536
    python training/entrenar_lora.py --modelo Qwen/Qwen2.5-1.5B-Instruct

El adaptador se guarda en training/salida/parker-lora/. Después:
    bash training/exportar_ollama.sh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATOS = BASE / "training" / "datos"


def _cargar(ruta: Path) -> list[dict]:
    filas = []
    with ruta.open("r", encoding="utf-8") as f:
        for n, linea in enumerate(f, 1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                fila = json.loads(linea)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{ruta}:{n}: JSON inválido ({e})")
            mensajes = fila.get("messages")
            if not isinstance(mensajes, list) or len(mensajes) < 3:
                raise SystemExit(f"{ruta}:{n}: faltan mensajes")
            if mensajes[0].get("role") != "system":
                raise SystemExit(f"{ruta}:{n}: el primer mensaje no es system")
            for i, m in enumerate(mensajes):
                if m.get("role") not in ("system", "user", "assistant"):
                    raise SystemExit(f"{ruta}:{n}: rol inválido en {i}")
                if not isinstance(m.get("content"), str) or not m["content"].strip():
                    raise SystemExit(f"{ruta}:{n}: contenido vacío en {i}")
            filas.append(fila)
    return filas


def _resumen(nombre: str, filas: list[dict]) -> None:
    turnos = sum(len(f["messages"]) - 1 for f in filas)
    chars = sum(len(m["content"]) for f in filas for m in f["messages"])
    print(f"[LoRA] {nombre}: {len(filas)} diálogos, {turnos} turnos, "
          f"~{chars / 4:.0f} tokens de contenido")


def main() -> int:
    ap = argparse.ArgumentParser(description="Entrena el LoRA de personalidad de Parker")
    ap.add_argument("--modelo", default="Qwen/Qwen2.5-3B-Instruct",
                    help="modelo base de Hugging Face")
    ap.add_argument("--train", type=Path, default=DATOS / "parker_train.jsonl")
    ap.add_argument("--val", type=Path, default=DATOS / "parker_val.jsonl")
    ap.add_argument("--salida", type=Path, default=BASE / "training" / "salida" / "parker-lora")
    ap.add_argument("--epocas", type=float, default=3.0)
    ap.add_argument("--max-seq", type=int, default=2048)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true",
                    help="valida el dataset y muestra el plan sin cargar el modelo")
    args = ap.parse_args()

    if not args.train.exists():
        print(f"[LoRA] ERROR: no existe {args.train}. Ejecuta antes "
              f"`python training/preparar_dataset.py`.")
        return 1
    train = _cargar(args.train)
    val = _cargar(args.val) if args.val.exists() else []
    _resumen("train", train)
    _resumen("val", val)
    if len(train) < 300:
        print("[LoRA] AVISO: menos de 300 diálogos. El adaptador puede "
              "sobreajustar y repetir frases; usa más datos reales o "
              "`training/generar_dataset.py` y revísalos.")
    if not val:
        print("[LoRA] AVISO: no hay validación; no podrás comparar de forma justa.")

    print(f"[LoRA] plan: {args.modelo} | r={args.r} alpha={args.alpha} "
          f"| {args.epocas} épocas | seq={args.max_seq} | "
          f"batch={args.batch} x grad_accum={args.grad_accum}")
    if args.dry_run:
        print("[LoRA] dry-run OK: dataset válido; no se ha cargado ningún modelo.")
        return 0

    try:
        import torch
    except ImportError:
        print("[LoRA] ERROR: falta torch. Instala training/requirements-lora.txt "
              "en una máquina con GPU.")
        return 1
    if not torch.cuda.is_available():
        print("[LoRA] ERROR: no hay CUDA. Este script necesita una GPU; "
              "usa Colab/Kaggle o una máquina con NVIDIA. El dataset sí se "
              "puede preparar y validar aquí con --dry-run.")
        return 1

    try:
        from unsloth import FastLanguageModel, is_bfloat16_supported
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
    except Exception as e:
        print(f"[LoRA] ERROR: faltan dependencias de entrenamiento: {e}")
        print("[LoRA] Instala training/requirements-lora.txt en el entorno con GPU.")
        return 1

    print("[LoRA] cargando modelo en 4 bits...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.modelo,
        max_seq_length=args.max_seq,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.alpha,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )

    eos = tokenizer.eos_token or ""
    def formatear(ejemplo: dict) -> dict:
        texto = tokenizer.apply_chat_template(
            ejemplo["messages"], tokenize=False, add_generation_prompt=False)
        if eos and not texto.endswith(eos):
            texto += eos
        return {"text": texto}

    archivos = {"train": str(args.train)}
    if val:
        archivos["validation"] = str(args.val)
    dataset = load_dataset("json", data_files=archivos)
    dataset = dataset.map(formatear, remove_columns=dataset["train"].column_names)

    config = SFTConfig(
        output_dir=str(args.salida),
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=10,
        num_train_epochs=args.epocas,
        learning_rate=args.lr,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        report_to="none",
        save_strategy="epoch",
    )
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        dataset_text_field="text",
        max_seq_length=args.max_seq,
        dataset_num_proc=2,
        packing=False,
        args=config,
    )
    print("[LoRA] entrenando...")
    trainer.train()
    args.salida.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.salida))
    tokenizer.save_pretrained(str(args.salida))
    print(f"[LoRA] adaptador guardado en {args.salida}")
    print("[LoRA] siguiente: bash training/exportar_ollama.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
