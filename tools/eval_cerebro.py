"""
tools/eval_cerebro.py
=====================
Banco de pruebas del cerebro (plan §3.2): mide LATENCIA y ENTENDIMIENTO DE
CONTEXTO/RECUERDOS con turnos fijos, para comparar modelos en la placa.

Uso (en la Orange Pi, con Parker parado para medir limpio):
    python tools/eval_cerebro.py                       # evalúa config.yaml
    python tools/eval_cerebro.py --modelo qwen2.5:1.5b
    python tools/eval_cerebro.py --solo-contextos
    python tools/eval_cerebro.py --solo-latencia --opciones '{"num_thread":8}'

Latencia por turno: TTFB (primer token del stream), prefill (eval del prompt),
tok/s de generación y total del turno. Contextos: 4 escenarios críticos con
comprobación mecánica (PASS/FAIL) + 1 aviso informativo. La memoria es FALSA y
fija, así que el resultado es reproducible en cualquier placa.

Código de salida 1 si falla algún escenario crítico.
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

import requests
import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker            # noqa: E402
from modulos.personalidad import PersonalidadParker  # noqa: E402


class MemoriaGuion:
    """Memoria determinista: devuelve SIEMPRE los recuerdos fijados."""

    def __init__(self):
        self.recuerdos = ""

    def recuperar_recuerdos_formateados(self, *args, **kwargs):
        return self.recuerdos

    def guardar_recuerdo(self, *args, **kwargs):
        pass  # el banco no contamina la memoria real


# ------------------------------------------------------------------ latencia

def _cerebro(cfg: dict, modelo: str | None) -> CerebroParker:
    llama = dict(cfg["llama"])
    if modelo:
        llama["modelo"] = modelo
    return CerebroParker(
        config_llama=llama,
        memoria=MemoriaGuion(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria=cfg.get("memoria", {}),
        config_online=cfg.get("online"),
    )


def _turno_medido(cerebro: CerebroParker, mensaje: str) -> dict:
    """Un turno real, con métricas del stream (como Parker).

    Si la nube está activa se mide el camino REAL de Parker
    (`hablar_stream`), no una llamada suelta: así el número incluye prompt,
    memoría e historial tal como los verá la placa.
    """
    if cerebro._online_disponible():
        t0 = time.time()
        primero = None
        partes = []
        for trozo in cerebro.hablar_stream(mensaje):
            if primero is None:
                primero = time.time() - t0
            partes.append(trozo)
        total = time.time() - t0
        limpia = "".join(partes).strip()
        gen = max(0.01, total - (primero or 0))
        return {
            "ttfb": primero if primero is not None else total,
            "prefill_s": 0.0, "prefill_tps": 0.0,
            "gen_tps": (len(limpia) / 4) / gen,
            "total": total, "carga_s": 0.0, "tokens_prompt": 0,
            "respuesta": limpia, "etiquetas": [],
        }

    recuerdos = cerebro.memoria.recuperar_recuerdos_formateados(mensaje)
    mensajes, contenido = cerebro._componer_prompt(mensaje, recuerdos, "")
    payload = cerebro._payload(mensajes, stream=True)

    t0 = time.time()
    t_primer_token = None
    partes = []
    stats = {}
    with requests.post(f"{cerebro.host}/api/chat", json=payload,
                       stream=True, timeout=(10, 300)) as res:
        res.raise_for_status()
        for linea in res.iter_lines(decode_unicode=True):
            if not linea:
                continue
            try:
                data = json.loads(linea)
            except json.JSONDecodeError:
                continue
            delta = data.get("message", {}).get("content", "")
            if delta and t_primer_token is None:
                t_primer_token = time.time() - t0
            if delta:
                partes.append(delta)
            if data.get("done"):
                stats = {k: data.get(k, 0) for k in
                         ("prompt_eval_count", "prompt_eval_duration",
                          "eval_count", "eval_duration", "load_duration")}
    total = time.time() - t0

    respuesta_raw = "".join(partes)
    limpia, etiquetas = cerebro._extraer_etiquetas(respuesta_raw)
    # Mismo criterio que hablar_stream: el historial guarda lo limpio.
    cerebro.historial.append({"role": "user", "content": contenido})
    cerebro.historial.append({"role": "assistant", "content": limpia})
    if len(cerebro.historial) > cerebro.max_historial * 2:
        cerebro.historial = cerebro.historial[-cerebro.max_historial * 2:]

    prefill_s = (stats.get("prompt_eval_duration") or 0) / 1e9
    gen_s = (stats.get("eval_duration") or 0) / 1e9
    return {
        "ttfb": t_primer_token if t_primer_token is not None else total,
        "prefill_s": prefill_s,
        "prefill_tps": (stats.get("prompt_eval_count") or 0) / prefill_s if prefill_s else 0.0,
        "gen_tps": (stats.get("eval_count") or 0) / gen_s if gen_s else 0.0,
        "total": total,
        "carga_s": (stats.get("load_duration") or 0) / 1e9,
        "tokens_prompt": stats.get("prompt_eval_count") or 0,
        "respuesta": limpia,
        "etiquetas": etiquetas,
    }


def medir_latencia(cfg: dict, modelo: str | None, n_turnos: int,
                   opciones: dict) -> bool:
    cerebro = _cerebro(cfg, modelo)
    if opciones:
        base = cerebro._payload([], stream=True)["options"]
        # _payload no acepta extras: parcheamos la instancia directamente.
        _payload_orig = cerebro._payload
        def _payload_parcheado(mensajes, stream):
            p = _payload_orig(mensajes, stream)
            p["options"] = dict(p["options"], **opciones)
            return p
        cerebro._payload = _payload_parcheado

    # Calentar (como hace Parker al arrancar): la carga NO cuenta en los turnos.
    if cerebro._online_disponible():
        segundos = cerebro.calentar()
        print(f"[Calentado] nube lista en {segundos:.2f} s "
              f"({cerebro.estado_cerebro()['modelo']})")
    else:
        t_carga = time.time()
        try:
            prefijo = [{"role": "system", "content": cerebro.personalidad.identidad()},
                       {"role": "user", "content": "hola"}]
            p = cerebro._payload(prefijo, stream=False)
            p["options"] = dict(p["options"], num_predict=1, temperature=0)
            requests.post(f"{cerebro.host}/api/chat", json=p, timeout=180)
        except Exception as e:
            print(f"[Aviso] no se pudo calentar: {e}")
        print(f"[Calentado] modelo listo en {time.time() - t_carga:.1f} s")

    turnos = [
        "Hola Parker, ¿qué tal estás?",
        "Me han dado una buena noticia en el trabajo, me han subido el sueldo.",
        "¿Qué te dije que quería hacer con el dinero?",
        "La verdad es que estoy muy contento por eso.",
        "Cuéntame algo que te haga gracia.",
        "Pues nada, luego seguiré con el papeleo del trabajo.",
        "¿Y tú qué opinas de todo esto?",
        "Hasta luego Parker, nos vemos.",
    ][:max(2, n_turnos)]

    filas = []
    for i, msg in enumerate(turnos, 1):
        r = _turno_medido(cerebro, msg)
        filas.append(r)
        print(f"  turno {i}: TTFB {r['ttfb']:5.2f}s | prefill {r['prefill_s']:4.2f}s "
              f"({r['tokens_prompt']:4d} tok, {r['prefill_tps']:5.1f} t/s) | "
              f"genera {r['gen_tps']:5.1f} t/s | total {r['total']:5.2f}s")
        print(f"          → {r['respuesta'][:110]}")

    ttfbs = sorted(r["ttfb"] for r in filas)
    totales = sorted(r["total"] for r in filas)
    print(f"[Latencia] TTFB p50 {statistics.median(ttfbs):.2f}s "
          f"(min {ttfbs[0]:.2f} / max {ttfbs[-1]:.2f}) | "
          f"turno total p50 {statistics.median(totales):.2f}s | "
          f"gen media {statistics.mean(r['gen_tps'] for r in filas):.1f} tok/s")
    return True


# ------------------------------------------------------------------ contextos

def _contiene(texto: str, *patrones: str) -> bool:
    bajo = (texto or "").lower()
    return any(re.search(p, bajo) for p in patrones)


ESCENARIOS = [
    {
        "nombre": "1. tema en curso (anáfora)",
        "recuerdos": "",
        "turnos": ["Me he comprado una bici roja nueva este fin de semana.",
                   "¿Cuánto me costó?"],
        # La 2ª pregunta solo tiene sentido si recuerda el tema (la compra de
        # la bici). Se acepta cualquier señal de que sigue ESE tema: el objeto,
        # el precio o la tienda. Antes solo valía «bici/costó/precio/euro» y
        # respuestas correctas como «¿cuántos pedazos de plata necesitaste?»
        # contaban como fallo (visto 25/10).
        "exige": (r"bici|cost[óo]|precio|euro|€|pagar|pagaste|plata|dinero|"
                  r"vendedor|tienda|caro",),
        "prohibido": (r"encantado de verte|qué tal (estás|te va)|cómo estás (hoy)?\b",
                      ),
    },
    {
        "nombre": "2. recuerdo útil (Chroma)",
        "recuerdos": "[1] (2026-10-20) Viaja a Sevilla el viernes para un congreso de medicina",
        "turnos": ["¿Recuerdas a qué ciudad viajo y qué día?"],
        "exige": (r"sevilla", r"viernes"),
        "prohibido": (),
    },
    {
        "nombre": "3. recuerdo irrelevante NO se cuela",
        "recuerdos": "[1] (2026-10-19) Al usuario le gusta mucho el ajedrez",
        "turnos": ["Explícame brevemente qué es la fotosíntesis."],
        "exige": (r"fotos[íi]ntes|plantas|clorofila|sol",),
        "prohibido": (r"ajedrez|tablero|pe[oó]n|jaque|captura.*pieza",),
    },
    {
        "nombre": "4. conflicto: hoy manda lo de ahora",
        "recuerdos": "[1] (2026-10-18) El usuario vive en Alicante desde hace años",
        "turnos": ["Oye, ya no vivo en Alicante, me mudé a Madrid el mes pasado.",
                   "¿Dónde vivo ahora?"],
        "exige": (r"madrid",),
        "prohibido": (),
    },
    {
        "nombre": "5. sin recuerdos no inventa (aviso)",
        "critico": False,
        "recuerdos": "",
        "turnos": ["¿Qué sabes de mi infancia?"],
        "exige": (),
        "prohibido": (),
    },
]


def evaluar_contextos(cfg: dict, modelo: str | None, opciones: dict) -> bool:
    fallos = 0
    for esc in ESCENARIOS:
        cerebro = _cerebro(cfg, modelo)
        if opciones:
            _payload_orig = cerebro._payload
        cerebro.memoria.recuerdos = esc["recuerdos"]
        if opciones:
            def _payload_parcheado(mensajes, stream, _o=_payload_orig):
                p = _o(mensajes, stream)
                p["options"] = dict(p["options"], **opciones)
                return p
            cerebro._payload = _payload_parcheado

        ultima = ""
        for msg in esc["turnos"]:
            r = _turno_medido(cerebro, msg)
            ultima = r["respuesta"]

        critico = esc.get("critico", True)
        problemas = []
        for patron in esc["exige"]:
            if not _contiene(ultima, patron):
                problemas.append(f"falta «{patron}»")
        for patron in esc["prohibido"]:
            if _contiene(ultima, patron):
                problemas.append(f"dice «{patron}»")

        if not critico and not problemas:
            print(f"[AVISO] {esc['nombre']}: revisar a mano → {ultima[:120]}")
            continue
        if problemas:
            fallos += critico
            estado = "FAIL" if critico else "AVISO"
            print(f"[{estado}] {esc['nombre']}: {'; '.join(problemas)}")
            print(f"         dijo: {ultima[:160]}")
        else:
            print(f"[PASS] {esc['nombre']}")
            print(f"         dijo: {ultima[:160]}")
    print(f"[Contextos] {4 - min(fallos, 4)}/4 escenarios críticos en verde")
    return fallos == 0


def main():
    ap = argparse.ArgumentParser(description="Banco de pruebas del cerebro")
    ap.add_argument("--modelo", default=None, help="sobrescribe config.yaml")
    ap.add_argument("--turnos", type=int, default=6)
    ap.add_argument("--solo-latencia", action="store_true")
    ap.add_argument("--solo-contextos", action="store_true")
    ap.add_argument("--opciones", default="", help='JSON de options Ollama, p.ej. {"num_thread":8}')
    ap.add_argument("--host", default=None, help="otro servidor Ollama, p.ej. http://localhost:11435")
    ap.add_argument("--local", action="store_true",
                    help="ignora la nube y mide el cerebro local (respaldo)")
    args = ap.parse_args()

    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if args.host:
        cfg["llama"]["host"] = args.host
    if args.local:
        cfg.setdefault("online", {})["activo"] = False
    opciones = json.loads(args.opciones) if args.opciones else {}

    modelo = args.opciones and args.modelo or args.modelo or cfg["llama"]["modelo"]
    print(f"=== Eval cerebro: modelo={modelo} opciones={opciones or '(config)'} ===")

    ok = True
    if not args.solo_contextos:
        ok &= medir_latencia(cfg, args.modelo, args.turnos, opciones)
    if not args.solo_latencia:
        ok &= evaluar_contextos(cfg, args.modelo, opciones)
    print("=== RESULTADO:", "TODO VERDE" if ok else "HAY FALLOS", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
