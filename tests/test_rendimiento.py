"""
tests/test_rendimiento.py
=========================
Tests de las decisiones que sostienen la latencia baja (sin Ollama, sin audio).

Ejecutar:  python tests/test_rendimiento.py

Cubre:
  1. Los recuerdos inyectados son cortos y se recortan
  2. El cerebro respeta top_k/umbral/max_caracteres de config.yaml
  3. El historial enviado está acotado y deja el prefijo cacheable
  4. La identidad (prefijo cacheable) no crece
  5. Los valores de config.yaml que sostienen la velocidad (modelo, STT,
     silencio de corte) no vuelven a los valores lentos sin darse cuenta
"""

import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker
from modulos.memoria import formatear_recuerdos
from modulos.personalidad import PersonalidadParker


def test_recuerdos_compactos():
    recuerdos = [
        {"texto": "Usuario: Hola Parker\nParker: ¡Ostras, qué alegría! Estaba pensando en la maceta.",
         "metadata": {"fecha": "2026-10-12", "tipo": "interaccion"}, "similitud": 0.72},
        {"texto": "Usuario: Me gusta el café por la mañana mientras leo el periódico\nParker: Vaya, buen comienzo de día.",
         "metadata": {"fecha": "2026-10-13", "tipo": "interaccion"}, "similitud": 0.65},
    ]
    texto = formatear_recuerdos(recuerdos)
    assert "=== RECUERDOS" not in texto, "la cabecera no aporta: el prompt ya la pone"
    assert "interaccion" not in texto and "sim:" not in texto, texto
    assert "\n" in texto and texto.count("\n") == 1, "un recuerdo por línea"
    # Solo la parte del usuario: la respuesta de Parker de aquel día no ayuda
    # a recordar a la persona y cuesta tokens en cada respuesta.
    assert "[1] (2026-10-12) Hola Parker" in texto, texto
    assert "Parker:" not in texto and "Usuario:" not in texto, texto

    # Un recuerdo repetido no se envía dos veces
    repetidos = recuerdos + [dict(recuerdos[0])]
    assert formatear_recuerdos(repetidos).count("Hola Parker") == 1

    recortado = formatear_recuerdos(recuerdos, max_caracteres=10)
    for linea in recortado.splitlines():
        assert len(linea) <= len("[1] (2026-10-12) ") + 10 + 1, linea
        assert linea.endswith("…"), linea
    assert formatear_recuerdos([]) == ""
    print("[OK] recuerdos compactos y recortados")


class MemoriaFalsa:
    def __init__(self):
        self.llamada = None
        self.guardados = []

    def recuperar_recuerdos_formateados(self, consulta, top_k=5, umbral=0.5, max_caracteres=0):
        self.llamada = {"consulta": consulta, "top_k": top_k,
                        "umbral": umbral, "max_caracteres": max_caracteres}
        return "[1] (2026-01-01) Recuerdo de prueba"

    def guardar_recuerdo(self, *args, **kwargs):
        self.guardados.append(args)


def test_cerebro_respeta_configuracion_de_memoria():
    memoria = MemoriaFalsa()
    cerebro = CerebroParker(
        config_llama={"modelo": "test", "historial_mensajes": 2},
        memoria=memoria,
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria={"top_k_recuerdos": 2, "umbral_relevancia": 0.6,
                        "max_caracteres_recuerdo": 80},
    )
    # Sin red: el stream se sustituye por una respuesta fija
    cerebro._llamar_ollama_stream = lambda mensajes: iter(["[CARA:feliz] Hola. ", "¿Qué tal? "])

    deltas = list(cerebro.hablar_stream("¿Cómo estás?"))
    assert deltas == ["[CARA:feliz] Hola. ", "¿Qué tal? "], deltas
    assert memoria.llamada == {"consulta": "¿Cómo estás?", "top_k": 2,
                               "umbral": 0.6, "max_caracteres": 80}, memoria.llamada

    # El historial no crece sin límite: se queda con el último intercambio
    for i in range(5):
        list(cerebro.hablar_stream(f"pregunta {i}"))
    assert len(cerebro.historial) <= 4, cerebro.historial
    print("[OK] el cerebro respeta top_k/umbral y acota el historial")


