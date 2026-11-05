#!/usr/bin/env python3
"""
training/fusionar_lora.py
=========================
Fusiona el adaptador LoRA con el modelo base (en CPU/GPU) y deja un modelo
Hugging Face completo, que es lo que `llama.cpp` convierte a GGUF.

Uso:
    python training/fusionar_lora.py \
        --base Qwen/Qwen2.5-3B-Instruct \
        --adapter training/salida/parker-lora \
        --salida training/salida/parker-lora-merged

Necesita transformers + peft + torch (ver training/requirements-lora.txt).
No se ejecuta en la Orange Pi: la fusión de un 3B pide varios GB de RAM/VRAM.
Con `--dry-run` solo comprueba rutas, sin cargar el modelo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Fusiona el adaptador LoRA de Parker")
    ap.add_argument("--base", default="Qwen/Qwen2.5-3B-Instruct")
    ap.add_argument("--adapter", type=Path, default=Path("training/salida/parker-lora"))
    ap.add_argument("--salida", type=Path, default=Path("training/salida/parker-lora-merged"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"[Fusión] base={args.base}")
    print(f"[Fusión] adaptador={args.adapter}")
    print(f"[Fusión] salida={args.salida}")
    if args.dry_run:
        print("[Fusión] dry-run OK (no se ha cargado el modelo).")
        return 0
    if not args.adapter.exists():
        print(f"[Fusión] ERROR: no existe el adaptador {args.adapter}")
        return 1

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:
        print(f"[Fusión] ERROR: faltan dependencias: {e}")
        print("[Fusión] Instala training/requirements-lora.txt.")
        return 1

    print("[Fusión] cargando base (fp16)...")
    modelo = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype=torch.float16, low_cpu_mem_usage=True)
    print("[Fusión] aplicando adaptador...")
    modelo = PeftModel.from_pretrained(modelo, str(args.adapter))
    modelo = modelo.merge_and_unload()
    args.salida.mkdir(parents=True, exist_ok=True)
    modelo.save_pretrained(str(args.salida), safe_serialization=True)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter))
    tokenizer.save_pretrained(str(args.salida))
    print(f"[Fusión] modelo fusionado en {args.salida}")
    print("[Fusión] siguiente: convertir a GGUF (training/exportar_ollama.sh).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
