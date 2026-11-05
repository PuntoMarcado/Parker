"""
tools/mide_cerebro.py
=====================
Mide el PRIMER TOKEN (TTFB) del cerebro LOCAL en la placa, con el prompt real
de Parker (identidad + hechos + ánimo + historial simulado), para verificar
que el caché de prefijo deja el turno de respaldo por debajo de ~1 s.

Qué mide exactamente:
  - TTFB: desde el POST a Ollama hasta el primer trozo de contenido.
  - Turno completo y tok/s de generación (eval_count del final del NDJSON).

Notas:
  - El primer turno está FRÍO (reserva de KV + prefill del system). A partir
    del segundo, si el prefijo coincide, Ollama solo paga el mensaje nuevo:
    esas cifras son las que importan para el turno real de respaldo.
  - No toca el estado real de Parker: usa `guardar_estado: False` y una
    memoria falsa; la base de datos y la ficha quedan intactas.
  - El online se apaga en la instancia: todo va al Ollama local.

Uso (en la placa, desde ~/parker):
  env/bin/python tools/mide_cerebro.py                # 6 turnos
  env/bin/python tools/mide_cerebro.py --turnos 10
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import yaml
import requests


class MemoriaFalsa:
    """Memoria sin Chroma ni embeddings: solo respeta el contrato que usa
    el cerebro (recuperar_formateados + guardar)."""

    def recuperar_recuerdos_formateados(self, consulta, top_k=5, umbral=0.5,
                                        max_caracteres=0):
        return "[1] (2026-01-01) Recuerdo de ejemplo para el prefill"

    def guardar_recuerdo(self, *a, **k):
        return ""


def main():
    parser = argparse.ArgumentParser(description="TTFB del cerebro local")
    parser.add_argument("--turnos", type=int, default=6)
    parser.add_argument("--config", type=str, default=str(BASE / "config.yaml"))
    parser.add_argument("--sin-hechos", action="store_true",
                        help="como el prompt de antes del 03/11 (para comparar)")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    llama = dict(cfg.get("llama") or {})

    from modulos.cerebro import CerebroParker
    from modulos.personalidad import PersonalidadParker
    from modulos.hechos import HechosParker

    # Hechos en un fichero temporal: ni toca la base real. Con --sin-hechos
    # se deja el system igual que el prompt del 01/11, para comparar en la
    # misma placa y a la misma hora qué cuesta el bloque estable.
    import tempfile
    hechos = None
    if args.sin_hechos:
        print("[TTFB] modo: SIN hechos (prompt del 01/11, para comparar)")
    else:
        print("[TTFB] modo: CON hechos (system estable del 03/11)")
    if not args.sin_hechos and (cfg.get("memoria") or {}).get("hechos", {}).get("activo", True):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        hechos = HechosParker(ruta=tmp.name)
        hechos.actualizar_desde_texto("Mi dentista es la Dra. Puig.")
        hechos.actualizar_desde_texto("Soy alérgico a la penicilina.")

    cerebro = CerebroParker(
        config_llama=llama,
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria={},
        config_online={"activo": False},   # solo cerebro local
        hechos=hechos,
    )

    host = cerebro.host
    preguntas = ["¿Qué tal va tu día?",
                 "¿Qué has desayunado?",
                 "Cuéntame algo de ti.",
                 "Hoy he tenido un día tranquilo.",
                 "¿Qué tal si charlamos un rato?",
                 "Me agobia un poco la semana que viene.",
                 "¿Qué tiempo hace?",
                 "Gracias por acompañarme."]
    print(f"[TTFB] modelo={cerebro.modelo} host={host} thread={cerebro.num_thread} "
          f"ctx={cerebro.num_ctx} turnos={args.turnos}")

    ttibs, totales, tokss = [], [], []
    for turno in range(args.turnos):
        pregunta = preguntas[turno % len(preguntas)]
        print(f"  turno {turno + 1}: en curso...", flush=True)
        # Guarda la hora con un solo reloj: dos llamadas a time.time()
        # además de la medición podrían ceder el turno del hilo.
        mensajes, _ = cerebro._componer_prompt(
            pregunta, recuerdos="[1] (2026-01-01) Mi dentista es la Dra. Puig.")
        payload = cerebro._payload(mensajes, stream=True)
        t0 = time.perf_counter()
        ttfb = None
        total_tokens = None
        with requests.post(f"{host}/api/chat", json=payload, stream=True,
                           timeout=(5, 180)) as res:
            res.raise_for_status()
            for linea in res.iter_lines(decode_unicode=True):
                if not linea:
                    continue
                try:
                    data = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                if ttfb is None and (data.get("message", {}) or {}).get("content"):
                    ttfb = time.perf_counter() - t0
                if data.get("done"):
                    total_tokens = int(data.get("eval_count") or 0)
                    break
        duracion_total = time.perf_counter() - t0
        ttrb_ms = ttfb or 0.0
        ttibs.append(ttrb_ms)
        totales.append(duracion_total)
        tok_s = (total_tokens or 0) / duracion_total if duracion_total else 0.0
        tokss.append(tok_s)
        etiquetal = "FRÍO" if turno == 0 else "caliente"
        print(f"    turn {turno + 1} [{etiquetal}]: TTFB {ttrb_ms*1000:7.0f} ms | "
              f"turno {duracion_total:5.2f}s | {tok_s:6.1f} tok/s", flush=True)

    if len(ttibs) > 1:
        calientes = ttibs[1:]
        p50 = statistics.median(calientes)
        print("\n[Resumen] TTFB CALIENTE (el del turno real):")
        print(f"  P50 {p50*1000:6.0f} ms  |  min {min(calientes)*1000:.0f}  "
              f"|  max {max(calientes)*1000:.0f}  ({len(calientes)} turnos)")
        objetivo = "< 1000 ms"
        print(f"  Objetivo {objetivo}: "
              f"{'CUMPLE' if p50 < 1.0 else 'NO CUMPLE'} "
              f"(frío {ttibs[0]*1000:.0f} ms; generación "
              f"p50 {statistics.median(tokss[1:]):.1f} tok/s)")


if __name__ == "__main__":
    main()