def test_prefijo_cacheable_entre_turnos():
    """El turno N+1 debe empezar igual que el N: así Ollama no reevalúa nada."""
    capturados = []
    cerebro = CerebroParker(
        config_llama={"modelo": "test", "historial_mensajes": 2},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria={"top_k_recuerdos": 1, "umbral_relevancia": 0.5,
                        "max_caracteres_recuerdo": 80},
    )

    def falso(mensajes):
        capturados.append([dict(m) for m in mensajes])
        return iter(["[CARA:feliz] Hola. "])

    cerebro._llamar_ollama_stream = falso
    list(cerebro.hablar_stream("primera pregunta"))
    list(cerebro.hablar_stream("segunda pregunta"))

    primero, segundo = capturados
    assert segundo[:len(primero)] == primero, (
        "el segundo prompt no reutiliza el prefijo del primero: el historial "
        "tiene que guardar el mensaje exacto que se envió")
    print("[OK] prefijo cacheable entre turnos")


def test_prefijo_precalentado_coincide():
    """El prefijo que se calienta mientras se transcribe debe ser el del prompt real."""
    memoria = MemoriaFalsa()
    cerebro = CerebroParker(
        config_llama={"modelo": "test", "historial_mensajes": 2},
        memoria=memoria,
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_memoria={"top_k_recuerdos": 1, "umbral_relevancia": 0.5,
                        "max_caracteres_recuerdo": 80},
    )
    cerebro._fecha_hora = staticmethod(lambda: "vie 17/10 14:40")  # sin carreras

    prefijo = cerebro._mensajes_prefijo()
    real = cerebro._construir_prompt("¿Qué tal?", recuerdos="[1] (2026-01-01) Algo")

    # El bloque volátil del prefijo aparece idéntico en el mensaje real; los
    # recuerdos se insertan antes de la instrucción de conversación.
    assert real[:len(prefijo) - 1] == prefijo[:-1], "el prefijo calentado no coincide"
    contenido_real = real[len(prefijo) - 1]["content"]
    assert prefijo[-1]["content"].split("\nInicio de conversación")[0] in contenido_real
    assert "Inicio de conversación" in contenido_real
    assert "Recuerdos:" in contenido_real
    print("[OK] prefijo precalentado = prefijo del prompt real")


def test_identidad_acotada():
    identidad = PersonalidadParker({"guardar_estado": False}).identidad()
    # Es el prefijo del prompt system que Ollama reevalúa EN CADA TURNO
    # (caché solo con coincidencia total): cada 100 chars ≈ 30 tok ≈ +0,1 s de
    # primer token. MEDIDO 24/10: 1850 chars = 600 tok; recortado a ~1670
    # añadiendo además la regla de «Recuerdos = pasado opcional».
    assert len(identidad) < 1700, f"la identidad vuelve a ser larga: {len(identidad)} caracteres"
    for obligatorio in ("Eres Parker", "QUIÉN ES QUIÉN", "TU CARÁCTER", "CONVERSACIÓN", "[CARA:...]"):
        assert obligatorio in identidad, obligatorio
    print(f"[OK] identidad acotada: {len(identidad)} caracteres")


