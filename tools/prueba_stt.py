"""
tools/prueba_stt.py
===================
Compara el reconocimiento de voz LOCAL con el de la NUBE usando el mismo audio
real: Parker dice una frase conocida por el altavoz, su micrófono la graba y
después se transcribe de las dos formas.

Así se decide con datos si merece la pena mandar el audio a Groq
(`whisper-large-v3-turbo`) en vez de transcribir en la placa:

    · precisión: qué texto sale de cada motor frente a la frase original
    · tiempo:    cuánto tarda cada uno

Uso (en la placa, con Parker parado o da igual: solo usa el micrófono):
    ~/env/bin/python3 tools/prueba_stt.py
    ~/env/bin/python3 tools/prueba_stt.py --frase "texto que quieras"
"""

import argparse
import json
import os
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import _leer_clave  # noqa: E402
from modulos.escucha import EscuchaParker  # noqa: E402
from modulos.voz import VozParker  # noqa: E402

FRASE = ("El otro día estuve en el médico y me dijo que tengo que descansar más, "
         "que no puedo seguir durmiendo cuatro horas.")


def _microfono(cfg: dict):
    preferencia = str((cfg.get("escucha") or {}).get("dispositivo_entrada") or "").lower()
    if preferencia:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and preferencia in str(dev["name"]).lower():
                return i
    return None


def _grabar(mientras, segundos: float, dispositivo, ruta: Path):
    """Graba en un hilo mientras `mientras()` se ejecuta (reproducir la frase)."""
    trozos = []
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                        device=dispositivo) as stream:
        hilo = threading.Thread(target=mientras, daemon=True)
        hilo.start()
        fin = time.time() + segundos
        while time.time() < fin:
            datos, _ = stream.read(1024)
            trozos.append(datos.copy())
        hilo.join(timeout=segundos)

    audio = np.concatenate(trozos, axis=0).ravel().astype(np.float32)
    pico = float(np.max(np.abs(audio))) or 1.0
    audio = audio / pico
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    return len(audio) / 16000.0


def _nube(ruta: Path, clave: str) -> tuple[str, float]:
    inicio = time.time()
    with ruta.open("rb") as f:
        res = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {clave}"},
            files={"file": (ruta.name, f, "audio/wav")},
            data={"model": "whisper-large-v3-turbo", "language": "es",
                  "response_format": "json", "temperature": "0"},
            timeout=(5, 30),
        )
    res.raise_for_status()
    return (res.json().get("text") or "").strip(), time.time() - inicio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frase", default=FRASE)
    args = ap.parse_args()

    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))
    voz_cfg = cfg.get("voz", {})
    voz = VozParker(modelo_path=str(BASE / voz_cfg.get("modelo_piper")),
                    config_path=str(BASE / voz_cfg["modelo_config"]),
                    velocidad=1.0, volumen=0.95)
    audio_frase = voz.sintetizar(args.frase)
    duracion_frase = len(audio_frase) / 22050

    dispositivo = _microfono(cfg)
    print(f"Micrófono: {dispositivo}; frase de {duracion_frase:.1f}s")
    ruta = Path("/tmp/stt_prueba.wav")
    grabado = _grabar(lambda: voz.reproducir(audio_frase, bloquear=True),
                      duracion_frase + 1.2, dispositivo, ruta)
    print(f"Grabados {grabado:.1f}s en {ruta}")

    print("\n--- LOCAL (faster-whisper base, int8) ---")
    escucha_local = EscuchaParker(modelo="base", idioma="es", backend="faster-whisper",
                                  modelo_faster="base", beam_size=1, vad_filter=True)
    with wave.open(str(ruta), "rb") as w:
        datos = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    datos /= 32768.0
    t0 = time.time()
    texto_local = escucha_local.transcribir(datos)
    t_local = time.time() - t0
    print(f"  {t_local:5.2f}s  {texto_local!r}")

    print("\n--- NUBE (Groq whisper-large-v3-turbo) ---")
    clave = _leer_clave("GROQ_API_KEY")
    if not clave:
        print("  (sin GROQ_API_KEY en .env: no se puede probar)")
    else:
        try:
            texto_nube, t_nube = _nube(ruta, clave)
            print(f"  {t_nube:5.2f}s  {texto_nube!r}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nOriginal: {args.frase!r}")
    _ = os  # silencio de linters


if __name__ == "__main__":
    main()
