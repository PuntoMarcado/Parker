"""
tests/test_personalidad.py
==========================
Tests de la identidad de Parker (sin hardware, sin Ollama, sin Qt).

Ejecutar:  python tests/test_personalidad.py

Cubre:
  1. La ficha del personaje está completa y es concreta (no relleno)
  2. El prompt de sistema lleva la identidad, las reglas de voz y el ánimo
  3. El ánimo evoluciona con las conversaciones y con el silencio, y no se
     sale de rango
  4. El ánimo se puede guardar y recuperar (y un fichero corrupto no lo rompe)
  5. La iniciativa proactiva varía (no siempre el mismo saludo)
  6. Originalidad: la ficha no referencia a otros personajes con dueño
  7. Integración con el cerebro: el prompt que se envía a Ollama la incluye
"""

import json
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker
from modulos.personalidad import (ESTADO_POR_DEFECTO, PERFIL_POR_DEFECTO,
                                  PersonalidadParker)

# Claves que debe tener la ficha y mínimo de entradas para que el personaje
# tenga sustancia (una lista de una sola cosa no da juego al LLM).
CLAVES_CONTENIDO = {
    "le_gusta": 5,
    "no_le_gusta": 3,
    "suenos": 3,
    "manias": 3,
    "miedos": 2,
    "cuando_nadie_mira": 2,
    "detalles": 2,
}

# Estas deben ser concretas pero cortas por naturaleza: una muletilla es una
# palabra ("Ostras") y exigirle tres palabras sería absurdo. Aquí solo se pide
# que existan y que haya variedad.
CLAVES_BREVES = {
    "muletillas": 3,
    "humor": 2,
}

# Si alguna de estas cadenas aparece en la ficha, Parker está copiando a otro
# personaje en vez de ser él mismo.
REFERENCIAS_AJENAS = ["bmo", "adventure time", "beemo", "finn", "jake",
                      "marceline", "bubbline", "kirby", "wall-e"]


def test_ficha_completa():
    perfil = PERFIL_POR_DEFECTO
    for clave in ("nombre", "esencia"):
        assert isinstance(perfil.get(clave), str) and perfil[clave].strip(), clave
    def _revisar(claves):
        for clave, minimo in claves.items():
            lista = perfil.get(clave)
            assert isinstance(lista, list), f"{clave} no es una lista"
            assert len(lista) >= minimo, f"{clave}: {len(lista)} entradas, se piden {minimo}"
            assert all(isinstance(x, str) and x.strip() for x in lista), clave
        return True

    _revisar(CLAVES_CONTENIDO)
    _revisar(CLAVES_BREVES)

    # Concreción: en las listas de contenido, una entrada de una o dos palabras
    # ("cosas", "la vida") no le sirve de nada al LLM para construir escenas.
    for clave in CLAVES_CONTENIDO:
        lista = perfil[clave]
        assert all(len(x.split()) >= 3 for x in lista), f"{clave} tiene entradas vagas: {lista}"

    texto = " ".join(str(v) for v in perfil.values()).lower()
    for referencia in REFERENCIAS_AJENAS:
        assert referencia not in texto, f"la ficha referencia a '{referencia}': Parker debe ser original"
    print("[OK] ficha del personaje: completa, concreta y original")


