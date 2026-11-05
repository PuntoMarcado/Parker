"""
tools/prueba_redonda.py
=======================
Prueba de punta a punta SIN hablar: Parker se dice una frase a sí mismo por el
altavoz, su propio micrófono la oye y el turno completo (VAD → Whisper →
cerebro → Piper) tiene que aparecer en el log.

Sirve para comprobar que la cadena entera funciona cuando no hay nadie delante:
    · que el micrófono elegido recibe audio de verdad,
    · que Whisper transcribe,
    · que el cerebro (nube o local) contesta,
    · que la voz suena.

Uso (en la placa, con Parker corriendo):
    ~/env/bin/python3 tools/prueba_redonda.py
    ~/env/bin/python3 tools/prueba_redonda.py --texto "Hola Parker, ¿me oyes?"
"""

import argparse
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import yaml  # noqa: E402

from modulos.voz import VozParker  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texto", default="Hola Parker, ¿cómo estás hoy?")
    ap.add_argument("--espera", type=float, default=12.0)
    # Volumen del altavoz: bajarlo simula hablar desde más lejos sin mover el
    # micro. Es la prueba de «¿me oye a distancia?» sin necesitar a nadie.
    ap.add_argument("--volumen", type=float, default=None,
                    help="0-1; por defecto, el volumen alto de la prueba")
    args = ap.parse_args()

    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))
    voz_cfg = cfg.get("voz", {})
    modelo = BASE / voz_cfg.get("modelo_piper", "./assets/voz/es_ES-davefx-medium.onnx")
    modelo_cfg = voz_cfg.get("modelo_config")
    config_path = (BASE / modelo_cfg) if modelo_cfg else None

    volumen = (float(args.volumen) if args.volumen is not None
               else max(0.9, float(voz_cfg.get("volumen", 0.9))))
    print(f"[Prueba] Parker dirá: «{args.texto}» (volumen {volumen:.2f})")
    voz = VozParker(modelo_path=str(modelo),
                    config_path=str(config_path) if config_path else None,
                    velocidad=float(voz_cfg.get("velocidad", 1.0)),
                    volumen=volumen, motor="piper")
    audio = voz.sintetizar(args.texto)
    voz.reproducir(audio, bloquear=True)

    print(f"[Prueba] frase dicha; espero {args.espera:.0f}s a que Parker conteste…")
    time.sleep(args.espera)
    print("[Prueba] mira el final del log: "
          "tail -25 ~/parker.log")


if __name__ == "__main__":
    main()
