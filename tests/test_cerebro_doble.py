"""
tests/test_cerebro_doble.py
===========================
Pruebas del cerebro doble (v6): la NUBE piensa y el LOCAL respalda.

Lo que se comprueba, que es justo lo que no se puede dejar al azar:
  1. Con la nube viva, la respuesta viene de la nube (el local ni se toca).
  2. Si la nube falla ANTES de decir nada, el mismo turno lo contesta el local.
  3. Tras un fallo no se reintenta en cada turno (circuit breaker): el
     siguiente turno va directo al local, sin esperar 3 s de timeout.
  4. Si la nube falla A MITAD de frase, se acaba ahí: no se repite la respuesta.
  5. Sin internet configurado (nube apagada) todo funciona como antes.

No hace red: se sustituyen `_llamar_online_stream` y `_llamar_ollama_stream`.
Ejecutar:
    QT_QPA_PLATFORM=offscreen python tests/test_cerebro_doble.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.cerebro import (  # noqa: E402
    CerebroParker,
    _texto_de_linea,
    limpiar_marcado,
    quitar_fugas_prompt,
)
from modulos.personalidad import PersonalidadParker  # noqa: E402


class MemoriaFalsa:
    def recuperar_recuerdos_formateados(self, *a, **k):
        return ""

    def guardar_recuerdo(self, *a, **k):
        pass


def _cerebro(online: bool = True, **extra) -> CerebroParker:
    cfg = {"activo": online, "modelo": "openai/gpt-oss-20b", "reintento_seg": 60}
    cfg.update(extra)
    cerebro = CerebroParker(
        config_llama={"modelo": "qwen2.5:3b", "historial_mensajes": 4},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_online=cfg,
    )
    cerebro.online_api_key = "clave-de-prueba"   # sin red: se sustituye el cliente
    return cerebro


def test_nube_primaria():
    cerebro = _cerebro()
    llamadas = {"nube": 0, "local": 0}

    def online(_mensajes):
        llamadas["nube"] += 1
        yield "[CARA:feliz] Hola Alan, "
        yield "qué gusto oírte."

    def local(_mensajes):
        llamadas["local"] += 1
        yield "respuesta local"

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    texto, etiquetas = cerebro.hablar("Hola Parker")
    assert "qué gusto oírte" in texto, texto
    assert llamadas == {"nube": 1, "local": 0}, llamadas
    assert cerebro.estado_cerebro()["motor"] == "nube"
    assert cerebro.historial[-1]["role"] == "assistant"
    print("[OK] la nube contesta y el local no se toca")


def test_respaldo_local_cuando_falla():
    cerebro = _cerebro()
    llamadas = {"nube": 0, "local": 0}

    def online(_mensajes):
        llamadas["nube"] += 1
        raise ConnectionError("sin internet")
        yield  # pragma: no cover  (generador válido)

    def local(_mensajes):
        llamadas["local"] += 1
        yield "[CARA:neutral] Te contesto desde casa."

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    texto, _ = cerebro.hablar("¿Sigues ahí?")
    assert "desde casa" in texto, texto
    assert llamadas == {"nube": 1, "local": 1}, llamadas
    assert "sin internet" in cerebro.online_ultimo_error, cerebro.online_ultimo_error

    # Segundo turno: ya no se intenta la nube (no se paga otro timeout).
    texto2, _ = cerebro.hablar("Otra cosa")
    assert "desde casa" in texto2, texto2
    assert llamadas == {"nube": 1, "local": 2}, llamadas
    assert cerebro.estado_cerebro()["motor"].startswith("local")
    print("[OK] si la nube falla, contesta el local y no se reintenta cada turno")


def test_fallo_a_mitad_no_repite():
    cerebro = _cerebro()

    def online(_mensajes):
        yield "Te estaba contando que"
        raise TimeoutError("se cortó")

    def local(_mensajes):
        yield "esto no debería oírse"
        yield " nunca"

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    texto, _ = cerebro.hablar("cuéntame")
    assert "Te estaba contando" in texto, texto
    assert "nunca" not in texto, texto
    print("[OK] un corte a mitad de frase acaba la frase, no la repite")


def test_sin_nube_configurada():
    cerebro = _cerebro(online=False)
    llamadas = {"nube": 0, "local": 0}

    def online(_mensajes):   # no debería llamarse nunca
        llamadas["nube"] += 1
        yield "nube"
        raise AssertionError("no debía llamarse la nube")

    def local(_mensajes):
        llamadas["local"] += 1
        yield "[CARA:neutral] Todo local, como antes."

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    texto, _ = cerebro.hablar("hola")
    assert "Todo local" in texto, texto
    assert llamadas == {"nube": 0, "local": 1}, llamadas
    assert cerebro.estado_cerebro()["motor"] == "local"
    print("[OK] con la nube apagada todo sigue funcionando en local")


def test_precalentar_no_gasta_cpu_con_nube():
    """Con la nube de primaria no se precalienta el prefijo de Ollama."""
    cerebro = _cerebro()
    cerebro.precalentar_turno_activo = True
    llamado = {"post": 0}

    import modulos.cerebro as modulo
    original = modulo.requests.post

    def falso_post(*a, **k):
        llamado["post"] += 1
        raise AssertionError("no debía precalentar")

    modulo.requests.post = falso_post
    try:
        cerebro.precalentar_turno()
    finally:
        modulo.requests.post = original
    assert llamado["post"] == 0
    print("[OK] con la nube activa el precalentado no gasta CPU")


def test_modo_local_no_intenta_la_nube():
    """En modo local la nube no se toca ni una vez (ni paga el timeout).

    Pedido el 27/10: «poder cambiar del cerebro de Groq al local y al revés por
    voz». Sin esto, pedir el local seguiría costando 3 s por turno cuando no
    hay internet.
    """
    cerebro = _cerebro()
    llamadas = {"nube": 0, "local": 0}

    def online(_mensajes):
        llamadas["nube"] += 1
        yield "esto no debería oírse"

    def local(_mensajes):
        llamadas["local"] += 1
        yield f"[CARA:neutral] Pienso en casa ({llamadas['local']})."

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    frase = cerebro.cambiar_modo("local")
    assert "local" in frase.lower(), frase
    assert llamadas == {"nube": 0, "local": 0}, llamadas  # cambiar no llama a nadie

    for _ in range(3):
        texto, _ = cerebro.hablar("hola")
        assert "casa" in texto, texto
    assert llamadas == {"nube": 0, "local": 3}, llamadas
    estado = cerebro.estado_cerebro()
    assert estado["motor"] == "local" and estado["modo"] == "local", estado
    assert "casa" in cerebro.frase_modo().lower(), cerebro.frase_modo()
    print("[OK] en modo local la nube ni se intenta")


def test_cambio_de_modo_por_voz_y_persistencia():
    """El modo pedido por voz se guarda: un reinicio no lo revierte a escondidas."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "parker.cerebro.json"
        cerebro = _cerebro(ruta_estado=str(ruta))
        assert cerebro.modo_actual() == "auto", cerebro.modo_actual()
        cerebro.cambiar_modo("local")
        assert ruta.exists(), "el modo elegido por voz debe guardarse"
        assert _cerebro(ruta_estado=str(ruta)).modo_actual() == "local"
        frase = cerebro.cambiar_modo("nube")
        assert "internet" in frase.lower(), frase
        assert _cerebro(ruta_estado=str(ruta)).modo_actual() == "nube"
        # Un modo inventado no cambia nada (y lo dice).
        antes = cerebro.modo_actual()
        assert "no conozco" in cerebro.cambiar_modo("telepatia").lower()
        assert cerebro.modo_actual() == antes
    # Sin nube configurada no se puede pedir la nube.
    sin = _cerebro(online=False)
    frase = sin.cambiar_modo("nube")
    assert "apagada" in frase.lower(), frase
    assert sin.modo_actual() == "auto", sin.modo_actual()
    print("[OK] el modo se cambia por voz, se guarda y no se puede pedir lo imposible")


