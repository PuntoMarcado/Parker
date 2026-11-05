"""
tools/chk_audio.py
==================
Diagnóstico del micrófono y del altavoz SIN arrancar Parker.

Responde a la pregunta que no se puede contestar mirando el log: «¿el bucle
de escucha está oyendo algo?». Lista los dispositivos de entrada, dice cuál
usa por defecto y graba 1,5 s para imprimir el RMS de cada bloque: si todos
los bloques son ~0, el micro no está llegando a Parker (dispositivo
equivocado, silenciado o sin permisos de PulseAudio).

Uso (en la placa, con Parker parado o no da igual, solo escucha):
    ~/env/bin/python3 tools/chk_audio.py
    ~/env/bin/python3 tools/chk_audio.py --segundos 3
"""

import argparse
import time

import numpy as np
import sounddevice as sd


def listar() -> None:
    print(f"Dispositivo por defecto (in, out): {sd.default.device}")
    try:
        print(f"Default del sistema: {sd.query_devices(kind='input')['name']}")
    except Exception as e:
        print(f"  (sin entrada por defecto: {e})")
    print("\nEntradas disponibles:")
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            print(f"  [{i}] {dev['name']} | canales={dev['max_input_channels']} "
                  f"| {dev['default_samplerate']} Hz")


def medir(segundos: float, dispositivo=None) -> None:
    bloques = int(segundos * 16000 / 1024)
    t0 = time.time()
    valores = []
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                        device=dispositivo) as stream:
        for _ in range(bloques):
            datos, _ = stream.read(1024)
            valores.append(float(np.sqrt(np.mean(datos.ravel().astype(np.float32) ** 2))))
    print(f"RMS de {len(valores)} bloques en {time.time() - t0:.2f}s:")
    print("  " + " ".join(f"{v:.4f}" for v in valores))
    print(f"  mínimo {min(valores):.4f} | máximo {max(valores):.4f} "
          f"| media {sum(valores) / len(valores):.4f}")
    if max(valores) < 0.001:
        print("AVISO: silencio absoluto. El micro no llega (dispositivo, mute o permisos).")
    else:
        print("OK: hay señal de audio entrando.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=float, default=1.5)
    ap.add_argument("--dispositivo", type=int, default=None)
    args = ap.parse_args()
    listar()
    print()
    try:
        medir(args.segundos, args.dispositivo)
    except Exception as e:
        print(f"ERROR al abrir el micro: {e}")


if __name__ == "__main__":
    main()
