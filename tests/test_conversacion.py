"""Pruebas offline de conversación, continuidad y memoria útil."""
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker
from modulos.personalidad import PersonalidadParker


class MemoriaFalsa:
    def __init__(self):
        self.guardados = []

    def recuperar_recuerdos_formateados(self, *args, **kwargs):
        return ""

    def guardar_recuerdo(self, texto, **kwargs):
        self.guardados.append(texto)


def test_no_guardar_saludos_ni_preguntas():
    mensajes = [
        "Hola Parker",
        "¿Qué tal?",
        "Estoy bien, gracias",
        "¿Cómo me llamo yo Parker?",
        "Parker",
        "Me han dado una buena noticia en el trabajo.",
        "Me han subido el sueldo; quiero ahorrar para volver a Alicante con mi hermana.",
    ]
    assert [CerebroParker._merece_recuerdo(m) for m in mensajes] == [
        False, False, False, False, False, True, True
    ]
    print("[OK] saludos, preguntas y audio corto no contaminan la memoria")


def test_dos_turnos_sin_saludos_de_plantilla():
    memoria = MemoriaFalsa()
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(
        config_llama={"modelo": "test", "historial_mensajes": 4,
                      "temperature": 0.45, "repeat_penalty": 1.15},
        memoria=memoria,
        personalidad=perfil,
        config_memoria={"solo_recuerdos_usuario": True, "max_char_turno_reciente": 100},
    )
    peticiones = []
    respuestas = iter([
        "[CARA:neutral] ¡Qué buena noticia! ¿Qué te gustaría hacer con ese dinero?",
        "[CARA:neutral] Me dijiste que querías ahorrar para volver a Alicante con tu hermana.",
    ])

    def falso(mensajes):
        peticiones.append([dict(m) for m in mensajes])
        texto = next(respuestas)
        assert mensajes[0]["role"] == "system"
        return iter([texto])

    cerebro._llamar_ollama_stream = falso
    list(cerebro.hablar_stream("Me han subido el sueldo; quiero ahorrar para volver a Alicante con mi hermana."))
    list(cerebro.hablar_stream("¿Qué te dije que quería hacer con el dinero?"))

    segunda = peticiones[1]
    prompt_user = "\n".join(m["content"] for m in segunda if m["role"] == "user")
    assert "Conversación en curso" in prompt_user
    assert "sigue el mismo tema" in prompt_user
    assert "Me han subido el sueldo" in prompt_user
    assert "Estoy encantado de verte" not in prompt_user
    assert peticiones[1][-1]["role"] == "user"
    prompt_previo = "\n".join(m["content"] for m in peticiones[1][:-1])
    assert "Alicante" in prompt_previo
    # Dos turnos seguidos son UNA conversación (el contador sube con hueco de
    # 45 min, no por frase: el 30/10 llegó a decir «231 charlas»).
    assert perfil.estado["charlas"] == 1
    assert len(memoria.guardados) == 1, memoria.guardados
    assert memoria.guardados[0] == "Usuario: Me han subido el sueldo; quiero ahorrar para volver a Alicante con mi hermana."
    assert "Parker:" not in memoria.guardados[0]

    opciones = cerebro._payload(peticiones[0], stream=True)["options"]
    assert opciones["temperature"] == 0.45
    assert opciones["repeat_penalty"] == 1.15
    assert cerebro.max_historial == 4
    print("[OK] continuidad temática, memoria factual y penalización anti-repetición")


