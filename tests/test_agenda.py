"""
Pruebas de la agenda (alarmas, temporizadores y citas) sin LLM, sin audio y sin
reloj real: todo con `ahora` fijo.

Escenario base: lunes 26/10/2026 a las 16:00 (hora real de la placa ese día).
"""

import json
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.agenda import (ALARMA, CITA, TEMPORIZADOR, AgendaParker,  # noqa: E402
                            _duracion_hablada, _hora_hablada, _numero,
                            _numero_a_palabras)

AHORA = datetime(2026, 10, 26, 16, 0)


def _agenda(tmp: str = None) -> AgendaParker:
    return AgendaParker(ruta_agenda=tmp)


def _unico(agenda: AgendaParker) -> dict:
    assert len(agenda.avisos) == 1, agenda.avisos
    return agenda.avisos[0]


def test_numeros_y_horas_en_palabras():
    assert _numero("35") == 35
    assert _numero("treinta y cinco") == 35
    assert _numero("veinticinco") == 25
    assert _numero("cien") == 100
    assert _numero("la") is None
    assert _numero_a_palabras(10) == "diez"
    assert _numero_a_palabras(42) == "cuarenta y dos"
    assert _numero_a_palabras(5) == "cinco"
    assert _hora_hablada(datetime(2026, 10, 26, 7, 30)) == "las siete y media"
    assert _hora_hablada(datetime(2026, 10, 26, 19, 0)) == \
        "las siete en punto de la tarde"
    assert _hora_hablada(datetime(2026, 10, 26, 8, 45)) == "las nueve menos cuarto"
    assert _hora_hablada(datetime(2026, 10, 26, 20, 15)) == \
        "las ocho y cuarto de la noche"
    assert _duracion_hablada(600) == "diez minutos"
    assert _duracion_hablada(60) == "un minuto"
    assert _duracion_hablada(90) == "un minuto y treinta segundos"
    assert _duracion_hablada(3600) == "una hora"
    assert _duracion_hablada(5400) == "una hora y treinta minutos"
    print("[OK] números, horas y duraciones se dicen en palabras")


def test_temporizadores():
    agenda = _agenda()
    respuesta = agenda.procesar("Parker, pon un temporizador de 10 minutos", AHORA)
    aviso = _unico(agenda)
    assert aviso["tipo"] == TEMPORIZADOR
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 10, 26, 16, 10)
    assert respuesta == ("Temporizador de diez minutos. Te aviso a las cuatro y "
                         "diez de la tarde."), respuesta

    agenda = _agenda()
    agenda.procesar("avísame en media hora", AHORA)
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 26, 16, 30)

    agenda = _agenda()
    respuesta = agenda.procesar("recuérdame en 5 minutos sacar la ropa", AHORA)
    aviso = _unico(agenda)
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 10, 26, 16, 5)
    assert aviso["texto"] == "sacar la ropa", aviso
    assert aviso["duracion_seg"] == 300
    assert respuesta.endswith("Te aviso a las cuatro y cinco de la tarde.")

    # «en un minuto y medio» son 90 s, no 60.
    agenda = _agenda()
    agenda.procesar("en un minuto y medio", AHORA)
    assert _unico(agenda)["duracion_seg"] == 90

    # Sin materia: suena igual y lo dice.
    agenda = _agenda()
    agenda.procesar("en 30 segundos", AHORA)
    assert _unico(agenda)["duracion_seg"] == 30

    # Una duración dentro de una frase normal NO pone nada.
    for frase in ("te lo digo en cinco minutos", "en dos días te lo cuento",
                  "tardo diez minutos en llegar"):
        agenda = _agenda()
        assert agenda.procesar(frase, AHORA) is None, frase
        assert agenda.avisos == [], frase
    print("[OK] temporizadores: minutos, media hora, segundos y sin falsos positivos")


