"""Órdenes directas: volumen, silencio y silbido (sin LLM)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.acciones import (AccionesParker, SONIDO_SILBIDO,
                              interpretar_orden_cerebro,
                              interpretar_orden_demo_cara,
                              interpretar_orden_modo_completo,
                              interpretar_orden_oido,
                              interpretar_orden_voz)


class VozFalsa:
    """Lo mínimo de VozParker que usan las acciones."""

    def __init__(self, volumen=0.55):
        self.volumen = volumen
        self.silenciado = False


def test_volumen_sube_y_baja():
    voz = VozFalsa()
    acciones = AccionesParker(voz)

    assert acciones.procesar("baja el volumen") == ("Bajado al 40 %.", None)
    assert round(voz.volumen, 2) == 0.40
    assert acciones.procesar("sube el volumen") == ("Subido al 55 %.", None)
    assert round(voz.volumen, 2) == 0.55
    assert acciones.procesar("pon el volumen al 70 %") == ("Volumen al 70 %.", None)
    assert round(voz.volumen, 2) == 0.70
    assert acciones.procesar("un poco más bajo") == ("Más bajo: 55 %.", None)
    assert acciones.procesar("más alto") == ("Más alto: 70 %.", None)
    # A secas también, pero solo si la frase no habla de otra cosa.
    assert acciones.procesar("baja") == ("Bajado al 55 %.", None)
    assert acciones.procesar("baja un poco") == ("Bajado al 40 %.", None)
    assert acciones.procesar("sube aún más") == ("Subido al 55 %.", None)
    assert acciones.procesar("bájalo") == ("Bajado al 40 %.", None)
    assert acciones.procesar("bájame el volumen") == ("Bajado al 25 %.", None)
    assert acciones.procesar("súbeme el bolumen") == ("Subido al 40 %.", None)
    print("[OK] volumen: subir, bajar, valor exacto y límites")


def test_limites_y_persistencia():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "parker.volumen.json")
        voz = VozFalsa()
        acciones = AccionesParker(voz, ruta_volumen=ruta)
        acciones._fijar(1.5)          # por encima del máximo
        assert round(voz.volumen, 2) == 1.00
        acciones._fijar(0.0)          # por debajo del mínimo
        assert round(voz.volumen, 2) == 0.01
        acciones._fijar(0.30)

        otra_voz = VozFalsa()
        otra = AccionesParker(otra_voz, ruta_volumen=ruta)
        assert round(otra_voz.volumen, 2) == 0.30, otra_voz.volumen
        assert otra.porcentaje() == 30
    print("[OK] volumen acotado y recordado entre reinicios")


def test_volumen_exacto_sin_palabra_volumen():
    """«Bájalo al 33 %» tiene que fijar 33, no dar un paso de 15."""
    voz = VozFalsa(0.65)
    acciones = AccionesParker(voz)

    casos = [
        ("Bájalo al 33%", "Bajado al 33 %.", 0.33),
        ("Baja al 1% el volumen", "Bajado al 1 %.", 0.01),
        ("Bájalo al 20%", "Bajado al 20 %.", 0.20),
        ("Tú bajas al 10%", "Bajado al 10 %.", 0.10),
        ("Súbelo al cien por cien", "Subido al 100 %.", 1.00),
        ("Pon el volumen al 80%", "Volumen al 80 %.", 0.80),
        ("Al cincuenta por ciento", "Volumen al 50 %.", 0.50),
    ]
    for frase, esperado, nivel in casos:
        resultado = acciones.procesar(frase)
        assert resultado == (esperado, None), (frase, resultado)
        assert round(voz.volumen, 2) == nivel, (frase, voz.volumen)
    print("[OK] nivel exacto: 33 %, 1 %, 100 % y «cien por cien»")


def test_consulta_de_volumen_sin_inventar():
    voz = VozFalsa(0.33)
    acciones = AccionesParker(voz)
    for frase in ("¿a qué nivel está tu volumen?",
                  "¿a qué porcentaje de volumen está tu audio?",
                  "¿qué volumen tienes?"):
        assert acciones.procesar(frase) == ("Estoy al 33 %.", None), frase
    assert acciones.procesar("¿a qué volumen está la tele?") is None
    print("[OK] el nivel se consulta con el dato real, no con el LLM")


def test_silencio_y_vuelta():
    voz = VozFalsa()
    acciones = AccionesParker(voz)
    # «silencio» dentro de una frase es un tema, no una orden.
    assert acciones.procesar("me gusta el silencio de la noche") is None
    assert voz.silenciado is False
    assert acciones.procesar("silencio por favor") == ("Silencio.", None)
    assert voz.silenciado is True
    assert acciones.procesar("quita el silencio")[0].startswith("Ya te oigo")
    assert voz.silenciado is False
    assert round(voz.volumen, 2) == 0.55
    print("[OK] silencio y vuelta al volumen anterior")


def test_silbido_de_verdad():
    voz = VozFalsa()
    acciones = AccionesParker(voz)
    for frase in ("prueba a silbar", "¿sabes silbar?", "Silba, simplemente silba.",
                  "no puedes silbar", "haz un silbido"):
        resultado = acciones.procesar(frase)
        assert resultado is not None, frase
        assert resultado[1] == "silbido", (frase, resultado)
    assert SONIDO_SILBIDO not in ("", None)
    # Hablar de silbar sin pedirlo no dispara el efecto.
    assert acciones.procesar("hoy he silbado en el trabajo mientras limpiaba") is None
    print("[OK] pedir un silbido devuelve la orden de sonido real")


def test_no_confunde_charla_con_ordenes():
    voz = VozFalsa()
    acciones = AccionesParker(voz)
    for frase in ("me gusta el volumen de tu voz",
                  "baja la persiana que hay sol",
                  "¿qué hora es?",
                  "hoy estoy más bajo de ánimo",
                  "cuéntame algo",
                  "no me gusta que silbes",
                  "deja de silbar",
                  "Silva es mi apellido"):
        assert acciones.procesar(frase) is None, frase
    assert round(voz.volumen, 2) == 0.55, "una frase normal no debe tocar el volumen"
    print("[OK] la charla normal no mueve el volumen")


def test_orden_cerebro_por_voz():
    """Cambiar de cerebro con la voz: se reconoce aquí, sin LLM (0 ms).

    Pedido el 27/10/2026: pasar de la nube al local y al revés hablando, y
    poder preguntar con cuál está pensando.
    """
    pedidos = {
        # A local
        "Parker, cambia al cerebro local": "local",
        "cerebro local": "local",
        "usa el cerebro de casa": "local",
        "cambia el cerebro a local": "local",
        "quiero el cerebro de la placa": "local",
        # A la nube
        "vuelve al cerebro de internet": "nube",
        "cambia el cerebro a la nube": "nube",
        "pasate al cerebro de groq": "nube",
        "usa el cerebro de internet": "nube",
        "usa el cerebro de internet otra vez": "nube",
        # Automático y consulta
        "ponte en modo automatico": "auto",
        "decide tu": "auto",
        "¿qué cerebro usas?": "estado",
        "¿con qué cerebro estás ahora?": "estado",
        "Parker, ¿estás con el local?": "estado",
        "¿donde piensas?": "estado",
        # Lo que de verdad llega del oído (placa, 27/10): el STT se come los
        # verbos («ponte» -> «Jonte», «vuelve a la nube» -> «Voy a dar nube»),
        # así que manda el destino y la frase corta.
        "Jonte el local.": "local",
        "Voy a dar nube.": "nube",
        "Ponte en lo caldo.": "local",   # el oído, 27/10: «Ponte en local"
        "Voy a la nube.": "nube",
        "Vuelve a la nube": "nube",
        "A la nube": "nube",
        "Al local.": "local",
        "Cerebro de casa": "local",
        "Pon el cerebro en local, por favor": "local",
        # Lo que llegó de verdad el 31/10: «Parker, cambio el cerebro en local».
        # No cambiaba nada y el modelo se inventaba que sí.
        "Parker, cambio el cerebro en local": "local",
        "cambio el cerebro local": "local",
        "cambiar el cerebro a local": "local",
        "cambiame el cerebro a local": "local",
        "cambio el cerebro a la nube": "nube",
    }
    for frase, esperado in pedidos.items():
        assert interpretar_orden_cerebro(frase) == esperado, (frase, esperado)

    # Charla normal: ni se toca el cerebro ni se cambia nada.
    for frase in ("el local de la esquina está cerrado",
                  "me he quedado sin internet en casa",
                  "tengo el auto en el taller",
                  "el volumen de la tele está muy alto",
                  "cuéntame algo del mar",
                  "vamos a la nube mañana",
                  "prefiero el local de la esquina para cenar",
                  "me voy a la nube de tags a mirar",
                  "¿qué es la nube?",
                  "¿dónde está el local de ensayo?",
                  "esta tarde voy a la nube con mi hermana"):
        assert interpretar_orden_cerebro(frase) is None, frase
    print("[OK] el cerebro se cambia por voz y la charla normal no lo toca")


def test_modo_completo_voz_y_oido():
    """El 01/11/2026: «cambia la voz al local» no cambiaba nada.

    Ahora hay tres órdenes separadas. La clave es que no se pisen: la voz no
    debe cambiar el cerebro, y «modo local completo» sí debe cambiar los tres.
    """
    completos = {
        "modo local": "local",
        "ponte en local": "local",
        "modo local completo": "local",
        "ponte en local completo": "local",
        "cambia todo a local": "local",
        "todo local": "local",
        "desconecta internet": "local",
        "modo sin internet": "local",
        "modo normal": "auto",
        "modo automatico completo": "auto",
        "modo online": "nube",
        "modo nube": "nube",
        "vuelve todo a la nube": "nube",
        "modo nube completo": "nube",
    }
    for frase, esperado in completos.items():
        assert interpretar_orden_modo_completo(frase) == esperado, (frase, esperado)

    # Solo voz: no toca el cerebro ni el oído.
    voces = {
        "cambia la voz al local": "piper",
        "Parker cambia la voz a la de local": "piper",
        "cambia la voz a la del local": "piper",
        "cambia tu voz al local": "piper",
        "voz local": "piper",
        "voz de internet": "edge",
        "cambia la voz a la nube": "edge",
        "usa la voz de Ximena": "edge",
    }
    for frase, esperado in voces.items():
        assert interpretar_orden_voz(frase) == esperado, (frase, esperado)

    # Solo oído.
    oidos = {
        "cambia el oido al local": "local",
        "transcribe en local": "local",
        "usa el oido de la nube": "nube",
        "transcribe con whisper en internet": "nube",
    }
    for frase, esperado in oidos.items():
        assert interpretar_orden_oido(frase) == esperado, (frase, esperado)
    # Un ruido transcrito como «oído local» no debe cambiar el STT; con el
    # nombre («Parker, oído local») o con un verbo sí.
    assert interpretar_orden_oido("oído local") is None
    assert interpretar_orden_oido("Parker, oído local") == "local"

    # «modo local» / «ponte en local» cambian los tres; el cambio parcial se
    # pide diciendo «cerebro local» o «cambia el cerebro a local».
    assert interpretar_orden_modo_completo("modo local") == "local"
    assert interpretar_orden_cerebro("modo local") is None
    assert interpretar_orden_modo_completo("ponte en local") == "local"
    assert interpretar_orden_cerebro("ponte en local") is None
    assert interpretar_orden_cerebro("cerebro local") == "local"
    assert interpretar_orden_cerebro("cambia el cerebro a local") == "local"
    # Y una orden de modo completo no se aplica a medias como cerebro.
    assert interpretar_orden_cerebro("modo local completo") is None

    # Charla normal: nada de esto se dispara.
    for frase in ("me gusta la voz de la radio",
                  "el oido me duele un poco",
                  "me he quedado sin internet en casa",
                  "vamos a la nube mañana",
                  "¿qué voz usas?",
                  "¿dónde está el local de ensayo?"):
        assert interpretar_orden_modo_completo(frase) is None, frase
        assert interpretar_orden_voz(frase) is None, frase
        assert interpretar_orden_oido(frase) is None, frase
    print("[OK] modo completo, voz y oído se cambian sin pisarse")


def test_orden_demo_cara():
    """«Modo demo» muestra las animaciones y «para la demo» lo corta."""
    for frase in ("Parker, modo demo",
                  "muéstrame todas tus animaciones",
                  "enséñame todos tus gestos",
                  "haz una demostración de la cara",
                  "¿puedes mostrar todas tus expresiones?",
                  "quiero ver todas tus animaciones",
                  "Parker, pon el modo demostración"):
        assert interpretar_orden_demo_cara(frase) == "iniciar", frase
    for frase in ("para la demo",
                  "Parker, detén la demostración",
                  "sal del modo demo",
                  "basta de demo"):
        assert interpretar_orden_demo_cara(frase) == "parar", frase
    for frase in ("me gusta la cara de esta moneda",
                  "¿qué animaciones tienes?",
                  "la demo de la tele"):
        assert interpretar_orden_demo_cara(frase) is None, frase
    print("[OK] modo demo: se inicia y se corta solo con una orden explícita")


if __name__ == "__main__":
    test_volumen_sube_y_baja()
    test_volumen_exacto_sin_palabra_volumen()
    test_limites_y_persistencia()
    test_consulta_de_volumen_sin_inventar()
    test_silencio_y_vuelta()
    test_silbido_de_verdad()
    test_no_confunde_charla_con_ordenes()
    test_orden_cerebro_por_voz()
    test_modo_completo_voz_y_oido()
    test_orden_demo_cara()
    print("\nAcciones: 10/10 en verde.")
