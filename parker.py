#!/usr/bin/env python3
"""
parker.py
Bucle principal de Parker. La ventana Qt con la cara vectorial
(parker_face_demo.py) es ahora la interfaz definitiva: este archivo
la levanta y conecta con voz, escucha y cerebro+memoria.

ESCUCHA MANUAL: pulsa 1 para hablar, 0 para salir.
Cerebro: solo Groq (online). Memoria: RAG con ChromaDB.
"""

import os
# Parche anti-congelación: evita que el modelo de memoria se bloquee en hilos secundarios
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re
import sys
import math
import random
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml
import numpy as np
import sounddevice as sd

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QLabel, QMainWindow, QVBoxLayout, QWidget

from modulos.escucha import EscuchaParker
from modulos.cerebro import CerebroParker
from modulos.voz import VozParker
from modulos.memoria import MemoriaParker
from modulos.cara_parker import FaceController, FACE_W, FACE_H, BG_BLACK


# =====================================================================
# Puente de señales: la cara (Qt) SOLO se toca desde el hilo principal.
# El worker de audio/cerebro corre en otro hilo y habla con la cara
# unicamente emitiendo estas señales (Qt las cruza de hilo de forma segura).
# =====================================================================
class SenalesCara(QObject):
    expresion = Signal(str)   # nombre de expresion: feliz, triste, sorpresa...
    hablando = Signal(bool)   # True = empieza a mover la boca, False = para
    estado = Signal(str)      # texto de estado para la etiqueta de la ventana


# =====================================================================
# Ventana principal: solo la cara + una etiqueta de estado. Sin botones
# de debug (esos viven en parker_face_demo.py si lo ejecutas suelto).
# =====================================================================
class ParkerWindow(QMainWindow):
    def __init__(self, senales: SenalesCara):
        super().__init__()
        self.setWindowTitle("Parker")
        self.setStyleSheet("background-color: black;")

        central = QWidget()
        central.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(central)

        self.scene = QGraphicsScene(0, 0, FACE_W, FACE_H)
        self.scene.setBackgroundBrush(QBrush(BG_BLACK))
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("border: none; background-color: black;")
        self.view.setFixedSize(FACE_W + 4, FACE_H + 4)
        layout.addWidget(self.view)

        self.estado_label = QLabel("Cargando módulos...")
        self.estado_label.setStyleSheet("color: white; font-size: 14px; padding: 6px;")
        self.estado_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.estado_label)

        self.setCentralWidget(central)

        self.face = FaceController(self.scene)

        # --- Simulación de boca mientras se reproduce audio ---
        self._talk_timer = QTimer(self)
        self._talk_timer.setInterval(90)
        self._talk_timer.timeout.connect(
            lambda: self.face.set_mouth_open(random.uniform(0.0, 0.9))
        )

        # --- Conexión con el hilo de audio/cerebro ---
        senales.expresion.connect(self.face.set_expression)
        senales.hablando.connect(self._on_hablando)
        senales.estado.connect(self.estado_label.setText)

    def _on_hablando(self, activo: bool):
        if activo:
            self._talk_timer.start()
        else:
            self._talk_timer.stop()
            self.face.set_mouth_open(0.0)


