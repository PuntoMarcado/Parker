"""Pruebas del filtro de transcripciones dudosas.

Lo que se comprueba:
  1. Las alucinaciones típicas de Whisper se descartan.
  2. Las respuestas cortas legítimas NO se descartan.
  3. Las métricas de Whisper solo actúan cuando son señales fuertes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.filtro_stt import (
    es_alucinacion_conocida,
    es_repeticion_sin_sentido,
    es_transcripcion_dudosa,
)


def test_alucinaciones_conocidas():
    for frase in ("Gracias por ver el video.", "gracias por ver el vídeo",
                  "No olvides suscribirte al canal.",
                  "Suscríbete al canal y dale like.",
                  "Hasta la próxima."):
        assert es_alucinacion_conocida(frase), frase
    for frase in ("Gracias, Parker.", "Hola, Parker.", "Vale.", "Sí.",
                  "Baja el volumen.", "¿Qué hora es?"):
        assert not es_alucinacion_conocida(frase), frase
    print("[OK] alucinaciones conocidas sí; saludos y frases cortas no")


def test_repeticiones():
    for frase in ("¡Ah! ¡Ah! ¡Ah!", "la la la la la", "mmm mmm mmm mmm"):
        assert es_repeticion_sin_sentido(frase), frase
    assert not es_repeticion_sin_sentido("sí sí sí")
    assert not es_repeticion_sin_sentido("no, no, no, no")
    assert not es_repeticion_sin_sentido("Parker, baja el volumen")
    # 02/11: la cola del altavoz repite un bloque corto y Whisper lo transcribe
    # como si fuera una frase («oído local, oído local, oído local»).
    assert es_repeticion_sin_sentido("oído local, oído local, oído local")
    assert es_repeticion_sin_sentido("muy bien, muy bien, muy bien")
    assert not es_repeticion_sin_sentido("no, no")
    assert not es_repeticion_sin_sentido("sí, sí, sí")
    print("[OK] repeticiones de golpes/interjecciones se descartan")


def test_metricas_solo_si_son_fuertes():
    assert es_transcripcion_dudosa("frase suelta", no_speech=0.9)
    assert es_transcripcion_dudosa("¡Ah!")
    assert es_transcripcion_dudosa("eh")
    assert not es_transcripcion_dudosa("Vale, vamos allá", no_speech=0.2,
                                       avg_logprob=-0.3, compression_ratio=1.2)
    assert es_transcripcion_dudosa("texto repetido", compression_ratio=3.2)
    assert es_transcripcion_dudosa("texto raro", avg_logprob=-1.8)
    assert es_transcripcion_dudosa("   ")
    print("[OK] las métricas solo descartan con señales fuertes")


if __name__ == "__main__":
    test_alucinaciones_conocidas()
    test_repeticiones()
    test_metricas_solo_si_son_fuertes()
    print("\nFiltro STT: 3/3 en verde.")