def test_avisos_de_caida_y_vuelta():
    """Avisa UNA vez cuando se cae la nube, y avisa cuando vuelve."""
    cerebro = _cerebro()
    estado = {"caido": True}

    def online(_mensajes):
        if estado["caido"]:
            raise ConnectionError("Network is unreachable")
        yield "[CARA:feliz] Ya estoy de vuelta."

    def local(_mensajes):
        yield "[CARA:neutral] Te contesto desde casa."

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local

    cerebro.hablar("¿sigues ahí?")
    avisos = cerebro.tomar_avisos()
    assert len(avisos) == 1 and "internet" in avisos[0].lower(), avisos
    # El siguiente turno va directo al local: no repite la queja.
    cerebro.hablar("otra cosa")
    assert cerebro.tomar_avisos() == [], "el aviso de caída se repite"
    # Cuando la nube vuelve, lo dice.
    estado["caido"] = False
    cerebro._online_caido_hasta = 0.0        # se cumple el plazo de reintento
    texto, _ = cerebro.hablar("¿ya estás?")
    assert "vuelta" in texto, texto
    avisos = cerebro.tomar_avisos()
    assert len(avisos) == 1 and "internet" in avisos[0].lower(), avisos
    assert "vuelvo" in avisos[0].lower(), avisos
    # Y no se queda repitiendo que ha vuelto.
    cerebro.hablar("más cosas")
    assert cerebro.tomar_avisos() == [], cerebro.tomar_avisos()
    print("[OK] avisa de la caída (una vez) y de la vuelta")