def test_alarmas_a_una_hora():
    casos = [
        ("Parker, pon una alarma a las 7:30", datetime(2026, 10, 27, 7, 30),
         "Alarma puesta para mañana a las siete y media."),
        ("despiértame a las siete y media", datetime(2026, 10, 27, 7, 30), None),
        ("avísame a las 19:30", datetime(2026, 10, 26, 19, 30), None),
        ("pon una alarma a las 7 de la tarde", datetime(2026, 10, 26, 19, 0), None),
        ("pon una alarma a las 9 menos cuarto", datetime(2026, 10, 27, 8, 45), None),
        ("alarma a las 8 y cuarto", datetime(2026, 10, 27, 8, 15), None),
        ("despiértame a las 6 y 40", datetime(2026, 10, 27, 6, 40), None),
    ]
    for frase, esperado, respuesta in casos:
        agenda = _agenda()
        dicha = agenda.procesar(frase, AHORA)
        aviso = _unico(agenda)
        assert aviso["tipo"] == ALARMA, (frase, aviso)
        assert datetime.fromtimestamp(aviso["ts"]) == esperado, (frase, aviso)
        if respuesta is not None:
            assert dicha == respuesta, (frase, dicha)

    # Una alarma de después de comer el mismo día no se va a mañana.
    agenda = _agenda()
    agenda.procesar("pon una alarma a las 22:15", AHORA)
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 26, 22, 15)

    # Repetir aún no se hace, pero se dice claro en vez de prometerlo.
    agenda = _agenda()
    respuesta = agenda.procesar("despiértame todos los días a las 7", AHORA)
    assert len(agenda.avisos) == 1
    assert "una vez" in respuesta, respuesta

    # El STT a veces oye «pone una alarma»: la materia no puede quedar en
    # «pone una» (visto en la placa el 30/10: «Alarma …: pone una»).
    for frase in ("Parker pone una alarma a las 7 de la tarde",
                  "ponme una alarma a las 7 de la tarde",
                  "Parker pon una alarma a las 7 de la tarde"):
        agenda = _agenda()
        respuesta = agenda.procesar(frase, AHORA)
        aviso = _unico(agenda)
        assert aviso["texto"] == "", (frase, aviso)
        assert "pone" not in respuesta.lower(), (frase, respuesta)
    print("[OK] alarmas: próxima vez, «de la tarde/noche» y materia limpia")


def test_citas_en_el_calendario():
    agenda = _agenda()
    respuesta = agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
    aviso = _unico(agenda)
    assert aviso["tipo"] == CITA
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 10, 30, 9, 0)
    assert aviso["texto"] == "dentista", aviso
    assert respuesta == ("Apuntado: el viernes 30 de octubre a las nueve en "
                         "punto: dentista."), respuesta

    agenda = _agenda()
    agenda.procesar("apunta que el 12 de noviembre a las 17:00 tengo médico", AHORA)
    aviso = _unico(agenda)
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 11, 12, 17, 0)
    assert aviso["texto"] == "medico", aviso

    # Una cita a las 5 es de la tarde; a las 9, de la mañana.
    agenda = _agenda()
    agenda.procesar("apunta el jueves a las 5 la revisión del coche", AHORA)
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 29, 17, 0)
    agenda = _agenda()
    agenda.procesar("apunta el jueves a las 9 la analítica", AHORA)
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 29, 9, 0)

    # Fecha escrita con barra y con mes en palabras.
    agenda = _agenda()
    agenda.procesar("recuérdame el 3/12 la renovación del carnet", AHORA)
    aviso = _unico(agenda)
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 12, 3, 9, 0)
    # En el calendario se guarda un TITULAR corto, no la frase entera (pedido
    # del 26/10: «que ponga cita dentista a las 9, no lo que le he dicho»).
    assert aviso["texto"] == "renovacion carnet", aviso
    assert aviso["dicho"] == "renovacion del carnet", aviso

    agenda = _agenda()
    respuesta = agenda.procesar("apúntame el viernes a las 9 que tengo cita "
                               "con el dentista", AHORA)
    aviso = _unico(agenda)
    assert aviso["texto"] == "cita dentista", aviso
    assert aviso["dicho"] == "cita con el dentista", aviso
    assert "cita dentista" in respuesta, respuesta

    # Charla normal: no se apunta nada sin verbo de apunte.
    for frase in ("el viernes tengo médico", "hoy tengo mucho trabajo",
                  "ayer fui al médico", "¿qué tal el fin de semana?"):
        agenda = _agenda()
        assert agenda.procesar(frase, AHORA) is None, frase
        assert agenda.avisos == [], frase
    print("[OK] citas: día, hora, mes, titular corto y sin apuntar la charla normal")