def test_prompt_de_sistema():
    perfil = PersonalidadParker({"guardar_estado": False, "nombre": "Parker"})
    prompt = perfil.system_prompt("martes 12 de octubre de 2026, 21:00",
                                  recuerdos="[1] Le gusta el café",
                                  contexto_extra="Es de noche")

    for esperado in ("Eres Parker", "QUIÉN ES QUIÉN", "NO es Parker", "CONVERSACIÓN", "[CARA:...]",
                     "Recuerdos:", "CONTEXTO ADICIONAL",
                     "martes 12 de octubre de 2026, 21:00", "Ánimo", "CONVERSACIÓN",
                     # Sabe dónde vive y qué es: sin esto se inventaba paseos.
                     "Orange Pi", "micrófono", "altavoz", "Sin cuerpo ni boca",
                     "no prometas acciones físicas"):
        assert esperado in prompt, f"falta en el prompt: {esperado}"

    # El ejemplo no puede ofrecer una emoción fuera del catálogo: el 3B la
    # copiaba tal cual ("[CARA:emocion]") y la cara caía a neutral.
    assert "CARA:emocion" not in prompt, "el prompt vuelve a ofrecer una emoción inválida"

    # El ánimo y la fecha van AL FINAL: así el bloque de identidad (que es el
    # prefijo que cachea Ollama) es idéntico entre llamadas. Si esto se rompe,
    # la latencia por respuesta se multiplica (medido en la placa).
    assert prompt.index("TU CARÁCTER") < prompt.index("Ánimo"), \
        "el ánimo debe ir después del bloque de identidad"
    assert prompt.index("Ánimo") < prompt.index("Hora:"), \
        "la fecha, que cambia cada minuto, va al final"
    identidad = perfil._bloque_identidad()
    assert not perfil.system_prompt("una hora", ).startswith("Ánimo"), \
        "el prompt no puede empezar por la parte volátil"
    # El bloque fijo se cachea: lo nuevo son reglas de conversación para no
    # saludar/repetir y mantener el hilo, y se prepara al arrancar.
    assert len(identidad) < 1900, f"el bloque fijo es demasiado largo: {len(identidad)} caracteres"
    print(f"[OK] prompt: bloque de identidad estable de {len(identidad)} caracteres")

    # La identidad no puede quedarse en la esencia: tiene que llevar sus cosas
    assert any(g in prompt for g in perfil.perfil["le_gusta"]), "no incluye sus gustos"
    assert any(s in prompt for s in perfil.perfil["suenos"]), "no incluye sus sueños"

    # El ánimo va en abstracto: si se manda una frase en primera persona, los
    # modelos pequeños la recitan tal cual (visto en la placa con 1.5b y 3b).
    assert "energía" in prompt and "cariño" in prompt, prompt
    assert "estoy tranquilo y con ganas" not in prompt, prompt

    # Y las reglas que hacen que suene a amigo y no a asistente
    assert "no digas que eres una ia" in prompt.lower()
    assert "expresa dudas con pausas" in prompt.lower()
    assert "no escribas rellenos como \"mmm\"" in prompt.lower()
    assert "¿en qué puedo ayudarte?" in prompt.lower()  # prohibición explícita
    texto = prompt.lower()
    assert "no como un asistente" in texto, \
        "el prompt debe dejar claro que Parker no es un asistente"
    assert "no uses frases de plantilla" in texto
    # Regla reescrita el 25/10: no «sigue el mismo tema» (se anclaba a su propia
    # idea y seguía con ella aunque le corrigieras), sino contestar a lo último.
    assert "contesta a lo último que te dicen" in texto
    assert "no inventes" in texto
    assert "rechaza ayuda para dañar o delinquir" in texto
    print("[OK] prompt de sistema: identidad + ánimo + reglas de voz/seguridad")


def test_animo_evoluciona():
    perfil = PersonalidadParker({"guardar_estado": False})
    inicial = dict(perfil.estado)

    for _ in range(5):
        perfil.registrar_interaccion("feliz")
    assert perfil.estado["energia"] > inicial["energia"], perfil.estado
    assert perfil.estado["curiosidad"] > inicial["curiosidad"], perfil.estado
    assert perfil.estado["carino"] > inicial["carino"], perfil.estado
    assert int(perfil.estado["interacciones"]) == 5, perfil.estado
    assert perfil.silencio_seg() < 5

    # Hablar mucho no lo puede llevar fuera de rango
    for _ in range(60):
        perfil.registrar_interaccion()
    fuera_de_rango = ("interacciones", "ultima_interaccion", "despertado",
                      "primer_contacto", "vinculo_inicio", "charlas",
                      "charlas_version", "nombre_usuario")  # no son números 0-1
    for clave, valor in perfil.estado.items():
        if clave in fuera_de_rango:
            continue
        # El bandit guarda listas y el pendiente un dict: no son ánimo 0-1.
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            continue
        assert 0.0 <= valor <= 1.0, f"{clave} fuera de rango: {valor}"

    # Un silencio largo le baja la energía y le sube el cariño
    energia_antes = perfil.estado["energia"]
    carino_antes = perfil.estado["carino"]
    for _ in range(10):
        perfil.latido(silencio_seg=3600)
    assert perfil.estado["energia"] < energia_antes, perfil.estado
    assert perfil.estado["carino"] >= carino_antes, perfil.estado

    # El ánimo se puede describir en una frase y no queda vacío
    assert len(perfil.describir_momento()) > 10
    print("[OK] ánimo: sube con las charlas, baja con el silencio y queda acotado")


