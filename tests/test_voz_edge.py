"""
tests/test_voz_edge.py
======================
Prueba la lógica de Edge TTS/Piper sin llamar a Microsoft ni abrir audio.

Cubre lo importante del cambio del 30/10/2026:
  - `voz.motor: edge` usa Edge cuando está disponible.
  - si Edge falla, la misma frase sale por Piper y se marca un enfriamiento
    para no pagar el timeout en cada frase.
  - el ritmo se traduce a porcentaje (0.85 -> -15%) sin tocar el tono.

Ejecutar:  python tests/test_voz_edge.py
"""

import sys
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.voz import VozParker


def _voz_falsa() -> VozParker:
    """Objeto VozParker sin cargar Piper ni tocar la tarjeta de sonido."""
    voz = object.__new__(VozParker)
    voz.motor = "edge"
    voz.velocidad = 0.9
    voz.volumen = 0.55
    voz.silenciado = False
    voz.edge_voz = "es-ES-XimenaNeural"
    voz.edge_timeout = 8.0
    voz.edge_reintento_seg = 60.0
    voz.edge_ffmpeg = "ffmpeg"
    voz._edge_disponible = True
    voz._edge_fallo_hasta = 0.0
    voz._edge_ultimo_error = ""
    voz.sample_rate = 22050
    return voz


def main():
    # 1. Ritmo: Edge usa porcentaje, no remuestreo (no cambia el tono).
    assert VozParker._edge_rate(0.85) == "-15%"
    assert VozParker._edge_rate(1.0) == "+0%"
    assert VozParker._edge_rate(2.0) == "+40%"   # límite superior
    assert VozParker._edge_rate(0.1) == "-40%"   # límite inferior

    # 2. Con Edge disponible, se usa Edge.
    voz = _voz_falsa()
    usados = []
    voz._sintetizar_edge = lambda t, v, vol: (usados.append("edge") or
                                               np.full(8, 0.5, dtype=np.float32))
    voz._sintetizar_piper = lambda t, v, vol: (usados.append("piper") or
                                               np.zeros(4, dtype=np.float32))
    audio = voz.sintetizar("Hola")
    assert usados == ["edge"], usados
    assert len(audio) == 8 and abs(float(audio[0]) - 0.5) < 1e-6

    # 3. Si Edge falla, Piper entra solo y no se propaga la excepción.
    voz = _voz_falsa()
    usados = []

    def edge_roto(t, v, vol):
        usados.append("edge")
        raise RuntimeError("sin internet")

    voz._sintetizar_edge = edge_roto
    voz._sintetizar_piper = lambda t, v, vol: (usados.append("piper") or
                                               np.full(4, 0.2, dtype=np.float32))
    audio = voz.sintetizar("Hola")
    assert usados == ["edge", "piper"], usados
    assert len(audio) == 4
    assert voz._edge_fallo_hasta > time.time(), "no se marcó el enfriamiento"

    # 4. Durante el enfriamiento no se vuelve a intentar Edge en cada frase.
    usados.clear()
    voz.sintetizar("Otra frase")
    assert usados == ["piper"], usados

    # 5. Si el usuario vuelve a pedir Piper, no se llama a Edge.
    voz = _voz_falsa()
    voz.motor = "piper"
    usados = []
    voz._sintetizar_edge = lambda t, v, vol: (usados.append("edge") or
                                               np.zeros(1, dtype=np.float32))
    voz._sintetizar_piper = lambda t, v, vol: (usados.append("piper") or
                                               np.zeros(2, dtype=np.float32))
    voz.sintetizar("Hola")
    assert usados == ["piper"], usados

    print("[OK] Edge/Piper: selección, respaldo, enfriamiento y ritmo correctos.")
    print("\nTodos los tests de voz Edge han pasado.")


if __name__ == "__main__":
    main()
