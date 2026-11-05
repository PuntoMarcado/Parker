"""
modulos/vad.py
==============
Detección de voz para el micrófono de Parker.

El VAD antiguo comparaba el volumen bruto con un umbral que subía con el ruido
de fondo. En una sala normal eso obliga a hablar alto: el ruido también sube y
la voz lejana se queda por debajo. Aquí se usa el modelo **Silero VAD v6** que
ya viene dentro de faster-whisper (no hay descarga nueva) y una **ganancia
automática** antes del modelo.

Por qué la ganancia automática: Silero es sensible a la amplitud. Medido en la
placa con una frase real reducida al 5 % de su nivel, el modelo daba 0,09 de
probabilidad sin ganancia y 0,34-0,58 con el AGC de esta clase. El ruido de una
sala doméstica sigue por debajo de 0,10. Así una voz lejana entra sin tener que
gritar y sin abrir el turno con el ventilador o la tele.

El AGC solo se usa para el VAD. El audio que se manda a Whisper se sigue
normalizando por pico (en parker.py), así que no se altera lo que transcribe.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np


class AGC:
    """Ganancia automática suave, pensada para VAD (no para el audio final).

    Mantiene un nivel medio de la señal y aplica la ganancia necesaria para
    acercarla a `objetivo`. Nunca atenúa (mínimo 1.0) y nunca amplifica más de
    `max_ganancia`. El limitador `tanh` evita que un golpe de voz sature la
    entrada del modelo.
    """

    def __init__(self, objetivo: float = 0.12, alfa: float = 0.2,
                 max_ganancia: float = 6.0, suelo: float = 1e-5):
        self.objetivo = max(0.01, float(objetivo))
        self.alfa = min(0.9, max(0.01, float(alfa)))
        self.max_ganancia = max(1.0, float(max_ganancia))
        self.suelo = max(1e-8, float(suelo))
        self.nivel = 0.01

    def reiniciar(self) -> None:
        self.nivel = 0.01

    def procesar(self, bloque: np.ndarray) -> tuple[np.ndarray, float]:
        bloque = np.asarray(bloque, dtype=np.float32).ravel()
        if bloque.size == 0:
            return bloque, 1.0
        rms = float(np.sqrt(np.mean(bloque ** 2)))
        self.nivel = ((1.0 - self.alfa) * self.nivel
                      + self.alfa * max(rms, self.suelo))
        ganancia = min(self.max_ganancia,
                       max(1.0, self.objetivo / max(self.nivel, self.suelo)))
        # tanh limita los picos; la división deja el máximo en 1.0.
        salida = np.tanh(bloque * ganancia * 1.2) / math.tanh(1.2)
        return salida.astype(np.float32, copy=False), ganancia


class VADSilero:
    """VAD Silero por streaming, con estado entre bloques de 512 muestras.

    `procesar()` acepta cualquier longitud (el bucle de Parker lee 1024
    muestras) y devuelve la probabilidad máxima de voz del bloque. Si el modelo
    o onnxruntime no están disponibles, `disponible` queda en False y Parker
    vuelve al VAD de volumen de siempre.
    """

    def __init__(self, ruta_modelo: Optional[str] = None,
                 agc_objetivo: float = 0.12, agc_alfa: float = 0.2,
                 agc_max_ganancia: float = 6.0):
        self.disponible = False
        self.ultimo_error = ""
        self.agc = AGC(objetivo=agc_objetivo, alfa=agc_alfa,
                       max_ganancia=agc_max_ganancia)
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._contexto = np.zeros(64, dtype=np.float32)
        self.ultima_ganancia = 1.0

        ruta = Path(ruta_modelo) if ruta_modelo else self._ruta_por_defecto()
        if ruta is None:
            self.ultimo_error = ("no encuentro silero_vad_v6.onnx dentro de "
                                 "faster_whisper")
            return
        try:
            import onnxruntime as ort
        except ImportError as e:
            self.ultimo_error = f"falta onnxruntime ({e})"
            return
        try:
            opciones = ort.SessionOptions()
            opciones.inter_op_num_threads = 1
            opciones.intra_op_num_threads = 1
            opciones.enable_cpu_mem_arena = False
            opciones.log_severity_level = 4
            self._sesion = ort.InferenceSession(
                str(ruta), providers=["CPUExecutionProvider"],
                sess_options=opciones)
            self.disponible = True
        except Exception as e:  # modelo roto, versión incompatible...
            self.ultimo_error = f"{type(e).__name__}: {e}"

    @staticmethod
    def _ruta_por_defecto() -> Optional[Path]:
        try:
            import faster_whisper
        except ImportError:
            return None
        base = Path(faster_whisper.__file__).resolve().parent / "assets"
        for nombre in ("silero_vad_v6.onnx", "silero_vad.onnx"):
            ruta = base / nombre
            if ruta.exists():
                return ruta
        return None

    def reiniciar(self) -> None:
        """Olvida el estado de la frase anterior (al rearmar el micro o turno)."""
        self._h[:] = 0.0
        self._c[:] = 0.0
        self._contexto[:] = 0.0
        self.agc.reiniciar()
        self.ultima_ganancia = 1.0

    def procesar(self, audio: np.ndarray) -> Optional[float]:
        """Probabilidad de voz (0-1) del bloque; None si no hay modelo."""
        if not self.disponible:
            return None
        audio = np.asarray(audio, dtype=np.float32).ravel()
        if audio.size == 0:
            return 0.0
        if audio.size < 512:
            audio = np.pad(audio, (0, 512 - audio.size))
        probabilidades: list[float] = []
        for inicio in range(0, audio.size, 512):
            bloque = audio[inicio:inicio + 512]
            if bloque.size < 512:
                bloque = np.pad(bloque, (0, 512 - bloque.size))
            bloque, ganancia = self.agc.procesar(bloque)
            self.ultima_ganancia = ganancia
            entrada = np.concatenate([self._contexto, bloque]).reshape(1, 576)
            salida, self._h, self._c = self._sesion.run(
                None, {"input": entrada, "h": self._h, "c": self._c})
            probabilidades.append(float(np.asarray(salida).reshape(-1)[0]))
            self._contexto = bloque[-64:].copy()
        return max(probabilidades) if probabilidades else 0.0