def test_configuracion_rapida():
    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    llama = cfg["llama"]
    # Decisión del dueño 24/10: «útil y que tarde» — el 3b entiende contextos y
    # recuerdos; con num_ctx 2048 + identidad recortada su TTFB bajó a 2-3 s.
    # 01/11: el 3B daba turnos de ~12 s; el 2B bajó a p50 5,5 s y pasó 4/4
    # contextos en la placa. El 1,5B era más rápido pero incoherente.
    assert llama["modelo"] == "qwen3.5-local:2b", llama["modelo"]
    # Cota amplia (200): el dueño prioriza «útil y que tarde» sobre corto y
    # rápido; el corte real lo pone max_oraciones, no num_predict.
    assert int(llama["max_tokens"]) <= 200, llama["max_tokens"]
    # Corte por frases COMPLETAS. 3 desde el 24/10: el prompt pide dos frases
    # y con 5 el 3B divagaba; además cada frase extra son ~4 s en la placa.
    # 01/11: dos frases bastan para voz y recortan ~1/3 de la generación.
    assert int(llama["max_oraciones"]) == 2, llama["max_oraciones"]
    # 25/10: con el cerebro de la nube el prompt extra cuesta céntimos y el
    # contexto largo es lo que permite seguir el hilo; el local (respaldo) es
    # el único que paga reevaluarlo. Se admite 4 si algún día se vuelve a
    # 100 % local.
    assert int(llama["historial_mensajes"]) in (4, 8), llama["historial_mensajes"]
    assert float(llama["temperature"]) <= 0.5, llama["temperature"]
    assert float(llama["repeat_penalty"]) >= 1.1, llama["repeat_penalty"]
    # MEDIDO 24/10: prompt real ~1067 tok; con 1024 se recortaba contexto y
    # se reevaluaba entero cada turno. 2048 es el mínimo sin recorte.
    assert int(llama["num_ctx"]) == 2048, llama["num_ctx"]

    memoria = cfg["memoria"]
    assert int(memoria["top_k_recuerdos"]) == 3, memoria["top_k_recuerdos"]
    assert memoria["solo_recuerdos_usuario"] is True
    assert int(memoria["max_caracteres_recuerdo"]) <= 200, memoria["max_caracteres_recuerdo"]

    escucha = cfg["escucha"]
    assert escucha["modelo_faster"] == "base", escucha["modelo_faster"]
    assert float(escucha["silencio_corte_seg"]) <= 0.8, escucha["silencio_corte_seg"]
    # Front-end de audio y corpus STT (plan §2.1/§2.4, patrones de Rocky)
    assert float(escucha["pre_roll_seg"]) <= 0.5, "pre-roll largo alarga el turno"
    assert 0 < float(escucha["factor_umbral_voz"]) < 1, "histéresis debe BAJAR el umbral"
    assert 0 <= float(escucha["filtro_paso_alto_hz"]) <= 200, escucha["filtro_paso_alto_hz"]
    # 01/11: el prompt de Whisper está apagado a propósito (la nube devolvía
    # el prompt entero con audio poco claro). El nombre lo cubre `hotwords`,
    # que es lo que se exige; si algún día se enciende el prompt, debe
    # llevar el nombre y no órdenes.
    assert ("Parker" in (escucha.get("initial_prompt") or "")
            or "Parker" in (escucha.get("hotwords") or "")), \
        "el nombre no está ni en initial_prompt ni en hotwords"
    # 01/11: el corpus STT está activo para comparar `base` con `small`.
    assert escucha.get("volcar_audio_dir") == "./corpus_stt", escucha.get("volcar_audio_dir")
    assert escucha.get("vad_parameters") is None, "VAD a medida = parámetro de medición en placa"
    assert float(escucha.get("vad_rms_minimo", 0)) >= 0.001, \
        "sin mínimo de RMS, el AGC abre turnos con el ventilador"

    # 01/11: con la nube primaria, precargar el local no ahorra latencia y
    # llenaba la RAM (3 modelos, 5,3 GB, swap al 100 %). Se carga si falla.
    assert llama.get("precalentar", True) is False, \
        "precargar el local con la nube activa llena la RAM sin usarse"
    # 01/11: en local el prefijo tardaba 20 s y competía con el turno real
    # (timeouts de 30 s en el log de la placa). El 2B ya responde en ~3 s de
    # TTFB sin él; se prefiere no ahogar la CPU.
    assert llama.get("precalentar_turno", True) is False, \
        "en local el precalentado del prefijo cuesta más de lo que ahorra"
    assert int(llama["num_thread"]) == 4, "4 hilos fueron más rápidos que 3 en la placa"
    assert float(cfg["temperatura"]["aviso_c"]) == 70.0
    print("[OK] config.yaml mantiene rapidez y umbral térmico preventivo")


if __name__ == "__main__":
    test_recuerdos_compactos()
    test_cerebro_respeta_configuracion_de_memoria()
    test_prefijo_cacheable_entre_turnos()
    test_prefijo_precalentado_coincide()
    test_identidad_acotada()
    test_configuracion_rapida()
    print("\nTodos los tests de rendimiento han pasado.")