def test_vinculo_confianza():
    """El vínculo empieza en 0 % y crece con los días y las charlas."""
    perfil = PersonalidadParker({"guardar_estado": False})

    # Recién conocido: 0 % y el prompt lo dice con todas las letras
    v = perfil.vinculo()
    assert v["pct"] == 0, v
    assert v["charlas"] == 0, v
    linea = perfil.vinculo_para_prompt()
    assert linea.startswith("Pauta de trato"), linea
    assert "sin fingir" in linea, linea
    # Sin números ni etiqueta «Vínculo»: era lo que el modelo copiaba.
    assert "%" not in linea and "Vínculo" not in linea, linea
    assert "charlas" not in linea, linea

    # 5 charlas -> 5 % (1 punto por charla hasta 50). Cada llamada va con un
    # hueco de una hora: si fueran turnos seguidos contarían como una sola.
    base = time.time()
    for i in range(5):
        perfil.registrar_interaccion(ahora=base + i * 3600)
    assert perfil.vinculo()["pct"] == 5, perfil.vinculo()

    # Y el prompt lo lleva dentro del mensaje del usuario, no en el sistema
    volatil = perfil.contexto_volatil("vie 17/10 15:00")
    assert "Pauta de trato" in volatil, volatil
    assert "sin fingir" in volatil, volatil
    assert "%" not in volatil and "charlas" not in volatil, volatil

    # Mucho tiempo + muchas charlas -> 100 % como máximo
    perfil.estado["vinculo_inicio"] = time.time() - 30 * 86400  # un mes juntos
    momento = base + 5 * 3600
    for _ in range(200):
        perfil.registrar_interaccion(ahora=momento)
        momento += 3600
    v = perfil.vinculo()
    assert v["pct"] == 100, v
    assert "muy cercano" in perfil.vinculo_para_prompt()
    print("[OK] vínculo: 0 % al conocerse, sube con días y charlas, tope 100 %")


def test_charlas_no_se_inflan_por_turno():
    """«Charla» es conversación, no frase: el 30/10 decía 231 charlas."""
    perfil = PersonalidadParker({"guardar_estado": False})
    base = time.time()
    for i in range(6):
        perfil.registrar_interaccion(ahora=base + i * 30)   # misma charla
    assert perfil.estado["interacciones"] == 6
    assert perfil.estado["charlas"] == 1

    perfil.registrar_interaccion(ahora=base + 3600)          # hueco de 1 h
    assert perfil.estado["charlas"] == 2

    # El prompt ya NO lleva el número (el modelo lo copiaba literal).
    perfil.estado["nombre_usuario"] = "Alan"
    linea = perfil.vinculo_para_prompt()
    assert "charlas" not in linea and "%" not in linea, linea
    assert "Pauta de trato" in linea, linea
    # El nombre sigue en el bloque estable, una sola vez.

    # Y si pregunta, contesta con los días, no con un número inventado.
    perfil.estado["vinculo_inicio"] = time.time() - 12.5 * 86400
    assert "12 días" in perfil.respuesta_directa("¿Cuántos días llevamos?")
    respuesta = perfil.respuesta_directa("¿Cuántas charlas llevamos?")
    assert "No las cuento" in respuesta and "231" not in respuesta, respuesta
    assert "%" in perfil.respuesta_directa("¿Cuánto confías en mí?")
    print("[OK] charlas = conversaciones; el prompt no lleva el contador")


