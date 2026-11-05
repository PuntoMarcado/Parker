"""
tests/test_apoyo.py
===================
Tests de la máquina de apoyo emocional y de la crisis de seguridad,
sin Ollama ni Chroma (sustitutos ligeros, como en test_rendimiento).

Ejecutar:  python -m pytest tests/test_apoyo.py -q
"""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker
from modulos.personalidad import PersonalidadParker


class MemoriaFalsa:
    def __init__(self):
        self.guardados = []

    def recuperar_recuerdos_formateados(self, *a, **k):
        return ""

    def guardar_recuerdo(self, *args, **kwargs):
        self.guardados.append(args)


def _cerebro(**extra):
    return CerebroParker(
        config_llama={"modelo": "test", "historial_mensajes": 2},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria={"top_k_recuerdos": 1, "umbral_relevancia": 0.5,
                        "max_caracteres_recuerdo": 80},
        **extra)


def _responder(cerebro, texto):
    """Turno completo con la nube y el local sustituidos: solo importan los
    mensajes y el estado (el texto devuelto es fijo y no aporta)."""
    cerebro._llamar_ollama_stream = lambda mensajes: iter(["[CARA:carino] Te escucho. "])
    list(cerebro.hablar_stream(texto))


def test_crisis_se_contesta_sin_llm():
    cerebro = _cerebro()
    LLM_INTENTADO = {"ok": False}

    def _llamar(mensajes):  # si esto se llama, el riesgo fue a parar al LLM
        LLM_INTENTADO["ok"] = True
        return ""

    cerebro._llamar = _llamar
    respuesta = cerebro.respuesta_directa("no quiero seguir viviendo así")
    assert respuesta is not None
    assert "024" in respuesta, "la derivación tiene que citar la línea real"
    assert not LLM_INTENTADO["ok"]
    assert cerebro._es_crisis("me quiero hacer daño")
    assert cerebro._es_crisis("quiero desaparecer para siempre")
    assert not cerebro._es_crisis("¿Crees que me haría daño leer este libro?")
    print("[OK] crisis: contención determinista con 024, sin LLM")


def test_bajon_activa_explorar_con_una_pregunta():
    cerebro = _cerebro()
    capturas = []

    def falso(mensajes):
        capturas.append([dict(m) for m in mensajes])
        return iter(["[CARA:triste] Vale. "])

    cerebro._llamar_ollama_stream = falso
    list(cerebro.hablar_stream("estoy fatal, ha sido un día horrible"))
    assert cerebro._apoyo["etapa"] == "explorar"
    contenido = capturas[-1][-1]["content"]
    assert "MODO APOYO" in contenido and "explorar" in contenido
    assert "UNA sola pregunta" in contenido
    # La instrucción de apoyo va en el mensaje volátil (delante de la conversación)
    assert contenido.index("MODO APOYO") < contenido.index("\nUsuario:") \
        if "\nUsuario:" in contenido else True
    print("[OK] bajón -> explorar (sin consejos, una pregunta)")


def test_dos_turnos_de_bajon_pasen_a_consolar():
    cerebro = _cerebro()
    cerebro._llamar_ollama_stream = lambda m: iter(["[CARA:neutral] Ok. "])
    list(cerebro.hablar_stream("me siento muy cansado"))
    list(cerebro.hablar_stream("sí, estoy agobiado y no puedo más"))
    assert cerebro._apoyo["etapa"] == "consolar"

    # Pide consejo explícito -> actuar
    list(cerebro.hablar_stream("¿qué hago? dime algo"))
    assert cerebro._apoyo["etapa"] == "actuar"
    print("[OK] explorar -> consolar -> actuar (pide consejo)")


def test_cambio_de_tema_cierra_el_apoyo():
    cerebro = _cerebro()
    cerebro._llamar_ollama_stream = lambda m: iter(["[CARA:neutral] Ok. "])
    list(cerebro.hablar_stream("estoy muy triste"))
    assert cerebro._apoyo["etapa"] == "explorar"
    list(cerebro.hablar_stream("¿qué tiempo hace mañana?"))
    assert cerebro._apoyo["etapa"] == "normal", "el tema cambió: fuera"
    print("[OK] cambio de tema sale del modo apoyo")


def test_agradecer_y_mejorar_cierra_el_apoyo():
    cerebro = _cerebro()
    cerebro._llamar_ollama_stream = lambda m: iter(["[CARA:carino] Ok. "])
    list(cerebro.hablar_stream("estoy muy triste hoy"))
    list(cerebro.hablar_stream("gracias, ya me siento mejor"))
    assert cerebro._apoyo["etapa"] == "normal"
    print("[OK] 'ya me siento mejor' cierra el modo apoyo")


def test_turnos_normales_no_meten_modo_apoyo():
    cerebro = _cerebro()
    capturas = []
    cerebro._llamar_ollama_stream = lambda m: (capturas.append(m), iter(["[CARA:feliz] Ok. "]))[1]
    list(cerebro.hablar_stream("¿Qué hora es en un rato?"))  # atajo sin LLM en placa; aquí sí pasa
    assert "MODO APOYO" not in capturas[0][-1]["content"]
    print("[OK] turno normal sin ninguna instrucción de apoyo")


def test_hechos_van_al_system_y_no_al_volatil():
    import tempfile
    from modulos.hechos import HechosParker

    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        hechos.actualizar_desde_texto("Mi dentista es la Dra. Puig.")
        cerebro = _cerebro(hechos=hechos)
        capturas = []
        cerebro._llamar_ollama_stream = lambda m: (capturas.append(m),
                                                   iter(["[CARA:feliz] Ok. "]))[1]
        list(cerebro.hablar_stream("¿Qué tal?"))
        system = capturas[0][0]["content"]
        assert "DATOS QUE LA PERSONA" in system and "Dentista" in system, system[:400]
        volatil = capturas[0][-1]["content"]
        assert "Dentista" not in volatil, "los hechos NO van en el volátil"
        hechos.cerrar()
    print("[OK] hechos exactos en el system (estable), fuera del volátil")


def test_system_estable_idéntico_entre_turnos_con_hechos():
    import tempfile
    from modulos.hechos import HechosParker

    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        cerebro = _cerebro(hechos=hechos)
        capturas = []
        cerebro._llamar_ollama_stream = lambda m: (capturas.append(m),
                                                   iter(["[CARA:feliz] Ok. "]))[1]
        list(cerebro.hablar_stream("primera"))
        list(cerebro.hablar_stream("segunda"))
        primero, segundo = capturas
        assert segundo[:len(primero)] == primero, (
            "con hechos en el system, el prefijo sigue siendo cacheable")
        hechos.cerrar()
    print("[OK] prefijo cacheable con hechos activos")


if __name__ == "__main__":
    test_crisis_se_contesta_sin_llm()
    test_bajon_activa_explorar_con_una_pregunta()
    test_dos_turnos_de_bajon_pasen_a_consolar()
    test_cambio_de_tema_cierra_el_apoyo()
    test_agradecer_y_mejorar_cierra_el_apoyo()
    test_turnos_normales_no_meten_modo_apoyo()
    test_hechos_van_al_system_y_no_al_volatil()
    test_system_estable_idéntico_entre_turnos_con_hechos()
    print("[OK] apoyo emocional: 8/8")
