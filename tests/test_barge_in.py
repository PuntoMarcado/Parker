"""
tests/test_barge_in.py
======================
Pruebas de la capa de decisión del barge-in, sin micrófono ni audio.

Lo que se comprueba:
  1. «Parker, para» / «Parker, cállate» se reconocen; una pregunta con «para
     qué» no.
  2. Una transcripción parecida a la frase que Parker está diciendo se trata
     como eco y no corta.
  3. «para» sin el nombre no basta: evita cortes por conversaciones de fondo.
"""

import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.barge_in import (es_eco_de_lo_hablado, normalizar,
                              parece_orden_de_parada)
import parker as modulo  # noqa: E402


def test_orden_de_parada():
    for frase in ("Parker, para.", "Parker para ya", "Oye Parker, cállate",
                  "Parker, basta", "Parker, para un momento",
                  "Parker, para de hablar"):
        assert parece_orden_de_parada(frase), frase

    # «para» como preposición/pregunta no es una orden.
    for frase in ("Parker, ¿para qué sirve esto?",
                  "Parker, ¿para dónde vamos?",
                  "Parker, ¿qué hora es?",
                  "quiero para comer",
                  "para la mesa"):
        assert not parece_orden_de_parada(frase), frase
    print("[OK] «Parker, para/cállate» se reconoce; las preguntas no")


def test_eco_de_la_propia_voz():
    hablado = ["Son las ocho y cuarenta y cinco de la noche."]
    assert es_eco_de_lo_hablado(
        "son las ocho y cuarenta y cinco de la noche", hablado)
    assert not es_eco_de_lo_hablado("Parker, para", hablado)
    assert not es_eco_de_lo_hablado("Parker, pon música", hablado)
    # Texto muy corto: no se puede decidir y no se descarta por si acaso.
    assert not es_eco_de_lo_hablado("sí", hablado)
    print("[OK] el eco de la voz de Parker se separa de una orden")


def test_normalizar():
    assert normalizar("  ¡PÁRKER,  cállate! ") == "parker callate"
    assert normalizar("¿Qué día es hoy?") == "que dia es hoy"
    print("[OK] normalización sin tildes ni signos")


def test_monitor_corta_la_voz():
    """El monitor, con un micro simulado, corta al oír la orden."""
    class EscuchaFalsa:
        volcar_dir = "./no-se-debe-usar"

        def transcribir(self, audio):
            return "Parker, para."

    class VozFalsa:
        def __init__(self):
            self.cortes = 0

        def detener(self):
            self.cortes += 1

    class StreamFalso:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, frames):
            return (np.full((frames, 1), 0.5, dtype=np.float32), None)

    original = modulo.sd.InputStream
    modulo.sd.InputStream = lambda **kwargs: StreamFalso()
    try:
        obj = modulo.Parker.__new__(modulo.Parker)
        obj.corriendo = True
        obj._barge_in = threading.Event()
        obj._barge_in_activo = True
        obj._barge_in_permitido = True
        obj._textos_sonando = deque()
        obj.config = {"barge_in": {"ventana_seg": 0.8, "solape_seg": 0.2,
                                    "umbral_rms": 0.001, "similitud_eco": 0.55},
                      "escucha": {}}
        obj.escucha = EscuchaFalsa()
        obj.voz = VozFalsa()
        obj._emitir = lambda *a, **k: None
        obj._resolver_microfono = lambda cfg, esperar_seg=0: None

        obj._vigilar_barge_in()
        assert obj._barge_in.is_set(), "el monitor no marcó el corte"
        assert obj.voz.cortes == 1, obj.voz.cortes
        # El monitor no debe guardar su audio en el corpus del STT.
        assert obj.escucha.volcar_dir == "./no-se-debe-usar"
    finally:
        modulo.sd.InputStream = original
    print("[OK] el monitor corta con «Parker, para» y no toca el corpus")


def test_cancelar_stream_desbloquea():
    """El corte también cierra el generador del cerebro, no solo la voz.

    Si el modelo se queda callado a mitad de respuesta, el `for delta in
    deltas` sigue esperando al siguiente token y Parker no vuelve a escuchar
    aunque la voz ya esté parada (fallo real del 01/11 en la placa).
    """
    class StreamLento:
        def __init__(self):
            self.cerrado = threading.Event()
            self.leidos = 0

        def __iter__(self):
            yield "Hola. "
            self.leidos += 1
            self.cerrado.wait(2.0)   # simula al modelo que no manda más

        def close(self):
            self.cerrado.set()

    obj = modulo.Parker.__new__(modulo.Parker)
    stream = StreamLento()
    obj._stream_actual = stream

    def _consumir():
        for _ in stream:
            pass

    hilo = threading.Thread(target=_consumir, daemon=True)
    hilo.start()
    while stream.leidos == 0:
        time.sleep(0.01)

    obj._cancelar_stream_actual()
    hilo.join(timeout=1.0)
    assert not hilo.is_alive(), "el stream del cerebro no se desbloqueó"
    assert stream.cerrado.is_set()
    print("[OK] el barge-in cierra el stream del cerebro y desbloquea el turno")


def test_lector_con_corte_no_bloquea():
    """El lector abandona la cola aunque el modelo se quede callado."""
    class StreamLento:
        def __init__(self):
            self.cerrado = threading.Event()

        def __iter__(self):
            yield "uno"
            self.cerrado.wait(2.0)
            yield "dos"

        def close(self):
            self.cerrado.set()

    obj = modulo.Parker.__new__(modulo.Parker)
    obj.corriendo = True
    obj._barge_in = threading.Event()
    stream = StreamLento()
    obj._stream_actual = stream

    lector = obj._deltas_con_corte(stream)
    assert next(lector) == "uno"
    obj._barge_in.set()

    def _siguiente():
        try:
            next(lector)
        except StopIteration:
            pass

    hilo = threading.Thread(target=_siguiente, daemon=True)
    hilo.start()
    hilo.join(timeout=0.8)
    stream.cerrado.set()
    assert not hilo.is_alive(), "el lector siguió esperando al token"
    print("[OK] el lector abandona la cola al primer aviso de corte")


if __name__ == "__main__":
    test_orden_de_parada()
    test_eco_de_la_propia_voz()
    test_normalizar()
    test_monitor_corta_la_voz()
    test_cancelar_stream_desbloquea()
    test_lector_con_corte_no_bloquea()
    print("\nBarge-in: 6/6 en verde.")
