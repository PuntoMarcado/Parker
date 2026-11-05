"""
parker.py
Bucle principal de Parker con ESCUCHA CONTINUA AUTÓNOMA (VAD / Manos Libres)
y sincronización optimizada con el motor de animación Disney de cara_parker.py.
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import re
import signal
import subprocess
import sys
import queue
import threading
import time
from collections import deque
from pathlib import Path

try:
    import fcntl
except ImportError:          # Windows: el candado de instancia no hace falta
    fcntl = None

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Se guarda el fichero abierto para que el `flock` no se suelte mientras el
# proceso sigue vivo (ver `_tomar_lock_instancia`).
_LOCK_INSTANCIA = None

import yaml
import numpy as np
import sounddevice as sd

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget
)

from modulos.escucha import (EscuchaParker, parece_eco_del_prompt,
                             limpiar_marcas_prompt)
from modulos.filtro_stt import (es_alucinacion_conocida,
                               es_repeticion_sin_sentido,
                               es_transcripcion_dudosa)
from modulos.vad import VADSilero
from modulos.barge_in import es_eco_de_lo_hablado, parece_orden_de_parada
from modulos.cerebro import CerebroParker, limpiar_marcado, quitar_fugas_prompt
from modulos.hechos import HechosParker
from modulos.prosodia import ProsodiaParker
from modulos.voz import VozParker
from modulos.memoria import MemoriaParker
from modulos.personalidad import PersonalidadParker
from modulos.acciones import (
    AccionesParker,
    SONIDO_SILBIDO,
    interpretar_orden_cerebro,
    interpretar_orden_demo_cara,
    interpretar_orden_modo_completo,
    interpretar_orden_oido,
    interpretar_orden_voz,
)
from modulos.agenda import AgendaParker
from modulos.apuntes import ApuntesParker
from modulos.musica import MusicaParker, OyenteMusica
from modulos.rutinas import (ORDEN_APAGAR, ORDEN_BORRAR_MEMORIA,
                             ORDEN_DESPERTAR, ORDEN_DORMIR, ORDEN_REINICIAR,
                             RutinasParker)
from modulos.sonidos import silbar, despertador, micro_listo
from modulos.tiempo import TiempoParker
from modulos.cara_parker import FaceController, FACE_W, FACE_H, BG_BLACK
from modulos.version import etiqueta, linea_arranque

try:
    from modulos.display_spidev import GC9A01Display
except Exception as e:  # spidev/gpiod solo existen en la SBC Linux
    GC9A01Display = None
    print(f"[Display] Módulo SPI no disponible en este equipo: {e}")


# Patrones de etiquetas de estado que el cerebro inyecta ([CARA:feliz], ...)
# A-Za-z y no solo A-Z: los modelos pequeños escriben a veces "[Cara: neutral]"
# o la emoción suelta "[Neutral]". Si la etiqueta no se reconoce, se colaría en
# el audio (visto en la placa).
EMOCIONES = ("feliz", "triste", "pensando", "confundido", "sorpresa",
             "neutral", "escuchando", "carino")
PATRON_ETIQUETA = re.compile(r"\[\s*([A-Za-z_]+)\s*:\s*([^\]]*)\]")
LIMPIAR_ETIQUETAS = re.compile(
    r"\[\s*(?:[A-Za-z_]+\s*:\s*[^\]]*|" + "|".join(EMOCIONES) + r")\s*\]",
    re.IGNORECASE,
)
FIN_ORACION = re.compile(r"[.!?…]+\s+")


def limpiar_etiquetas(texto: str) -> str:
    """Quita [CARA:...] y los signos que quedan huérfanos al quitarla.

    Los modelos pequeños escriben la etiqueta en medio de la frase
    ("Buenas noches, [Cara: neutral]. Hasta mañana") y al limpiarla queda
    "Buenas noches, ." — que se oiría mal en voz alta.
    """
    # Primero el marcado duro (tokens <|channel|>, entidades HTML, vallas,
    # corchetes): con la nube apareció y Piper lo leía letra a letra (25/10).
    texto = limpiar_marcado(texto)
    # El modelo a veces copia el bloque de estado del prompt («100% (desde…,
    # 231 charlas). Estás hablando con Alan. mucha confianza.»): no se dice.
    texto = quitar_fugas_prompt(texto)
    texto = LIMPIAR_ETIQUETAS.sub("", texto)
    # Etiqueta SIN corchetes en cualquier posición ("CARA:pensando." al
    # inicio o "…y no sé qué decir. cara:bien" en medio): los modelos
    # pequeños la escriben y, sin este barrido, el TTS la leía en voz alta
    # (visto en la placa 24/10: "[Parker -> Voz] CARA:pensando").
    texto = re.sub(r"\[?\bCARA\s*:\s*[A-Za-zÁÉÍÓÚáéíóúñÑ]{1,20}\]?", "", texto,
                   flags=re.IGNORECASE)
    # Notas entre corchetes que el modelo repite del prompt ("[Tutéame como
    # siempre]", placa 24/10): el TTS las leería tal cual.
    texto = re.sub(r"\[[^\]\n]{1,60}\]", "", texto)
    # Etiqueta de interlocutor copiada de los ejemplos («Alan: Claro…»): el
    # TTS la leería como si empezara llamando a alguien.
    texto = re.sub(r"^\s*[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{1,15}:\s+", "", texto)
    # Un punto huérfano si la etiqueta se comía la frase entera (". No me…")
    texto = re.sub(r"^[.,;:]+\s*", "", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    # Markdown: los modelos pequeños escriben "**cariño**" y el TTS lo leería
    # como "asterisco asterisco cariño".
    texto = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", texto)
    texto = texto.replace("**", "").replace("__", "").replace("`", "")
    texto = re.sub(r"\s+([.,;:!?])", r"\1", texto)
    texto = re.sub(r",\s*([.!?])", r"\1", texto)
    # Copula duplicada al presentarse: el 3b mezcla el "Soy" de la respuesta
    # con el "Eres Parker" del prompt y suelta "Soy Eres Parker" (oído en la
    # placa 24/10).
    texto = re.sub(r"\b([Ss]oy)\s+[Ee]res\b", r"\1", texto)
    return texto.strip()


def dividir_oraciones(texto: str) -> tuple[list[str], str]:
    """
    Separa las oraciones COMPLETAS (acabadas en . ! ? … seguidas de espacio)
    del resto del texto aún incompleto que llega por streaming.
    Devuelve (oraciones_completas, resto_incompleto).
    """
    corte = None
    for m in FIN_ORACION.finditer(texto):
        corte = m.end()
    if corte is None:
        return [], texto
    completo, resto = texto[:corte], texto[corte:]
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?…])\s+", completo) if o.strip()]
    return oraciones, resto


def termina_frase(texto: str) -> bool:
    """¿El texto acaba en punto, signo de cierre o comillas? (fin de frase)

    El resto del stream solo se dicta si cumple esto: si `num_predict` cortó a
    media palabra, el trozo suena truncado y se descarta (Rocky descarta su
    `tail` incompleto por el mismo motivo).
    """
    t = (texto or "").rstrip().rstrip("\"'»)’”")
    return bool(t) and t[-1] in ".!?…"


def extraer_emocion(texto: str) -> str | None:
    """Devuelve la emoción de la última etiqueta [CARA:...] encontrada."""
    encontradas = PATRON_ETIQUETA.findall(texto)
    for nombre, contenido in reversed(encontradas):
        if nombre.upper() == "CARA":                return contenido.strip().lower() or None
    return None


class FiltroPasoAlto:
    """High-pass one-pole de 1.º orden (patrón de Rocky/desk-robot, MIT).

    Quita el DC y el ronquido por debajo de ~150 Hz (tele, ventilador) del RMS
    con el que se decide si alguien habla: menos activaciones falsas = menos
    turnos basura que Parker intenta contestar. Bucle por muestra sobre 1024
    muestras, ~16 bloques/s (~1 % de CPU), sin dependencias nuevas. hz=0 off.
    """

    def __init__(self, hz: float = 120.0, sample_rate: int = 16000):
        self.a = (1.0 / (1.0 + 2.0 * np.pi * hz / sample_rate)) if hz and hz > 0 else None
        self._x = 0.0
        self._y = 0.0

    def procesar(self, bloque) -> np.ndarray:
        """Filtra un bloque manteniendo el estado entre llamadas."""
        if self.a is None:
            return bloque
        a, x, y = self.a, self._x, self._y
        salida = np.empty(len(bloque), dtype=np.float32)
        for i, muestra in enumerate(bloque):
            y = a * (y + float(muestra) - x)
            x = float(muestra)
            salida[i] = y
        self._x, self._y = x, y
        return salida


def mic_muerto(ruido_piso: float, segundos_bajo: float,
               umbral: float = 0.0005, rearmar_seg: float = 90.0) -> bool:
    """¿La entrada de audio lleva demasiado tiempo en silencio absoluto?

    Idea 8 (26/10/2026): el fallo real que se vio en la placa no es que el
    micrófono dé error, es que se queda **entregando silencio** (índice de ALSA
    cambiado tras reiniciar, USB a medio conectar): Parker parece sordo y no
    hay ninguna excepción que lo delate. Cuando el ruido de fondo se queda
    plano (`< 0.0005`) durante más de `rearmar_seg`, el bucle de escucha cierra
    el flujo, vuelve a buscar el micrófono por nombre y lo abre de nuevo.
    """
    return ruido_piso < umbral and segundos_bajo >= rearmar_seg


class SenalesCara(QObject):
    expresion = Signal(str)
    hablando = Signal(bool)
    estado = Signal(str)
    # «Parker, apágate»: la cara se despide (se va de lado y se funde a negro)
    # y solo después se corta la corriente. El texto dice hacia dónde se marcha.
    despedida = Signal(str)
    # Dormir y despertar la cara (ojos cerrados, sin parpadeos de fondo).
    dormir = Signal(bool)
    # Deshacer la despedida si al final no se pudo apagar la placa. Lleva texto
    # (el motivo) porque las señales de Qt no aceptan `emit()` sin argumentos.
    reaparecer = Signal(str)
    # Cuánto lleva la persona sin hablarle, en segundos (lo manda el bucle de
    # autonomía): con eso la cara elige la familia de gestos de reposo
    # (despierto → solo → aburrido) y el ritmo de los parpadeos.
    silencio = Signal(int)
    # Modo demo: True = mostrar todas las expresiones y gestos; False = cortar.
    # La cara es la única que lo ejecuta; cerebro, oído y voz no se tocan.
    demo_cara = Signal(bool)


class ParkerWindow(QMainWindow):
    def __init__(self, senales: SenalesCara, pantalla_config: dict | None = None,
                 activar_display: bool = True):
        super().__init__()
        self.setWindowTitle("Parker AI")
        self.setStyleSheet("background-color: black;")

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()
        QApplication.setOverrideCursor(Qt.BlankCursor)

        central = QWidget()
        central.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene(0, 0, FACE_W, FACE_H)
        self.scene.setBackgroundBrush(QBrush(BG_BLACK))

        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("border: none; background-color: black;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Calidad vectorial: sin esto las curvas se rasterizan con "escalones".
        self.view.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setFrameStyle(0)
        self.view.setOptimizationFlags(QGraphicsView.DontSavePainterState)
        layout.addWidget(self.view, alignment=Qt.AlignCenter)

        self.estado_label = QLabel("Iniciando Parker...")
        self.estado_label.setStyleSheet("color: #444444; font-size: 16px; padding: 10px;")
        self.estado_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.estado_label)

        self.setCentralWidget(central)

        # En la placa se arranca con QT_QPA_PLATFORM=offscreen: no hay monitor y
        # la QGraphicsView repintaba 30 veces por segundo un lienzo que nadie
        # ve. En el PC de desarrollo pasó del 16,7 % al 0,6 % de un núcleo; en
        # la Orange Pi el ahorro es pequeño (6,9 % → 6,5 % en la prueba
        # aislada) porque esa vista ya no llegaba a pintarse, pero es trabajo
        # que sobra. La escena sigue igual y se envía por SPI.
        self._sin_ventana = QGuiApplication.platformName() == "offscreen"
        if self._sin_ventana:
            self.view.hide()
            self.estado_label.hide()

        # Controlador de cara vectorial con Alive Motion Engine y estilo Disney
        self.face = FaceController(self.scene)
        self.face.reproducir_intro()
        # Mientras la demo manda, las expresiones normales no deben pisarla.
        self._demo_cara_activa = False

        # Latido del hilo gráfico: si Qt se queda sin turno más de 1,5 s, queda
        # anotado con cuánto tiempo. Sin esto, un congelado de la cara y un
        # panel SPI atascado se ven igual en el log.
        self._ultimo_latido = time.monotonic()
        self._inicio_ui = self._ultimo_latido
        self._latido = QTimer(self)
        self._latido.setInterval(1000)
        self._latido.timeout.connect(self._latido_cara)
        self._latido.start()

        # Marca de versión: 6 s en la pantalla al arrancar, para saber de un
        # vistazo qué código corre en la placa (luego se va para no molestar).
        self._marca_version = None
        self._mostrar_version()

        if activar_display and GC9A01Display is not None:
            try:
                self.display = GC9A01Display(config=pantalla_config)
                self.display.attach_scene(self.scene)
                print("[Display] Pantalla SPI GC9A01 vinculada correctamente.")
            except Exception as e:
                print(f"[Error Display] No se pudo inicializar la pantalla SPI: {e}")
                self.display = None
        else:
            self.display = None

        # Conectar señales del sistema a la cara y a la interfaz
        senales.expresion.connect(self._actualizar_expresion)
        senales.hablando.connect(self._on_hablando)
        senales.estado.connect(self.estado_label.setText)
        senales.despedida.connect(self._despedida)
        senales.dormir.connect(self._dormir)
        senales.reaparecer.connect(self._reaparecer)
        senales.silencio.connect(self._recibir_silencio)
        senales.demo_cara.connect(self._demo_cara)

    def _latido_cara(self):
        ahora = time.monotonic()
        retraso = ahora - self._ultimo_latido - 1.0
        # Los primeros 90 s son el arranque: cargar embeddings y Whisper en
        # segundo plano retiene el GIL a ratos y no es un congelado de la cara.
        if retraso > 1.5 and ahora - self._inicio_ui > 90:
            print(f"[Cara] AVISO: el hilo de la interfaz estuvo bloqueado "
                  f"{retraso:.1f}s")
        self._ultimo_latido = ahora

    def closeEvent(self, event):
        self.face.detener()  # para los timers de la cara para salir limpiamente
        if hasattr(self, 'display') and self.display:
            self.display.close()
        event.accept()

    def _mostrar_version(self):
        """Pinta la versión en la base de la cara durante unos segundos."""
        texto = QGraphicsSimpleTextItem(etiqueta())
        texto.setFont(QFont("DejaVu Sans", 15))
        texto.setBrush(QBrush(QColor("#666666")))
        ancho = texto.boundingRect().width()
        texto.setPos((FACE_W - ancho) / 2, FACE_H - 46)
        self.scene.addItem(texto)
        self._marca_version = texto
        QTimer.singleShot(6000, self._ocultar_version)

    def _ocultar_version(self):
        if self._marca_version is not None:
            self.scene.removeItem(self._marca_version)
            self._marca_version = None

    def _actualizar_expresion(self, nombre_expresion: str):
        if self._demo_cara_activa:
            return
        self.face.set_expression(nombre_expresion.lower())

    def _on_hablando(self, activo: bool):
        if self._demo_cara_activa:
            return
        if activo:
            self.face.iniciar_habla()
        else:
            self.face.detener_habla()

    def _despedida(self, hacia: str):
        """«Parker, apágate»: última animación en pantalla antes de caer."""
        self._cancelar_demo_cara()
        self.estado_label.setText("Hasta luego.")
        self.face.despedida(hacia=hacia or "derecha")

    def _dormir(self, dormido: bool):
        self._cancelar_demo_cara()
        if dormido:
            self.face.dormirse()
        else:
            self.face.despertarse()

    def _reaparecer(self, motivo: str = ""):
        """No se pudo apagar: la cara vuelve a su sitio y Parker sigue vivo."""
        if motivo:
            print(f"[Apagado] Despedida deshecha ({motivo})")
        self._cancelar_demo_cara()
        self.face.reaparecer()
        self.estado_label.setText("")

    def _recibir_silencio(self, segundos: int):
        """El silencio alimenta el director de gestos en reposo de la cara."""
        self.face.set_silencio(max(0, int(segundos)))

    def _demo_cara(self, activo: bool):
        """Enciende o corta el modo demo pedido por voz."""
        if not activo:
            if self._demo_cara_activa:
                self._cancelar_demo_cara()
            return
        if self._demo_cara_activa:
            return
        self._demo_cara_activa = True
        self.estado_label.setText("Mostrando animaciones...")
        self.face.modo_demo(al_terminar=self._fin_demo_cara)

    def _fin_demo_cara(self):
        self._demo_cara_activa = False
        self.estado_label.setText("")

    def _cancelar_demo_cara(self):
        self._demo_cara_activa = False
        self.face.detener_demo()
        self.estado_label.setText("")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.face.detener()
            if hasattr(self, 'display') and self.display:
                self.display.close()
            QApplication.quit()


SECCIONES_OBLIGATORIAS = ("online", "llama", "escucha", "voz", "memoria",
                           "personalidad", "pantalla", "acciones", "agenda",
                           "rutinas", "apuntes", "tiempo", "musica")


def _revisar_secciones(config: dict) -> None:
    """Avisa de secciones que faltan (config incompleta = Parker a medias)."""
    faltan = [clave for clave in SECCIONES_OBLIGATORIAS if clave not in (config or {})]
    if faltan:
        print(f"[Config] AVISO: faltan secciones {faltan}; se usan valores por "
              "defecto y algunas funciones pueden no activarse.")


class Parker:
    # Los tests construyen Parker con `__new__` (sin __init__): el ánimo se
    # consulta siempre con getattr para que esa ruta siga funcionando.
    personalidad = None

    def __init__(self, senales: SenalesCara, config_path: str = "config.yaml"):
        self.senales = senales
        # Qué código corre en la placa, en la primera línea del log y en cada
        # respaldo. Sin esto hay que adivinar por fechas de fichero.
        print(linea_arranque())
        cfg_file = BASE_DIR / config_path if not os.path.isabs(config_path) else config_path
        self.config = self._cargar_config(cfg_file)
        _revisar_secciones(self.config)

        self.ocupado = False
        self.corriendo = True
        # Serializa quién habla: la escucha y el hilo de autonomía comparten la voz
        self._lock_voz = threading.Lock()

        self._ultima_interaccion_ts = time.time()
        # Borrado de memoria en dos pasos: la primera orden pregunta y la
        # segunda, dentro de 60 s, borra de verdad.
        self._memoria_borrado_hasta = 0.0

        # Barge-in (01/11/2026): mientras Parker habla, un monitor aparte
        # escucha una orden de parada. El evento lo consultan los dos hilos de
        # voz para no seguir sintetizando/reproduciendo lo que ya no se quiere.
        # `_barge_in_permitido` queda en False en los objetos de test creados
        # con `__new__`, que no tienen micrófono ni quieren abrir un stream.
        self._barge_in = threading.Event()
        self._barge_in_activo = False
        self._barge_in_permitido = True
        self._barge_in_hilo = None
        self._textos_sonando = deque(maxlen=3)
        # Generador de tokens que se está leyendo AHORA. El monitor de barge-in
        # lo cierra al oír «Parker, para»: si solo se marca el evento, el
        # `for delta in deltas` puede quedarse esperando al siguiente token
        # (visto en la placa el 01/11: la voz se cortaba y Parker no volvía a
        # escuchar nunca).
        self._stream_actual = None
        # Hook de prueba: con PARKER_TEST_BARGE=1, `kill -USR1 <pid>` simula el
        # corte sin depender del altavoz ni del micrófono. Sirve para verificar
        # que el turno se desbloquea y vuelve a escuchar.
        self._instalar_hook_barge()

        # Cargar Memoria
        config_mem = self.config.get("memoria", {})
        db_path_rel = config_mem.get("db_path", "./parker.db")
        db_path_abs = str(BASE_DIR / db_path_rel) if not os.path.isabs(db_path_rel) else db_path_rel
        self.memoria = MemoriaParker(
            db_path=db_path_abs,
            coleccion=config_mem.get("coleccion", "recuerdos_parker"),
            modelo_embeddings=config_mem.get("modelo_embeddings", "paraphrase-multilingual-MiniLM-L12-v2"),
            ruta_fts=(config_mem.get("ruta_fts") or None),
            hibrida=bool(config_mem.get("hibrida", True)),
        )

        # Hechos exactos (slots de datos dichos por la persona). Van al system
        # estable del cerebro, no a la recuperación: son tan pocos que no
        # necesitan búsqueda, y así no pagan prefill por turno.
        cfg_hechos = config_mem.get("hechos") or {}
        self.hechos = None
        if cfg_hechos.get("activo", True):
            ruta_h = str((cfg_hechos.get("ruta") or "./parker.hechos.db"))
            if not os.path.isabs(ruta_h):
                ruta_h = str(BASE_DIR / ruta_h)
            self.hechos = HechosParker(ruta=ruta_h)
            print(f"[Hechos] Tabla de hechos lista ({self.hechos.contar_activos()} "
                  "activos; van siempre con el prompt)")

        # Cargar Escucha
        cfg_esc = self.config.get("escucha", {})
        self.escucha = EscuchaParker(
            modelo=cfg_esc.get("modelo_whisper", "base"),
            idioma=cfg_esc.get("idioma", "es"),
            backend=cfg_esc.get("backend", "auto"),
            modelo_faster=cfg_esc.get("modelo_faster", "base"),
            beam_size=cfg_esc.get("beam_size", 1),
            vad_filter=cfg_esc.get("vad_filter", True),
            cpu_threads=cfg_esc.get("hilos_cpu"),
            hotwords=cfg_esc.get("hotwords"),
            initial_prompt=cfg_esc.get("initial_prompt"),
            vad_parameters=cfg_esc.get("vad_parameters"),
            volcar_dir=cfg_esc.get("volcar_audio_dir"),
            # STT: nube si hay red (0,68 s y texto exacto, medido 25/10),
            # local si falla (4,31 s con «base» y algún error).
            motor=cfg_esc.get("motor", "auto"),
            modelo_nube=cfg_esc.get("modelo_nube", "whisper-large-v3-turbo"),
            url_nube=cfg_esc.get("url_nube", "https://api.groq.com/openai/v1"),
            nombre_clave=cfg_esc.get("api_key_env", "GROQ_API_KEY"),
            timeout_nube=float(cfg_esc.get("timeout_nube_seg", 8.0)),
            reintento_nube_seg=float(cfg_esc.get("reintento_stt_seg", 60.0)),
        )
        print(f"[Escucha] Motor STT: {self.escucha.motor_preferido} "
              f"(nube: {self.escucha.modelo_nube})")

        # Cargar Personalidad (quién es Parker y cómo está hoy)
        config_pers = dict(self.config.get("personalidad") or {})
        ruta_estado = config_pers.get("ruta_estado")
        if ruta_estado and not os.path.isabs(ruta_estado):
            config_pers["ruta_estado"] = str(BASE_DIR / ruta_estado)
        self.personalidad = PersonalidadParker(config_pers)
        print(f"[Personalidad] {self.personalidad.resumen_para_log()}")

        # Cargar Cerebro (la personalidad construye su prompt de sistema)
        self.cerebro = CerebroParker(
            config_llama=self.config.get("llama"),
            memoria=self.memoria,
            personalidad=self.personalidad,
            config_memoria=config_mem,
            config_online=self.config.get("online"),
            hechos=self.hechos,
        )

        # Prosodia del turno (señal DÉBIL de ánimo): features básicas de cada
        # frase y tendencia contra la línea base de la propia persona. Solo
        # sirve para decidir si preguntar «cómo va la semana»; nada más.
        cfg_pros = self.config.get("prosodia") or {}
        self.prosodia = None
        if cfg_pros.get("activo", True):
            ruta_p = str(cfg_pros.get("ruta") or "./parker.prosodia.db")
            if not os.path.isabs(ruta_p):
                ruta_p = str(BASE_DIR / ruta_p)
            self.prosodia = ProsodiaParker(
                ruta=ruta_p,
                dias_recientes=int(cfg_pros.get("dias_recientes", 3)),
                dias_base=int(cfg_pros.get("dias_base", 14)))
            # La personalidad consulta la tendencia al elegir su pregunta de
            # iniciativa; si no hay datos, no cambia nada.
            self.personalidad.senal_prosodia = self._senal_prosodia

        # Cargar Voz
        config_voz = self.config.get("voz", {})
        v_path_rel = config_voz.get("modelo_piper", "./assets/voz/es_ES-davefx-medium.onnx")
        v_path_abs = str(BASE_DIR / v_path_rel) if not os.path.isabs(v_path_rel) else v_path_rel

        cfg_v_rel = config_voz.get("modelo_config")
        cfg_v_abs = str(BASE_DIR / cfg_v_rel) if (cfg_v_rel and not os.path.isabs(cfg_v_rel)) else cfg_v_rel

        self.voz = VozParker(
            modelo_path=v_path_abs,
            config_path=cfg_v_abs,
            velocidad=config_voz.get("velocidad", 1.0),
            volumen=config_voz.get("volumen", 0.9),
            motor=config_voz.get("motor", "piper"),
            edge_voz=config_voz.get("edge_voz", "es-ES-XimenaNeural"),
            edge_timeout=float(config_voz.get("edge_timeout_seg", 8.0)),
            edge_reintento_seg=float(config_voz.get("edge_reintento_seg", 60.0)),
            edge_ffmpeg=config_voz.get("edge_ffmpeg", "ffmpeg"),
        )

        # Modo completo (cerebro + oído + voz) guardado por voz: se restaura
        # después de crear los tres componentes. Si no hay fichero, se respeta
        # lo que diga config.yaml y `parker.cerebro.json` (comportamiento de
        # antes). El fichero evita que un reinicio devuelva la voz a Edge
        # cuando el dueño pidió quedarse 100 % local.
        cfg_modo = self.config.get("modo") or {}
        ruta_modo = cfg_modo.get("ruta_estado", "parker.modo.json")
        self.ruta_modo_completo = (Path(ruta_modo) if os.path.isabs(ruta_modo)
                                   else BASE_DIR / ruta_modo)
        self._restaurar_modo_completo()

        # Órdenes directas («baja el volumen», «silencia», «silba»): se ejecutan
        # aquí, sin LLM, y se confirman con una frase corta.
        cfg_acc = self.config.get("acciones") or {}
        ruta_vol = cfg_acc.get("ruta_volumen", "parker.volumen.json")
        self.acciones = AccionesParker(
            voz=self.voz,
            ruta_volumen=str(BASE_DIR / ruta_vol) if not os.path.isabs(ruta_vol) else ruta_vol,
            paso=float(cfg_acc.get("paso_volumen", 0.15)),
            volumen_min=float(cfg_acc.get("volumen_min", 0.05)),
            volumen_max=float(cfg_acc.get("volumen_max", 0.9)),
        )
        print(f"[Acciones] Volumen de voz: {self.acciones.porcentaje()} % "
              "(«baja el volumen», «silencia», «silba»)")

        # Agenda (alarmas, temporizadores y citas): se apunta sin LLM y el aviso
        # lo dispara un hilo propio (campana por el altavoz + frase).
        cfg_agenda = self.config.get("agenda") or {}
        ruta_agenda = cfg_agenda.get("ruta_agenda", "parker.agenda.json")
        self.agenda = AgendaParker(
            ruta_agenda=(str(BASE_DIR / ruta_agenda)
                         if not os.path.isabs(ruta_agenda) else ruta_agenda),
            hora_citas=str(cfg_agenda.get("hora_citas", "09:00")),
            caducidad_horas=float(cfg_agenda.get("caducidad_horas", 12)),
        )
        print(f"[Agenda] {len(self.agenda.avisos)} avisos guardados "
              "(«pon una alarma a las 7», «avísame en 10 minutos»)")

        # Rutinas del día: dormir, despertar, callarse un rato y apagarse.
        cfg_rut = self.config.get("rutinas") or {}
        self.rutinas = RutinasParker(
            hora_parte=str(cfg_rut.get("hora_parte", "08:30")),
            parte_si_vacio=bool(cfg_rut.get("parte_si_vacio", False)),
        )
        print(f"[Rutinas] Parte del día a las {cfg_rut.get('hora_parte', '08:30')}; "
              "«buenas noches», «cállate diez minutos», «apágate»")

        # Apuntes sin hora: notas, listas y contadores («litros de agua»).
        cfg_ap = self.config.get("apuntes") or {}
        ruta_ap = cfg_ap.get("ruta_apuntes", "parker.apuntes.json")
        self.apuntes = ApuntesParker(
            ruta_apuntes=(str(BASE_DIR / ruta_ap) if not os.path.isabs(ruta_ap)
                          else ruta_ap),
            dias_conservar=int(cfg_ap.get("dias_conservar", 60)),
        )
        print(f"[Apuntes] {len(self.apuntes.notas)} notas y "
              f"{len(self.apuntes.contadores)} contadores guardados "
              "(«apunta un litro de agua», «¿cuánta agua llevo hoy?»)")

        # El tiempo (Open-Meteo, sin clave) con la ciudad como variable: se
        # cambia por voz («estamos en Madrid») y se guarda en la placa.
        cfg_tiem = self.config.get("tiempo") or {}
        ruta_ciudad = cfg_tiem.get("ruta_ciudad", "parker.tiempo.json")
        self.tiempo = TiempoParker(
            ciudad=str(cfg_tiem.get("ciudad") or "Barcelona"),
            ruta_ciudad=(str(BASE_DIR / ruta_ciudad)
                         if not os.path.isabs(ruta_ciudad) else ruta_ciudad),
            latitud=cfg_tiem.get("latitud"),
            longitud=cfg_tiem.get("longitud"),
            cache_seg=float(cfg_tiem.get("cache_seg", 600)),
        )
        print(f"[Tiempo] Ciudad: {self.tiempo.zona()} "
              "(se cambia diciendo «estamos en …»)")

        # Música por orden de voz: búsqueda en Deezer (sin clave) y adelantos
        # de 30 s decodificados con ffmpeg. La reproducción vive en su hilo.
        cfg_mus = self.config.get("musica") or {}
        # 01/11: el dueño pide quitar funciones extra (música) hasta arreglar
        # el audio. Se queda el objeto para reconocer la orden y contestar
        # «está desactivada», pero no se arranca su hilo ni se reproduce nada.
        self.musica_activa = bool(cfg_mus.get("activo", True))
        self.musica = MusicaParker(
            volumen=float(cfg_mus.get("volumen", 0.7)),
            max_segundos=float(cfg_mus.get("max_segundos", 40)),
            duck_factor=float(cfg_mus.get("duck_factor", 0.15)),
        )
        # Distingue la voz de la canción cuando algo suena por encima (ver
        # modulos/musica.OyenteMusica): «bajar la música y mirar».
        self.oyente_musica = OyenteMusica(
            factor_disparo=float(cfg_mus.get("factor_disparo", 1.2)),
            chunk_seg=1024 / 16000.0,
        )
        self.musica_temas_seguidos = int(cfg_mus.get("temas_seguidos", 3))
        self._cola_musica: queue.Queue = queue.Queue()
        self._parar_musica = threading.Event()
        self.musica_sonando = False
        self.hilo_musica = threading.Thread(target=self._loop_musica, daemon=True)
        if self.musica_activa:
            self.hilo_musica.start()
            print(f"[Música] Lista: «pon algo de Queen», «para la música», "
                  f"«baja el volumen» con música sonando "
                  f"(volumen {self.musica.porcentaje()} %; te oigo por encima)")
        else:
            print("[Música] Desactivada (musica.activo: false); no se "
                  "reproduce ni se busca nada.")

        # Orador a dos etapas (look-ahead estilo Rocky): _cola_voz lleva texto
        # por sintetizar y _cola_audio audio listo por sonar, así la frase n+1
        # se sintetiza mientras la n suena y desaparece el hueco muerto de
        # Piper entre frases (0,2-0,5 s medidos).
        self._cola_voz: queue.Queue = queue.Queue()
        self._cola_audio: queue.Queue = queue.Queue()
        self._sonando = False
        self.hilo_voz = threading.Thread(target=self._bucle_orador, daemon=True)
        self.hilo_voz.start()
        self.hilo_audio = threading.Thread(target=self._bucle_reproductor, daemon=True)
        self.hilo_audio.start()

        # No reproducir un saludo fijo en cada inicio: abre el micrófono en
        # silencio y responde de forma contextual a la primera interacción.
        print("[Parker] Voz preparada; inicio sin saludo prefabricado.")

        # El micrófono se abre PRIMERO. Antes se cargaba el LLM antes de
        # escuchar (55 s medidos en la placa) y en ese rato Parker no oía nada:
        # «lo enciendo, le hablo y no reacciona» (25/10). Escuchar no depende
        # del modelo, así que no tiene por qué esperar.
        self.hilo_escucha = threading.Thread(target=self._bucle_escucha_continua, daemon=True)
        self.hilo_escucha.start()

        # El modelo (nube o local) se prepara después y en segundo plano.
        if self.config.get("llama", {}).get("precalentar", True):
            threading.Thread(target=self._precalentar_cerebro, daemon=True).start()

        self.hilo_autonomia = threading.Thread(target=self._loop_autonomia, daemon=True)
        self.hilo_autonomia.start()

        # Los avisos de la agenda se vigilan aparte y cada segundo: un
        # temporizador de 3 minutos no puede depender del latido de autonomía.
        self.hilo_agenda = threading.Thread(target=self._loop_agenda, daemon=True)
        self.hilo_agenda.start()

    def _cargar_config(self, path) -> dict:
        """Lee config.yaml y AVISA si está roto.

        Antes el error se tragaba y Parker seguía con valores por defecto sin
        cerebro ni claves (pasó el 25/10 con una línea de comentario mal
        indentada): parecía «no coger el contexto» cuando en realidad no había
        configuración. Un fallo así tiene que verse en el log.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Config] ERROR: config.yaml inválido ({e})")
            print("[Config] Parker sigue con valores POR DEFECTO: revisa la"
                  " indentación; sin config no hay cerebro ni pantalla.")
            return {}

    def _emitir(self, nombre_senal: str, valor):
        getattr(self.senales, nombre_senal).emit(valor)

    def _precalentar_cerebro(self):
        """Comprueba la nube y deja cargado el respaldo local (en segundo plano).

        El retraso configurable (`llama.precalentar_retraso_seg`) evita que la
        carga del modelo local compita con el STT del primer turno.
        """
        retraso = float((self.config.get("llama") or {}).get("precalentar_retraso_seg", 25))
        if retraso > 0:
            time.sleep(retraso)
        # Cargar el modelo local son ~55 s de CPU: si hay alguien charlando, se
        # espera (medido 25/10: un turno con la carga en marcha tardó 29 s en
        # transcribir y 2,85 s en el primer token).
        while self.corriendo and time.time() - self._ultima_interaccion_ts < 60:
            time.sleep(5)
        segundos = self.cerebro.calentar()
        estado = self.cerebro.estado_cerebro()
        print(f"[Cerebro] Listo en {segundos:.1f}s | motor: {estado['motor']} "
              f"({estado['modelo']})")
        if self.cerebro.online_activo:
            # El respaldo tiene que estar caliente ANTES de necesitarlo: si cae
            # internet, la primera frase local no debe pagar la carga del modelo.
            self.cerebro._calentar_local()
            print("[Cerebro] Respaldo local cargado en memoria (por si falla internet).")

    def _emocion_desde_etiquetas(self, etiquetas: list[str]) -> str | None:
        for tag in etiquetas:
            match = re.match(r"\[\s*([A-Za-z_]+)\s*:\s*([^\]]*)\]", tag)
            if match and match.group(1).upper() == "CARA":
                return match.group(2).strip().lower()
        return None

    def _instalar_hook_barge(self) -> None:
        """Instala `SIGUSR1` como barge-in simulado, solo en pruebas.

        No se activa por defecto: hay que arrancar con `PARKER_TEST_BARGE=1`.
        Así se puede comprobar en la placa que, tras el corte, el turno se
        desbloquea y Parker vuelve a escuchar, sin depender de que el altavoz
        del PC llegue al micrófono.
        """
        if os.environ.get("PARKER_TEST_BARGE") != "1":
            return
        senal = getattr(signal, "SIGUSR1", None)
        if senal is None:
            return
        try:
            signal.signal(senal, self._barge_prueba)
        except (ValueError, OSError):
            pass

    def _barge_prueba(self, *_args) -> None:
        print("[Barge-in] Simulado por SIGUSR1 (solo prueba)")
        self._barge_in.set()
        self.voz.detener()
        # No se cierra el generador desde aquí: `close()` sobre un generador
        # que otro hilo está leyendo puede bloquearse o lanzar «generator
        # already executing». El hilo lector ve el evento y abandona; es la
        # vía que funciona.

    def _barge_in_pedido(self) -> bool:
        """¿El monitor de barge-in ha pedido cortar la voz?"""
        evento = getattr(self, "_barge_in", None)
        return bool(evento is not None and evento.is_set())

    def _cancelar_stream_actual(self) -> None:
        """Cierra el generador de tokens en curso para desbloquear el turno.

        `_barge_in` solo se consulta al recibir un token. Si el modelo se
        queda callado a mitad de respuesta, el hilo principal seguiría
        esperando dentro de `for delta in deltas` y Parker no volvería a
        escuchar. Cerrar el generador es la única forma de interrumpirlo.
        """
        stream = getattr(self, "_stream_actual", None)
        if stream is None:
            return
        cerrar = getattr(stream, "close", None)
        if cerrar is None:
            return
        try:
            cerrar()
        except Exception as e:
            print(f"[Barge-in] No pude cerrar el stream del cerebro: {e}")

    def _bucle_orador(self, cola_voz=None, cola_audio=None):
        """
        Hilo de SÍNTESIS: convierte texto en audio y lo deja en la cola audio.
        No reproduce: mientras este hilo sintetiza la frase n+1, el hilo de
        reproducción está sonando la n (look-ahead; antes la cadena
        sintetizar→sonar→sintetizar dejaba un hueco muerto en cada frase).

        Las colas se pasan como argumento para poder abandonar un hilo colgado
        tras un barge-in: el hilo viejo termina en sus colas viejas y uno nuevo
        atiende las nuevas (visto en la placa el 01/11 con Edge).
        """
        cola_voz = cola_voz or self._cola_voz
        cola_audio = cola_audio or self._cola_audio
        while self.corriendo:
            item = cola_voz.get()
            try:
                if item is None:
                    continue
                if self._barge_in_pedido():
                    print("[Barge-in] (síntesis pendiente descartada)")
                    continue
                texto, emocion = item
                if texto == SONIDO_SILBIDO:
                    # No es texto: es un efecto real por el altavoz.
                    audio = silbar(volumen=self.voz.volumen)
                else:
                    audio = self.voz.sintetizar(texto)
                if self._barge_in_pedido():
                    print("[Barge-in] (audio sintetizado descartado)")
                    continue
                cola_audio.put((audio, emocion, texto))
            except Exception as e:
                print(f"[Error voz] {e}")
            finally:
                cola_voz.task_done()

    def _bucle_reproductor(self, cola_audio=None):
        """Hilo de REPRODUCCIÓN: suena el audio ya sintetizado, en orden."""
        cola_audio = cola_audio or self._cola_audio
        while self.corriendo:
            item = cola_audio.get()
            try:
                if item is None:
                    continue
                if self._barge_in_pedido():
                    print("[Barge-in] (audio pendiente descartado)")
                    continue
                audio, emocion, texto = item
                if not self._sonando:
                    self._sonando = True
                    self._emitir("hablando", True)
                if emocion:
                    self._emitir("expresion", emocion)
                # Se imprime AQUÍ (no al encolar): es el momento real en que
                # suena, y así el log refleja lo que Parker dice de verdad.
                # ASCII a propósito: en Windows el print de "→" reventaba el
                # hilo y SE PERDÍA el audio (visto en tests locales).
                # El marcador del silbido es interno: al log va como «(silba)»
                # y nunca como el byte NUL (hacía binario el fichero de log).
                visible = "(silba)" if texto == SONIDO_SILBIDO else texto
                print(f"[Parker -> Voz] {visible}")
                textos = getattr(self, "_textos_sonando", None)
                if textos is not None:
                    textos.append(visible)
                self.voz.reproducir(audio, bloquear=True)
            except Exception as e:
                print(f"[Error voz] {e}")
            finally:
                cola_audio.task_done()

    @staticmethod
    def _esperar_cola(cola: queue.Queue, timeout: float) -> bool:
        """Espera a que una cola termine sin bloquearse para siempre."""
        limite = time.time() + max(0.1, timeout)
        while cola.unfinished_tasks and time.time() < limite:
            time.sleep(0.02)
        return cola.unfinished_tasks == 0

    def _reiniciar_canales_voz(self) -> None:
        """Abandona los hilos de voz colgados y arranca unos limpios.

        El hilo viejo queda en sus colas viejas (daemon): si Edge termina
        alguna vez, su audio se descarta y no vuelve a contaminar el turno. El
        turno siguiente usa colas y hilos nuevos.
        """
        if not getattr(self, "corriendo", False):
            return
        self._cola_voz = queue.Queue()
        self._cola_audio = queue.Queue()
        self.hilo_voz = threading.Thread(
            target=self._bucle_orador,
            args=(self._cola_voz, self._cola_audio), daemon=True)
        self.hilo_audio = threading.Thread(
            target=self._bucle_reproductor,
            args=(self._cola_audio,), daemon=True)
        self.hilo_voz.start()
        self.hilo_audio.start()

    def _transcribir_barge_in(self, audio) -> str:
        """Transcribe una ventana del monitor sin guardarla en el corpus STT.

        El corpus es para voz del usuario; aquí se oye sobre todo la voz de
        Parker por el altavoz, así que no debe acabar en `corpus_stt`.
        """
        escucha = getattr(self, "escucha", None)
        if escucha is None:
            return ""
        volcar = getattr(escucha, "volcar_dir", None)
        try:
            escucha.volcar_dir = None
            texto = escucha.transcribir(audio)
            # El monitor oye sobre todo a Parker: las alucinaciones típicas
            # («¡Suscríbete al canal!», «Gracias.») y los bloques repetidos no
            # deben llegar al log ni a la decisión de corte.
            if (es_alucinacion_conocida(texto)
                    or es_repeticion_sin_sentido(texto)):
                return ""
            return texto
        except Exception as e:
            print(f"[Barge-in] STT no pudo transcribir: {e}")
            return ""
        finally:
            escucha.volcar_dir = volcar

    def _vigilar_barge_in(self):
        """Escucha mientras Parker habla y corta si oye «Parker, para».

        No es un segundo bucle de conversación: solo transcribe ventanas cortas
        y decide parar. Si el micro está ocupado o el audio no abre, sale en
        silencio y el turno normal sigue funcionando.
        """
        cfg = (getattr(self, "config", {}) or {}).get("barge_in", {}) or {}
        cfg_esc = (getattr(self, "config", {}) or {}).get("escucha", {}) or {}
        sr = 16000
        chunk = 1024
        ventana_seg = max(0.8, float(cfg.get("ventana_seg", 1.4)))
        solape_seg = max(0.0, min(ventana_seg - 0.2,
                                float(cfg.get("solape_seg", 0.4))))
        frames_ventana = max(4, int(ventana_seg * sr / chunk))
        frames_solape = max(0, int(solape_seg * sr / chunk))
        umbral_rms = float(cfg.get("umbral_rms", 0.004))
        umbral_eco = float(cfg.get("similitud_eco", 0.55))
        indice = self._resolver_microfono(cfg_esc, esperar_seg=0)
        try:
            with sd.InputStream(samplerate=sr, channels=1, dtype=np.float32,
                                device=indice) as stream:
                buffer = []
                while (self.corriendo
                       and getattr(self, "_barge_in_activo", False)
                       and not self._barge_in_pedido()):
                    data, _ = stream.read(chunk)
                    data = data.ravel().astype(np.float32)
                    buffer.append(data)
                    if len(buffer) < frames_ventana:
                        continue

                    audio = np.concatenate(buffer)
                    buffer = buffer[-frames_solape:] if frames_solape else []
                    rms = float(np.sqrt(np.mean(audio ** 2)))
                    if rms < umbral_rms:
                        continue

                    texto = self._transcribir_barge_in(audio)
                    if not texto or not getattr(self, "_barge_in_activo", False):
                        continue
                    # Primero el eco: si la propia voz de Parker suena como
                    # «Parker, para», no debe cortarse a sí misma.
                    if es_eco_de_lo_hablado(
                            texto, list(getattr(self, "_textos_sonando", [])),
                            umbral_eco):
                        continue
                    if parece_orden_de_parada(texto):
                        print(f"[Barge-in] «{texto[:60]}» -> corto la voz")
                        self._barge_in.set()
                        self.voz.detener()
                        # El hilo lector de `_deltas_con_corte` ve el evento y
                        # abandona; no se cierra el generador desde aquí.
                        self._emitir("expresion", "neutral")
                        break
                    # No se imprime cada frase oída: mientras Parker habla, el
                    # micro capta sobre todo su propia voz y llenaría el log.
                    # Solo llega aquí una frase distinta que no es orden.
        except Exception as e:
            # No es un fallo del turno: simplemente no habrá barge-in esta vez.
            print(f"[Barge-in] No pude escuchar mientras hablo: {e}")

    def _corregir_vocativo(self, texto: str) -> str:
        """Quita el "Parker" mal dicho al dirigirse a la persona.

        `qwen2.5:1.5b` se equivoca de vez en cuando y saluda a su amigo con el
        nombre de Parker (visto en la placa: "¡Hola, Parker!", "¿Y tú, Parker,
        ...?"). Se corrige antes de sintetizar, sin depender del modelo.
        """
        personalidad = getattr(getattr(self, "cerebro", None), "personalidad", None)
        if not texto or personalidad is None:
            return texto
        return personalidad.corregir_nombre(texto)

    def _preparar_frase(self, texto: str, emocion: str,
                        filtrar_inventos: bool = False) -> tuple[str, str] | None:
        """Deja una frase del stream lista para la cola de voz.

        Quita etiquetas [CARA:...], corrige el vocativo y las fórmulas de
        plantilla, y descarta las frases meta del modelo (no se dicen ni se
        refuerzan — filtro `_thinking_aloud` de Rocky). Devuelve (frase,
        emoción) o None si no queda nada que decir.
        """
        frase = self._corregir_vocativo(limpiar_etiquetas(texto)).strip()
        # Solo la salida del modelo: la agenda y las acciones dicen cosas que
        # SÍ han pasado («he guardado tu alarma») y no se pueden tirar.
        if filtrar_inventos and frase and getattr(self, "cerebro", None) is not None:
            frase = self.cerebro._quitar_inventos(frase)
        personalidad = getattr(getattr(self, "cerebro", None), "personalidad", None)
        if personalidad is not None and frase:
            historial = getattr(getattr(self, "cerebro", None), "historial", [])
            frase = personalidad.limpiar_frases_plantilla(
                frase, conversacion_en_curso=bool(historial))
            if frase and personalidad.es_frase_meta(frase):
                print(f"[Parker] (no dicha, meta) {frase}")
                frase = ""
        # Sin una sola letra no hay nada que decir: restos de marcado («...»,
        # ««»», comillas sueltas) solo harían que Piper articulara ruido.
        if not frase or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", frase):
            return None
        return (frase, emocion)

    def _deltas_con_corte(self, deltas):
        """Lee el stream del cerebro en otro hilo para poder abandonarlo.

        `requests` puede quedarse bloqueado esperando el siguiente token. Si el
        bucle principal itera el generador directamente, la orden «Parker,
        para» no se atiende hasta que llegue ese token (o venza el timeout de
        lectura) y Parker sigue sin escuchar. El hilo lector es daemon: si se
        abandona, muere con el proceso sin bloquear el turno siguiente.
        """
        cola = queue.Queue(maxsize=32)

        def _leer():
            try:
                for delta in deltas:
                    while True:
                        if not getattr(self, "corriendo", True):
                            return
                        try:
                            cola.put(delta, timeout=0.2)
                            break
                        except queue.Full:
                            if self._barge_in_pedido():
                                return
            except Exception as e:
                if not self._barge_in_pedido():
                    print(f"[Cerebro] El stream se cortó: {e}")
            finally:
                try:
                    cola.put(None, timeout=0.5)
                except queue.Full:
                    pass

        threading.Thread(target=_leer, daemon=True).start()
        while True:
            if not getattr(self, "corriendo", True) or self._barge_in_pedido():
                return
            try:
                delta = cola.get(timeout=0.2)
            except queue.Empty:
                continue
            if delta is None:
                return
            yield delta

    def _hablar(self, texto: str, emocion: str = "neutral", motor: bool = True,
                filtrar_inventos: bool = False):
        """Habla un texto ya completo y espera a que termine de reproducirse."""
        self._hablar_desde_generador(iter([texto]), emocion, motor=motor,
                                     filtrar_inventos=filtrar_inventos)

    def _hablar_desde_generador(self, deltas, emocion_inicial: str = "neutral",
                                motor: bool = True, filtrar_inventos: bool = False):
        """
        Recibe un iterador de fragmentos de texto (salida en streaming del
        cerebro) y va encolando frases completas al orador.

        La primera frase empieza a sonar en cuanto el modelo la termina, sin
        esperar a que termine de generar la respuesta entera.
        """
        with self._lock_voz:
            self._hablar_stream_interno(deltas, emocion_inicial, motor=motor,
                                        filtrar_inventos=filtrar_inventos)

    def _hablar_stream_interno(self, deltas, emocion_inicial: str, motor: bool = True,
                               filtrar_inventos: bool = False):
        # Turno nuevo: se limpia cualquier corte del barge-in anterior. Si no,
        # la primera frase de este turno se descartaría en `sintetizar()` y
        # Parker seguiría mudo después de «para».
        voz = getattr(self, "voz", None)
        preparar = getattr(voz, "preparar_turno", None)
        if callable(preparar):
            preparar()
        self.ocupado = True
        self._emitir("estado", "")
        # Se guardan las colas de ESTE turno. Si el barge-in obliga a
        # reiniciar los canales, este turno termina en las suyas y el
        # siguiente usa unas nuevas.
        cola_voz = self._cola_voz
        cola_audio = self._cola_audio

        emocion = emocion_inicial
        emocion_vista = False
        pendiente = ""
        t_inicio = time.time()
        t_primer_dato = None
        t_primer_habla = None
        # Límite de frases COMPLETAS por respuesta (Rocky: REPLY_MAX_SENTENCES).
        # Cortar en frase entera evita hablar a media palabra y ahorra los
        # tokens que Ollama seguiría generando para nada.
        cfg = getattr(self, "config", None) or {}
        max_oraciones = int(cfg.get("llama", {}).get("max_oraciones", 3) or 0)
        encoladas = 0
        cortado = False

        # Barge-in: un hilo aparte escucha mientras este turno suena. Solo se
        # activa en producción (`_barge_in_permitido`) y si config lo permite;
        # los tests con `__new__` no abren micrófono. El evento se limpia al
        # empezar para no arrastrar un corte del turno anterior.
        textos_sonando = getattr(self, "_textos_sonando", None)
        if textos_sonando is not None:
            textos_sonando.clear()
        barge_cfg = (getattr(self, "config", {}) or {}).get("barge_in", {}) or {}
        if (getattr(self, "_barge_in_permitido", False)
                and barge_cfg.get("activo", True)):
            evento = getattr(self, "_barge_in", None)
            if evento is not None:
                evento.clear()
            if not getattr(self, "_barge_in_avisado", False):
                print("[Barge-in] monitor activo mientras Parker habla")
                self._barge_in_avisado = True
            self._barge_in_activo = True
            self._barge_in_hilo = threading.Thread(
                target=self._vigilar_barge_in, daemon=True)
            self._barge_in_hilo.start()

        try:
            self._stream_actual = deltas
            for delta in self._deltas_con_corte(deltas):
                if self._barge_in_pedido():
                    print("[Barge-in] corto también el stream del cerebro")
                    self._cancelar_stream_actual()
                    break
                if not delta:
                    continue
                if t_primer_dato is None:
                    t_primer_dato = time.time()
                    print(f"[Latencia] Primer token del cerebro: {t_primer_dato - t_inicio:.2f}s")
                pendiente += delta

                if not emocion_vista:
                    encontrada = extraer_emocion(pendiente)
                    if encontrada:
                        emocion = encontrada
                        emocion_vista = True

                oraciones, pendiente = dividir_oraciones(pendiente)
                for oracion in oraciones:
                    # Sin etiqueta [CARA:...] aún, la cara pasa a neutral
                    # (así no se queda en "pensando" mientras habla)
                    frase = self._preparar_frase(
                        oracion, emocion if emocion_vista else "neutral",
                        filtrar_inventos=filtrar_inventos)
                    if not frase:
                        continue
                    cola_voz.put(frase)
                    encoladas += 1
                    if t_primer_habla is None:
                        t_primer_habla = time.time()
                        print(f"[Latencia] Fin de frase lista para hablar: "
                              f"{t_primer_habla - t_inicio:.2f}s")
                    if max_oraciones and encoladas >= max_oraciones:
                        cortado = True
                        break
                if cortado:
                    break

            if self._barge_in_pedido():
                cortado = True
            if cortado:
                print(f"[Parker] (corte en {encoladas} frases completas; "
                      "lo que quede no se dice ni se genera)")
                # No se cierra aquí el generador: el hilo lector puede estar
                # dentro de él y `close()` desde otro hilo lanza «generator
                # already executing» (visto en la placa). Se abandona; el
                # lector es daemon y muere con el proceso.
            else:
                # Resto final (la última frase puede no llevar espacio detrás)
                resto = self._preparar_frase(
                    pendiente, emocion if emocion_vista else "neutral",
                    filtrar_inventos=filtrar_inventos)
                if resto:
                    # Solo se dice si termina la frase: si num_predict cortó a
                    # media palabra, el trozo suena truncado. Si no se ha dicho
                    # nada todavía, es la respuesta entera y se dicta igual.
                    if termina_frase(resto[0]) or not encoladas:
                        cola_voz.put(resto)
                    else:
                        print(f"[Parker] (resto incompleto descartado) «{resto[0]}»")

        finally:
            if getattr(self, "_stream_actual", None) is deltas:
                self._stream_actual = None
            # Espera a que el orador termine de SINTETIZAR y de REPRODUCIR
            # todo: sin la segunda espera, un turno nuevo se colaría en
            # mitad del anterior.
            if self._barge_in_pedido():
                # Edge puede quedarse colgado en una síntesis que ya no
                # interesa. No se espera para siempre: si en 2 s no ha
                # terminado, se abandonan esos canales y se abren otros.
                sintesis_ok = self._esperar_cola(cola_voz, 2.0)
                audio_ok = self._esperar_cola(cola_audio, 2.0)
                if not (sintesis_ok and audio_ok):
                    print("[Barge-in] La voz no terminó; reinicio los canales "
                          "de síntesis y reproducción.")
                    self._reiniciar_canales_voz()
            else:
                cola_voz.join()
                cola_audio.join()
            # El monitor se para ANTES de soltar `ocupado`: si siguiera vivo
            # podría abrir el micro a la vez que el bucle principal y dejar
            # «Device unavailable». Si estaba transcribiendo, se le da 2 s;
            # es daemon y comprobará `_barge_in_activo` antes de actuar.
            self._barge_in_activo = False
            hilo_barge = getattr(self, "_barge_in_hilo", None)
            if hilo_barge is not None:
                # 5 s, no 2: si el monitor está transcribiendo la última
                # ventana, el InputStream sigue abierto y el bucle principal
                # recibe «Device unavailable» al volver a escuchar (visto en
                # la placa el 01/11 tras una prueba de voz).
                hilo_barge.join(timeout=5.0)
                if hilo_barge.is_alive():
                    print("[Barge-in] El monitor sigue ocupado; el micro "
                          "puede tardar un instante en reabrirse.")
                self._barge_in_hilo = None
            evento = getattr(self, "_barge_in", None)
            if evento is not None:
                evento.clear()
            self._sonando = False
            # 01/11: el micro USB está pegado al altavoz y, al terminar de
            # hablar, el VAD oía la cola de la propia frase y Parker se
            # contestaba a sí mismo (visto en el log: dos respuestas seguidas
            # a «son las 6 y 34»). Este sello abre un enfriamiento de 0,9 s
            # antes de volver a escuchar.
            self._fin_habla_ts = time.time()
            self._emitir("hablando", False)
            self._emitir("expresion", "neutral")
            self._emitir("estado", "")
            self.ocupado = False
            # Qué cerebro contestó este turno: en el log y sin adivinar.
            cerebro = getattr(self, "cerebro", None)
            estado_cerebro = getattr(cerebro, "estado_cerebro", None)
            # Un reflejo (fecha, hora, nombre, orden de volumen) no llama al
            # modelo: decir «motor del turno: nube» ahí solo confunde el log.
            if motor and callable(estado_cerebro):
                estado = estado_cerebro()
                print(f"[Cerebro] Motor del turno: {estado['motor']} "
                      f"({estado['modelo']})")

    def _resolver_microfono(self, cfg_escucha: dict, esperar_seg: float = 0.0):
        """Micrófono a usar, por NOMBRE ("usb") y no por índice.

        Tras reiniciar la placa cambian los índices de ALSA y el 25/10 Parker
        se quedó escuchando el códec interno en silencio absoluto («le hablo y
        no reacciona») mientras el micro USB seguía conectado. Buscar por
        nombre lo resuelve solo, incluso si se desenchufa y se vuelve a poner.

        `esperar_seg` cubre el arranque en frío: el micro USB tarda ~20-30 s
        en enumerar y PortAudio cachea su lista al importar. Sin refrescarla,
        Parker abre el códec interno y se queda sordo hasta reiniciarlo.
        """
        preferencia = cfg_escucha.get("dispositivo_entrada")
        if preferencia is None:
            return None
        if isinstance(preferencia, int):
            return preferencia
        texto = str(preferencia).strip().lower()
        if not texto:
            return None

        def buscar():
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0 and texto in str(dev["name"]).lower():
                    if getattr(self, "_micro_elegido", "") != texto:
                        self._micro_elegido = texto
                        self._micro_aviso = ""
                        print(f"[Escucha] Micrófono elegido por nombre: "
                              f"[{i}] {dev['name']}")
                    return i
            return None

        try:
            indice = buscar()
        except Exception as e:
            print(f"[Escucha] No pude listar los micrófonos: {e}")
            return None
        if indice is not None:
            return indice

        limite = time.time() + max(0.0, float(esperar_seg))
        avisado_espera = False
        while True:
            if not avisado_espera:
                if esperar_seg > 0:
                    print(f"[Escucha] Esperando al micrófono «{texto}»: el USB "
                          "puede tardar en aparecer tras el arranque…")
                avisado_espera = True
            # PortAudio no ve un dispositivo que aparezca después del arranque
            # hasta que se reinicializa: esto es lo que hace útil el rearme.
            try:
                sd._terminate()
                sd._initialize()
            except Exception as e:
                print(f"[Escucha] No pude refrescar el audio: {e}")
            try:
                indice = buscar()
            except Exception as e:
                print(f"[Escucha] No pude listar los micrófonos: {e}")
                return None
            if indice is not None:
                return indice
            if time.time() >= limite:
                break
            time.sleep(0.5)

        if getattr(self, "_micro_aviso", "") != texto:
            self._micro_aviso = texto
            print(f"[Escucha] AVISO: ningún micrófono contiene «{texto}»; "
                  "uso el dispositivo por defecto del sistema.")
        return None

    def _bucle_escucha_continua(self):
        """Escucha continua autónoma usando umbral VAD por volumen y silencio"""
        cfg_escucha = self.config.get("escucha", {})
        # Umbral de voz ADAPTATIVO. Con un umbral fijo, en una sala silenciosa
        # (ruido de fondo 0,001) cualquier conversación lejana lo supera y Parker
        # contesta a quien no le habla; midiendo el ruido de fondo y exigiendo
        # varios fragmentos seguidos de voz, eso deja de pasar.
        umbral_base = float(cfg_escucha.get("umbral_silencio", 0.02))
        factor_ruido = float(cfg_escucha.get("factor_ruido", 3.5))
        duracion_minima = float(cfg_escucha.get("duracion_minima_seg", 0.8))
        chunks_voz_minimos = int(cfg_escucha.get("chunks_voz_minimos", 6))
        ruido_piso = umbral_base / factor_ruido
        # Silencio que cierra el turno. Antes 1,3 s fijos: cada décima aquí se
        # suma a TODAS las respuestas (medido: se nota al hablar).
        tiempo_silencio_corte = float(cfg_escucha.get("silencio_corte_seg", 0.6))
        # Front-end de audio (patrones de Rocky): pre-roll para no perder la
        # 1ª sílaba, histéresis para no cortar la última, high-pass sin ronquido.
        pre_roll_seg = float(cfg_escucha.get("pre_roll_seg", 0.3))
        factor_umbral_voz = float(cfg_escucha.get("factor_umbral_voz", 0.7))

        # VAD neuronal (Silero v6, ya incluido en faster-whisper) + AGC. El
        # umbral por volumen se queda como respaldo si el modelo no carga.
        # Medido en la placa (01/11): una frase al 5 % de nivel daba 0,09 de
        # probabilidad sin AGC y 0,34-0,58 con AGC; el ruido de sala sigue por
        # debajo de 0,10. Por eso el umbral de inicio es 0,18 y no 0,5.
        umbral_vad_inicio = float(cfg_escucha.get("vad_umbral_inicio", 0.18))
        umbral_vad_mantener = float(cfg_escucha.get("vad_umbral_mantener", 0.10))
        # 01/11: el AGC x6 convertía el ruido de sala (0,0017-0,0026 de RMS) en
        # «voz» para Silero y abría turnos vacíos cada pocos segundos. La voz
        # real, incluso de lejos, deja más señal bruta; este mínimo no la corta.
        rms_minimo_vad = float(cfg_escucha.get("vad_rms_minimo", 0.0035))
        vad = None
        if str(cfg_escucha.get("vad_motor", "silero")).lower() != "rms":
            vad = VADSilero(
                agc_objetivo=float(cfg_escucha.get("agc_objetivo", 0.12)),
                agc_alfa=float(cfg_escucha.get("agc_alfa", 0.2)),
                agc_max_ganancia=float(cfg_escucha.get("agc_max_ganancia", 6.0)),
            )
            if vad.disponible:
                print(f"[Escucha] VAD Silero activo (inicio {umbral_vad_inicio:.2f}, "
                      f"mantener {umbral_vad_mantener:.2f}, rms mínimo "
                      f"{rms_minimo_vad:.4f}, AGC x"
                      f"{float(cfg_escucha.get('agc_max_ganancia', 6.0)):.0f}).")
            else:
                print(f"[Escucha] VAD Silero no disponible ({vad.ultimo_error}); "
                      "uso el VAD por volumen.")
                vad = None

        sample_rate = 16000
        chunk_frames = 1024
        hp = FiltroPasoAlto(float(cfg_escucha.get("filtro_paso_alto_hz", 120)),
                           sample_rate=sample_rate)
        # Últimos ~0,3 s oídos antes de detectar voz (5 bloques ≈ 320 ms).
        pre_roll: deque = deque(
            maxlen=max(1, round(pre_roll_seg * sample_rate / chunk_frames)))
        # Para avisar en el log si lleva demasiado rato sin oír nada: es la
        # diferencia entre «Parker está roto» y «el micro USB no está».
        sin_voz_desde = time.time()
        # Vigilante del micrófono (idea 8): si la entrada se queda entregando
        # silencio absoluto (USB a medio conectar, índice de ALSA cambiado tras
        # un reinicio), se rearma sola en vez de esperar a que alguien reinicie
        # la placa a mano.
        rearmar_seg = float(cfg_escucha.get("rearmar_mic_seg", 90))
        muerto_desde = 0.0
        rearmes = 0
        # El micro USB puede tardar ~25 s en enumerar tras el arranque; la cara
        # ya está en pantalla. Se espera solo en el primer intento y, cuando
        # el oído queda abierto, un chime corto avisa de que ya se puede hablar.
        primer_intento_mic = True
        avisado_listo = False
        # Con música sonando, el pre-roll es más largo: cuando el «duck»
        # confirma que hay una persona, su frase ya empezó hace un momento.
        pre_roll_musica_seg = float(cfg_escucha.get("pre_roll_musica_seg", 1.1))
        pre_roll_musica: deque = deque(
            maxlen=max(1, round(pre_roll_musica_seg * sample_rate / chunk_frames)))
        # Corte del turno con la música bajada: el «duck» deja la canción en
        # `duck_factor`, así que todo lo que esté por encima de eso es voz.
        umbral_rel_musica = max(0.3, self.musica.duck_factor * 1.6)

        print("[Escucha] Bucle continuo activo. Esperando voz humana "
              f"(umbral base {umbral_base:.3f}, adaptativo x{factor_ruido:.1f} sobre el ruido de fondo)...")

        while self.corriendo:
            if self.ocupado:
                time.sleep(0.1)
                continue
            # 01/11: no reabrir el micro justo al acabar de hablar. Si no, el
            # VAD capta la reverberación del altavoz y Parker se responde solo.
            # 0,9 s no bastaba: el log mostraba turnos vacíos justo después de
            # cada respuesta. 2 s dejan pasar la cola de la sala.
            if time.time() - getattr(self, "_fin_habla_ts", 0.0) < 2.0:
                time.sleep(0.1)
                continue

            # 1. Fase de espera pasiva hasta detectar voz
            buffer_audio = []
            detectado_hablando = False
            seguidos = 0
            chunks_voz = 0
            pre_roll.clear()
            if vad is not None:
                vad.reiniciar()
            umbral = max(umbral_base, ruido_piso * factor_ruido)

            esperar_mic = (float(cfg_escucha.get("esperar_micro_seg", 25))
                           if primer_intento_mic else 0.0)
            primer_intento_mic = False
            indice_mic = self._resolver_microfono(cfg_escucha,
                                                 esperar_seg=esperar_mic)
            if indice_mic is not None and not avisado_listo:
                print("[Escucha] Micrófono listo; aviso sonoro.")
                self.voz.reproducir(
                    micro_listo(volumen=float(
                        cfg_escucha.get("aviso_micro_volumen", 0.35))),
                    bloquear=True)
                avisado_listo = True
            try:
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.float32,
                    device=indice_mic
                ) as stream:

                    # Esperar inicio de voz. El pre-roll guarda siempre los
                    # últimos ~0,3 s: la 1ª sílaba (donde vive «Parker») ya no
                    # se recorta al abrir turno.
                    while self.corriendo and not self.ocupado:
                        data, _ = stream.read(chunk_frames)
                        data = hp.procesar(data.ravel().astype(np.float32))
                        rms = float(np.sqrt(np.mean(data**2)))
                        pre_roll.append(data)
                        pre_roll_musica.append(data)

                        # --- Modo música (27/10/2026) ------------------------
                        # El micrófono oye la canción, así que el umbral va
                        # relativo a su nivel y el turno solo se abre cuando el
                        # «duck» confirma que quien sobresale es una PERSONA
                        # (no el estribillo). Mientras suena, esta rama manda.
                        if self.musica_sonando:
                            seguidos = 0
                            sin_voz_desde = time.time()
                            ahora_esc = time.time()
                            if rms > 0.0005:
                                muerto_desde = 0.0
                            elif not muerto_desde:
                                muerto_desde = ahora_esc
                            if muerto_desde and mic_muerto(
                                    0.0001, ahora_esc - muerto_desde,
                                    rearmar_seg=rearmar_seg):
                                rearmes += 1
                                print(f"[Escucha] Entrada de audio muerta "
                                      f"({rms:.5f}) con la música sonando "
                                      f"durante {rearmar_seg:.0f}s: rearmo el "
                                      f"micrófono (rearme nº {rearmes}).")
                                self._micro_elegido = ""
                                muerto_desde = 0.0
                                if vad is not None:
                                    vad.reiniciar()
                                self.oyente_musica.reiniciar()
                                self._duck_musica(False)
                                break
                            aviso = self.oyente_musica.observar(rms)
                            if aviso == "probar":
                                self._duck_musica(True)
                            elif aviso == "musica":
                                self._duck_musica(False)
                            elif aviso == "voz":
                                print("[Escucha] Por encima de la música: es "
                                      "una persona; abro turno")
                                detectado_hablando = True
                                chunks_voz = chunks_voz_minimos
                                # El pre-roll de música es más largo: la frase
                                # empezó mientras sonaba la canción.
                                buffer_audio = list(pre_roll_musica)
                                umbral = max(
                                    umbral_base,
                                    self.oyente_musica.piso * umbral_rel_musica)
                                break
                            continue
                        if self.oyente_musica.probando or self.musica.duck:
                            # La música se paró a mitad de la comprobación.
                            self.oyente_musica.reiniciar()
                            self._duck_musica(False)

                        prob_voz = (vad.procesar(data)
                                    if vad is not None else None)
                        hay_voz = ((prob_voz >= umbral_vad_inicio
                                    and rms >= rms_minimo_vad)
                                   if prob_voz is not None else rms > umbral)
                        if hay_voz:
                            seguidos += 1
                            sin_voz_desde = time.time()
                            # Dos fragmentos seguidos (~130 ms): un golpe suelto o
                            # una tos ya no abren conversación.
                            if seguidos >= 2:
                                detectado_hablando = True
                                chunks_voz += 2
                                if prob_voz is not None:
                                    print(f"[Escucha] Voz detectada por VAD "
                                          f"(p={prob_voz:.2f}, rms={rms:.4f}, "
                                          f"AGC x{vad.ultima_ganancia:.1f}).")
                                # El pre-roll completo ya es parte del turno:
                                # la 1ª sílaba se conserva.
                                buffer_audio = list(pre_roll)
                                break
                        else:
                            seguidos = 0
                            # Solo el silencio actualiza el ruido de fondo
                            ruido_piso = 0.9 * ruido_piso + 0.1 * rms
                            umbral = max(umbral_base, ruido_piso * factor_ruido)
                            # ¿Lleva demasiado tiempo en silencio absoluto?
                            ahora_esc = time.time()
                            if ruido_piso < 0.0005:
                                if not muerto_desde:
                                    muerto_desde = ahora_esc
                            else:
                                muerto_desde = 0.0
                            if mic_muerto(ruido_piso, ahora_esc - muerto_desde if muerto_desde else 0.0,
                                          rearmar_seg=rearmar_seg):
                                rearmes += 1
                                print(f"[Escucha] Entrada de audio muerta "
                                      f"({ruido_piso:.5f}) durante {rearmar_seg:.0f}s: "
                                      f"rearmo el micrófono (rearme nº {rearmes}).")
                                self._micro_elegido = ""
                                muerto_desde = 0.0
                                if vad is not None:
                                    vad.reiniciar()
                                break
                            if time.time() - sin_voz_desde > 600:
                                sin_voz_desde = time.time()
                                pista = (" Revisa el micro USB: si el nivel es este, "
                                         "no está llegando audio." if ruido_piso < 0.0005 else "")
                                print(f"[Escucha] 10 min sin oír voz (ruido de fondo "
                                      f"{ruido_piso:.4f}, umbral {umbral:.3f}).{pista}")

                    if not detectado_hablando or self.ocupado:
                        continue

                    # 2. Fase de grabación activa (mientras habla)
                    self._emitir("expresion", "escuchando")
                    self._emitir("estado", "Escuchando...")
                    # Aprovechamos el tiempo en que el usuario habla para dejar
                    # cacheado en Ollama el prefijo del turno (ánimo + hora +
                    # historial). Se lanza AQUÍ y no al transcribir: si compite
                    # con Whisper, el STT sube de 1,5 s a 2-3 s (medido). Así el
                    # prompt real solo evalúa recuerdos + pregunta y el primer
                    # token baja de ~2,3 s a ~0,6-1,3 s sin coste.
                    threading.Thread(target=self.cerebro.precalentar_turno,
                                     daemon=True).start()

                    ultimo_sonido_ts = time.time()
                    inicio_grabacion = time.time()
                    max_duracion = cfg_escucha.get("duracion_maxima_grabacion", 15)
                    # Histéresis (Rocky rebaja el umbral al oír voz): ya sabemos
                    # que hay alguien hablando, así que las sílabas suaves de
                    # cierre cuentan como voz y no cierran el turno antes de
                    # tiempo.
                    umbral_voz = umbral * factor_umbral_voz
                    motivo_corte = "silencio de cierre"

                    while self.corriendo and not self.ocupado:
                        data, _ = stream.read(chunk_frames)
                        data = hp.procesar(data.ravel().astype(np.float32))
                        buffer_audio.append(data)

                        rms = float(np.sqrt(np.mean(data**2)))
                        ahora = time.time()
                        prob_voz = (vad.procesar(data)
                                    if vad is not None else None)
                        sigue_hablando = (prob_voz >= umbral_vad_mantener
                                          if prob_voz is not None
                                          else rms > umbral_voz)

                        if sigue_hablando:
                            ultimo_sonido_ts = ahora
                            chunks_voz += 1

                        # Si ha pasado el silencio de corte o se excede el máximo
                        if (ahora - ultimo_sonido_ts) > tiempo_silencio_corte:
                            motivo_corte = f"silencio {tiempo_silencio_corte:.1f}s"
                            break
                        if (ahora - inicio_grabacion) > max_duracion:
                            motivo_corte = f"duración máxima {max_duracion:.0f}s"
                            break

            except Exception as e:
                print(f"[Error Stream Audio] {e}")
                time.sleep(0.5)
                continue

            # 3. Procesar el audio grabado
            if not buffer_audio:
                continue

            audio_total = np.concatenate(buffer_audio, axis=0).flatten()
            duracion_seg = len(audio_total) / sample_rate
            # Por qué cortó el turno (Rocky imprime lo mismo): sin esto, tunear
            # el VAD en la placa es a ciegas.
            print(f"[Escucha] Corte: {motivo_corte}; {duracion_seg:.1f}s de audio, "
                  f"{chunks_voz} chunks de voz")

            # Prosodia ANTES de normalizar por pico: si se normalizara, la
            # altura (RB del RMS) perdería el sentido entre turnos y la
            # tendencia de días no sería comparable. Es barato (pocos ms).
            if getattr(self, "prosodia", None) is not None:
                try:
                    medidas = self.prosodia.registrar(audio_total, sample_rate)
                    if medidas:
                        f0 = medidas.get("f0_hz")
                        print(f"[Prosodia] rms={medidas['rms_db']:.1f}dB "
                              f"f0={f0:.0f}Hz" if f0 else
                              f"[Prosodia] rms={medidas['rms_db']:.1f}dB "
                              "f0=n/a")
                except Exception as e:
                    print(f"[Prosodia] No pude registrar el turno: {e}")

            # Descartar ruidos: ni demasiado cortos ni con poca voz sostenida
            # (así una puerta o un cajón no se confunden con una frase).
            if duracion_seg < duracion_minima or chunks_voz < chunks_voz_minimos:
                self._emitir("expresion", "neutral")
                self._emitir("estado", "")
                continue

            self.ocupado = True
            self._emitir("expresion", "pensando")
            self._emitir("estado", "Pensando...")

            # Normalización
            pico = np.max(np.abs(audio_total))
            if pico > 0:
                audio_total = audio_total / pico

            try:
                t_turno = time.time()
                t_stt = time.time()
                texto = self.escucha.transcribir(audio_total)
                t_stt_fin = time.time()
                print(f"[Latencia] STT: {t_stt_fin - t_stt:.2f}s "
                      f"({getattr(self.escucha, 'ultimo_motor', 'local')})")
                # 01/11: Whisper puede devolver el initial_prompt. Si trae
                # comillas angulares, no es voz: se ignora antes de ejecutar
                # órdenes (así se coló «cambia el cerebro al local»).
                if parece_eco_del_prompt(texto):
                    print(f"[Escucha] Eco del prompt de sesgo; ignoro: {texto!r}")
                    texto = ""
                if texto:
                    # Una comilla suelta del prompt no invalida la frase: se
                    # quita. Antes se descartaba el turno entero y Parker
                    # parecía sordo (01/11, 20:39).
                    texto = limpiar_marcas_prompt(texto)
                if texto:
                    # 02/11: el micro está pegado al altavoz y el eco de la
                    # propia respuesta se colaba como turno («oído local,
                    # oído local»). Solo se compara dentro de la ventana en
                    # la que el eco es físicamente posible y con umbral alto:
                    # una paráfrasis de la persona no se descarta.
                    if (time.time() - getattr(self, "_fin_habla_ts", 0.0)
                            <= 12.0
                            and es_eco_de_lo_hablado(
                                texto,
                                list(getattr(self, "_textos_sonando", [])),
                                0.72)):
                        print(f"[Escucha] Eco de la propia voz; ignoro: {texto!r}")
                        texto = ""
                if texto:
                    # Whisper, sobre todo con ruido o la cola del altavoz,
                    # inventa frases («Gracias por ver el video», «¡Ah! ¡Ah!
                    # ¡Ah!»). Se descartan antes de ejecutar órdenes o llamar
                    # al cerebro; si no, Parker contesta a la tele.
                    if es_transcripcion_dudosa(
                            texto,
                            getattr(self.escucha, "ultimo_no_speech", None),
                            getattr(self.escucha, "ultimo_avg_logprob", None),
                            getattr(self.escucha, "ultimo_compresion", None)):
                        print(f"[Escucha] Transcripción dudosa; ignoro: {texto!r}")
                        texto = ""
                if texto and len(texto.strip()) > 1:
                    print(f"Usuario: {texto}")
                    self._ultima_interaccion_ts = time.time()
                    # Bandit (idea 14): si Parker tomó la iniciativa, esta
                    # respuesta es la señal de si acertó al hablar.
                    if getattr(self, "personalidad", None) is not None:
                        self.personalidad.cerrar_iniciativa(texto)
                    # Datos exactos dichos por la persona (dentista, alergias,
                    # mascota...) van a su tabla de hechos: regex barata, sin
                    # LLM, y aparecen en el system del siguiente turno.
                    if getattr(self, "hechos", None) is not None:
                        try:
                            nuevos = self.hechos.actualizar_desde_texto(texto)
                            if nuevos:
                                print(f"[Hechos] nuevos/cambiados: {nuevos}")
                        except Exception as e:
                            print(f"[Hechos] Error extrayendo: {e}")
                    # 1) Con música sonando, las órdenes de música van primero:
                    # «baja el volumen» con una canción puesta es la música (es
                    # lo que se está oyendo), no la voz (27/10).
                    orden_musica = (self.musica.procesar(texto, sonando=True)
                                    if self.musica_sonando else None)
                    # 2) Modo completo, voz u oído: cada uno cambia solo lo
                    # suyo y se comprueban ANTES que el cerebro para que
                    # «cambia la voz al local» no cambie el cerebro. Todo va
                    # sin LLM: son datos y órdenes que Parker ejecuta él (0 ms).
                    demo_cara = (None if orden_musica
                                 else interpretar_orden_demo_cara(texto))
                    modo_completo = (None if (orden_musica or demo_cara)
                                     else interpretar_orden_modo_completo(texto))
                    orden_voz = (None if (orden_musica or demo_cara or modo_completo)
                                 else interpretar_orden_voz(texto))
                    orden_oido = (None if (orden_musica or demo_cara or modo_completo
                                           or orden_voz)
                                  else interpretar_orden_oido(texto))
                    pedido_cerebro = (None if (orden_musica or demo_cara or modo_completo
                                               or orden_voz or orden_oido)
                                      else interpretar_orden_cerebro(texto))
                    # 3) ¿Es una orden que Parker puede ejecutar él mismo
                    # (volumen, silencio, silbido)? Se hace ya, sin LLM.
                    accion = (None if (orden_musica or demo_cara or modo_completo
                                       or orden_voz or orden_oido or pedido_cerebro)
                              else self.acciones.procesar(texto))
                    if demo_cara == "iniciar":
                        self._iniciar_demo_cara(texto)
                    elif demo_cara == "parar":
                        self._detener_demo_cara(texto)
                    elif modo_completo:
                        self._aplicar_orden_modo_completo(modo_completo, texto)
                    elif orden_voz:
                        self._aplicar_orden_voz(orden_voz, texto)
                    elif orden_oido:
                        self._aplicar_orden_oido(orden_oido, texto)
                    elif pedido_cerebro:
                        self._aplicar_orden_cerebro(pedido_cerebro, texto)
                    elif orden_musica:
                        self._ejecutar_orden_musica(*orden_musica)
                    elif accion:
                        respuesta, sonido = accion
                        print(f"[Acción] {respuesta}"
                              + (f" + {sonido}" if sonido else ""))
                        if respuesta:
                            self._hablar(respuesta, "feliz", motor=False)
                        if sonido:
                            self._cola_voz.put((SONIDO_SILBIDO, "feliz"))
                            # Esperar a que el silbido suene antes de volver a
                            # escuchar: si no, el micro lo oye y Parker se
                            # contesta a sí mismo.
                            self._cola_voz.join()
                            self._cola_audio.join()
                            self._sonando = False
                            self._emitir("hablando", False)
                            self._emitir("expresion", "neutral")
                    elif not self._responder_sin_llm(texto):
                        # 3) Streaming: la primera frase suena en cuanto el
                        # modelo la emite, sin esperar a la respuesta entera.
                        self._hablar_desde_generador(
                            self.cerebro.hablar_stream(texto),
                            emocion_inicial="pensando",
                            filtrar_inventos=True,
                        )
                    print(f"[Latencia] Turno completo (voz oída + respuesta hablada): "
                          f"{time.time() - t_turno:.2f}s")
                else:
                    self._emitir("expresion", "neutral")

            except Exception as e:
                print(f"[Error Procesamiento] {e}")
                self._emitir("expresion", "confundido")

            # El turno SIEMPRE se suelta, pase lo que pase, y la música vuelve
            # a su volumen. Un camino que no lo soltara dejaba a Parker sordo
            # para siempre (visto el 27/10: un turno nacido de la propia
            # canción se ignoraba sin hablar y sin soltar `ocupado`, y ya no
            # volvía a escuchar ni después de apagarse la música).
            self.ocupado = False
            if self.musica.duck or self.oyente_musica.probando:
                self.oyente_musica.reiniciar()
                self._duck_musica(False)
            self._emitir("estado", "")

    def _responder_sin_llm(self, texto: str) -> bool:
        """Órdenes y datos fijos (fecha, hora, agenda, música…), sin LLM.

        Devuelve True si ya ha contestado algo: en ese caso no se llama al LLM
        (cero latencia y cero invención). El orden importa (26/10/2026):

        1. Música, siempre primero: «pon», «para», volumen o «qué suena».
        2. Rutinas del día: dormir/despertar/cállate/apágate cambian el estado.
        3. Apuntes, tiempo, agenda y datos fijos: cada uno contesta con datos.
        4. Si está dormido o callado, no se contesta nada más.

        Con música sonando ya NO se ignora la charla (27/10): el bucle de
        escucha solo abre turno cuando el «duck» confirma que quien habla es
        una persona (`OyenteMusica`), así que aquí se contesta normal con la
        música bajada. La iniciativa y el parte del día sí esperan a que la
        canción termine (`_loop_autonomia`).
        """
        musica = self.musica.procesar(texto, sonando=self.musica_sonando)
        if musica:
            return self._ejecutar_orden_musica(*musica)

        rutina = self.rutinas.procesar(texto)
        if rutina:
            frase, accion = rutina
            print(f"[Rutinas] {frase}" + (f" ({accion})" if accion else ""))
            if accion == ORDEN_REINICIAR:
                self._reiniciar()
                return True
            if accion == ORDEN_BORRAR_MEMORIA:
                self._borrar_memoria()
                return True
            if accion == ORDEN_APAGAR:
                self._apagar()
                return True
            if accion == ORDEN_DORMIR:
                self._emitir("dormir", True)
            elif accion == ORDEN_DESPERTAR:
                self._emitir("dormir", False)
            if frase:
                self._hablar(frase, "carino" if accion != ORDEN_DESPERTAR
                             else "feliz", motor=False)
            if accion == ORDEN_DESPERTAR:
                self._decir_parte_del_dia()
            self._registrar_suceso(frase, texto)
            return True

        # Dormido o con el «cállate un rato» puesto: las órdenes de arriba ya
        # se han atendido, pero no se contesta charla (ni se gasta una llamada).
        if self.rutinas.debe_callarse():
            estado = "dormido" if self.rutinas.dormido else "callado"
            print(f"[Rutinas] ({estado}; no contesto: «{texto[:40]}»)")
            return True

        # Un contador manda sobre la agenda: «apunta un litro de agua a las dos
        # de la tarde» es una cantidad, no una cita con hora (en la placa se
        # convirtió en una alarma, 26/10).
        if self.apuntes.parece_contador(texto):
            respuesta = self.apuntes.procesar(texto)
            if respuesta:
                print(f"[Apuntes] {respuesta}")
                self._hablar(respuesta, "feliz", motor=False)
                self._registrar_suceso(respuesta, texto)
                return True

        # La agenda va ANTES que los apuntes: «apunta que mañana a las 9 tengo
        # al dentista» es una cita con fecha (y una nota sin hora no lleva
        # fecha, así que la agenda la deja pasar). Visto en el test el 26/10.
        for modulo, etiqueta_log in ((self.tiempo, "Tiempo"),
                                     (self.agenda, "Agenda"),
                                     (self.apuntes, "Apuntes")):
            respuesta = modulo.procesar(texto)
            if respuesta:
                print(f"[{etiqueta_log}] {respuesta}")
                self._hablar(respuesta, "feliz", motor=False)
                self._registrar_suceso(respuesta, texto)
                return True

        directa = self.cerebro.respuesta_directa(texto)
        if directa:
            print(f"[Atajo] respuesta directa (sin LLM): {directa}")
            self._hablar(directa, "feliz", motor=False)
            return True
        return False

    # ---------------------------------------------------------------- música

    # ------------------------------------------- modo completo, voz y oído
    def _voz_texto(self) -> str:
        if self.voz.motor_actual() == "piper":
            return "Piper, la voz local"
        return f"Edge, la voz de internet ({self.voz.edge_voz})"

    def _oido_texto(self) -> str:
        return {
            "local": "Whisper en la placa",
            "nube": "Whisper en la nube",
            "auto": "Whisper automático (nube y, si falla, la placa)",
        }.get(self.escucha.motor_actual(), "Whisper")

    def _descripcion_modo(self) -> str:
        estado = self.cerebro.estado_cerebro()
        return (f"cerebro {estado['modelo']} ({estado['motor']}), "
                f"oído {self._oido_texto()}, voz {self._voz_texto()}")

    def _guardar_modo_completo(self) -> None:
        """Guarda cerebro + oído + voz juntos y sobrevive al reinicio."""
        datos = {
            "cerebro": self.cerebro.modo,
            "oido": self.escucha.motor_actual(),
            "voz": self.voz.motor_actual(),
        }
        try:
            self.ruta_modo_completo.write_text(
                json.dumps(datos, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except OSError as e:
            print(f"[Modo] No pude guardar el modo: {e}")

    def _restaurar_modo_completo(self) -> None:
        """Aplica el último modo completo elegido por voz, si existe.

        Los tres componentes se cambiaban por separado, pero solo el cerebro
        se guardaba. Si el dueño pedía «todo local» y reiniciaba, la voz volvía
        a Edge sin avisar. Ahora se guarda el conjunto y se restaura tal cual.
        """
        if not self.ruta_modo_completo.exists():
            return
        try:
            datos = json.loads(self.ruta_modo_completo.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            print("[Modo] El fichero de modo está roto; uso config.yaml.")
            return
        cambios = []
        cerebro = str(datos.get("cerebro") or "").lower()
        if cerebro in ("auto", "nube", "local"):
            self.cerebro.cambiar_modo(cerebro, motivo="arranque")
            cambios.append(f"cerebro={self.cerebro.modo}")
        oido = str(datos.get("oido") or "").lower()
        if oido in ("auto", "nube", "local"):
            real = self.escucha.cambiar_motor(oido)
            cambios.append(f"oído={real}")
        voz = str(datos.get("voz") or "").lower()
        if voz in ("piper", "edge"):
            real = self.voz.cambiar_motor(voz)
            cambios.append(f"voz={real}")
        if cambios:
            print(f"[Modo] Restaurado: {', '.join(cambios)}")

    def _aplicar_orden_modo_completo(self, pedido: str, texto: str = "") -> None:
        """Cambia cerebro, oído y voz de una vez (modo local/nube/auto)."""
        if pedido == "local":
            self.cerebro.cambiar_modo("local")
            real_voz = self.voz.cambiar_motor("piper")
            real_oido = self.escucha.cambiar_motor("local")
            completo = (self.cerebro.modo == "local" and real_voz == "piper"
                        and real_oido == "local")
            frase = ("Modo local completo: pienso, te oigo y hablo aquí dentro. "
                     "Nada de la conversación sale de casa." if completo else
                     "He puesto el cerebro en local, pero no he podido cambiar "
                     "todo; te digo qué queda por fuera.")
        elif pedido == "nube":
            self.cerebro.cambiar_modo("nube")
            real_voz = self.voz.cambiar_motor("edge")
            real_oido = self.escucha.cambiar_motor("auto")
            completo = (self.cerebro.modo == "nube" and real_voz == "edge"
                        and real_oido in ("nube", "auto"))
            frase = ("Modo nube completo: pienso y hablo por internet. "
                     "Si falla la red, sigo en local." if completo else
                     "No he podido poner todo en la nube; sigo con lo que "
                     "funciona aquí dentro.")
        else:
            self.cerebro.cambiar_modo("auto")
            self.voz.cambiar_motor("edge")
            self.escucha.cambiar_motor("auto")
            frase = "Modo normal: internet cuando hay, y la placa cuando falla."
        self._guardar_modo_completo()
        print(f"[Modo] {frase} | {self._descripcion_modo()}")
        self._hablar(frase, "feliz", motor=False)
        self._registrar_suceso(frase, texto)

    def _aplicar_orden_voz(self, pedido: str, texto: str = "") -> None:
        """Cambia solo la voz: Piper local o Edge de internet."""
        real = self.voz.cambiar_motor(pedido)
        if pedido == "edge" and real != "edge":
            frase = ("No he podido usar la voz de internet; sigo con Piper "
                     "local, aquí dentro.")
        elif real == "piper":
            frase = "Voz local: hablo con Piper, aquí dentro."
        else:
            frase = f"Voz de internet: hablo con {self.voz.edge_voz}."
        self._guardar_modo_completo()
        print(f"[Voz] {frase}")
        self._hablar(frase, "feliz", motor=False)
        self._registrar_suceso(frase, texto)

    def _aplicar_orden_oido(self, pedido: str, texto: str = "") -> None:
        """Cambia solo el STT: Whisper local, nube o automático."""
        real = self.escucha.cambiar_motor(pedido)
        if real == "local":
            frase = ("Oído local: transcribo con Whisper en la placa; el "
                     "audio no sale de casa.")
        elif real == "nube":
            frase = "Oído en la nube: transcribo con Whisper en internet."
        else:
            frase = ("Oído automático: transcribo en la nube y, si falla, en "
                     "la placa.")
        if real != pedido:
            frase += f" (se ha quedado en {real})."
        self._guardar_modo_completo()
        print(f"[Oído] {frase}")
        self._hablar(frase, "feliz", motor=False)
        self._registrar_suceso(frase, texto)

    def _aplicar_orden_cerebro(self, pedido: str, texto: str = "") -> None:
        """Cambia el cerebro (o dice cuál usa) sin pasar por el modelo.

        `pedido` viene de `acciones.interpretar_orden_cerebro()`: `local`,
        `nube`, `auto` o `estado`. El cambio se guarda (`parker.cerebro.json`),
        así que un reinicio mantiene lo que se pidió por voz.
        """
        if pedido == "estado":
            frase = (f"{self.cerebro.frase_modo()} "
                     f"Te oigo con {self._oido_texto()} y hablo con "
                     f"{self._voz_texto()}.")
        else:
            frase = self.cerebro.cambiar_modo(pedido)
            self._guardar_modo_completo()
            # Que no parezca que «cambia el cerebro al local» también cambia
            # la voz: son dos piezas distintas. Si la voz sigue en internet,
            # se dice, para que no haya que adivinarlo por la latencia.
            if pedido == "local" and self.voz.motor_actual() != "piper":
                frase += (" La voz sigue en internet; di «modo local "
                          "completo» si la quieres también de casa.")
            elif pedido == "nube" and self.voz.motor_actual() != "edge":
                frase += (" La voz sigue siendo la local; di «modo nube "
                          "completo» para cambiarla también.")
        print(f"[Cerebro] {frase}")
        self._hablar(frase, "feliz", motor=False)
        self._registrar_suceso(frase, texto)

    def _iniciar_demo_cara(self, texto: str = "") -> None:
        """«Parker, modo demo»: muestra todas las expresiones y gestos."""
        print("[Cara] Modo demo solicitado por voz.")
        self._emitir("demo_cara", True)
        self._registrar_suceso("Modo demo de la cara", texto)

    def _detener_demo_cara(self, texto: str = "") -> None:
        """«Para la demo»: corta la secuencia y vuelve a la cara normal."""
        print("[Cara] Modo demo detenido por voz.")
        self._emitir("demo_cara", False)
        self._registrar_suceso("Modo demo detenido", texto)

    def _decir_avisos_cerebro(self) -> None:
        """Dice lo que el cerebro tenga pendiente (se cayó la nube, ya volvió).

        El cerebro los apunta una sola vez por caída; aquí se sacan y se dicen
        cuando Parker no está hablando, para no pisar una respuesta.
        """
        tomar = getattr(self.cerebro, "tomar_avisos", None)
        if tomar is None:
            return
        for aviso in tomar():
            print(f"[Cerebro] Aviso por voz: {aviso}")
            self._hablar(aviso, "neutral", motor=False)

    def _ejecutar_orden_musica(self, frase: str, orden: str, cancion=None) -> bool:
        """Pone/para/ajusta la música. La frase se dice; el audio va aparte."""
        if not getattr(self, "musica_activa", True):
            print(f"[Música] Desactivada; ignoro «{orden}»")
            self._hablar("La música está desactivada ahora mismo.", "neutral",
                         motor=False)
            return True
        print(f"[Música] {frase} ({orden})")
        if orden == "poner" and cancion:
            self._parar_musica.clear()
            # Arranca al volumen que pidió el dueño (no con el «duck» puesto).
            self._duck_musica(False)
            self._hablar(frase, "feliz", motor=False)
            # Después de la confirmación (si no, se pisan el altavoz): el tema
            # pedido y, para no quedarse a medias a los 30 s, unos cuantos más
            # de la misma búsqueda.
            self._cola_musica.put(dict(cancion))
            for extra in list(getattr(self.musica, "cola", []))[:max(0, self.musica_temas_seguidos - 1)]:
                self._cola_musica.put(dict(extra))
            self._registrar_suceso(frase)
            return True
        if orden == "parar":
            self._parar_musica_ya()
            self._hablar(frase, "neutral", motor=False)
            self._registrar_suceso(frase)
            return True
        self._hablar(frase, "feliz", motor=False)
        return True

    def _duck_musica(self, activo: bool) -> None:
        """Baja (o devuelve) la música sin tocar el volumen que pidió el dueño.

        Lo usa el bucle de escucha mientras comprueba si hay una persona sobre
        la canción y mientras atiende su turno: con la música baja se le oye a
        él y el micrófono deja de oír el altavoz. La ganancia entra y sale
        suave (rampa en `_reproducir_cancion`), no de golpe.
        """
        activo = bool(activo)
        if activo == self.musica.duck:
            return
        self.musica.duck = activo
        print(f"[Música] {'Bajo' if activo else 'Devuelvo'} la música para "
              f"{'comprobar/atender la voz' if activo else 'seguir sonando'}")

    def _parar_musica_ya(self):
        """Corta la música y vacía lo que estuviera en cola."""
        self._parar_musica.set()
        try:
            while True:
                self._cola_musica.get_nowait()
        except queue.Empty:
            pass
        espera = 0.0
        while self.musica_sonando and espera < 2.0:
            time.sleep(0.05)
            espera += 0.05
        self._emitir("expresion", "neutral")

    def _loop_musica(self):
        """Hilo reproductor: saca temas de la cola y los suena uno a uno."""
        while self.corriendo:
            try:
                cancion = self._cola_musica.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._parar_musica.is_set():
                continue
            try:
                self._reproducir_cancion(cancion)
            except Exception as e:
                print(f"[Música] Error al reproducir: {e}")

    def _reproducir_cancion(self, cancion: dict):
        """Descarga, decodifica y suena un adelanto, bloque a bloque.

        Se escribe en un flujo de salida de 0,25 s por bloque (no `sd.play`)
        para poder parar a media canción sin cortar el altavoz a lo bruto y
        para aplicar el volumen de la música en cada bloque.
        """
        datos = self.musica.preparar(cancion)
        if not datos:
            print("[Música] No pude preparar el audio")
            self._hablar("No he podido poner esa música.", "triste", motor=False)
            return
        audio, sr = datos
        self.musica_sonando = True
        self._emitir("expresion", "feliz")
        self._emitir("estado", "")
        print(f"[Música] Suena «{cancion.get('titulo')}» de "
              f"{cancion.get('artista')} ({len(audio) / sr:.1f}s)")
        bloque = max(256, int(sr * 0.25))
        # La ganancia va acercándose a la que toca en cada bloque (0,25 s): los
        # cambios de volumen y el «duck» entran y salen suaves, sin golpes.
        ganancia_actual = self.musica.ganancia_objetivo()
        try:
            with sd.OutputStream(samplerate=sr, channels=1, dtype="float32") as flujo:
                for inicio in range(0, len(audio), bloque):
                    if self._parar_musica.is_set() or not self.corriendo:
                        break
                    ganancia_actual += (self.musica.ganancia_objetivo()
                                        - ganancia_actual) * 0.6
                    trozo = self.musica.ganancia(audio[inicio:inicio + bloque],
                                                 ganancia=ganancia_actual)
                    if trozo.shape[0] < bloque:
                        trozo = np.pad(trozo, (0, bloque - trozo.shape[0]))
                    flujo.write(trozo.reshape(-1, 1))
        except Exception as e:
            print(f"[Música] Error de audio: {e}")
        finally:
            self.musica_sonando = False
            self._emitir("expresion", "neutral")

    # ------------------------------------------------------------ día y apagado

    def _decir_parte_del_dia(self, forzar: bool = False) -> bool:
        """Dice el parte del día con datos reales (agenda), sin LLM."""
        if self.rutinas.dormido:
            return False
        nombre = (self.personalidad.estado.get("nombre_usuario") or "") \
            if getattr(self, "personalidad", None) else ""
        frase = self.rutinas.parte_del_dia(self.agenda, nombre=nombre)
        if not frase:
            return False
        print(f"[Rutinas] Parte del día: {frase}")
        self.rutinas.marcar_parte()
        self._hablar(frase, "feliz", motor=False)
        self._registrar_suceso(frase)
        return True

    def _orden_apagado(self) -> list:
        """Comandos que apagan la placa, del más limpio al último recurso."""
        cfg = self.config.get("rutinas") or {}
        preferida = str(cfg.get("orden_apagado") or "").strip()
        ordenes = []
        if preferida:
            ordenes.append(preferida.split())
        ordenes += [["systemctl", "poweroff"],
                    ["loginctl", "poweroff"],
                    ["shutdown", "-h", "now"]]
        return ordenes

    def _borrar_memoria(self):
        """«Parker, borra tu memoria»: pide confirmación y vacía Chroma.

        Dos pasos para que una transcripción mala no borre meses de recuerdos:
        la primera orden solo pregunta; la segunda, dentro de 60 s, borra. La
        agenda, los apuntes y la personalidad NO se tocan.
        """
        ahora = time.time()
        if ahora > getattr(self, "_memoria_borrado_hasta", 0.0):
            self._memoria_borrado_hasta = ahora + 60.0
            print("[Memoria] Borrado pendiente de confirmación (60 s)")
            self._hablar("¿Seguro? Voy a borrar todos mis recuerdos. Si es que "
                         "sí, dime «borra la memoria» otra vez.", "neutral",
                         motor=False)
            return

        self._memoria_borrado_hasta = 0.0
        try:
            total = self.memoria.borrar_todos()
        except Exception as e:
            print(f"[Memoria] No pude borrar: {e}")
            self._hablar("No he podido borrar la memoria; sigue intacta.",
                         "triste", motor=False)
            return
        # Los hechos exactos SON memoria: si se borra Chroma, la tabla de
        # datos personales también se vacía (pide confirmación igual).
        if getattr(self, "hechos", None) is not None:
            try:
                n_hechos = self.hechos.borrar_todos()
                print(f"[Hechos] Borrados {n_hechos} datos")
            except Exception as e:
                print(f"[Hechos] No pude borrar la tabla de datos: {e}")
        if getattr(self, "prosodia", None) is not None:
            try:
                self.prosodia.borrar_todos()
                print("[Prosodia] Historial prosódico borrado")
            except Exception as e:
                print(f"[Prosodia] No pude borrar las medidas: {e}")
        # El historial de la sesión también tenía las frases de prueba: si no
        # se limpia, el modelo las sigue viendo aunque Chroma esté vacío.
        try:
            self.cerebro.historial.clear()
            self.cerebro._ultima_iniciativa = None
            self.cerebro.ultimo_mensaje_usuario = ""
        except Exception as e:
            print(f"[Memoria] Chroma vacío, pero no pude limpiar el historial: {e}")
        print(f"[Memoria] Borrados {total} recuerdos; historial limpio")
        self._hablar(f"Memoria borrada: {total} recuerdos menos. "
                     "Empezamos de cero.", "neutral", motor=False)

    def _reiniciar(self):
        """«Parker, reiníciate»: se despide y sale con 75 para que el lanzador
        lo vuelva a levantar. No borra memoria, agenda ni ajustes."""
        print("[Reinicio] Pedido por voz: salgo con código 75")
        self.ocupado = True
        try:
            self._hablar("Vale, me reinicio. Vuelvo en unos segundos.",
                         "neutral", motor=False)
            self._cola_voz.join()
            self._cola_audio.join()
        except Exception as e:
            print(f"[Reinicio] No pude despedirme: {e}")
        self._emitir("despedida", "derecha")
        time.sleep(2.0)
        self.corriendo = False
        os._exit(75)

    def _apagar(self):
        """«Parker, apágate»: despedida, guardado y corriente fuera.

        Orden (para no dejar la tarjeta a medias): se dice la despedida, se
        espera a que suene, la cara se marcha con su animación y solo después
        se pide el apagado al sistema. Si no hay permiso, se avisa por voz y
        Parker sigue vivo (mejor eso que una pantalla en negro sin explicación).
        """
        cfg = self.config.get("rutinas") or {}
        seco = bool(cfg.get("apagado_seco", False))
        if str(os.environ.get("PARKER_APAGADO_SECO", "")).lower() in ("1", "true", "si", "sí"):
            seco = True
        espera = float(cfg.get("despedida_seg", 2.4))
        self.ocupado = True
        print("[Apagado] Despedida y cierre ordenado")
        try:
            self._hablar("Me voy a dormir del todo. Hasta luego.", "carino",
                         motor=False)
            self._cola_voz.join()
            self._cola_audio.join()
        except Exception as e:
            print(f"[Apagado] No pude despedirme por voz: {e}")
        self._emitir("despedida", "derecha")
        time.sleep(max(0.5, espera))
        if seco:
            print("[Apagado] MODO SECO (rutinas.apagado_seco / PARKER_APAGADO_SECO): "
                  "no apago el sistema, solo lo apunto")
            self._emitir("reaparecer", "seco")
            self._hablar("Modo de prueba: no apago la placa.", "neutral", motor=False)
            self.ocupado = False
            return
        apagada = False
        for orden in self._orden_apagado():
            print(f"[Apagado] Ejecutando: {' '.join(orden)}")
            try:
                subprocess.run(orden, check=True, timeout=20,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                apagada = True
                break
            except Exception as e:
                print(f"[Apagado] «{' '.join(orden)}» no pudo: {e}")
        if not apagada:
            print("[Apagado] No tengo permiso para apagar el sistema. "
                  "Se sigue escuchando (ver docs/placa.md §apagado).")
            self._emitir("reaparecer", "sin permiso")
            self._hablar("No he podido apagar la placa: no tengo permiso. Sigo aquí.",
                         "triste", motor=False)
            self.ocupado = False
            return
        # Con el apagado pedido, systemd cierra todo; si algo lo cancelara, se
        # termina el proceso para que arrancar.sh no lo reinicie en bucle.
        time.sleep(8)
        self.corriendo = False

    def _registrar_suceso(self, respuesta: str, mensaje_usuario: str = "") -> None:
        """Apunta en el historial lo resuelto sin LLM (agenda, aviso que suena).

        Si no se apunta, el turno siguiente no sabe que existe: al preguntar por
        la alarma recién puesta, el modelo diría que él no pone alarmas.
        """
        cerebro = getattr(self, "cerebro", None)
        if cerebro is None or not hasattr(cerebro, "registrar_suceso"):
            return
        cerebro.registrar_suceso(respuesta, mensaje_usuario or None)

    def _loop_agenda(self):
        """Vigila alarmas, temporizadores y citas y los avisa por el altavoz.

        Un hilo propio de 1 s: la agenda no puede depender del latido de
        autonomía (que duerme 300 s) ni del turno de conversación.
        """
        cfg = self.config.get("agenda") or {}
        intervalo = float(cfg.get("intervalo_comprobacion_seg", 1.0) or 1.0)
        while self.corriendo:
            time.sleep(max(0.2, intervalo))
            try:
                vencidos = self.agenda.vencidos()
            except Exception as e:
                print(f"[Agenda] Error al revisar la agenda: {e}")
                continue
            for aviso in vencidos:
                try:
                    self._avisar_agenda(aviso)
                except Exception as e:
                    print(f"[Agenda] No pude avisar: {e}")

    def _avisar_agenda(self, aviso: dict):
        """Suena el aviso y lo dice: es la razón de ser de la agenda."""
        frase = self.agenda.frase_aviso(aviso)
        self.agenda.marcar_avisado(aviso)
        print(f"[Agenda] AVISO ({aviso.get('tipo')}): {frase}")
        # Un aviso manda: si había música, se corta para que la campana y la
        # frase se oigan (son dos altavoces peleándose por el mismo sitio).
        if self.musica_sonando:
            self._parar_musica_ya()
        # Si estaba hablando (o el usuario está a mitad de frase), se espera un
        # poco: sonar encima cortaría el turno en curso.
        espera = 0.0
        while self.ocupado and espera < 5.0:
            time.sleep(0.2)
            espera += 0.2
        self._emitir("expresion", "sorpresa")
        cfg = self.config.get("agenda") or {}
        piso = float(cfg.get("volumen_minimo_aviso", 0.35))
        volumen = max(piso, self.acciones.volumen_actual())
        try:
            # `forzar`: un aviso pedido a propósito tiene que sonar aunque la
            # voz esté silenciada.
            self.voz.reproducir(despertador(volumen), bloquear=True, forzar=True)
        except Exception as e:
            print(f"[Agenda] No pude sonar la campana: {e}")
        self._hablar(frase, "sorpresa", motor=False)
        self._registrar_suceso(frase)

    def _loop_autonomia(self):
        cfg = self.config.get("autonomia", {})
        intervalo = cfg.get("intervalo_comprobacion_seg", 300)
        ultimo_muestreo_termico = 0.0

        while self.corriendo:
            time.sleep(min(intervalo, 30))
            ahora = time.time()
            if ahora - ultimo_muestreo_termico >= 60:
                self._comprobar_temperatura()
                self._caducar_iniciativa()
                ultimo_muestreo_termico = ahora
            # El parte del día va a su hora, aunque no haya silencio: es una cita.
            if not self.ocupado and not self.musica_sonando:
                self._comprobar_parte()
            self._avisar_silencio_expirado()
            # La cara sabe cuánto llevas callado: con eso cambia de familia de
            # gestos (mira alrededor → piensa → se le nota el sueño).
            self._emitir("silencio", int(ahora - self._ultima_interaccion_ts))
            if self.ocupado or self.musica_sonando:
                continue
            # Lo que el cerebro tenga pendiente que decir (se ha caído la nube,
            # ya ha vuelto): se dice cuando Parker no está hablando, no encima.
            self._decir_avisos_cerebro()
            if self.rutinas.debe_callarse():
                continue
            if ahora - self._ultima_interaccion_ts < intervalo:
                continue
            self._comprobar_autonomia()

    def _comprobar_parte(self):
        """Dice el parte del día cuando toca (una vez al día, a su hora)."""
        if not self.rutinas.toca_parte():
            return
        if not self._decir_parte_del_dia():
            # Hoy no había nada que contar: se marca igual para no reintentarlo
            # cada 30 segundos hasta la noche.
            self.rutinas.marcar_parte()

    def _avisar_silencio_expirado(self):
        """Cuando termina el «cállate un rato», lo avisa UNA vez."""
        if not self.rutinas.silencio_expirado():
            return
        print("[Rutinas] Fin del silencio temporal")
        self._hablar("Ya estoy otra vez por aquí.", "feliz", motor=False)

    def _caducar_iniciativa(self):
        """Cierra la iniciativa pendiente si nadie contestó (bandit, −0,3)."""
        personalidad = getattr(self, "personalidad", None)
        if personalidad is None:
            return
        limite = float((self.config.get("autonomia") or {})
                       .get("recompensa_iniciativa_seg", 1800))
        personalidad.caducar_iniciativa(limite_seg=limite)

    def _comprobar_temperatura(self, ruta_base="/sys/class/thermal"):
        """Lee sensores y trips térmicos del kernel que realmente ejecuta."""
        zonas = []
        try:
            rutas = sorted(Path(ruta_base).glob("thermal_zone*"))
        except OSError:
            return []
        for zona in rutas:
            try:
                celsius = int((zona / "temp").read_text(encoding="ascii").strip()) / 1000.0
            except (OSError, ValueError):
                continue
            try:
                tipo = (zona / "type").read_text(encoding="ascii").strip() or "desconocido"
            except OSError:
                tipo = "desconocido"
            trips = []
            for archivo in sorted(zona.glob("trip_point_*_temp")):
                try:
                    valor = int(archivo.read_text(encoding="ascii").strip()) / 1000.0
                    indice = archivo.stem.removeprefix("trip_point_").removesuffix("_temp")
                    tipo_trip = (zona / f"trip_point_{indice}_type").read_text(encoding="ascii").strip()
                    trips.append(f"{tipo_trip} {valor:.1f}°C")
                except (OSError, ValueError):
                    continue
            zonas.append({"zona": zona.name, "tipo": tipo, "celsius": celsius, "trips": trips})
            texto_trips = f"; trips: {', '.join(trips)}" if trips else "; trips no expuestos"
            print(f"[Térmica] {zona.name} ({tipo}): {celsius:.1f}°C{texto_trips}")
        if not zonas:
            return []
        maximo = max(zonas, key=lambda item: item["celsius"])
        umbral = float(self.config.get("temperatura", {}).get("aviso_c", 70.0))
        aviso_activo = maximo["celsius"] >= umbral
        anterior = getattr(self, "_aviso_termico_activo", False)
        if aviso_activo and not anterior:
            print(f"[Térmica] AVISO preventivo: {maximo['tipo']} a {maximo['celsius']:.1f}°C "
                  f"(umbral configurable {umbral:.1f}°C); revisar carga, refrigeración y trips reales.")
        elif anterior and not aviso_activo:
            print(f"[Térmica] Temperatura bajo el umbral preventivo ({umbral:.1f}°C).")
        self._aviso_termico_activo = aviso_activo
        return zonas

    def _senal_prosodia(self) -> dict | None:
        """Tendencia prosódica que consulta la personalidad (None si no hay).

        Envuelto en try/except: una base de datos rota no puede tumbar la
        iniciativa de Parker.
        """
        if getattr(self, "prosodia", None) is None:
            return None
        try:
            senal = self.prosodia.tendencia()
            if isinstance(senal, dict) and senal.get("nivel") != "normal":
                print(f"[Prosodia] Tendencia: {senal['nivel']} "
                      f"(rms {senal['delta_rms_db']:+.1f}dB, "
                      f"{senal['muestras']} turnos recientes vs baseline)")
            return senal
        except Exception as e:
            print(f"[Prosodia] No pude calcular la tendencia: {e}")
            return None

    def _comprobar_autonomia(self):
        """Iniciativa propia: la personalidad decide qué decir y con qué ánimo.

        Antes esto mandaba siempre "el usuario lleva callado, salúdale". Ahora el
        ánimo evoluciona con el silencio (baja energía, sube el cariño) y la
        instrucción sale del perfil: a veces cuenta algo suyo, a veces pregunta
        por algo pequeño, a veces dice que te ha echado de menos.
        """
        cfg = self.config.get("autonomia", {})
        ahora = time.time()
        silencio = ahora - self._ultima_interaccion_ts
        personalidad = getattr(self, "personalidad", None)
        if personalidad is not None:
            personalidad.latido(silencio)
            print(f"[Personalidad] {personalidad.resumen_para_log()}")
            print(f"[Bandit] {personalidad.bandits_resumen()}")
        if silencio < cfg.get("umbral_silencio_seg", 2700):
            return

        # Idea 14 (26/10/2026): el brazo lo elige el bandit, no el azar. Con
        # «callar» no se llama al modelo: Parker se queda mirando y ya.
        brazo, instruccion = "contar", ""
        if personalidad is not None:
            brazo, instruccion = personalidad.elegir_iniciativa(silencio)
        if brazo == "callar" or not instruccion:
            print("[Bandit] Toca callar: no digo nada, solo miro")
            if personalidad is not None:
                personalidad.registrar_iniciativa("callar")
            self._ultima_interaccion_ts = ahora
            self._emitir("expresion", "neutral")
            return
        try:
            if personalidad is not None:
                personalidad.registrar_iniciativa(brazo)
            # La cara se pone a pensar ANTES de hablar: así el turno se lee
            # como una idea suya y no como un aviso del sistema.
            self._emitir("expresion", "pensando")
            respuesta, etiquetas = self.cerebro.hablar_proactivo(
                instruccion, brazo=brazo)
            if not respuesta:
                print(f"[Autonomía] {brazo}: sin frase concreta, me callo")
                self._ultima_interaccion_ts = ahora
                self._emitir("expresion", "neutral")
                return
            print(f"[Autonomía] {brazo}: {respuesta}")
            emocion = self._emocion_desde_etiquetas(etiquetas) or "neutral"
            self._hablar(respuesta, emocion)
            self._ultima_interaccion_ts = ahora
        except Exception as e:
            # Sin esto la cara se quedaba en «pensando» si el cerebro fallaba
            # justo ahí, y con ella los gestos de reposo (van con la expresión).
            self._emitir("expresion", "neutral")
            print(f"[Error autonomía] {e}")

    def salir(self):
        self.corriendo = False


def _cargar_pantalla_config(config_path: str = "config.yaml") -> dict:
    """Sección `pantalla` de config.yaml (pines/velocidad SPI de la GC9A01)."""
    cfg_file = BASE_DIR / config_path if not os.path.isabs(config_path) else Path(config_path)
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("pantalla") or {}
    except Exception:
        return {}


def _tomar_lock_instancia():
    """Impide que dos Parker se peleen por el SPI y el micrófono.

    `arrancar.sh` ya usa un `flock` para su relanzamiento automático, pero si
    alguien lanza `python parker.py` a mano (por ejemplo, para probar un
    cambio) el candado del lanzador no lo cubre. Dos procesos abren el mismo
    micrófono y escriben en el mismo panel: la cara se congela a saltos y el
    micrófono deja de responder (visto el 25/10 y documentado en
    `docs/TREC/errades/Dues instancies i el micro.md`).

    El candado vive en `~/.parker.runtime.lock`, no en el proyecto, y se
    libera solo cuando el proceso muere. En Windows no se aplica: allí no hay
    SPI ni el mismo problema de audio.
    """
    global _LOCK_INSTANCIA
    if fcntl is None:
        return True
    ruta = Path.home() / ".parker.runtime.lock"
    try:
        archivo = open(ruta, "w")
    except OSError as e:
        print(f"[Parker] No pude crear el candado de instancia ({e}); sigo.")
        return True
    try:
        fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        archivo.close()
        print("[Parker] Ya hay otra instancia de Parker en marcha; esta no "
              "arranca para no pelearse por el micrófono y la pantalla SPI.")
        return False
    archivo.write(str(os.getpid()))
    archivo.flush()
    _LOCK_INSTANCIA = archivo      # se mantiene abierto mientras viva Parker
    return True


def main():
    if not _tomar_lock_instancia():
        return
    app = QApplication(sys.argv)

    senales = SenalesCara()
    window = ParkerWindow(senales, _cargar_pantalla_config())

    parker_ref = {}

    # El hook de prueba tiene que instalarse en el hilo PRINCIPAL: `Parker` se
    # construye en otro hilo y allí `signal.signal` lanza ValueError. Sin esto,
    # `kill -USR1` terminaba el proceso en vez de simular el barge-in.
    if os.environ.get("PARKER_TEST_BARGE") == "1":
        senal = getattr(signal, "SIGUSR1", None)
        if senal is not None:
            def _hook_barge_main(*_args):
                inst = parker_ref.get("instancia")
                if inst is not None:
                    inst._barge_prueba()
            try:
                signal.signal(senal, _hook_barge_main)
                print("[Barge-in] Hook de prueba SIGUSR1 activo")
            except (ValueError, OSError) as e:
                print(f"[Barge-in] No pude instalar el hook SIGUSR1: {e}")

    def _cargar():
        parker_ref["instancia"] = Parker(senales=senales)

    threading.Thread(target=_cargar, daemon=True).start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
