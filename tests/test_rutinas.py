"""
Pruebas de las rutinas del día: dormir, despertar, el parte, «cállate un rato» y
apagarse. Sin LLM, sin audio y con hora fija (lunes 26/10/2026, 16:00).
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.agenda import AgendaParker           # noqa: E402
from modulos.rutinas import (ORDEN_BORRAR_MEMORIA, ORDEN_REINICIAR,  # noqa: E402
                             RutinasParker)

AHORA = datetime(2026, 10, 26, 16, 0)


def _agenda() -> AgendaParker:
    return AgendaParker(ruta_agenda=None, hora_citas="09:00")


def test_dormir_y_despertar():
    rutinas = RutinasParker(hora_parte="08:30")
    assert not rutinas.dormido
    assert rutinas.procesar("Parker, buenas noches", AHORA) == \
        ("Buenas noches. Descansa.", "dormir")
    assert rutinas.dormido and rutinas.debe_callarse(AHORA)
    assert rutinas.procesar("¿estás dormido?", AHORA)[0].startswith("Estoy dormido")
    assert rutinas.procesar("Parker, buenos días", AHORA) == ("Buenos días.", "despertar")
    assert not rutinas.dormido and not rutinas.debe_callarse(AHORA)
    assert rutinas.procesar("¿estás despierto?", AHORA)[0].startswith("Despierto")

    # «despiértate» con muletillas delante también vale.
    rutinas.dormir()
    assert rutinas.procesar("Oye Parker, despiértate", AHORA)[1] == "despertar"

    # Charla normal: no son órdenes.
    for frase in ("hoy hace un día precioso", "me gusta la noche",
                  "despierta a tu hermana", "buenas tardes"):
        otra = RutinasParker()
        assert otra.procesar(frase, AHORA) is None, frase
        assert not otra.dormido, frase
    print("[OK] buenas noches y buenos días, sin confundir la charla")


def test_callate_un_rato():
    rutinas = RutinasParker()
    frase, accion = rutinas.procesar("Parker, cállate diez minutos", AHORA)
    assert accion is None and "diez minutos" in frase, frase
    assert rutinas.debe_callarse(AHORA + timedelta(minutes=9))
    assert not rutinas.silencio_expirado(AHORA + timedelta(minutes=9))
    assert not rutinas.debe_callarse(AHORA + timedelta(minutes=11))
    assert rutinas.silencio_expirado(AHORA + timedelta(minutes=11))
    # Se avisa UNA vez, no en cada vuelta del bucle.
    assert not rutinas.silencio_expirado(AHORA + timedelta(minutes=12))

    # Sin decir cuánto: un rato corto (10 min). «no hables más»: indefinido.
    otro = RutinasParker()
    assert "un rato" in otro.procesar("cállate un rato", AHORA)[0]
    assert otro.debe_callarse(AHORA + timedelta(minutes=5))
    indefinido = RutinasParker()
    indefinido.procesar("no hables más", AHORA)
    assert indefinido.debe_callarse(AHORA + timedelta(days=30))
    # «¿puedes callarte media hora?» también se entiende.
    media = RutinasParker()
    assert media.procesar("¿puedes callarte media hora?", AHORA)[0].endswith(
        "treinta minutos.")
    # Dormido ya está callado; y hablar del silencio no es pedirlo.
    assert RutinasParker().procesar("me gusta el silencio de la noche", AHORA) is None
    print("[OK] «cállate N minutos»: se calla, vuelve solo y avisa una vez")


def test_apagate():
    rutinas = RutinasParker()
    frase, accion = rutinas.procesar("Parker, apágate", AHORA)
    assert accion == "apagar" and "Hasta luego" in frase, (frase, accion)
    assert rutinas.procesar("apágate del todo", AHORA)[1] == "apagar"
    # Variantes que el STT escribe de verdad (medido en la placa el 26/10:
    # «apágate» llegó como «apajate» y no se apagó nada).
    for variante in ("apajate", "apagate", "apágate ya", "apaga todo",
                     "apaga el sistema", "apaga la placa", "apaga parker"):
        assert RutinasParker().procesar(variante, AHORA)[1] == "apagar", variante
    # Otras cosas que se apagan no son «apágate».
    for frase in ("apaga la luz del salón", "esa radio se apaga sola",
                  "apaga el café de la máquina"):
        assert RutinasParker().procesar(frase, AHORA) is None, frase
    print("[OK] «apágate» solo cuando lo pide a él")


def test_mantenimiento_por_voz():
    """«borra la memoria» y «reiníciate»: las dos órdenes del 01/11."""
    for frase in ("Parker, borra tu memoria", "borra la memoria",
                  "borra memoria", "vacía tu memoria",
                  "olvida todos los recuerdos", "borra los recuerdos"):
        assert RutinasParker().procesar(frase, AHORA)[1] == ORDEN_BORRAR_MEMORIA, frase
    # La memoria de OTRO aparato no es la suya.
    for frase in ("borra la memoria del móvil", "borra la memoria del ordenador",
                  "borra la memoria de la placa", "borra la alarma de las siete",
                  "olvida la cita del dentista", "reinicia la alarma",
                  "limpia la mesa"):
        assert RutinasParker().procesar(frase, AHORA) is None, frase
    for frase in ("Parker, reiníciate", "reiníciate", "reinicia",
                  "reinicia el sistema", "reiniciar", "reinicio"):
        assert RutinasParker().procesar(frase, AHORA)[1] == ORDEN_REINICIAR, frase
    print("[OK] borrado de memoria y reinicio por voz")


def test_parte_del_dia():
    agenda = _agenda()
    agenda.procesar("apunta que hoy a las 17:00 tengo al dentista", AHORA)
    agenda.procesar("pon un temporizador de 10 minutos", AHORA)
    rutinas = RutinasParker(hora_parte="08:30")

    assert not rutinas.toca_parte(datetime(2026, 10, 26, 7, 0))
    assert rutinas.toca_parte(AHORA)
    texto = rutinas.parte_del_dia(agenda, AHORA, nombre="Alan")
    assert texto.startswith("Buenos días, Alan. Hoy tienes:"), texto
    assert "dentista" in texto and "a las cinco" in texto, texto
    # El temporizador de la sesión no sale en el parte del día.
    assert "temporizador" not in texto and "cuatro y diez" not in texto, texto

    rutinas.marcar_parte(AHORA)
    assert not rutinas.toca_parte(AHORA + timedelta(hours=1))

    # Sin nada apuntado no da la tabarra (salvo que se pida lo contrario).
    vacia = _agenda()
    assert RutinasParker().parte_del_dia(vacia, AHORA) is None
    con_vacio = RutinasParker(parte_si_vacio=True).parte_del_dia(vacia, AHORA, "Alan")
    assert con_vacio.endswith("nada apuntado para hoy."), con_vacio

    # Dormido o callado no suelta el parte.
    dormido = RutinasParker()
    dormido.dormir()
    assert not dormido.toca_parte(AHORA)
    callado = RutinasParker()
    callado.callar(600, AHORA)
    assert not callado.toca_parte(AHORA)
    print("[OK] parte del día: a su hora, una vez y solo si hay algo que contar")


if __name__ == "__main__":
    test_dormir_y_despertar()
    test_callate_un_rato()
    test_apagate()
    test_mantenimiento_por_voz()
    test_parte_del_dia()
    print("\nRutinas: 5/5 en verde.")