def test_aviso_distinto_si_el_proveedor_frena():
    """Un 429 no es «sin internet»: se dice de otra manera."""
    cerebro = _cerebro()

    def online(_mensajes):
        raise RuntimeError("429 Client Error: Too Many Requests for url: https://...")
        yield  # pragma: no cover

    def local(_mensajes):
        yield "respuesta de casa"

    cerebro._llamar_online_stream = online
    cerebro._llamar_ollama_stream = local
    cerebro.hablar("hola")
    avisos = cerebro.tomar_avisos()
    assert avisos and "frenando" in avisos[0].lower(), avisos
    assert "sin internet" not in avisos[0].lower(), avisos
    # Y se puede apagar el aviso hablado desde config.yaml.
    callado = _cerebro(avisar_por_voz=False)
    callado._llamar_online_stream = online
    callado._llamar_ollama_stream = local
    callado.hablar("hola")
    assert callado.tomar_avisos() == [], "avisar_por_voz=false y habló igual"
    print("[OK] el 429 se avisa como «me están frenando» y se puede silenciar")


def test_frase_modo_por_voz():
    """«¿Qué cerebro usas?» se contesta sin LLM, en castellano claro."""
    cerebro = _cerebro()
    assert "internet" in cerebro.frase_modo().lower(), cerebro.frase_modo()
    cerebro.cambiar_modo("nube")
    assert "internet" in cerebro.frase_modo().lower()
    cerebro.cambiar_modo("local")
    assert "casa" in cerebro.frase_modo().lower(), cerebro.frase_modo()
    cerebro.cambiar_modo("auto")
    assert "casa listo" in cerebro.frase_modo().lower(), cerebro.frase_modo()
    sin = _cerebro(online=False)
    assert "apagada" in sin.frase_modo().lower(), sin.frase_modo()
    print("[OK] el estado del cerebro se cuenta por voz")


def test_acentos_no_se_rompen():
    """El stream SSE se decodifica en UTF-8, no en ISO-8859-1.

    Sin esto, «¿Qué tal?» llegaba a Piper como «Â¿QuÃ© tal?» (visto 25/10) y el
    TTS intentaba pronunciar «Â» y «Ã».
    """
    crudo = 'data: {"choices":[{"delta":{"content":"¿Qué tal, señor?"}}]}'
    texto = _texto_de_linea(crudo.encode("utf-8"))
    assert "¿Qué tal, señor?" in texto, texto
    assert "Ã" not in texto and "Â" not in texto, texto
    # Y si un día llegara latin-1 de verdad, no revienta: degrada a latín.
    assert "año" in _texto_de_linea("año".encode("latin-1"))
    print("[OK] acentos y eñes llegan íntegros a la voz")


def test_no_se_lee_el_marcado():
    """Ni etiquetas de cara, ni tokens de canal, ni entidades se pronuncian."""
    casos = {
        "[CARA:feliz] Hola Alan.": "Hola Alan.",
        "<|channel|>final<|message|>Hola Alan.": "Hola Alan.",
        "&quot;Hola&quot; Alan.": '"Hola" Alan.',
        "```json\n{\"cara\": \"feliz\"}\n``` Hola.": "Hola.",
        "【CARA:feliz】Hola.": "Hola.",
        "Hola [Tutéame como siempre] Alan.": "Hola Alan.",
    }
    for entrada, esperado in casos.items():
        limpio = limpiar_marcado(entrada)
        limpio = " ".join(limpio.split())
        assert limpio == esperado, f"{entrada!r} -> {limpio!r} (esperaba {esperado!r})"
    print("[OK] el marcado no llega a la boca")


def test_espanol_de_espana():
    """El 2B local decía «qué onda» aunque el prompt pidiera España (01/11)."""
    casos = {
        "¡Qué onda! ¿Cómo va el carro?": "¡qué tal! ¿Cómo va el coche?",
        "Te llamo al celular luego, ahorita platicamos.":
            "Te llamo al móvil luego, ahora hablamos.",
        "Estoy en la computadora de acá.": "Estoy en el ordenador de aquí.",
    }
    for entrada, esperado in casos.items():
        limpio = " ".join(limpiar_marcado(entrada).split())
        assert limpio.lower() == esperado.lower(), (entrada, limpio)
    print("[OK] el 2B no cuela modismos latinoamericanos")