def test_nombre_del_usuario():
    """Parker aprende el nombre y no lo inventa (ni se lo pone al usuario)."""
    perfil = PersonalidadParker({"guardar_estado": False})

    # No lo sabe: lo dice, no lo inventa
    assert perfil.respuesta_directa("¿cómo me llamo?") == \
        "Todavía no me lo has dicho. ¿Cómo te llamas?"
    assert perfil.respuesta_directa("¿sabes mi nombre?") is not None
    assert perfil.respuesta_directa("cuéntame algo tuyo") is None
    assert perfil.respuesta_directa("¿cómo te llamas?") == "Me llamo Parker."

    # Lo aprende cuando se lo dicen (y no acepta "Parker" como nombre del otro)
    assert perfil.registrar_nombre("hola Parker, me llamo Alan") == "Alan"
    assert perfil.registrar_nombre("mi nombre es Parker") == "Alan"
    assert perfil.respuesta_directa("¿cómo me llamo yo Parker?") == "Te llamas Alan."
    # Segunda persona: «Tu amigo se llama Alan» hacía que el 3b hablara de
    # Alan como si fuera un tercero («Alan parece pendiente de ti», placa 24/10).
    assert "Estás hablando con Alan" in perfil.identidad()

    # Y las reglas del prompt cubren los dos fallos vistos en la placa
    identidad = perfil.identidad()
    assert "NO es Parker" in identidad, identidad
    # El nombre se ata a la persona en una sola línea corta (sin «No la llames
    # Parker», que gastaba tokens en cada turno).
    assert "Estás hablando con Alan" in identidad, identidad
    # El motor de voz aparecía como «Piper» y el 3B lo usó como nombre de Alan
    # (placa 24/10: «eres tú, Piper»). Ni en el prompt ni en la salida.
    assert "piper" not in identidad.lower(), identidad
    assert perfil.corregir_nombre("¡Hola, Piper!") == "¡Hola, Alan!"
    assert perfil.corregir_nombre("¡Oh! Claro, eres tú, Piper.") == \
        "¡Oh! Claro, eres tú, Alan."
    # Roles invertidos: Parker no es Alan y Alan no es Parker
    assert perfil.corregir_nombre("Soy Alan, tu amigo en la pantalla.") == \
        "Soy Parker, tu amigo en la pantalla."
    assert perfil.corregir_nombre("¿Eres Parker?") == "¿Eres Alan?"
    # Y la pregunta de memoria se contesta sin pasar por el modelo
    assert perfil.respuesta_directa("¿te acuerdas de mi nombre?") == "Te llamas Alan."
    # El ejemplo de roles va dentro del prompt (enseña quién es quién)
    assert "quién soy yo?" in identidad.lower() and "yo soy parker" in \
        identidad.lower(), identidad
    assert "no inventes recuerdos" in identidad.lower(), identidad
    assert "no los atribuyas a la persona" in identidad.lower(), identidad
    # Red de seguridad determinista: aunque el modelo se equivoque, Parker no
    # llama "Parker" a su amigo... pero sí puede decir su propio nombre.
    assert perfil.corregir_nombre("¡Hola, Parker!") == "¡Hola, Alan!"
    assert perfil.corregir_nombre("¿Y tú, Parker, qué tal?") == "¿Y tú, Alan, qué tal?"
    assert perfil.corregir_nombre("Me llamo Parker.") == "Me llamo Parker."
    assert perfil.corregir_nombre("Soy Parker, tu amigo.") == "Soy Parker, tu amigo."
    assert perfil.corregir_nombre("Te lo dije, Parker.") == "Te lo dije, Alan."

    # Sin saber el nombre, se usa un apelativo neutro en vez del nombre de Parker
    nuevo = PersonalidadParker({"guardar_estado": False})
    assert nuevo.corregir_nombre("¡Hola, Parker!") == "¡Hola, amigo!"
    # Frases de plantilla conocidas se eliminan sin perder una reacción real.
    plantillas = [
        "Estoy encantado de verte otra vez. ¡Qué bueno lo del trabajo!",
        "Me alegra verte de nuevo. Alicante suena genial.",
        "Hola, Alan. ¿Qué tal estás? Me dijiste que querías ahorrar.",
        "¡Hola, Parker! Me acuerdo que has empezado el curso de dibujo.",
    ]
    for frase in plantillas:
        limpio = perfil.limpiar_frases_plantilla(frase, conversacion_en_curso=True)
        assert "encantado de verte" not in limpio.lower(), limpio
        assert "me alegra verte" not in limpio.lower(), limpio
        assert not limpio.lower().startswith("hola"), limpio
        assert "¿qué tal" not in limpio.lower(), limpio
        assert not limpio.lower().startswith("¡hola"), limpio
    assert "¡Qué bueno lo del trabajo!" in perfil.limpiar_frases_plantilla(
        plantillas[0], conversacion_en_curso=True)
    print("[OK] nombre y filtro anti-plantillas conservan el contenido útil")


def test_persistencia():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "estado.json"

        perfil = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        for _ in range(3):
            perfil.registrar_interaccion("carino")
        esperado = dict(perfil.estado)
        assert ruta.exists(), "no se guardó el estado"

        otro = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        assert int(otro.estado["interacciones"]) == int(esperado["interacciones"])
        assert abs(otro.estado["carino"] - esperado["carino"]) < 1e-9

        # Un fichero corrupto no puede impedir el arranque
        ruta.write_text("{esto no es json", encoding="utf-8")
        tercero = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        assert tercero.estado["energia"] == ESTADO_POR_DEFECTO["energia"]
    print("[OK] persistencia: guarda, recupera y tolera un fichero corrupto")


