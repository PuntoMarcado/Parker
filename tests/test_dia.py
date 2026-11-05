"""
tests/test_dia.py
=================
El día de Parker sin LLM ni hardware: quién manda en cada frase.

Se comprueba el reparto de `Parker._responder_sin_llm` (el orden importa y es
lo que decide si Parker tarda 0 o 3 segundos en obedecer):

  1. Rutinas: «buenas noches» duerme, «despiértate» despierta, «cállate diez
     minutos» calla, «apágate» llama al apagado ordenado.
  2. Apuntes: un contador de agua se crea y se consulta por voz.
  3. El tiempo y la agenda contestan sin tocar el modelo.
  4. Música: la orden pone el tema en la cola; con la música sonando el
     volumen a secas es la música y la charla NO se traga el módulo (la abre
     el bucle de escucha solo cuando confirma que hay una persona).
  5. Dormido o callado no se contesta charla (pero las órdenes de arriba sí).

Ejecutar:
    QT_QPA_PLATFORM=offscreen python tests/test_dia.py
"""

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parker as P  # noqa: E402
from modulos.agenda import AgendaParker  # noqa: E402
from modulos.apuntes import ApuntesParker  # noqa: E402
from modulos.musica import MusicaParker  # noqa: E402
from modulos.personalidad import PersonalidadParker  # noqa: E402
from modulos.rutinas import RutinasParker  # noqa: E402


class CerebroFalso:
    def respuesta_directa(self, _texto):
        return None


class ModuloFijo:
    """Módulo de mentira: contesta solo si la frase lleva su palabra clave."""

    def __init__(self, palabra, respuesta):
        self.palabra = palabra
        self.respuesta = respuesta
        self.veces = 0

    def procesar(self, texto):
        if self.palabra in texto:
            self.veces += 1
            return self.respuesta
        return None


def _parker(agenda=None):
    p = P.Parker.__new__(P.Parker)
    p.config = {}
    p.rutinas = RutinasParker()
    p.apuntes = ApuntesParker()
    p.agenda = agenda or AgendaParker()
    p.tiempo = ModuloFijo("tiempo", "En Barcelona hace veinte grados.")
    p.musica = MusicaParker(volumen=0.7)
    p.cerebro = CerebroFalso()
    p.personalidad = PersonalidadParker({"guardar_estado": False})
    p.musica_sonando = False
    p.musica_temas_seguidos = 2
    p._cola_musica = queue.Queue()
    p._parar_musica = threading.Event()
    p.hablado = []
    p.emitido = []
    p._hablar = lambda texto, emocion="neutral", motor=True: p.hablado.append(texto)
    p._registrar_suceso = lambda *a, **k: None
    p._emitir = lambda nombre, valor: p.emitido.append((nombre, valor))
    p._apagar = lambda: p.hablado.append("APAGADO")
    return p


def test_rutinas_del_dia():
    p = _parker()
    assert p._responder_sin_llm("Parker, buenas noches") is True
    assert p.rutinas.dormido is True
    assert any("Buenas noches" in t for t in p.hablado), p.hablado
    assert ("dormir", True) in p.emitido, p.emitido

    # Dormido, un dato directo sigue contestándose (es una orden, no charla).
    p.hablado.clear()
    assert p._responder_sin_llm("¿estás despierto?") is True
    assert p.hablado and "dormido" in p.hablado[0].lower(), p.hablado

    p.hablado.clear()
    assert p._responder_sin_llm("Parker, despiértate") is True
    assert p.rutinas.dormido is False
    assert ("dormir", False) in p.emitido, p.emitido

    p.hablado.clear()
    assert p._responder_sin_llm("cállate diez minutos") is True
    assert p.rutinas.debe_callarse() is True
    assert any("me callo" in t for t in p.hablado), p.hablado

    p.hablado.clear()
    assert p._responder_sin_llm("Parker, apágate") is True
    assert "APAGADO" in p.hablado, p.hablado
    print("[OK] buenas noches, despiértate, cállate y apágate")