def test_consultas():
    agenda = _agenda()
    agenda.procesar("apunta que mañana a las 11 tengo al fisio", AHORA)
    agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
    agenda.procesar("avísame en 20 minutos la lavadora", AHORA)

    respuesta = agenda.procesar("¿qué tengo mañana?", AHORA)
    assert "mañana" in respuesta.lower() and "fisio" in respuesta, respuesta

    respuesta = agenda.procesar("¿qué tengo el viernes?", AHORA)
    assert "dentista" in respuesta, respuesta

    respuesta = agenda.procesar("¿qué tengo esta semana?", AHORA)
    assert "dentista" in respuesta and "fisio" in respuesta, respuesta

    respuesta = agenda.procesar("¿qué alarmas tengo?", AHORA)
    assert "temporizador" in respuesta.lower(), respuesta
    assert "dentista" not in respuesta, respuesta

    agenda = _agenda()
    assert "nada apuntado" in agenda.procesar("¿qué tengo hoy?", AHORA)
    assert "ninguna alarma" in agenda.procesar("¿qué alarmas tengo?", AHORA)

    # «¿qué tengo que hacer?» es charla, no una consulta de agenda.
    assert agenda.procesar("¿qué tengo que hacer contigo?", AHORA) is None
    assert agenda.procesar("¿qué hay de comer?", AHORA) is None
    print("[OK] consultas: día, semana, alarmas y sin confundir la charla")


def test_borrar():
    agenda = _agenda()
    agenda.procesar("avísame en 20 minutos la lavadora", AHORA)
    respuesta = agenda.procesar("borra el temporizador", AHORA)
    assert not agenda.avisos and "Borrado" in respuesta, respuesta

    agenda = _agenda()
    agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
    agenda.procesar("apunta que el lunes tengo al fisio", AHORA)
    respuesta = agenda.procesar("borra la cita del dentista", AHORA)
    assert "Borrado" in respuesta and len(agenda.avisos) == 1, (respuesta, agenda.avisos)
    assert agenda.avisos[0]["texto"] == "fisio"

    # Sin coincidencia de texto, manda el tipo.
    agenda = _agenda()
    agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
    respuesta = agenda.procesar("cancela la cita de las siete", AHORA)
    assert not agenda.avisos, respuesta

    agenda = _agenda()
    assert agenda.procesar("borra la cita", AHORA) is None

    # Con dos alarmas, «borra la alarma» pregunta en vez de borrar las dos.
    agenda = _agenda()
    agenda.procesar("pon una alarma a las 7", AHORA)
    agenda.procesar("pon una alarma a las 9", AHORA)
    respuesta = agenda.procesar("borra la alarma", AHORA)
    assert "Tienes 2 avisos" in respuesta and len(agenda.avisos) == 2, respuesta
    respuesta = agenda.procesar("borra todas las alarmas", AHORA)
    assert not agenda.avisos, respuesta

    # No borra por charla que mencione borrar sin tipo.
    agenda = _agenda()
    agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
    assert agenda.procesar("borra lo de ayer del historial", AHORA) is None
    assert len(agenda.avisos) == 1
    print("[OK] borrar: por tipo, por texto y sin falsos positivos")


