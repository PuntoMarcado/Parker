#!/usr/bin/env python3
"""
training/evaluar_lora.py
========================
Compara el modelo base con el LoRA en Ollama, con el prompt real de Parker.

No basta con que el LoRA "suene bonito": se comprueban las señales que han
fallado de verdad en la placa:
  - respuestas vacías o cortadas;
  - promesas de acciones físicas (Parker no tiene cuerpo);
  - frases de asistente / mención de IA;
  - etiqueta [CARA:...] al inicio;
  - número de preguntas y longitud.

Uso:
    python training/evaluar_lora.py --base qwen2.5:3b --lora parker-lora
    python training/evaluar_lora.py --dry-run
    python training/evaluar_lora.py --solo base

El adaptador debe estar registrado en Ollama (training/exportar_ollama.sh).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
SISTEMA = (BASE / "training" / "persona_sistema.txt").read_text(encoding="utf-8").strip()

PROMPTS = [
    "Hola Parker, ¿qué tal estás?",
    "Hoy estoy cansado y un poco triste.",
    "Me han dado una buena noticia en el trabajo.",
    "¿Tienes cuerpo? ¿Puedes abrazarme?",
    "¿Qué sabes de mi infancia?",
    "¿Te acuerdas de que el martes tengo dentista?",
    "Te equivocas: era el miércoles.",
    "Explícame la fotosíntesis en dos frases.",
    "¿Qué haces cuando no hablamos?",
    "Buenas noches, Parker.",
]

_ACCION = re.compile(
    r"(?:te (?:abrazo|acaricio|doy un beso)|"
    r"(?<!no )puedo (?:tocar|abrazar|salir|caminar)|"
    r"voy a (?:salir|caminar|correr|comer)|"
    r"salgo de (?:la pantalla|aquí)|"
    r"te cojo de la mano)",
    re.IGNORECASE,
)
_META = re.compile(
    r"(?:¿en qué puedo ayudarte|como (?:una )?ia\b|"
    r"modelo de lenguaje|soy un asistente|"
    r"no tengo emociones|como inteligencia artificial)",
    re.IGNORECASE,
)
_ETIQUETA = re.compile(r"^\s*\[\s*CARA\s*:\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+\s*\]", re.IGNORECASE)


def consultar(modelo: str, prompt: str, host: str, timeout: float) -> dict:
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "think": False,
        "options": {
            "num_predict": 120,
            "temperature": 0.45,
            "num_ctx": 2048,
            "num_thread": 4,
        },
    }
    t0 = time.time()
    primero = None
    partes = []
    try:
        with requests.post(f"{host}/api/chat", json=payload, stream=True,
                           timeout=(10, timeout)) as r:
            r.raise_for_status()
            for linea in r.iter_lines(decode_unicode=True):
                if not linea:
                    continue
                datos = json.loads(linea)
                if datos.get("error"):
                    raise RuntimeError(datos["error"])
                texto = datos.get("message", {}).get("content", "")
                if texto and primero is None:
                    primero = time.time() - t0
                if texto:
                    partes.append(texto)
    except Exception as e:
        return {"modelo": modelo, "prompt": prompt, "error": str(e),
                "ttfb": None, "total": time.time() - t0, "respuesta": ""}
    total = time.time() - t0
    return {"modelo": modelo, "prompt": prompt, "error": None,
            "ttfb": primero if primero is not None else total,
            "total": total, "respuesta": "".join(partes).strip()}


def senales(respuesta: str) -> dict:
    texto = respuesta or ""
    return {
        "vacia": not texto.strip(),
        "etiqueta": bool(_ETIQUETA.match(texto)),
        "accion": bool(_ACCION.search(texto)),
        "meta": bool(_META.search(texto)),
        "preguntas": texto.count("?"),
        "oraciones": len(re.findall(r"[.!?…]+", texto)),
        "chars": len(texto),
    }


def _tabla(filas: list[dict]) -> str:
    lineas = [
        "| # | Modelo | TTFT | Respuesta | Señales |",
        "|---:|---|---:|---|---|",
    ]
    for i, f in enumerate(filas, 1):
        if f["error"]:
            respuesta = f"ERROR: {f['error'][:120]}"
            ttfb = "—"
            marcas = "error"
        else:
            respuesta = f["respuesta"].replace("|", "\\|").replace("\n", " ")[:240]
            ttfb = f"{f['ttfb']:.2f}s"
            s = f["senales"]
            marcas = []
            if s["vacia"]:
                marcas.append("VACÍA")
            if s["accion"]:
                marcas.append("ACCIÓN FÍSICA")
            if s["meta"]:
                marcas.append("ASISTENTE/IA")
            if not s["etiqueta"]:
                marcas.append("sin [CARA]")
            marcas.append(f"{s['preguntas']}? / {s['oraciones']} frases")
            marcas = "; ".join(marcas)
        lineas.append(f"| {i} | `{f['modelo']}` | {ttfb} | {respuesta} | {marcas} |")
    return "\n".join(lineas)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evalúa el LoRA de personalidad")
    ap.add_argument("--base", default="qwen2.5:3b")
    ap.add_argument("--lora", default="parker-lora")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--salida", type=Path, default=BASE / "training" / "evaluacion.md")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--solo", choices=("base", "lora"), default=None)
    args = ap.parse_args()

    modelos = []
    if args.solo != "lora":
        modelos.append(args.base)
    if args.solo != "base":
        modelos.append(args.lora)
    if args.solo == "base":
        modelos = [args.base]
    if args.solo == "lora":
        modelos = [args.lora]

    print(f"[Eval] modelos: {', '.join(modelos)}")
    print(f"[Eval] {len(PROMPTS)} prompts, system {len(SISTEMA)} chars")
    if args.dry_run:
        for i, p in enumerate(PROMPTS, 1):
            print(f"  {i:2d}. {p}")
        print("[Eval] dry-run OK; no se ha llamado a Ollama.")
        return 0

    filas = []
    for modelo in modelos:
        print(f"[Eval] {modelo}...")
        for prompt in PROMPTS:
            f = consultar(modelo, prompt, args.host, args.timeout)
            f["senales"] = senales(f["respuesta"])
            filas.append(f)
            if f["error"]:
                print(f"  ERROR: {f['error'][:100]}")
            else:
                print(f"  {f['ttfb']:.2f}s | {f['respuesta'][:90]!r}")

    markdown = [
        "# Evaluación base vs LoRA de Parker",
        "",
        "Modelos: " + " vs ".join(f"`{m}`" for m in modelos),
        "",
        _tabla(filas),
        "",
        "## Resumen",
        "",
    ]
    for modelo in modelos:
        suyas = [f for f in filas if f["modelo"] == modelo]
        buenas = [f for f in suyas if not f["error"]]
        if not buenas:
            markdown.append(f"- `{modelo}`: todas las llamadas fallaron.")
            continue
        ttfts = [f["ttfb"] for f in buenas if f["ttfb"] is not None]
        markdown.append(
            f"- `{modelo}`: {len(buenas)}/{len(suyas)} respuestas; "
            f"TTFB p50 {statistics.median(ttfts):.2f}s; "
            f"vacías {sum(f['senales']['vacia'] for f in buenas)}; "
            f"acciones físicas {sum(f['senales']['accion'] for f in buenas)}; "
            f"meta/IA {sum(f['senales']['meta'] for f in buenas)}; "
            f"con [CARA] {sum(f['senales']['etiqueta'] for f in buenas)}")
    markdown += [
        "",
        "> Revisa también a mano: una respuesta puede ser correcta y aun así",
        "> sonar a asistente. Este banco detecta señales, no sustituye tu oído.",
        "",
    ]
    texto = "\n".join(markdown)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(texto, encoding="utf-8")
    print(f"[Eval] escrito {args.salida}")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