def test_apuntes_y_tiempo_sin_llm():
    p = _parker()
    p.hablado.clear()
    assert p._responder_sin_llm("Parker, apunta un litro de agua") is True
    assert p.apuntes.contadores, p.apuntes.contadores
    assert any("Anotado" in t and "agua" in t for t in p.hablado), p.hablado

    p.hablado.clear()
    assert p._responder_sin_llm("¿cuánta agua llevo hoy?") is True
    assert any("Hoy llevas" in t for t in p.hablado), p.hablado

    # Un contador con hora sigue siendo un contador, no una alarma
    # («apunta un litro de agua a las dos de la tarde» en la placa, 26/10).
    p.hablado.clear()
    assert p._responder_sin_llm("Parker, apunta un litro de agua a las dos de la tarde") is True
    assert p.agenda.avisos == [], p.agenda.avisos
    assert any("Anotado" in t for t in p.hablado), p.hablado
    p.apuntes.contadores.clear()

    p.hablado.clear()
    assert p._responder_sin_llm("¿qué tiempo hace hoy?") is True
    assert p.tiempo.veces == 1
    assert p.hablado == ["En Barcelona hace veinte grados."], p.hablado

    # Una orden de agenda sigue funcionando por el mismo camino.
    p.hablado.clear()
    ahora = datetime.now()
    assert p._responder_sin_llm("apunta que mañana a las 9 tengo al dentista") is True
    assert len(p.agenda.avisos) == 1, p.agenda.avisos
    assert any("Apuntado" in t for t in p.hablado), (p.hablado, ahora)
    print("[OK] apuntes, tiempo y agenda contestan con datos reales, sin LLM")


def test_musica_y_su_silencio():
    p = _parker()
    # La búsqueda se sustituye: aquí no hay red.
    p.musica.buscar = lambda consulta="": {
        "titulo": "Bohemian Rhapsody", "artista": "Queen",
        "url": "https://cdn.example/x.mp3", "segundos": 355, "id": "1"}
    p.musica.cola = [{"titulo": "Don't Stop Me Now", "artista": "Queen",
                      "url": "https://cdn.example/y.mp3", "segundos": 209,
                      "id": "2"}]
    p.hablado.clear()
    assert p._responder_sin_llm("Parker, pon algo de Queen") is True
    assert p._cola_musica.qsize() == 2, p._cola_musica.qsize()
    assert any("Bohemian" in t for t in p.hablado), p.hablado

    # Con música sonando, «baja el volumen» es la música (es lo que se oye).
    p.hablado.clear()
    p.musica_sonando = True
    antes = p.musica.porcentaje()
    assert p._responder_sin_llm("Parker, baja el volumen") is True
    assert p.musica.porcentaje() < antes, p.musica.porcentaje()
    assert any("Bajo la música" in t for t in p.hablado), p.hablado

    # La charla con música puesta ya NO se ignora: la música no se la traga,
    # la contesta el cerebro (con la música bajada).
    p.hablado.clear()
    assert p._responder_sin_llm("hola Parker, ¿qué tal estás?") is False
    assert p.hablado == [], p.hablado

    # Y una orden de música sí se atiende.
    assert p._responder_sin_llm("para la música") is True
    assert p._parar_musica.is_set()
    assert any("quito la música" in t for t in p.hablado), p.hablado
    p.musica_sonando = False
    print("[OK] música: pone, atiende el volumen por encima y el «para»")


def test_callado_no_contesta_charla():
    p = _parker()
    p.rutinas.callar(600)
    p.hablado.clear()
    assert p._responder_sin_llm("hola, ¿qué tal el día?") is True
    assert p.hablado == [], p.hablado
    # Y el parte del día no se dice estando callado (es hablar).
    assert p._decir_parte_del_dia() is False
    print("[OK] callado no contesta charla; el parte espera")


if __name__ == "__main__":
    test_rutinas_del_dia()
    test_apuntes_y_tiempo_sin_llm()
    test_musica_y_su_silencio()
    test_callado_no_contesta_charla()
    print("\nDía de Parker: 4/4 en verde.")
