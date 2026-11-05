"""
tests/test_pipeline.py
======================
Tests offline del pipeline de respuesta (sin Ollama, sin audio, sin hardware).

Ejecutar:  python tests/test_pipeline.py

Cubre:
  1. Corte de oraciones por streaming (dividir_oraciones)
  2. Extracción y limpieza de etiquetas [CARA:...]
  3. Stream del cerebro contra un servidor Ollama falso (NDJSON)
  4. La cola del orador: frases habladas en orden y sin etiquetas
"""

import json
import queue
import sys
import tempfile
import threading
import time
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import parker as P
from modulos.cerebro import CerebroParker


# ---------------------------------------------------------------- utilidades
class Senal:
    def __init__(self):
        self.valores = []

    def emit(self, valor):
        self.valores.append(valor)


class SenalesFalsas:
    def __init__(self):
        self.expresion = Senal()
        self.hablando = Senal()
        self.estado = Senal()


class VozFalsa:
    def __init__(self):
        self.hechas = []
        self.espera = 0.01
        self.marcas = []  # (evento, t, texto): para comprobar el look-ahead

    def sintetizar(self, texto, velocidad=None, volumen=None):
        self.marcas.append(("sintetizar", time.time(), texto))
        return texto

    def reproducir(self, audio, bloquear=True):
        self.marcas.append(("reproducir", time.time(), audio))
        time.sleep(self.espera)
        if isinstance(audio, str):
            self.hechas.append(audio)

    def hablar(self, texto, velocidad=None, volumen=None, bloquear=True):
        self.reproducir(self.sintetizar(texto), bloquear=bloquear)


class CerebroFalso:
    """Solo lo que usa el orador: la personalidad para el vocativo."""

    def __init__(self):
        from modulos.personalidad import PersonalidadParker
        self.personalidad = PersonalidadParker({"guardar_estado": False})
        self.historial = []


class MemoriaFalsa:
    def __init__(self):
        self.guardados = []

    def recuperar_recuerdos_formateados(self, consulta, top_k=5, umbral=0.5,
                                         max_caracteres=0):
        return "[1] (2026-01-01) Recuerdo viejo"

    def guardar_recuerdo(self, texto, metadata=None, tipo="interaccion", texto_embedding=None):
        self.guardados.append((texto, tipo, texto_embedding))


# ---------------------------------------------------------------- 1 y 2
def test_division_y_etiquetas():
    oraciones, resto = P.dividir_oraciones("[CARA:feliz] ¡Hola! ¿Qué tal? Todo bie")
    assert oraciones == ["[CARA:feliz] ¡Hola!", "¿Qué tal?"], oraciones
    assert resto == "Todo bie", resto

    oraciones, resto = P.dividir_oraciones("Sin fin de oración")
    assert oraciones == [] and resto == "Sin fin de oración"

    # Último fragmento sin espacio detrás: se queda para el flush final
    oraciones, resto = P.dividir_oraciones("Hola mundo.")
    assert oraciones == [] and resto == "Hola mundo."

    assert P.extraer_emocion("[CARA:feliz] hola") == "feliz"
    assert P.extraer_emocion("nada de etiquetas") is None
    assert P.extraer_emocion("[CARA:triste] a") == "triste"

    limpio = P.LIMPIAR_ETIQUETAS.sub("", "[CARA:pensando] Bueno, ya lo veo.").strip()
    assert limpio == "Bueno, ya lo veo.", limpio

    # qwen2.5:1.5b escribe a veces "[Cara: neutral]": si no se reconoce, la
    # etiqueta se colaría en el audio (visto en la placa).
    assert P.extraer_emocion("Buenas noches, [Cara: neutral].") == "neutral"
    limpio = P.limpiar_etiquetas("Buenas noches, [Cara: neutral]. Hasta mañana.")
    assert limpio == "Buenas noches. Hasta mañana.", limpio
    # Markdown: el TTS leería "asterisco asterisco cariño"
    assert P.limpiar_etiquetas("Hola, **cariño**. ¿Qué tal?") == "Hola, cariño. ¿Qué tal?"
    # Emoción suelta, sin "CARA:" (también la escriben los modelos pequeños)
    assert P.limpiar_etiquetas("[Neutral] Hola.") == "Hola."
    # Etiqueta SIN corchetes, en cualquier posición: el TTS la leía en voz
    # alta (visto en la placa 24/10: "[Parker -> Voz] CARA:pensando").
    limpio = P.limpiar_etiquetas("CARA:pensando. No tengo recuerdos tuyos.")
    assert limpio == "No tengo recuerdos tuyos.", limpio
    limpio = P.limpiar_etiquetas("Estoy bien. cara:bien ¿Y tú qué tal?")
    assert "cara:bien" not in limpio.lower() and "Estoy bien." in limpio, limpio
    # Cópula duplicada al presentarse (visto en la placa 24/10).
    assert P.limpiar_etiquetas("Soy Eres Parker, tu amigo.") == "Soy Parker, tu amigo."
    assert P.limpiar_etiquetas("Soy Parker.") == "Soy Parker."
    # Nota entre corchetes copiada del prompt (visto en la placa 24/10).
    assert P.limpiar_etiquetas("[Tutéame ] Ahora estoy aquí.") == "Ahora estoy aquí."
    # Etiqueta de interlocutor copiada de los ejemplos («Alan: Claro…»).
    assert P.limpiar_etiquetas("Alan: Claro que me acuerdo.") == "Claro que me acuerdo."
    print("[OK] división de oraciones y etiquetas (mayúsculas y minúsculas)")