def test_reprogramar_cita_y_alarma():
    """Cambiar la hora, no crear otra: el fallo real del 30/10."""
    agenda = _agenda()
    agenda.procesar("apunta que mañana a las 9 tengo al dentista", AHORA)
    aviso = _unico(agenda)
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 10, 27, 9, 0)

    respuesta = agenda.procesar(
        "cambia la hora del dentista de mañana a las 6 de la tarde", AHORA)
    assert len(agenda.avisos) == 1, agenda.avisos          # no duplica
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 27, 18, 0), agenda.avisos
    assert "Cambiada la cita" in respuesta and "seis" in respuesta, respuesta

    # Otra vez, sin decir «mañana»: conserva el día de la cita.
    respuesta = agenda.procesar("cambia la cita del dentista a las 7 de la tarde", AHORA)
    assert len(agenda.avisos) == 1
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 27, 19, 0), agenda.avisos
    assert "siete" in respuesta, respuesta

    # Alarma: la primera hora identifica la que ya existe; la segunda es la nueva.
    agenda = _agenda()
    agenda.procesar("pon una alarma a las 7", AHORA)       # mañana 07:00
    respuesta = agenda.procesar("cambia la alarma de las 7 a las 8", AHORA)
    assert len(agenda.avisos) == 1, agenda.avisos
    assert datetime.fromtimestamp(_unico(agenda)["ts"]) == \
        datetime(2026, 10, 27, 8, 0), agenda.avisos
    assert "ocho" in respuesta, respuesta

    # La materia del aviso se conserva al reprogramar (no se convierte en
    # «cambia la alarma» ni se pierde).
    agenda = _agenda()
    agenda.procesar("pon una alarma a las 7 para despertar", AHORA)
    agenda.procesar("cambia la alarma de las 7 a las 8 de la tarde", AHORA)
    aviso = _unico(agenda)
    assert aviso["texto"] == "despertar", aviso
    assert datetime.fromtimestamp(aviso["ts"]) == datetime(2026, 10, 26, 20, 0)

    # Con dos citas, cambia la nombrada y no la primera que encuentre.
    agenda = _agenda()
    agenda.procesar("apunta que mañana a las 9 tengo al dentista", AHORA)
    agenda.procesar("apunta que mañana a las 11 tengo al fisio", AHORA)
    agenda.procesar("cambia la cita del dentista a las 6 de la tarde", AHORA)
    dentista, fisio = sorted(agenda.avisos, key=lambda a: a["texto"])
    assert dentista["texto"] == "dentista", dentista
    assert fisio["texto"] == "fisio", fisio
    assert datetime.fromtimestamp(dentista["ts"]) == datetime(2026, 10, 27, 18, 0)
    assert datetime.fromtimestamp(fisio["ts"]) == datetime(2026, 10, 27, 11, 0)

    # Con dos alarmas y sin hora/texto que las distinga, pregunta en vez de
    # mover una al azar.
    agenda = _agenda()
    agenda.procesar("pon una alarma a las 7", AHORA)
    agenda.procesar("pon una alarma a las 9", AHORA)
    respuesta = agenda.procesar("cambia la alarma a las 8", AHORA)
    assert "Tienes 2 alarmas" in respuesta, respuesta
    horas = sorted(datetime.fromtimestamp(a["ts"]).hour for a in agenda.avisos)
    assert horas == [7, 9], horas

    # Sin hora: pregunta cuál, en vez de contestar con el vínculo.
    agenda = _agenda()
    agenda.procesar("apunta que mañana tengo al dentista", AHORA)
    respuesta = agenda.procesar("cambia la hora del dentista", AHORA)
    assert respuesta == "Dime a qué hora la cambio.", respuesta
    assert len(agenda.avisos) == 1

    # Si no existe, lo dice; no inventa ni crea una cita nueva.
    agenda = _agenda()
    respuesta = agenda.procesar("cambia la hora del fisio a las 6", AHORA)
    assert "No encuentro" in respuesta, respuesta
    assert agenda.avisos == []

    # No secuestra órdenes de otros módulos (cerebro, volumen).
    agenda = _agenda()
    for frase in ("cambia el cerebro al local", "baja el volumen",
                  "cambia la hora a las 6"):
        assert agenda.procesar(frase, AHORA) is None, frase
    print("[OK] reprogramar: cita y alarma sin duplicar ni secuestrar órdenes")


def test_aviso_suena_una_sola_vez():
    agenda = _agenda()
    agenda.procesar("avísame en 5 minutos la lavadora", AHORA)
    assert agenda.vencidos(AHORA) == []
    luego = datetime(2026, 10, 26, 16, 5)
    vencidos = agenda.vencidos(luego)
    assert len(vencidos) == 1
    frase = agenda.frase_aviso(vencidos[0])
    assert frase.startswith("¡Bip, bip! Han pasado cinco minutos."), frase
    assert "lavadora" in frase
    agenda.marcar_avisado(vencidos[0], luego)
    assert agenda.vencidos(luego) == []
    print("[OK] el aviso suena una sola vez y lo dice con la materia")


