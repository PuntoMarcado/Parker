"""
tools/medir_latencia.py
=======================
Mide la latencia real de un turno con los módulos de Parker (sin micrófono):
voz Piper -> STT -> LLM -> primera frase -> TTS.

    QT_QPA_PLATFORM=offscreen python tools/medir_latencia.py

Imita el flujo real: el STT escucha una frase Piper y el LLM/voz responden.
El precalentado del prefijo durante el turno está desactivado por defecto porque
compite con Whisper por la CPU. Los números importantes son «TTFB» (primer
token) y «percibido» (hasta sonar la primera frase).
"""

import os
import sys
import threading
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(BASE))
os.chdir(BASE)

import yaml  # noqa: E402
from modulos.cerebro import CerebroParker  # noqa: E402
from modulos.escucha import EscuchaParker  # noqa: E402
from modulos.memoria import MemoriaParker  # noqa: E402
from modulos.personalidad import PersonalidadParker  # noqa: E402
from modulos.voz import VozParker  # noqa: E402
from parker import LIMPIAR_ETIQUETAS, dividir_oraciones  # noqa: E402

PREGUNTAS = [
    "Oye Parker, hoy he tenido un día tranquilo y he pensado en ti.",
    "Me han dado una buena noticia en el trabajo.",
    "¿Qué te apetece hacer este fin de semana?",
    "Hoy ha llovido un montón por la tarde.",
    "Buenas noches, Parker.",
]


def main() -> int:
    cfg = yaml.safe_load(open(BASE / "config.yaml", encoding="utf-8"))
    esc_cfg = cfg.get("escucha", {})
    silencio = float(esc_cfg.get("silencio_corte_seg", 0.6))

    personalidad = PersonalidadParker(dict(cfg.get("personalidad") or {}))
    memoria = MemoriaParker(db_path=cfg["memoria"]["db_path"],
                            coleccion=cfg["memoria"]["coleccion"],
                            modelo_embeddings=cfg["memoria"]["modelo_embeddings"])
    cerebro = CerebroParker(config_llama=cfg["llama"], memoria=memoria,
                            personalidad=personalidad,
                            config_memoria=cfg.get("memoria"))
    voz = VozParker(cfg["voz"]["modelo_piper"], cfg["voz"]["modelo_config"],
                    velocidad=cfg["voz"]["velocidad"], volumen=cfg["voz"]["volumen"])
    escucha = EscuchaParker(modelo_faster=esc_cfg.get("modelo_faster", "base"),
                            idioma=esc_cfg.get("idioma", "es"),
                            beam_size=esc_cfg.get("beam_size", 1),
                            vad_filter=esc_cfg.get("vad_filter", True),
                            hotwords=esc_cfg.get("hotwords"))
    print("[precalentado inicial] %.2fs" % cerebro.calentar())

    print("\n turno |  STT  | TTFB  | 1ª frase |  TTS  | percibido | respuesta")
    for i, pregunta in enumerate(PREGUNTAS, 1):
        wav = voz.sintetizar(pregunta)
        audio = np.interp(np.linspace(0, len(wav) - 1, int(len(wav) * 16000 / voz.sample_rate)),
                          np.arange(len(wav)), wav).astype(np.float32)
        audio = np.concatenate([audio, np.zeros(int(silencio * 16000), np.float32)])

        # Reproduce el tiempo de hablar sin lanzar inferencia en paralelo con
        # Whisper: esa concurrencia elevó el primer turno a 24 s en la placa.
        time.sleep(min(3.0, len(audio) / 16000))

        t0 = time.time()
        texto = escucha.transcribir(audio)
        stt = time.time() - t0

        t0 = time.time()
        ttfb = primera = tts = None
        pendiente = completo = ""
        for delta in cerebro.hablar_stream(texto):
            if ttfb is None:
                ttfb = time.time() - t0
            completo += delta
            pendiente += delta
            oraciones, pendiente = dividir_oraciones(pendiente)
            for oracion in oraciones:
                limpia = LIMPIAR_ETIQUETAS.sub("", oracion).strip()
                if limpia and primera is None:
                    primera = time.time() - t0
                    t = time.time()
                    voz.sintetizar(limpia)
                    tts = time.time() - t
        percibido = silencio + stt + primera + tts
        print("  %d    | %.2f | %.2f |  %5.2f   | %.2f |   %.2f   | %s" % (
            i, stt, ttfb, primera, tts, percibido,
            LIMPIAR_ETIQUETAS.sub("", completo).strip().replace("\n", " ")[:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