def test_fecha_se_resuelve_sin_modelo():
    memoria = MemoriaFalsa()
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=memoria, personalidad=perfil)

    assert cerebro._es_pregunta_fecha("¿Qué día es hoy?")
    assert cerebro._es_pregunta_fecha("¿Qué fecha tenemos?")
    assert cerebro._es_pregunta_fecha("que diría soy")  # transcripción real de Whisper
    assert not cerebro._es_pregunta_fecha("¿Qué tal te va?")
    assert cerebro._respuesta_fecha(datetime(2026, 10, 17)) == \
        "Hoy es sábado, 17 de octubre de 2026."
    respuesta = cerebro.respuesta_directa("que diría soy")
    assert respuesta is not None and respuesta.startswith("Hoy es "), respuesta

    # Fechas RELATIVAS: antes todas devolvían la fecha de hoy (oído en la
    # placa 25/10: «¿qué día es mañana?» -> «Hoy es domingo, 25 de octubre»).
    sabado = datetime(2026, 10, 17)
    assert cerebro._responder_fecha("¿Qué día es mañana?", sabado) == \
        "Mañana será domingo, 18 de octubre de 2026."
    # La nube transcribió «día» como «dirá» (oído 25/10): mismo dato.
    assert cerebro._responder_fecha("¿Qué dirá es mañana?", sabado) == \
        "Mañana será domingo, 18 de octubre de 2026."
    # Pero «¿qué dirá Parker mañana?» no es una pregunta de fecha.
    assert not cerebro._es_pregunta_fecha("¿Qué dirá Parker mañana?")
    assert cerebro._responder_fecha("¿Qué día fue ayer?", sabado) == \
        "Ayer fue viernes, 16 de octubre de 2026."
    assert cerebro._responder_fecha("¿Qué día será en 7 días?", sabado) == \
        "En 7 días será sábado, 24 de octubre de 2026."
    assert cerebro._responder_fecha("¿Qué día será el próximo lunes?", sabado) == \
        "En 2 días será lunes, 19 de octubre de 2026."
    # Si hoy es domingo, el próximo lunes es mañana: singular, no «1 días».
    assert cerebro._responder_fecha("¿Qué día será el próximo lunes?",
                                    datetime(2026, 10, 25)) == \
        "En 1 día será lunes, 26 de octubre de 2026."
    # «en siete días» con letras: es como lo deja Whisper a veces.
    assert cerebro._desplazamiento_dias("qué día será en siete días", sabado) == 7

    # La hora también es un dato seguro; «a qué hora es la cita» no lo es.
    assert cerebro._es_pregunta_hora("¿Qué hora es?")
    assert not cerebro._es_pregunta_hora("¿A qué hora es la cita?")
    assert cerebro._respuesta_hora(datetime(2026, 10, 17, 19, 5)) == \
        "Son las 7 y 5 de la tarde."
    assert cerebro.respuesta_directa("¿Qué hora es?").startswith(("Son las", "Es la"))
    print("[OK] fecha relativa y hora se resuelven localmente, sin inventar")


def test_inicio_no_saluda_efusivamente():
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=MemoriaFalsa(), personalidad=perfil)
    assert "Inicio de conversación" in cerebro._instruccion_conversacion()
    assert "sin saludo efusivo" in cerebro._instruccion_conversacion()
    cerebro.historial = [{"role": "user", "content": "hola"},
                         {"role": "assistant", "content": "¡Hola!"}]
    instruccion = cerebro._instruccion_conversacion()
    assert "Conversación en curso" in instruccion
    assert "No saludes" in instruccion
    print("[OK] distingue inicio de conversación y charla en curso")


def test_filtra_frases_repetidas_de_la_respuesta():
    perfil = PersonalidadParker({"guardar_estado": False})
    casos = [
        "Estoy encantado de verte. ¡Qué bueno lo del trabajo!",
        "Me alegra verte de nuevo. Alicante suena genial.",
        "Hola, Alan. ¿Qué tal estás? Me dijiste que querías ahorrar.",
        "¡Hola, Parker! Me acuerdo que has empezado el curso de dibujo.",
    ]
    for frase in casos:
        limpio = perfil.limpiar_frases_plantilla(frase, conversacion_en_curso=True)
        assert "encantado de verte" not in limpio.lower(), limpio
        assert "me alegra verte" not in limpio.lower(), limpio
        assert not limpio.lower().startswith("hola"), limpio
        assert "¿qué tal" not in limpio.lower(), limpio
        assert not limpio.lower().startswith("¡hola"), limpio
    assert "Qué bueno lo del trabajo" in perfil.limpiar_frases_plantilla(
        casos[0], conversacion_en_curso=True)
    assert "Alicante suena genial" in perfil.limpiar_frases_plantilla(
        casos[1], conversacion_en_curso=True)
    # El hueco se come hasta el final de la oración: sin eso, la frase
    # «…en la pantalla. ¿Cómo estás hoy, Alan? Espero que bien.» quedaba
    # «pantalla.hoy, Alan?» (visto en la placa 24/10).
    limpio = perfil.limpiar_frases_plantilla(
        "Y yo soy Parker, tu amiguito en la pantalla. "
        "¿Cómo estás hoy, Alan? Espero que bien.",
        conversacion_en_curso=True)
    assert limpio == "Y yo soy Parker, tu amiguito en la pantalla. Espero que bien.", limpio

    salida_mala = "Mmm...... Sí, claro que sí. Estoy aquí para ayudarte siempre que necesites algo. ¿Cómo puedo asistirte hoy?"
    assert perfil.limpiar_frases_plantilla(salida_mala, conversacion_en_curso=True) == "", \
        perfil.limpiar_frases_plantilla(salida_mala, conversacion_en_curso=True)
    contenido = perfil.limpiar_frases_plantilla(
        "Mmm, hoy es sábado; te preguntaba por la fecha.", conversacion_en_curso=True)
    assert contenido == "hoy es sábado; te preguntaba por la fecha.", contenido
    respuesta_sin_relleno = perfil.limpiar_frases_plantilla(
        "Mmm. Hoy es sábado, 17 de octubre.", conversacion_en_curso=True)
    assert respuesta_sin_relleno == "Hoy es sábado, 17 de octubre.", respuesta_sin_relleno
    print("[OK] filtra mmm y fórmulas de asistente, conserva la respuesta con contenido")