# ---------------------------------------------------------------- 3
RESPUESTA_STREAM = ["[CARA:feliz] ¡Hola! ", "¿Qué tal? ", "Todo bien."]


class HandlerOllamaFalso(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        self.rfile.read(largo)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for trozo in RESPUESTA_STREAM:
            linea = json.dumps({"message": {"content": trozo}, "done": False})
            self.wfile.write((linea + "\n").encode("utf-8"))
        self.wfile.write(json.dumps({"message": {"content": ""}, "done": True}).encode("utf-8"))
        self.wfile.write(b"\n")

    def log_message(self, *args):
        pass


def test_cerebro_stream():
    servidor = HTTPServer(("127.0.0.1", 0), HandlerOllamaFalso)
    puerto = servidor.server_address[1]
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    memoria = MemoriaFalsa()
    from modulos.personalidad import PersonalidadParker
    perfil = PersonalidadParker({"guardar_estado": False})
    cerebro = CerebroParker(
        config_llama={"host": f"http://127.0.0.1:{puerto}", "modelo": "test"},
        memoria=memoria,
        personalidad=perfil,
    )

    deltas = list(cerebro.hablar_stream("¿Cómo estás?"))
    assert deltas == RESPUESTA_STREAM, deltas
    assert len(cerebro.historial) == 2, cerebro.historial
    # En el historial va el mensaje EXACTO enviado (ánimo + pregunta): si se
    # guardara limpio, el prefijo cambiaría y Ollama reprocesaría el historial
    # en cada turno (medido: +2-3 s al primer token).
    assert cerebro.historial[0]["content"].endswith("¿Cómo estás?"), cerebro.historial[0]
    assert "Ánimo" in cerebro.historial[0]["content"], cerebro.historial[0]
    # Un saludo/pregunta breve no es un recuerdo duradero; se filtra para no
    # contaminar Chroma con plantillas y transcripciones fugaces.
    assert len(memoria.guardados) == 0, memoria.guardados

    # Versión síncrona: aplica la MISMA cadena de limpieza que la voz (desde
    # el 24/10). A mitad de una charla, «¡Hola! ¿Qué tal?» es plantilla de
    # reinicio y no se dice: la vía en streaming ya lo hacía, la síncrona no.
    texto, etiquetas = cerebro.hablar("¿Otra vez?")
    assert texto == "Todo bien.", texto
    assert etiquetas == ["[CARA:feliz]"], etiquetas

    limpio, etiquetas = cerebro._extraer_etiquetas("[Cara: neutral] Buenas noches.")
    assert limpio == "Buenas noches.", limpio
    assert etiquetas == ["[Cara:neutral]"], etiquetas
    assert cerebro._emocion_de_etiquetas(etiquetas) == "neutral"

    servidor.shutdown()
    print("[OK] stream del cerebro contra Ollama falso")


# ---------------------------------------------------------------- 4
def _parker_falso():
    obj = P.Parker.__new__(P.Parker)
    obj.senales = SenalesFalsas()
    obj.ocupado = False
    obj.corriendo = True
    obj._sonando = False
    obj._lock_voz = threading.Lock()
    obj._cola_voz = queue.Queue()
    obj._cola_audio = queue.Queue()
    obj.voz = VozFalsa()
    obj.cerebro = CerebroFalso()
    obj.cerebro.historial = [{"role": "user", "content": "hola"},
                             {"role": "assistant", "content": "Buenas."}]
    threading.Thread(target=obj._bucle_orador, daemon=True).start()
    threading.Thread(target=obj._bucle_reproductor, daemon=True).start()
    return obj


def test_cola_orador():
    obj = _parker_falso()

    deltas = ["[CARA:feliz] ¡Hola! ", "¿Qué tal? ", "Todo bien."]
    obj._hablar_desde_generador(iter(deltas), emocion_inicial="pensando")

    assert obj.voz.hechas == ["Todo bien."], obj.voz.hechas
    assert "¿Qué tal?" not in obj.voz.hechas
    assert obj.ocupado is False
    assert obj._sonando is False

    # El orador tuvo que encender 'hablando' al empezar y apagarlo al final
    assert True in obj.senales.hablando.valores
    assert obj.senales.hablando.valores[-1] is False
    # La emoción de la etiqueta llegó a la cara
    assert "feliz" in obj.senales.expresion.valores
    # Ninguna etiqueta se coló en el audio
    assert not any("[CARA" in t for t in obj.voz.hechas)

    # Ruta síncrona (_hablar) por la misma cola
    obj.cerebro.historial = []
    obj._hablar("Frase única.", "triste")
    assert obj.voz.hechas[-1] == "Frase única."
    obj.cerebro.historial = [{"role": "user", "content": "hola"},
                             {"role": "assistant", "content": "Buenas."}]

    # El saludo no se repite, aunque incluya Parker en vocativo; se mantiene
    # la parte específica del mensaje.
    obj._hablar("¡Hola, Parker! Me acuerdo que has empezado el curso de dibujo.", "feliz")
    assert obj.voz.hechas[-1] == "Me acuerdo que has empezado el curso de dibujo.", obj.voz.hechas[-1]

    # Las fórmulas de saludo y los rellenos se eliminan antes de llamar a Piper,
    # preservando las respuestas concretas.
    obj.cerebro.historial = [{"role": "user", "content": "hola"},
                             {"role": "assistant", "content": "Buenas."}]
    obj._hablar("Estoy encantado de verte. La placa está a 60 grados.", "neutral")
    assert obj.voz.hechas[-1] == "La placa está a 60 grados.", obj.voz.hechas[-1]
    obj._hablar("Mmm...... Hoy es sábado, 17 de octubre.", "neutral")
    assert obj.voz.hechas[-1] == "Hoy es sábado, 17 de octubre.", obj.voz.hechas[-1]
    cuantas = len(obj.voz.hechas)
    obj._hablar("Mmm......", "neutral")
    assert len(obj.voz.hechas) == cuantas, obj.voz.hechas
    print("[OK] cola del orador: orden, limpieza, vocativo, rellenos y señales")


def test_serializacion_voz():
    """La escucha y la autonomía no deben solaparse en la voz."""
    obj = _parker_falso()

    def generador_lento():
        yield "Primera. "
        time.sleep(0.2)
        yield "Segunda. "

    threading.Thread(
        target=obj._hablar_desde_generador,
        args=(generador_lento(), "neutral"),
        daemon=True,
    ).start()

    time.sleep(0.05)  # la segunda intervención llega mientras la primera habla
    obj._hablar_desde_generador(iter(["Tercera. "]), "neutral")

    # Sin el lock, "Tercera" se encolaría entre "Primera" y "Segunda"
    assert obj.voz.hechas == ["Primera.", "Segunda.", "Tercera."], obj.voz.hechas
    print("[OK] serialización de la voz entre hilos")


def test_diagnostico_termico_usa_tipo_y_trips_reales():
    obj = P.Parker.__new__(P.Parker)
    obj.config = {"temperatura": {"aviso_c": 70}}
    obj._aviso_termico_activo = False
    with tempfile.TemporaryDirectory() as tmp:
        zona = Path(tmp) / "thermal_zone7"
        zona.mkdir()
        (zona / "type").write_text("cpu_big", encoding="ascii")
        (zona / "temp").write_text("60000", encoding="ascii")
        (zona / "trip_point_0_temp").write_text("85000", encoding="ascii")
        (zona / "trip_point_0_type").write_text("passive", encoding="ascii")
        lecturas = obj._comprobar_temperatura(tmp)
        assert lecturas == [{"zona": "thermal_zone7", "tipo": "cpu_big",
                             "celsius": 60.0, "trips": ["passive 85.0°C"]}], lecturas
        assert not obj._aviso_termico_activo
        (zona / "temp").write_text("72000", encoding="ascii")
        obj._comprobar_temperatura(tmp)
        assert obj._aviso_termico_activo
        (zona / "temp").write_text("60000", encoding="ascii")
        obj._comprobar_temperatura(tmp)
        assert not obj._aviso_termico_activo
    print("[OK] térmica: tipo y trip del kernel, alarma preventiva con histéresis")


def test_corte_por_oraciones_completas():
    """Límite de frases (Rocky: REPLY_MAX_SENTENCES): corta en frase entera,
    nunca a media palabra, y cierra el stream (ahorra tokens de Ollama)."""
    obj = _parker_falso()
    obj.config = {"llama": {"max_oraciones": 3}}
    cerrado = []

    def generador():
        try:
            for i in range(1, 8):
                yield f"Oración número {i}. "
        finally:
            cerrado.append(True)

    obj._hablar_desde_generador(generador(), emocion_inicial="neutral")
    assert obj.voz.hechas == ["Oración número 1.", "Oración número 2.",
                              "Oración número 3."], obj.voz.hechas
    assert cerrado, "el stream debe cerrarse al llegar al límite"
    assert obj.ocupado is False
    print("[OK] corte por oraciones completas + cierre del stream")


def test_resto_incompleto_no_se_dice():
    """Si num_predict corta a media palabra, el resto no suena truncado."""
    obj = _parker_falso()
    deltas = iter(["[CARA:neutral] Te cuento algo interesante. Y luego te cuen"])
    obj._hablar_desde_generador(deltas, emocion_inicial="neutral")
    assert obj.voz.hechas == ["Te cuento algo interesante."], obj.voz.hechas
    assert obj.ocupado is False
    print("[OK] el resto a media palabra se descarta en vez de sonar truncado")


def test_lookahead_orador():
    """La frase n+1 se sintetiza mientras la n suena (hueco muerto ≈ 0)."""
    obj = _parker_falso()
    obj.voz.espera = 0.3  # reproducir tarda 0,3 s: simula audio de esa duración
    deltas = ["Primera frase. ", "Segunda frase. ", "Tercera frase. "]
    obj._hablar_desde_generador(iter(deltas), emocion_inicial="neutral")
    sint = {m[2]: m[1] for m in obj.voz.marcas if m[0] == "sintetizar"}
    rep = {m[2]: m[1] for m in obj.voz.marcas if m[0] == "reproducir"}
    # Con la cadena vieja (sintetizar→sonar→sintetizar) la 2ª sintetización
    # ocurriría DESPUÉS de terminar de sonar la 1ª: la aserción fallaría.
    assert sint["Segunda frase."] < rep["Primera frase."] + obj.voz.espera * 0.9, \
        (sint, rep)
    assert obj.voz.hechas == ["Primera frase.", "Segunda frase.", "Tercera frase."]
    print("[OK] look-ahead: la frase n+1 se sintetiza mientras la n suena")


def test_frase_meta_no_llega_a_la_cola():
    """El filtro anti «pensar en voz alta» descarta la frase meta antes de Piper."""
    obj = _parker_falso()
    obj._hablar("[CARA:neutral] Déjame analizar esto. ¿Qué prefieres comer?",
                "neutral")
    assert obj.voz.hechas == ["¿Qué prefieres comer?"], obj.voz.hechas
    print("[OK] la frase meta no llega a la cola de voz")


def test_filtro_paso_alto():
    """High-pass 120 Hz: DC fuera, ronquido grave atenuado, voz intacta."""
    def filtrar(senales, hz=120):
        hp = P.FiltroPasoAlto(hz=hz, sample_rate=16000)
        salida = hp.procesar(senales.astype(np.float32))
        return salida[len(salida) // 2:]  # mitad estable, sin transitorio

    t = np.arange(3200) / 16000
    dc = np.ones(3200, dtype=np.float32)
    assert float(np.max(np.abs(filtrar(dc)))) < 0.05

    voz = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    rms_in = float(np.sqrt(np.mean(voz ** 2)))
    rms_out = float(np.sqrt(np.mean(filtrar(voz) ** 2)))
    assert rms_out > 0.9 * rms_in, (rms_in, rms_out)

    grave = (0.5 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
    rms_g = float(np.sqrt(np.mean(filtrar(grave) ** 2)))
    assert rms_g < 0.6 * float(np.sqrt(np.mean(grave ** 2))), rms_g

    assert P.FiltroPasoAlto(hz=0).procesar(dc) is dc  # hz=0 = desactivado
    print("[OK] high-pass: DC eliminado, voz intacta, ronquido grave atenuado")


def test_borrado_memoria_con_confirmacion():
    """Una orden no borra: la segunda, dentro de 60 s, sí."""
    p = P.Parker.__new__(P.Parker)
    p._memoria_borrado_hasta = 0.0
    dichos = []
    p._hablar = lambda texto, *a, **k: dichos.append(texto)

    class Memoria:
        borrados = 0

        def borrar_todos(self):
            Memoria.borrados += 1
            return 7

    class Cerebro:
        def __init__(self):
            self.historial = ["basura"]
            self._ultima_iniciativa = {"texto": "basura"}
            self.ultimo_mensaje_usuario = "basura"

    p.memoria = Memoria()
    p.cerebro = Cerebro()
    p._borrar_memoria()
    assert Memoria.borrados == 0, "la primera orden no puede borrar"
    assert "Seguro" in dichos[-1], dichos
    p._borrar_memoria()
    assert Memoria.borrados == 1, "la segunda orden debe borrar"
    assert p.cerebro.historial == [] and not p.cerebro._ultima_iniciativa
    assert "7" in dichos[-1], dichos
    print("[OK] borrado de memoria: confirma antes y limpia también el historial")


def test_vigilante_del_microfono():
    """Idea 8: silencio absoluto durante demasiado tiempo = rearmar el micro."""
    # Ruido de fondo normal: el micro está vivo, no hay nada que rearmar.
    assert P.mic_muerto(0.004, 300) is False
    # Silencio absoluto pero reciente: todavía no (puede ser una sala en calma).
    assert P.mic_muerto(0.0001, 10) is False
    # Silencio absoluto sostenido: el USB no está entregando audio.
    assert P.mic_muerto(0.0001, 100) is True
    assert P.mic_muerto(0.0001, 100, rearmar_seg=30) is True
    assert P.mic_muerto(0.0001, 20, rearmar_seg=30) is False
    print("[OK] vigilante del micrófono: rearma solo si el silencio es total")


if __name__ == "__main__":
    test_division_y_etiquetas()
    test_cerebro_stream()
    test_cola_orador()
    test_serializacion_voz()
    test_corte_por_oraciones_completas()
    test_resto_incompleto_no_se_dice()
    test_lookahead_orador()
    test_frase_meta_no_llega_a_la_cola()
    test_filtro_paso_alto()
    test_diagnostico_termico_usa_tipo_y_trips_reales()
    test_borrado_memoria_con_confirmacion()
    test_vigilante_del_microfono()
    print("\nTodos los tests del pipeline han pasado.")
