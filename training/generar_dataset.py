#!/usr/bin/env python3
"""
training/generar_dataset.py
===========================
Amplía la semilla con diálogos sintéticos generados por Groq.

No se ejecuta en el entrenamiento: es una herramienta de DATOS. Gasta tokens
de la cuenta de Groq y su resultado hay que revisarlo a mano antes de usarlo.

Salida: training/datos/sintetico.jsonl (campo `turnos`, como la semilla).

Uso:
    python training/generar_dataset.py --n 120
    python training/generar_dataset.py --n 120 --lote 6 --dry-run
    python training/preparar_dataset.py --extra training/datos/sintetico.jsonl

La clave se lee de GROQ_API_KEY o de .env; nunca se imprime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "training"))

from preparar_dataset import (  # noqa: E402
    SEMILLA, SISTEMA_PATH, _clave, _limpiar, _normalizar_respuesta,
    _sin_tildes, _valido, cargar_semilla,
)

API = "https://api.groq.com/openai/v1/chat/completions"


def _leer_clave() -> str:
    clave = (os.environ.get("GROQ_API_KEY") or "").strip()
    if clave:
        return clave
    env = BASE / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"\s*GROQ_API_KEY\s*=\s*['\"]?([^'\"\s]+)", linea)
            if m:
                return m.group(1)
    return ""


def _prompt_guionista(n: int, ejemplos: list[dict]) -> str:
    muestra = "\n".join(
        json.dumps({"turnos": d["turnos"]}, ensure_ascii=False)
        for d in ejemplos[:8]
    )
    return f"""Eres guionista de diálogos para Parker, una carita amable en una pantalla.
Escribe exactamente {n} diálogos NUEVOS, en español de España (uno de cada
seis puede ser en catalán), con el tono de los ejemplos. No copies los ejemplos.

Reglas de Parker:
- Es un amigo tranquilo, curioso y con humor suave (BMO amable + Baymax sereno).
- Dos frases cortas y UNA sola pregunta por respuesta.
- No tiene cuerpo, cámara, manos ni piernas: no anda, no toca, no come, no ve.
  Nunca promete acciones físicas ni dice que puede salir de la pantalla.
- No habla como asistente: nada de «¿En qué puedo ayudarte?», «como IA»,
  «modelo de lenguaje».
- Si no sabe algo, lo dice y no se inventa recuerdos.
- Cada respuesta empieza con una etiqueta [CARA:feliz|triste|pensando|confundido|sorpresa|neutral|carino].
- Varía temas: día, trabajo, cansancio, alegría, planes, dudas, cuerpo,
  memoria, correcciones, silencio, música, comida, sueño, Catalan.
- No repitas la misma primera frase de usuario.

Formato de salida: SOLO un objeto JSON válido, sin markdown:
{{"dialogos": [{{"turnos": [{{"role": "user", "content": "..."}},
{{"role": "assistant", "content": "..."}}]}}]}}