def test_frase_meta_fuera_del_historial():
    memoria = MemoriaFalsa()
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=memoria,
                            personalidad=perfil)

    def falso(mensajes):
        return iter(["[CARA:neutral] Déjame analizar la pregunta. ¡Claro que sí!"])

    cerebro._llamar_ollama_stream = falso
    list(cerebro.hablar_stream("¿Me ayudas con algo?"))
    assert cerebro.historial[-1]["content"] == "¡Claro que sí!", cerebro.historial[-1]
    print("[OK] la frase meta no se guarda en el historial")


def test_cierre_a_mitad_no_arrastra_media_palabra():
    memoria = MemoriaFalsa()
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=memoria,
                            personalidad=perfil)
    cerebro._llamar_ollama_stream = lambda mensajes: iter(
        ["[CARA:neutral] Primera frase completa. Y esto queda a media pa"])
    flujo = cerebro.hablar_stream("Cuenta algo")
    next(flujo)
    flujo.close()  # así corta Parker al llegar a su límite de frases
    assert cerebro.historial[-1]["content"] == "Primera frase completa.", \
        cerebro.historial[-1]
    print("[OK] cerrar el stream a mitad no arrastra el fragmento al historial")


def test_etiqueta_sin_corchetes_no_se_dice_en_voz():
    """El 3b escribe a veces «CARA:pensando» sin corchetes (medido en la
    placa 24/10): no debe colarse en el texto que se lee en voz alta."""
    memoria = MemoriaFalsa()
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=memoria,
                            personalidad=perfil)
    limpio, _ = cerebro._extraer_etiquetas(
        "CARA:pensando\nNo tengo recuerdos de tu infancia.")
    assert limpio == "No tengo recuerdos de tu infancia.", limpio
    limpio2, _ = cerebro._extraer_etiquetas(
        "**CARA:sorprendido**\n¡Me alegro de verte!")
    assert "CARA" not in limpio2 and "¡Me alegro de verte!" in limpio2, limpio2
    limpio3, _ = cerebro._extraer_etiquetas(
        "Estoy contento. cara:bien ¿Y tú qué tal?")
    assert "cara:bien" not in limpio3.lower() and "Estoy contento." in limpio3, limpio3
    assert cerebro._extraer_etiquetas("Soy Eres Parker, tu amigo.")[0] == \
        "Soy Parker, tu amigo."
    assert cerebro._extraer_etiquetas("[Tutéame como siempre] Hola, Alan.")[0] == \
        "Hola, Alan."
    print("[OK] etiqueta sin corchetes no se cuela y no dice «Soy Eres Parker»")


if __name__ == "__main__":
    test_no_guardar_saludos_ni_preguntas()
    test_dos_turnos_sin_saludos_de_plantilla()
    test_fecha_se_resuelve_sin_modelo()
    test_inicio_no_saluda_efusivamente()
    test_filtra_frases_repetidas_de_la_respuesta()
    test_frase_meta_fuera_del_historial()
    test_cierre_a_mitad_no_arrastra_media_palabra()
    test_etiqueta_sin_corchetes_no_se_dice_en_voz()
    print("\nTodos los tests de conversación han pasado.")