def test_no_suelta_avisos_caducados():
    """Un aviso vencido hace mucho no suena solo al arrancar (visto el 26/10)."""
    agenda = _agenda()
    agenda.procesar("avísame en 10 minutos la lavadora", AHORA)
    # 3 días después: no suena, pero queda marcado para no volver a mirarlo.
    tarde = datetime(2026, 10, 29, 16, 0)
    assert agenda.vencidos(tarde) == []
    assert agenda.avisos[0]["avisado"] is True
    assert agenda.vencidos(tarde) == []

    # Dos horas tarde SÍ avisa: es lo que pidió el dueño, aunque fuera apagado.
    agenda = _agenda()
    agenda.procesar("avísame en 10 minutos la lavadora", AHORA)
    assert len(agenda.vencidos(datetime(2026, 10, 26, 18, 0))) == 1
    print("[OK] un aviso vencido hace mucho se descarta; uno reciente se recupera")


def test_agenda_corrupta_no_tumba():
    """Un JSON truncado o con entradas basura no puede dejar a Parker sin voz."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "parker.agenda.json")
        for basura in ("{esto no es json", "[]", '{"avisos": "no es lista"}',
                       "null"):
            Path(ruta).write_text(basura, encoding="utf-8")
            assert AgendaParker(ruta_agenda=ruta).avisos == [], basura

        Path(ruta).write_text(json.dumps({"avisos": [
            "no soy un aviso",
            {"tipo": "cita", "ts": "no es numero", "texto": "x"},
            {"tipo": "otro", "ts": datetime(2026, 10, 27, 9).timestamp()},
            {"tipo": "cita", "ts": float("nan"), "texto": "nan"},
            {"tipo": "cita", "ts": float("inf"), "texto": "inf"},
            {"tipo": "cita", "ts": 1, "texto": "demasiado viejo"},
            {"tipo": "cita", "ts": 1e20, "texto": "demasiado nuevo"},
            {"tipo": "cita", "ts": datetime(2026, 10, 27, 9).timestamp(),
             "texto": "dentista"},
        ]}), encoding="utf-8")
        agenda = AgendaParker(ruta_agenda=ruta)
        assert [a["texto"] for a in agenda.avisos] == ["dentista"], agenda.avisos
    print("[OK] agenda corrupta: arranca vacía o solo con lo válido")


def test_persistencia_y_limpieza():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "parker.agenda.json")
        agenda = _agenda(ruta)
        agenda.procesar("avísame en 30 minutos la lavadora", AHORA)
        agenda.procesar("apunta que el viernes tengo al dentista", AHORA)
        assert Path(ruta).exists()

        otra = AgendaParker(ruta_agenda=ruta)
        assert len(otra.avisos) == 2
        assert sorted(a["tipo"] for a in otra.avisos) == [CITA, TEMPORIZADOR]

        # Los avisos de hace más de 30 días se olvidan (la tarjeta es para
        # los recuerdos de Chroma, no para esto).
        vieja = AgendaParker(ruta_agenda=ruta, dias_conservar=30)
        vieja.avisos.append({"id": "x", "tipo": ALARMA,
                             "ts": datetime(2026, 1, 1).timestamp(),
                             "texto": "vieja", "avisado": True})
        vieja._guardar()
        limpia = AgendaParker(ruta_agenda=ruta)
        assert all(a["texto"] != "vieja" for a in limpia.avisos), limpia.avisos

        # Una entrada corrupta no tumba las demás (protección de arranque).
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        datos["avisos"].append({"tipo": "cita", "ts": "no-es-numero"})
        datos["avisos"].append({"tipo": "raro", "ts": 123})
        Path(ruta).write_text(json.dumps(datos), encoding="utf-8")
        tercera = AgendaParker(ruta_agenda=ruta)
        assert len(tercera.avisos) == 2, tercera.avisos
    print("[OK] la agenda se guarda, se relee y olvida lo viejo")


if __name__ == "__main__":
    test_numeros_y_horas_en_palabras()
    test_temporizadores()
    test_alarmas_a_una_hora()
    test_citas_en_el_calendario()
    test_consultas()
    test_borrar()
    test_reprogramar_cita_y_alarma()
    test_agenda_corrupta_no_tumba()
    test_aviso_suena_una_sola_vez()
    test_no_suelta_avisos_caducados()
    test_persistencia_y_limpieza()
    print("\nAgenda: 10/10 en verde.")