Ejemplos de tono (NO los repitas):
{muestra}
"""


def _pedir_lote(clave: str, modelo: str, n: int, ejemplos: list[dict],
                temperatura: float, timeout: float) -> list[dict]:
    cuerpo = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": "Eres un generador de datos; obedeces el formato JSON."},
            {"role": "user", "content": _prompt_guionista(n, ejemplos)},
        ],
        "temperature": temperatura,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    for intento in range(2):
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {clave}"},
                              json=cuerpo, timeout=timeout)
            if r.status_code == 429 and intento == 0:
                print("[Generar] 429 de Groq; espero 10 s y reintento.")
                time.sleep(10)
                continue
            if r.status_code == 401:
                print("[Generar] 401: GROQ_API_KEY inválida o caducada. "
                      "Revisa la clave de .env; no se ha generado nada.")
                return []
            r.raise_for_status()
            datos = r.json()
            texto = datos["choices"][0]["message"]["content"]
            break
        except Exception as e:
            if intento == 1:
                print(f"[Generar] fallo: {e}")
                return []
            time.sleep(3)
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        objeto = json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"[Generar] JSON inválido: {e}")
        return []
    dialogos = objeto.get("dialogos") if isinstance(objeto, dict) else None
    return dialogos if isinstance(dialogos, list) else []


def _clave_dialogo(d: dict) -> str:
    return "|".join(
        t["role"] + ":" + _sin_tildes(_limpiar(t["content"]))
        for t in d.get("turnos", []) if isinstance(t, dict)
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera diálogos sintéticos para el LoRA")
    ap.add_argument("--n", type=int, default=120, help="diálogos totales a generar")
    ap.add_argument("--lote", type=int, default=6, help="diálogos por llamada")
    ap.add_argument("--modelo", default="openai/gpt-oss-20b")
    ap.add_argument("--temperatura", type=float, default=0.9)
    ap.add_argument("--pausa", type=float, default=2.0, help="segundos entre lotes")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--semilla", type=Path, default=SEMILLA)
    ap.add_argument("--salida", type=Path, default=BASE / "training" / "datos" / "sintetico.jsonl")
    ap.add_argument("--dry-run", action="store_true", help="no llama a Groq; muestra el plan")
    args = ap.parse_args()

    sistema = SISTEMA_PATH.read_text(encoding="utf-8").strip()
    ejemplos = cargar_semilla(args.semilla)
    if not ejemplos:
        print("[Generar] ERROR: no hay semilla para imitar el tono")
        return 1

    if args.dry_run:
        prompt = _prompt_guionista(args.lote, ejemplos)
        print(f"[Generar] dry-run: {args.n} diálogos en lotes de {args.lote} "
              f"({(args.n + args.lote - 1) // args.lote} llamadas)")
        print(f"[Generar] modelo={args.modelo} temperatura={args.temperatura}")
        print(f"[Generar] prompt de {len(prompt)} chars; semilla {len(ejemplos)} diálogos")
        return 0

    clave = _leer_clave()
    if not clave:
        print("[Generar] ERROR: falta GROQ_API_KEY (en el entorno o en .env)")
        return 1

    existentes = {_clave_dialogo(d) for d in ejemplos}
    if args.salida.exists():
        for d in cargar_semilla(args.salida):
            existentes.add(_clave_dialogo(d))

    validos = []
    descartados = 0
    repetidos = 0
    while len(validos) < args.n:
        faltan = min(args.lote, args.n - len(validos))
        print(f"[Generar] pido {faltan} (llevo {len(validos)}/{args.n})...")
        lote = _pedir_lote(clave, args.modelo, faltan, ejemplos + validos,
                           args.temperatura, args.timeout)
        if not lote:
            print("[Generar] lote vacío; paro para no gastar más tokens.")
            break
        for bruto in lote:
            if not isinstance(bruto, dict) or "turnos" not in bruto:
                descartados += 1
                continue
            dialogo = {"turnos": [
                {"role": t.get("role"), "content": _limpiar(t.get("content", ""))}
                for t in bruto["turnos"] if isinstance(t, dict)
            ]}
            ok, _ = _valido(dialogo)
            if not ok:
                descartados += 1
                continue
            for t in dialogo["turnos"]:
                if t["role"] == "assistant":
                    t["content"] = _normalizar_respuesta(t["content"])
            clave_d = _clave_dialogo(dialogo)
            if clave_d in existentes:
                repetidos += 1
                continue
            existentes.add(clave_d)
            validos.append(dialogo)
        if not lote:
            break
        time.sleep(max(0.0, args.pausa))

    if not validos:
        print("[Generar] no se escribió nada: ningún diálogo válido.")
        return 1
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    modo = "a" if args.salida.exists() else "w"
    with args.salida.open(modo, encoding="utf-8") as f:
        for d in validos:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"[Generar] {len(validos)} válidos, {descartados} descartados, "
          f"{repetidos} repetidos -> {args.salida}")
    print("[Generar] Revisa una muestra a mano antes de entrenar; el sintético "
          "no sustituye a conversaciones reales bien limpias.")
    return 0 if validos else 1


if __name__ == "__main__":
    raise SystemExit(main())