# =====================================================================
# Lógica de Parker: audio, cerebro+memoria, voz. Corre en un hilo
# normal (no Qt) porque puede bloquear todo lo que haga falta.
# =====================================================================
class Parker:
    def __init__(self, senales: SenalesCara, config_path: str = "config.yaml"):
        self.senales = senales
        self.config = self._cargar_config(config_path)

        self.ocupado = False
        self.corriendo = True
        self.grabando = False
        self._start_signal = False
        self._stop_signal = False

        # --- Estado para los avisos proactivos (autonomía) ---
        self._ultima_interaccion_ts = time.time()
        self._sesion_inicio_ts = time.time()
        self._ultima_emocion = "neutral"

        print("=" * 60)
        print("  PARKER v5")
        print("=" * 60)
        print("\n[Cargando módulos...]")

        config_mem = self.config.get("memoria", {})
        self.memoria = MemoriaParker(
            db_path=config_mem.get("db_path", "./parker.db"),
            coleccion=config_mem.get("coleccion", "recuerdos_parker"),
            modelo_embeddings=config_mem.get("modelo_embeddings", "paraphrase-multilingual-MiniLM-L12-v2")
        )

        self.escucha = EscuchaParker(
            modelo=self.config.get("escucha", {}).get("modelo_whisper", "base"),
            idioma=self.config.get("escucha", {}).get("idioma", "es")
        )

        self.cerebro = CerebroParker(
            config_groq=self.config.get("groq"),
            memoria=self.memoria
        )

        config_voz = self.config.get("voz", {})
        self.voz = VozParker(
            modelo_path=config_voz.get("modelo_piper", "./assets/voz/es_ES-davefx-medium.onnx"),
            config_path=config_voz.get("modelo_config")
        )

        print("[Todos los módulos cargados]\n")

        self.hilo_worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.hilo_worker.start()

        self.hilo_autonomia = threading.Thread(target=self._loop_autonomia, daemon=True)
        self.hilo_autonomia.start()

        threading.Thread(
            target=self._hablar,
            args=("¡Hola! Soy Parker. Pulsa 1 para hablar.", "feliz"),
            daemon=True
        ).start()

    def _cargar_config(self, path: str) -> dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _emitir(self, nombre_senal: str, valor):
        getattr(self.senales, nombre_senal).emit(valor)

    # -------------------------------------------------------------
    # La emoción real viene de la etiqueta [CARA:x] que el propio
    # LLM genera (más fiable que adivinar por palabras clave). Si
    # por lo que sea no llega ninguna etiqueta, caemos al detector
    # local por palabras clave como red de seguridad.
    # -------------------------------------------------------------
    def _emocion_desde_etiquetas(self, etiquetas: list[str]) -> str | None:
        for tag in etiquetas:
            match = re.match(r"\[([A-Z_]+):([^\]]*)\]", tag)
            if match and match.group(1).upper() == "CARA":
                return match.group(2).strip().lower()
        return None

    def detectar_emocion(self, texto: str) -> str:
        texto_lower = texto.lower()
        emociones = {
            'feliz': ['feliz', 'genial', 'excelente', 'me alegro', 'perfecto', 'bien', '¡', '!', 'jaja', 'jeje'],
            'triste': ['triste', 'lo siento', 'lástima', 'pena', 'decepcionado', 'decepcionada'],
            'sorpresa': ['no me lo puedo creer', 'vaya', 'wow', 'no sabía'],
            'confundido': ['no entiendo', 'qué', 'cómo', 'perdón', 'confundido', 'confundida'],
            'pensando': ['pensando', 'déjame pensar', 'un momento', 'reflexionando'],
        }
        for emocion, palabras in emociones.items():
            if any(p in texto_lower for p in palabras):
                return emocion
        return 'neutral'

    def _hablar(self, texto: str, emocion: str = "neutral"):
        self.ocupado = True
        self._emitir("expresion", emocion)
        self._emitir("estado", " Hablando...")
        self._emitir("hablando", True)
        try:
            self.voz.hablar(texto, bloquear=True)
        except Exception as e:
            print(f"[Error voz] {e}")
        self._emitir("hablando", False)
        self._emitir("expresion", "neutral")
        self._emitir("estado", "Listo — pulsa 1 para hablar")
        self.ocupado = False

    def _worker_loop(self):
        while self.corriendo:
            if self._start_signal:
                self._start_signal = False
                self._grabar_y_procesar()
            else:
                time.sleep(0.05)

    def _grabar_y_procesar(self):
        """
        Graba por toggle: empieza al llamar a esta función, y para cuando
        se pulsa 1 de nuevo (self._stop_signal) o al alcanzar el límite
        máximo de seguridad (duracion_maxima_grabacion en config.yaml).
        """
        self.ocupado = True
        self.grabando = True
        self._emitir("expresion", "neutral")
        self._emitir("estado", " Grabando... (pulsa 1 para terminar)")

        buffer = []
        max_duracion = self.config.get("escucha", {}).get("duracion_maxima_grabacion", 20)
        inicio = time.time()

        def callback(indata, frames, time_info, status):
            buffer.append(indata.copy())

        try:
            with sd.InputStream(samplerate=16000, channels=1, dtype=np.float32,
                                 device=self.config.get("escucha", {}).get("dispositivo_entrada"),
                                 callback=callback):
                while self.grabando and self.corriendo:
                    time.sleep(0.05)
                    if self._stop_signal:
                        self._stop_signal = False
                        self.grabando = False
                    elif time.time() - inicio > max_duracion:
                        print(f"[Escucha] Límite máximo de {max_duracion}s alcanzado, cortando grabación")
                        self.grabando = False
        except Exception as e:
            print(f"[Error grabación] {e}")
            self.grabando = False
            self.ocupado = False
            self._emitir("expresion", "confundido")
            self._emitir("estado", "Error al grabar, pulsa 1 para reintentar")
            return

        if not buffer:
            print("[Escucha] Grabación vacía")
            self.ocupado = False
            self._emitir("estado", "Listo — pulsa 1 para hablar")
            return

        audio = np.concatenate(buffer, axis=0).flatten()
        duracion_real = len(audio) / 16000
        print(f"\n[Escucha] Grabado: {duracion_real:.1f}s")

        if duracion_real < 0.3:
            print("[Escucha] Grabación demasiado corta, ignorada")
            self.ocupado = False
            self._emitir("estado", "Listo — pulsa 1 para hablar")
            return

        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))

        try:
            self._emitir("expresion", "pensando")
            self._emitir("estado", "Transcribiendo...")
            print("[Escucha] Transcribiendo...")
            texto = self.escucha.transcribir(audio)

            if not texto:
                print("[Escucha] No se detectó texto")
                self._emitir("expresion", "confundido")
                self._emitir("estado", "No te he entendido, pulsa 1 para repetir")
                self.ocupado = False
                return

            print(f"[Tú] {texto}")
            self._emitir("estado", "Pensando...")

            respuesta, etiquetas = self.cerebro.hablar(texto)

            emocion = self._emocion_desde_etiquetas(etiquetas) or self.detectar_emocion(respuesta)
            print(f"[Parker] {respuesta[:80]}...")

            self._ultima_interaccion_ts = time.time()
            self._sesion_inicio_ts = time.time()
            self._ultima_emocion = emocion

            self._hablar(respuesta, emocion)

        except Exception as e:
            print(f"[Error Worker] {e}")
            import traceback
            traceback.print_exc()
            self._emitir("expresion", "confundido")
            self._emitir("estado", "Algo ha fallado, pulsa 1 para reintentar")
            self.ocupado = False

    # -------------------------------------------------------------
    # Autonomía: cada X minutos comprueba si Parker debería hablar
    # por su cuenta (silencio prolongado, o mucho rato sin pausas).
    # Solo actúa si Parker no está ya ocupado (pensando/hablando/grabando).
    # -------------------------------------------------------------
    def _loop_autonomia(self):
        cfg = self.config.get("autonomia", {})
        intervalo = cfg.get("intervalo_comprobacion_seg", 300)  # 5 min

        while self.corriendo:
            time.sleep(intervalo)
            if self.ocupado or self.grabando:
                continue
            self._comprobar_autonomia()

    def _comprobar_autonomia(self):
        cfg = self.config.get("autonomia", {})
        umbral_silencio = cfg.get("umbral_silencio_seg", 2700)      # 45 min
        umbral_sedentario = cfg.get("umbral_sedentario_seg", 3600)  # 60 min

        ahora = time.time()
        silencio = ahora - self._ultima_interaccion_ts
        sedentario = ahora - self._sesion_inicio_ts

        if silencio >= umbral_silencio:
            minutos = int(silencio / 60)
            if self._ultima_emocion in ("triste", "confundido"):
                instruccion = (
                    f"El usuario lleva {minutos} minutos sin hablar contigo, y la última "
                    f"vez que hablasteis parecía estar {self._ultima_emocion}. "
                    "Pregúntale con cariño cómo está ahora."
                )
            else:
                instruccion = (
                    f"El usuario lleva {minutos} minutos sin hablar contigo. "
                    "Salúdale de forma natural y pregúntale qué tal va todo."
                )
            self._hablar_proactivo(instruccion)
            self._ultima_interaccion_ts = ahora
            return  # un solo aviso por comprobación, no encadenar los dos

        if sedentario >= umbral_sedentario:
            minutos = int(sedentario / 60)
            instruccion = (
                f"El usuario lleva alrededor de {minutos} minutos seguidos en esta sesión "
                "sin pausas detectadas. Sugiérele de forma breve y cercana, sin sonar a "
                "aviso médico, que se levante un momento o beba agua."
            )
            self._hablar_proactivo(instruccion)
            self._sesion_inicio_ts = ahora

    def _hablar_proactivo(self, instruccion: str):
        try:
            respuesta, etiquetas = self.cerebro.hablar_proactivo(instruccion)
            emocion = self._emocion_desde_etiquetas(etiquetas) or self.detectar_emocion(respuesta)
            self._ultima_emocion = emocion
            print(f"\n[Parker - proactivo] {respuesta}")
            self._hablar(respuesta, emocion)
        except Exception as e:
            print(f"[Error autonomía] {e}")

    def on_grabar(self):
        """Tecla 1: si no está grabando, empieza; si ya está grabando, termina."""
        if not self.grabando:
            if self.ocupado:
                return  # está pensando o hablando, ignorar
            self._start_signal = True
        else:
            self._stop_signal = True

    def salir(self):
        self.corriendo = False


def main():
    app = QApplication(sys.argv)

    senales = SenalesCara()
    window = ParkerWindow(senales)
    window.show()

    # Cargar los modelos (Whisper, Groq, Chroma, Piper) tarda unos
    # segundos: lo hacemos en un hilo aparte para que la ventana ya
    # se vea y "respire" mientras carga en segundo plano.
    parker_ref = {}

    def _cargar():
        parker_ref["instancia"] = Parker(senales=senales)

    threading.Thread(target=_cargar, daemon=True).start()

    try:
        import keyboard
        print("[INFO] Usando librería 'keyboard' para captura de teclas (global, no necesita foco de ventana)")
        print("[INFO] Si no funciona, ejecuta como administrador\n")

        def _on_grabar():
            if "instancia" in parker_ref:
                parker_ref["instancia"].on_grabar()

        def _on_salir():
            if "instancia" in parker_ref:
                parker_ref["instancia"].salir()
            app.quit()

        keyboard.on_press_key('1', lambda _: _on_grabar())
        keyboard.on_press_key('0', lambda _: _on_salir())
        print("[CONTROLES] 1 = Hablar | 0 = Salir")
    except ImportError:
        print("[ERROR] Instala 'keyboard': pip install keyboard")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()