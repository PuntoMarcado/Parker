"""
tests/test_escucha.py
=====================
Tests offline del módulo de escucha: el volcado WAV+TXT del corpus STT
(plan §2.4) y los parámetros de transcripción (plan §2.1).

Ejecutar:  python tests/test_escucha.py
"""

import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.escucha import (EscuchaParker, limpiar_marcas_prompt,
                             parece_eco_del_prompt, volcar_audio)


def test_volcar_audio_guarda_wav_y_txt():
    with tempfile.TemporaryDirectory() as tmp:
        audio = (0.5 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)).astype(np.float32)
        ruta = volcar_audio(tmp, audio, "Oye Parker, ¿qué hora es?", 16000)

        assert ruta.endswith(".wav") and Path(ruta).exists(), ruta
        with wave.open(ruta, "rb") as wf:
            assert wf.getnframes() == 16000, wf.getnframes()
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1

        txt = Path(ruta).with_suffix(".txt")
        assert txt.read_text(encoding="utf-8") == "Oye Parker, ¿qué hora es?"
        assert len(list(Path(tmp).glob("*.wav"))) == 1

        # Dos volcados en el mismo segundo no pisan el primero
        ruta2 = volcar_audio(tmp, audio, "Segunda frase.", 16000)
        assert ruta2 != ruta, (ruta, ruta2)
        assert len(list(Path(tmp).glob("*.wav"))) == 2
    print("[OK] volcado WAV+TXT del corpus STT (sin colisiones)")


class ModeloFalso:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs

        class Segmento:
            text = " Hola."

        return [Segmento()], None


def _escucha_sin_modelo():
    """EscuchaParker sin cargar ningún Whisper (para inspeccionar kwargs)."""
    e = EscuchaParker.__new__(EscuchaParker)
    e.idioma = "es"
    e.backend = "faster-whisper"
    e.beam_size = 1
    e.vad_filter = True
    e.hotwords = "Parker"
    e.initial_prompt = "El nombre propio Parker se escribe Parker."
    e.vad_parameters = {"threshold": 0.4, "speech_pad_ms": 500}
    e.volcar_dir = None
    e.sample_rate = 16000
    e.modelo_faster = ModeloFalso()
    e.modelo = None
    return e


def test_transcribir_pasa_sesgos_y_vad():
    e = _escucha_sin_modelo()
    texto = e.transcribir(np.zeros(16000, dtype=np.float32))
    kw = e.modelo_faster.kwargs

    assert kw["hotwords"] == "Parker", kw
    assert kw["initial_prompt"] == "El nombre propio Parker se escribe Parker.", kw
    assert kw["vad_parameters"]["threshold"] == 0.4, kw
    # Sin esto, la frase anterior contamina la siguiente (visto: arrastraba
    # transcripciones) y el caché de prefijo se rompe.
    assert kw["condition_on_previous_text"] is False, kw
    assert texto == "Hola.", texto
    print("[OK] transcribir pasa initial_prompt, hotwords y vad_parameters")


def test_eco_del_prompt_no_se_ejecuta():
    """El 01/11 Whisper devolvió el prompt y se cambió el cerebro solo."""
    eco = " ¡¿qué día es hoy?», «cambia el cerebro al local»."
    assert parece_eco_del_prompt(eco), eco
    # Una orden de verdad no lleva comillas de prompt y debe ejecutarse.
    assert not parece_eco_del_prompt("Parker, cambia el cerebro al local")
    assert not parece_eco_del_prompt("Parker, ¿qué hora es?")
    # Medido en la placa el 01/11 a las 20:39: Whisper añadía SOLO el cierre a
    # una frase real y el filtro tiraba el turno entero (Parker parecía sordo).
    assert not parece_eco_del_prompt("¡¿qué día es hoy?».")
    assert limpiar_marcas_prompt("¡¿qué día es hoy?».") == "¡¿qué día es hoy?."
    assert limpiar_marcas_prompt("Parker, reiníciate»") == "Parker, reiníciate"
    print("[OK] el eco del initial_prompt no se confunde con una orden")


def test_sin_volcado_no_escribe_nada():
    with tempfile.TemporaryDirectory() as tmp:
        e = _escucha_sin_modelo()
        e.transcribir(np.zeros(16000, dtype=np.float32))
        assert list(Path(tmp).glob("*")) == []  # volcar_dir=None → off
    print("[OK] sin volcar_audio_dir no se escribe nada en disco")


if __name__ == "__main__":
    test_volcar_audio_guarda_wav_y_txt()
    test_transcribir_pasa_sesgos_y_vad()
    test_eco_del_prompt_no_se_ejecuta()
    test_sin_volcado_no_escribe_nada()
    print("\nTodos los tests de escucha han pasado.")