def test_migracion_de_charlas_infladas():
    """El estado real de la placa (232 charlas, 12 días) se corrige al cargar."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "estado.json"
        ahora = time.time()
        ruta.write_text(json.dumps({"estado": {
            "energia": "rota",
            "interacciones": 324,
            "charlas": 232,
            "primer_contacto": ahora - 12.9 * 86400,
            "vinculo_inicio": ahora - 12.9 * 86400,
            "nombre_usuario": "Alan",
        }}), encoding="utf-8")
        perfil = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        # Techo honesto: dos conversaciones al día desde el primer contacto.
        assert perfil.estado["charlas"] <= 26, perfil.estado
        assert perfil.estado["charlas_version"] == 2, perfil.estado
        assert perfil.estado["energia"] == 0.75, perfil.estado
        assert perfil.vinculo()["pct"] < 100, perfil.vinculo()

        # Una vez migrado, el contador vuelve a crecer desde donde toca.
        perfil.estado["charlas"] = 7
        perfil._guardar()
        otro = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        assert otro.estado["charlas"] == 7, otro.estado["charlas"]

        # Campos con el tipo equivocado no pueden tumbar el arranque.
        ruta.write_text(json.dumps({"estado": {
            "energia": "x", "ultima_interaccion": "ayer",
            "despertado": None, "primer_contacto": "ayer",
            "vinculo_inicio": float("nan"), "nombre_usuario": 123,
            "charlas": "232", "interacciones": None,
        }}), encoding="utf-8")
        raro = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        assert raro.estado["energia"] == 0.75, raro.estado
        assert raro.estado["nombre_usuario"] == "", raro.estado
        assert raro.estado["charlas"] == 0, raro.estado
        assert raro.estado["primer_contacto"] > 0, raro.estado
        assert raro.vinculo()["dias"] >= 0, raro.vinculo()
    print("[OK] migración: 232 charlas inventadas -> techo de 2/día")


def test_iniciativa_variada():
    perfil = PersonalidadParker({"guardar_estado": False})
    instrucciones = {perfil.instruccion_proactiva(2700) for _ in range(40)}
    assert len(instrucciones) >= 3, f"la iniciativa no varía: {instrucciones}"
    assert all(len(i) > 15 for i in instrucciones)

    # Con muchísimo silencio aparece la opción de echar de menos
    largas = {perfil.instruccion_proactiva(7200) for _ in range(60)}
    assert any("echado de menos" in i for i in largas), largas
    print(f"[OK] iniciativa proactiva: {len(instrucciones)} variantes distintas")


def test_iniciativa_concreta():
    """Las frases automáticas salen de datos reales, no de improvisación."""
    perfil = PersonalidadParker({"guardar_estado": False})
    for brazo in ("contar", "preguntar", "proponer", "eco"):
        frase = perfil.semilla_iniciativa(brazo, "ayer me caí de la bici")
        assert frase, brazo
        assert 10 < len(frase) < 220, (brazo, frase)
        for raro in ("lluvia", "zumbido", "constelaci", "universo", "galaxia"):
            assert raro not in frase.lower(), (brazo, frase)

    assert perfil.semilla_iniciativa("callar") == ""
    eco = perfil.semilla_iniciativa("eco", "ayer me caí de la bici")
    assert "bici" in eco, eco
    # Una orden no es una confidencia: no se repite como «eco».
    orden = perfil.semilla_iniciativa("eco", "pon música").lower()
    assert "pon música" not in orden, orden
    # Una transcripción mala tampoco se repite como recuerdo: si se cita
    # «dipre oscuro o algo», Parker suena a que se ha vuelto loco.
    basura = perfil.semilla_iniciativa("eco", "dipre oscuro o algo").lower()
    assert "dipre" not in basura, basura
    # Las manías no se cuentan como creencias (30/10: «Creo que ordeno las
    # palabras antes de decirlas» no significaba nada).
    for _ in range(40):
        frase = perfil.semilla_iniciativa("contar")
        assert not frase.startswith("Creo que"), frase
        assert frase.endswith("."), frase
    print("[OK] iniciativa concreta: ficha, hora y recuerdo; sin imágenes inventadas")


def test_contexto_de_la_iniciativa():
    """Si preguntan por la frase espontánea, el modelo recibe el motivo real."""
    class MemoriaFalsa:
        def recuperar_recuerdos_formateados(self, *a, **kw):
            return ""

        def guardar_recuerdo(self, *a, **kw):
            pass

    cerebro = CerebroParker(
        config_llama={"modelo": "test"},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
    )
    cerebro._ultima_iniciativa = {
        "texto": "¿Qué has comido hoy?", "brazo": "preguntar",
        "ts": time.time(),
    }
    pregunta = cerebro._construir_prompt("¿por qué me has preguntado eso?")[-1]["content"]
    assert "¿Qué has comido hoy?" in pregunta, pregunta
    assert "querías preguntarle" in pregunta, pregunta
    # Y la vía directa (sin LLM) dice la frase y el motivo, sin inventar.
    directa = cerebro.respuesta_directa("¿qué me estabas diciendo?")
    assert directa and "Te pregunté" in directa and "¿Qué has comido hoy?" in directa, directa
    # Sin pregunta sobre la iniciativa no se mete en el prompt.
    normal = cerebro._construir_prompt("hola")[-1]["content"]
    assert "¿Qué has comido hoy?" not in normal, normal
    print("[OK] iniciativa: motivo en el prompt y respuesta directa sin LLM")


def test_proactivo_usa_semilla_sin_llm():
    """La iniciativa real no llama al modelo: usa una frase concreta."""
    class MemoriaFalsa:
        def recuperar_recuerdos_formateados(self, *a, **kw):
            return ""

        def guardar_recuerdo(self, *a, **kw):
            pass

    cerebro = CerebroParker(
        config_llama={"modelo": "test"},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_online={"activo": False},
    )
    cerebro.ultimo_mensaje_usuario = "ayer me caí de la bici"
    texto, etiquetas = cerebro.hablar_proactivo(brazo="eco")
    assert "bici" in texto, texto
    assert etiquetas and etiquetas[0].startswith("[CARA:"), etiquetas
    assert cerebro._ultima_iniciativa["brazo"] == "eco"
    assert cerebro._ultima_iniciativa["texto"] == texto
    print("[OK] proactivo: frase de semilla, sin llamar al LLM ni inventar")


def test_la_iniciativa_se_explica_tras_reiniciar():
    """Tras un reinicio, Parker sigue sabiendo qué dijo y por qué.

    Antes la frase espontánea solo vivía en memoria: si el proceso se
    reiniciaba (o si se preguntaba por una frase del arranque anterior), el
    modelo contestaba inventándose el motivo.
    """
    class MemoriaFalsa:
        def recuperar_recuerdos_formateados(self, *a, **kw):
            return ""

        def guardar_recuerdo(self, *a, **kw):
            pass

    ficha = PersonalidadParker({"guardar_estado": False})
    primero = CerebroParker(config_llama={"modelo": "test"}, memoria=MemoriaFalsa(),
                            personalidad=ficha, config_online={"activo": False})
    texto, _ = primero.hablar_proactivo(brazo="preguntar")
    assert texto, "la semilla de preguntar no puede quedar vacía"

    # Simula el reinicio: un cerebro nuevo que comparte la ficha guardada.
    segundo = CerebroParker(config_llama={"modelo": "test"}, memoria=MemoriaFalsa(),
                            personalidad=ficha, config_online={"activo": False})
    assert segundo._ultima_iniciativa and segundo._ultima_iniciativa.get("texto") == texto
    directa = segundo.respuesta_directa("¿qué has dicho?")
    assert directa and "Te pregunté" in directa and texto in directa, directa
    print("[OK] iniciativa: explicable también después de reiniciar")


def test_integracion_con_cerebro():
    perfil = PersonalidadParker({"guardar_estado": False, "nivel_carino": 0.9})

    class MemoriaFalsa:
        def recuperar_recuerdos_formateados(self, consulta, top_k=5, umbral=0.5,
                                             max_caracteres=0):
            return "[1] (2026-01-01) Recuerdo de prueba"

        def guardar_recuerdo(self, *a, **kw):
            pass

    cerebro = CerebroParker(config_llama={"modelo": "test"}, memoria=MemoriaFalsa(),
                            personalidad=perfil)
    # Igual que el camino real: el cerebro entrega los recuerdos recuperados
    mensajes = cerebro._construir_prompt("¿Qué tal el día?",
                                         recuerdos="[1] (2026-01-01) Recuerdo de prueba")
    system = mensajes[0]["content"]
    assert mensajes[0]["role"] == "system"
    assert "Eres Parker" in system
    assert perfil.matiz in system
    # La ternura configurada llega al prompt
    assert "0.9" in system

    # Lo volátil (ánimo, fecha, recuerdos) viaja con el mensaje del usuario
    usuario = mensajes[-1]["content"]
    assert mensajes[-1]["role"] == "user"
    assert "Ánimo" in usuario, usuario
    assert "Pauta de trato" in usuario, usuario
    assert "charlas" not in usuario and "Vínculo" not in usuario, usuario
    assert "Recuerdo de prueba" in usuario, usuario
    assert "¿Qué tal el día?" in usuario

    # Y el mensaje de sistema es IDÉNTICO entre llamadas distintas: es la
    # propiedad que permite a Ollama cachear el prefijo (latencia).
    otro = cerebro._construir_prompt("Otra cosa", recuerdos="otro recuerdo")
    assert otro[0]["content"] == mensajes[0]["content"], \
        "el mensaje de sistema cambia entre llamadas: se pierde el caché de Ollama"

    # La etiqueta de la respuesta mueve su ánimo
    assert CerebroParker._emocion_de_etiquetas(["[CARA:carino]"]) == "carino"
    assert CerebroParker._emocion_de_etiquetas([]) == "neutral"
    print("[OK] integración con el cerebro: sistema estable, volátil en el mensaje")


def test_rotacion_de_la_ficha():
    """El gusto y el sueño del prompt rotan entre conversaciones.

    Motivo (27/10): Parker sacaba siempre los mismos gustos. La causa era que
    `_lista('le_gusta', 1)` cogía siempre la primera entrada, así que solo veía
    de sí mismo una frase y la repetía. La variedad tiene que llegar SIN romper
    la propiedad que da la latencia: el bloque de identidad no puede cambiar de
    un turno a otro.
    """
    perfil = PersonalidadParker({"guardar_estado": False})
    gustos = perfil.perfil["le_gusta"]
    suenos = perfil.perfil["suenos"]

    primero = perfil.identidad()
    assert gustos[0] in primero and suenos[0] in primero
    # Dentro de una conversación: idéntico llamada tras llamada (prefijo
    # cacheable de Ollama). Si esto falla, la latencia se multiplica.
    assert perfil.identidad() == primero
    assert perfil.identidad() == primero

    # Sin ninguna charla previa (primer arranque) no rota: empieza por el
    # principio, que no hay conversación anterior de la que diferenciarse.
    assert perfil._rotar_si_toca(ahora=time.time() + 99999) is False
    assert perfil.identidad() == primero

    # Dentro de la misma conversación tampoco: siguen siendo segundos.
    ahora = time.time()
    perfil.registrar_interaccion(ahora=ahora)
    assert perfil._rotar_si_toca(ahora=ahora + 60) is False
    assert perfil.identidad() == primero

    # Con el hueco de rigor empieza conversación nueva y sale la entrada
    # siguiente (un gusto distinto y un sueño distinto).
    assert perfil._rotar_si_toca(ahora=ahora + 46 * 60) is True
    segunda = perfil.identidad()
    assert segunda != primero
    assert gustos[1] in segunda and suenos[1] in segunda
    assert gustos[0] not in segunda
    # Y una sola rotación por hueco, aunque nadie hable y se pida el prompt
    # muchas veces (iniciativa, herramientas, logs).
    assert perfil._rotar_si_toca(ahora=ahora + 47 * 60) is False
    assert perfil.identidad() == segunda

    # Ocho charlas después vuelve el primer gusto. Los sueños son cinco, así
    # que las dos listas se reencuentran cada 40 charlas (el mcm).
    momento = ahora
    for _ in range(len(gustos) - 1):
        momento += 46 * 60                          # rato largo sin hablar
        perfil.registrar_interaccion(ahora=momento)  # charla nueva
        momento += 46 * 60                          # y otro rato largo
        assert perfil._rotar_si_toca(ahora=momento) is True
    octava = perfil.identidad()
    assert gustos[0] in octava
    assert suenos[len(gustos) % len(suenos)] in octava

    # Ciclo completo (40 charlas): el prompt vuelve a ser el del principio, y
    # entre medias han salido todos sus gustos y todos sus sueños.
    for _ in range(len(gustos) * len(suenos) - len(gustos)):
        momento += 46 * 60
        perfil.registrar_interaccion(ahora=momento)
        momento += 46 * 60
        assert perfil._rotar_si_toca(ahora=momento) is True
    assert perfil.rotacion() % len(gustos) == 0
    assert perfil.identidad() == primero

    # Se puede apagar: la ficha se queda quieta en la primera entrada.
    quieto = PersonalidadParker({"guardar_estado": False, "rotacion": False})
    quieto.registrar_interaccion(ahora=ahora)
    assert quieto._rotar_si_toca(ahora=ahora + 10 * 3600) is False
    assert quieto.identidad() == primero

    # Y el índice se guarda: un reinicio tras un rato apagado rota igual.
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "estado.json"
        uno = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        uno.registrar_interaccion(ahora=ahora)
        assert uno._rotar_si_toca(ahora=ahora + 3600) is True
        dos = PersonalidadParker({"guardar_estado": True, "ruta_estado": str(ruta)})
        assert dos.rotacion() == uno.rotacion() == 1
    print("[OK] rotación: fija dentro de la charla, distinta en la siguiente")


def test_reparacion_sin_inventar():
    """«No te entiendo / de qué hablas» se contesta con un reflejo honesto.

    Oído el 25/10: a «No, no» Parker se inventó un tema y siguió por ahí. Un
    reflejo breve (sin LLM) corta la espiral antes de que empiece.
    """
    perfil = PersonalidadParker({"guardar_estado": False})
    for frase in ("¿De qué estás hablando Parker?",
                  "no te entiendo",
                  "Parker, te has liado",
                  "esto no tiene sentido",
                  "qué dices"):
        respuesta = perfil.respuesta_directa(frase)
        assert respuesta, f"sin reparación para {frase!r}"
        bajo = respuesta.lower()
        assert any(p in bajo for p in ("liado", "perdido", "ramas")), respuesta
        assert len(respuesta) < 70, respuesta
    # Y no se dispara con una pregunta normal.
    assert perfil.respuesta_directa("¿qué hora es?") is None
    print("[OK] reparación: reconoce el lío y pide que se lo repitan")


def test_sabe_que_no_tiene_cuerpo():
    """No tiene cuerpo, no promete acciones físicas y silba con el altavoz."""
    perfil = PersonalidadParker({"guardar_estado": False})
    identidad = perfil.identidad()
    assert "Sin cuerpo ni boca" in identidad, identidad
    assert "no prometas acciones físicas" in identidad, identidad
    assert "silbar por el altavoz" in identidad, identidad
    # Y sabe lo que SÍ puede hacer: si no, contesta que él no pone alarmas.
    assert "agenda" in identidad and "alarmas" in identidad, identidad

    # El dato se contesta al instante y sin inventar.
    assert "ni cuerpo ni manos" in perfil.respuesta_directa("¿tienes manos?")
    assert perfil.respuesta_directa("¿puedes andar?") is not None
    # 01/11: fuera el cebo de música/silbido de la ficha. Era lo que hacía
    # que todos los modelos volvieran al sintetizador y a la canción.
    assert not any("silbar con el altavoz" in s for s in perfil.perfil["suenos"])
    assert not any("música de sintetizador" in s for s in perfil.perfil["le_gusta"])
    assert any("que me enseñes algo que no sepa" in s for s in perfil.perfil["suenos"])
    print("[OK] sin cuerpo: lo dice, no lo promete y silba con el altavoz")


if __name__ == "__main__":
    test_sabe_que_no_tiene_cuerpo()
    test_rotacion_de_la_ficha()
    test_reparacion_sin_inventar()
    test_ficha_completa()
    test_prompt_de_sistema()
    test_animo_evoluciona()
    test_vinculo_confianza()
    test_charlas_no_se_inflan_por_turno()
    test_migracion_de_charlas_infladas()
    test_nombre_del_usuario()
    test_persistencia()
    test_iniciativa_variada()
    test_iniciativa_concreta()
    test_contexto_de_la_iniciativa()
    test_proactivo_usa_semilla_sin_llm()
    test_la_iniciativa_se_explica_tras_reiniciar()
    test_integracion_con_cerebro()
    print("\nTodos los tests de personalidad han pasado.")
