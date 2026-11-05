"""
tools/bench_online.py
=====================
Mide la API online (Groq, compatible OpenAI) con el prompt REAL de Parker
para elegir modelo con datos, no con intuición.

Qué mide, por modelo y por turno:
    ttfb     segundos hasta el primer token de CONTENIDO (lo que se puede decir;
             los tokens de razonamiento no cuentan: no se hablan)
    total    segundos hasta terminar la respuesta
    tok/s    velocidad de generación
    razón    si el modelo emite razonamiento aparte (delta.reasoning)

Uso (en el PC; necesita GROQ_API_KEY en el entorno o en .env):
    python tools/bench_online.py
    python tools/bench_online.py --modelos openai/gpt-oss-20b qwen/qwen3.8-27b
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

MODELOS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
BASE_URL = "https://api.groq.com/openai/v1"
TURNOS = [
    "Hola Parker, ¿qué tal tu día?",
    "Hoy he tenido un día largo en el trabajo, estoy cansado.",
    "¿Te acuerdas de lo que te conté ayer?",
]


def _clave() -> str:
    """Clave de la API: primero el .env del proyecto, luego el entorno.

    En Windows es fácil que quede una variable de entorno vieja en la sesión
    (visto 25/10: /models daba 200 y /chat/completions 401 con la misma clave).
    El .env es la fuente que usa Parker al arrancar, así que manda.
    """
    env = BASE / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if linea.strip().startswith("GROQ_API_KEY="):
                clave = linea.split("=", 1)[1].strip().strip('"').strip("'")
                if clave:
                    return clave
    clave = os.getenv("GROQ_API_KEY", "").strip()
    if clave:
        return clave
    sys.exit("Falta GROQ_API_KEY (entorno o .env)")


def _system() -> str:
    from modulos.personalidad import PersonalidadParker
    perfil = PersonalidadParker({"guardar_estado": False})
    return perfil.identidad()


def medir(modelo: str, clave: str, system: str, mensaje: str) -> dict:
    inicio = time.time()
    ttfb = None
    ttfb_razon = None
    piezas = []
    razonamiento = False
    with requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
        json={
            "model": modelo,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": mensaje}],
            "max_tokens": 160,
            "temperature": 0.6,
            "stream": True,
            # Los gpt-oss de Groq razonan aparte: con reasoning_effort bajo el
            # contenido empieza antes y el texto hablado no se retrasa.
            "reasoning_effort": "low",
            "include_reasoning": False,
        },
        stream=True,
        timeout=(6, 30),
    ) as res:
        res.raise_for_status()
        for linea in res.iter_lines(decode_unicode=True):
            if not linea or not linea.startswith("data: "):
                continue
            dato = linea[6:].strip()
            if dato == "[DONE]":
                break
            try:
                evento = json.loads(dato)
            except json.JSONDecodeError:
                continue
            delta = (evento.get("choices") or [{}])[0].get("delta") or {}
            if delta.get("reasoning"):
                razonamiento = True
                if ttfb_razon is None:
                    ttfb_razon = time.time() - inicio
            trozo = delta.get("content")
            if trozo:
                if ttfb is None:
                    ttfb = time.time() - inicio
                piezas.append(trozo)
    total = time.time() - inicio
    texto = "".join(piezas).strip()
    # Aproximación de tokens: 1 token ≈ 4 caracteres en español.
    tok = max(1, len(texto) / 4)
    return {
        "ttfb": ttfb or total,
        "ttfb_razon": ttfb_razon,
        "total": total,
        "toks": tok / max(0.01, total - (ttfb or 0)),
        "razonamiento": razonamiento,
        "texto": texto,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", nargs="*", default=MODELOS)
    args = ap.parse_args()

    clave = _clave()
    system = _system()
    print(f"Prompt de sistema: {len(system)} caracteres")
    print(f"{'modelo':<24} {'ttfb':>6} {'total':>6} {'tok/s':>7}  razón")
    for modelo in args.modelos:
        try:
            medir(modelo, clave, system, "hola")  # calentar / validar nombre
            filas = []
            for mensaje in TURNOS:
                r = medir(modelo, clave, system, mensaje)
                filas.append(r)
            ttfb = sum(f["ttfb"] for f in filas) / len(filas)
            total = sum(f["total"] for f in filas) / len(filas)
            toks = sum(f["toks"] for f in filas) / len(filas)
            razon = "sí" if any(f["razonamiento"] for f in filas) else "no"
            print(f"{modelo:<24} {ttfb:6.2f} {total:6.2f} {toks:7.1f}  {razon}")
            for mensaje, fila in zip(TURNOS, filas):
                print(f"    · {mensaje[:34]:<35} -> {fila['texto'][:90]}")
        except Exception as e:
            print(f"{modelo:<24} ERROR: {e}")


if __name__ == "__main__":
    main()
