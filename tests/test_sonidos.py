"""El silbido y los sonidos de aviso son sonido real: duración, pico y banda."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.sonidos import SAMPLE_RATE, campana, despertador, micro_listo, silbar


def test_silbido_suena_y_respeta_el_volumen():
    audio = silbar(0.5)
    assert audio.dtype == np.float32
    assert len(audio) > 0

    duracion = len(audio) / SAMPLE_RATE
    assert 1.2 < duracion < 3.0, f"duración rara: {duracion:.2f}s"

    pico = float(np.max(np.abs(audio)))
    assert abs(pico - 0.5) < 0.02, f"pico {pico:.3f} != 0.5"

    # Un silbido humano vive entre ~600 y ~1500 Hz: la energía dominante tiene
    # que estar ahí, no en un zumbido grave ni en ruido de fondo.
    espectro = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
    banda = (freqs > 600) & (freqs < 1500)
    assert espectro[banda].max() > 0.8 * espectro.max()

    # Sin saltos bruscos (clics) entre muestras.
    assert float(np.max(np.abs(np.diff(audio)))) < 0.6
    print(f"[OK] silbido: {duracion:.2f}s, pico {pico:.2f}, "
          "energía en la banda del silbido")


def _rafagas(audio: np.ndarray, umbral: float = 0.15,
             ventana_seg: float = 0.02) -> int:
    """Cuenta ráfagas separadas por silencio (para reconocer una alarma)."""
    ventana = int(SAMPLE_RATE * ventana_seg)
    sobres = []
    for i in range(0, len(audio) - ventana, ventana):
        sobres.append(float(np.max(np.abs(audio[i:i + ventana]))) > umbral)
    return sum(1 for i, activo in enumerate(sobres)
               if activo and not (i and sobres[i - 1]))


def test_campana_avisa():
    audio = campana(0.6)
    duracion = len(audio) / SAMPLE_RATE
    assert 0.8 < duracion < 2.0, f"duración rara: {duracion:.2f}s"
    assert abs(float(np.max(np.abs(audio))) - 0.6) < 0.02
    # Dos notas: el «din-don» se distingue del silencio de en medio.
    assert _rafagas(audio) == 2, _rafagas(audio)
    print(f"[OK] campana: {duracion:.2f}s, pico 0.60, dos notas")


def test_micro_listo_avisa():
    """El chime del arranque: corto, dos notas y distinto de la campana."""
    audio = micro_listo(0.4)
    duracion = len(audio) / SAMPLE_RATE
    assert 0.3 < duracion < 0.8, f"duración rara: {duracion:.2f}s"
    assert abs(float(np.max(np.abs(audio))) - 0.4) < 0.02
    # Dos notas ascendentes: se distinguen del «din-don» de la agenda.
    assert _rafagas(audio) == 2, _rafagas(audio)
    espectro = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
    banda = (freqs > 600) & (freqs < 1100)
    assert espectro[banda].max() > 0.8 * espectro.max()
    print(f"[OK] micro_listo: {duracion:.2f}s, pico 0.40, dos notas")


def test_despertador_se_oye():
    audio = despertador(0.7)
    duracion = len(audio) / SAMPLE_RATE
    assert 2.0 < duracion < 4.0, f"duración rara: {duracion:.2f}s"
    assert abs(float(np.max(np.abs(audio))) - 0.7) < 0.02
    # Cuatro ráfagas de dos pitidos (8 en total): una alarma insiste, no suena
    # una sola vez.
    pitidos = _rafagas(audio, umbral=0.35)
    assert pitidos == 8, pitidos
    # Y tiene que ser agudo (un aviso, no un zumbido grave).
    espectro = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), 1 / SAMPLE_RATE)
    assert espectro[(freqs > 900) & (freqs < 1500)].max() > 0.8 * espectro.max()
    print(f"[OK] despertador: {duracion:.2f}s, pico 0.70, {pitidos} pitidos agudos")


if __name__ == "__main__":
    test_silbido_suena_y_respeta_el_volumen()
    test_campana_avisa()
    test_micro_listo_avisa()
    test_despertador_se_oye()
    print("\nSonidos: 4/4 en verde.")