def test_frase_hablada_sin_marcado():
    """La limpieza que usa parker.py por frase también lo quita."""
    from parker import limpiar_etiquetas

    for entrada in ("[CARA:feliz] Hola Alan.",
                    "<|channel|>final<|message|>Hola Alan.",
                    "Hola [CARA:pensando] Alan.",
                    "&quot;Hola&quot; Alan."):
        limpio = limpiar_etiquetas(entrada)
        assert "CARA" not in limpio.upper(), limpio
        assert "<|" not in limpio, limpio
        assert "&quot;" not in limpio, limpio
        assert "Hola" in limpio and "Alan" in limpio, limpio

    # El bloque de estado del prompt no se convierte en habla (30/10).
    fugado = limpiar_etiquetas(
        "100% (desde hace 12 días, 231 charlas). Estás hablando con Alan. "
        "mucha confianza.")
    assert "231" not in fugado and "charlas" not in fugado, fugado
    assert "mucha confianza" not in fugado.lower(), fugado
    print("[OK] lo que se sintetiza no lleva marcado ni estado interno")


def test_no_se_filtra_el_vinculo():
    """El modelo copiaba el estado del prompt; no debe llegar a la boca."""
    fugas = (
        "100% (desde hace 12 días, 231 charlas).",
        "100% (desde hace 12 días, 231 charlas). Estás hablando con Alan. "
        "mucha confianza.",
        "Vínculo: 100% (desde hace 12 días, 231 charlas).",
        # La pauta nueva tampoco debe llegar a la boca.
        "Pauta de trato (no la menciones): de amigos: puedes bromear un poco.",
        "Trato: muy cercano, con naturalidad.",
    )
    for fuga in fugas:
        limpio = quitar_fugas_prompt(fuga)
        assert "231" not in limpio and "charlas" not in limpio, limpio
        assert "mucha confianza" not in limpio.lower(), limpio

    # El 01/11 el 3B pegó el bloque de estado (sin puntos) delante de la
    # frase real; el filtro antiguo no lo veía porque no había oración.
    fuga_lineas = (
        "energía baja, curiosidad media, cariño alto \n"
        "Pauta de trato: de amigos: puedes bromear un poco\n\n"
        "Hey Piper, parece que eres uno de mis nuevos vecinos."
    )
    limpio = quitar_fugas_prompt(fuga_lineas)
    assert "energía" not in limpio.lower(), limpio
    assert "pauta de trato" not in limpio.lower(), limpio
    assert "Hey Piper" in limpio, limpio

    # Una frase normal que habla de confianza no se toca.
    normal = "Te tengo mucha confianza, Alan."
    assert quitar_fugas_prompt(normal) == normal
    print("[OK] el estado del prompt no se dice en voz alta")


def test_no_se_dicen_inventos():
    """Ni actividades falsas ni recuerdos que no están en Chroma.

    El 01/11 el modelo dijo «he estado escuchando graves» y «la receta de
    pasta que te mencioné» sin que existiera nada de eso. El filtro solo se
    aplica a la salida del modelo; la agenda sigue diciendo lo que sí hizo.
    """
    cerebro = _cerebro(online=False)
    cerebro._recuerdos_turno = ""
    assert cerebro._quitar_inventos(
        "He estado escuchando música de sintetizador. ¿Qué tal tu día?") \
        == "¿Qué tal tu día?"
    assert "Perdona" in cerebro._quitar_inventos(
        "La receta de pasta que te mencioné ayer.")
    assert "Perdona" in cerebro._quitar_inventos(
        "He guardado algunos recordatorios en mi agenda.")
    # Una frase normal de escucha no se toca.
    normal = "He escuchado tus palabras y me alegra oírte."
    assert cerebro._quitar_inventos(normal) == normal
    # Si el recuerdo sí se inyectó, el modelo puede citarlo.
    cerebro._recuerdos_turno = "[1] (2026-01-01) receta de pasta"
    con_recuerdo = cerebro._quitar_inventos("La receta de pasta que te mencioné.")
    assert "receta" in con_recuerdo, con_recuerdo
    print("[OK] no se dicen actividades ni recuerdos inventados")


def main():
    test_acentos_no_se_rompen()
    test_no_se_lee_el_marcado()
    test_espanol_de_espana()
    test_no_se_filtra_el_vinculo()
    test_frase_hablada_sin_marcado()
    test_nube_primaria()
    test_respaldo_local_cuando_falla()
    test_fallo_a_mitad_no_repite()
    test_sin_nube_configurada()
    test_precalentar_no_gasta_cpu_con_nube()
    test_modo_local_no_intenta_la_nube()
    test_cambio_de_modo_por_voz_y_persistencia()
    test_avisos_de_caida_y_vuelta()
    test_aviso_distinto_si_el_proveedor_frena()
    test_frase_modo_por_voz()
    test_no_se_dicen_inventos()
    print("\nCerebro doble: 15/15 en verde.")


if __name__ == "__main__":
    main()
