"""
modulos/escucha.py
==================
Transcripción de voz a texto.

Dos backends:
  - "faster-whisper" (CTranslate2, int8, VAD): ~4x más rápido que
    openai-whisper con la misma precisión. Recomendado en la SBC.
  - "openai-whisper": implementación original (openai-whisper).

El backend "auto" intenta faster-whisper y cae a openai-whisper si no está
instalado, para no romper instalaciones existentes.
"""

import io
import numpy as np
import sounddevice as sd
import tempfile
import time
import wave
import os

import requests

try:
    from faster_whisper import WhisperModel as _FasterWhisperModel
    _TIENE_FASTER = True
except ImportError:
    _FasterWhisperModel = None
    _TIENE_FASTER = False

try:
    import whisper as _openai_whisper
except ImportError:
    _openai_whisper = None


def parece_eco_del_prompt(texto: str) -> bool:
    """¿Whisper devolvió el `initial_prompt` entero en vez de la voz?

    El 01/11/2026 el sesgo incluía «cambia el cerebro al local» y Whisper lo
    escupió tal cual; Parker obedeció una orden que nadie dijo. La señal es el
    par de comillas angulares («…»), no una comilla suelta: Whisper añadía a
    veces solo el cierre (`¿qué día es hoy?».`) a una frase REAL y el filtro
    anterior tiraba el turno entero, así que Parker parecía sordo (medido en
    la placa el 01/11 a las 20:39).
    """
    return bool(texto) and "«" in texto and "»" in texto


def limpiar_marcas_prompt(texto: str) -> str:
    """Quita las comillas angulares que Whisper arrastra del `initial_prompt`.

    Una frase normal no lleva «»; si aparece solo una, es un resto del sesgo y
    se elimina para que la orden se pueda ejecutar. El par completo ya lo
    descarta `parece_eco_del_prompt`.
    """
    return (texto or "").replace("«", "").replace("»", "").strip()


def volcar_audio(directorio: str, audio: np.ndarray, texto: str,
                 sample_rate: int = 16000) -> str:
    """Guarda el audio transcrito en WAV y su texto en .txt (plan §2.4).

    El corpus del banco de STT se crea solo, mientras Parker se usa con
    normalidad: el WAV permite retranscribir y el TXT guarda la hipótesis de
    Whisper, que se corrige a mano y pasa a ser la referencia medida.
    """
    os.makedirs(directorio, exist_ok=True)
    nombre = f"{time.strftime('%Y%m%d-%H%M%S')}_{int((time.time() % 1) * 1000):03d}"
    ruta = os.path.join(directorio, nombre)
    sufijo = 0
    while os.path.exists(ruta + ".wav") or os.path.exists(ruta + ".txt"):
        sufijo += 1
        ruta = os.path.join(directorio, f"{nombre}_{sufijo}")

    audio_int16 = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
                   * 32767).astype(np.int16)
    with wave.open(ruta + ".wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    with open(ruta + ".txt", "w", encoding="utf-8") as f:
        f.write(texto or "")
    return ruta + ".wav"


class EscuchaParker:
    """
    Motor de Speech-to-Text: nube si hay red, local siempre disponible.
    """

    # Valores por defecto a nivel de clase: los tests construyen la instancia
    # con `__new__` (sin __init__) para inspeccionar el comportamiento sin
    # cargar un Whisper, y así `transcribir()` sigue siendo válido.
    motor_preferido = "local"
    modelo_nube = "whisper-large-v3-turbo"
    url_nube = ""
    nombre_clave = "GROQ_API_KEY"
    timeout_nube = 8.0
    reintento_nube_seg = 60.0
    _nube_caida_hasta = 0.0
    _clave_nube = ""
    ultimo_motor = "local"
    ultima_latencia = 0.0
    ultimo_error_nube = ""
    # Métricas de calidad del último segmento (Whisper). Se usan para no
    # contestar a ruido. None = el backend no las ha dado.
    ultimo_no_speech = None
    ultimo_avg_logprob = None
    ultimo_compresion = None

    def __init__(self, modelo: str = "base", idioma: str = "es",
                 backend: str = "auto", modelo_faster: str = "base",
                 beam_size: int = 1, vad_filter: bool = True,
                 cpu_threads: int | None = None, hotwords: str | None = None,
                 initial_prompt: str | None = None,
                 vad_parameters: dict | None = None,
                 volcar_dir: str | None = None,
                 motor: str = "auto",
                 modelo_nube: str = "whisper-large-v3-turbo",
                 url_nube: str = "https://api.groq.com/openai/v1",
                 nombre_clave: str = "GROQ_API_KEY",
                 timeout_nube: float = 8.0,
                 reintento_nube_seg: float = 60.0,
                 cargar_modelo: bool = True):
        self.idioma = idioma
        # --- Motor del STT: nube si se puede, local si no ---
        # Medido en la placa el 25/10 con la misma frase (6,1 s):
        #   local faster-whisper base -> 4,31 s y «en al médico» (error)
        #   nube whisper-large-v3-turbo -> 0,68 s y texto exacto
        # El audio solo sale de casa con motor "auto"/"nube"; con "local" no.
        self.motor_preferido = (motor or "auto").lower()
        self.modelo_nube = modelo_nube
        self.url_nube = (url_nube or "").rstrip("/")
        self.nombre_clave = nombre_clave
        self.timeout_nube = timeout_nube
        self.reintento_nube_seg = reintento_nube_seg
        self._nube_caida_hasta = 0.0
        self._clave_nube = None
        self.ultimo_motor = "local"
        self.ultima_latencia = 0.0
        self.ultimo_error_nube = ""
        self.ultimo_no_speech = None
        self.ultimo_avg_logprob = None
        self.ultimo_compresion = None
        # Palabras que Whisper debe reconocer sí o sí. Medido en la placa: con
        # el modelo `base` sin sesgo, "Oye Parker" salía "Oye parquear"; con
        # hotwords="Parker" se transcribe bien y no cuesta tiempo.
        self.hotwords = hotwords
        # Plan §2.1: `initial_prompt` es un sesgo alternativo a hotwords y
        # `vad_parameters` deja el VAD Silero a medida; ambos None = sin cambios.
        # `volcar_dir` activa el volcado WAV+TXT del corpus STT (plan §2.4).
        self.initial_prompt = initial_prompt
        self.vad_parameters = vad_parameters or None
        self.volcar_dir = volcar_dir or None
        self.sample_rate = 16000
        self.backend = "openai"
        # Los tests del enrutado nube/local no necesitan cargar Whisper (1-2 s
        # por instancia): con `cargar_modelo=False` solo se prueba la lógica.
        if not cargar_modelo:
            self.backend = "ninguno"
            self.modelo = None
            self.modelo_faster = None
            self.beam_size = beam_size
            self.vad_filter = vad_filter
            return
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.modelo = None
        self.modelo_faster = None

        if backend in ("auto", "faster-whisper") and _TIENE_FASTER:
            try:
                nombre = modelo_faster or modelo
                print(f"[Escucha] Cargando faster-whisper '{nombre}' (int8, CPU)...")
                # int8 = más rápido y menos RAM en ARM; cpu_threads = núcleos a usar.
                # Medido en la placa con audio de 5,9 s: `base` tarda 1,6-2,0 s
                # frente a 4,8-5,3 s de `small` y 1,0-1,3 s de `tiny` (ilegible).
                self.modelo_faster = _FasterWhisperModel(
                    nombre, device="cpu", compute_type="int8",
                    cpu_threads=cpu_threads or os.cpu_count() or 4,
                )
                self.backend = "faster-whisper"
                print("[Escucha] faster-whisper cargado correctamente")
                return
            except Exception as e:
                print(f"[Escucha] No se pudo cargar faster-whisper ({e}); usando openai-whisper.")
                self.modelo_faster = None

        if _openai_whisper is None:
            raise ImportError(
                "Ni faster-whisper ni openai-whisper están instalados. "
                "Instala uno (pip install faster-whisper)."
            )

        print(f"[Escucha] Cargando modelo Whisper: {modelo}")
        self.modelo = _openai_whisper.load_model(modelo)
        print("[Escucha] Modelo cargado (backend openai-whisper)")

    def _normalizar(self, audio: np.ndarray) -> np.ndarray:
        audio = np.asarray(audio, dtype=np.float32).flatten()
        pico = np.max(np.abs(audio))
        if pico > 0:
            audio = audio / pico
        return audio
    
    # --------------------------------------------------------------- nube ---
    def _clave(self) -> str:
        """Clave de la API (del .env o del entorno), leída una sola vez."""
        if self._clave_nube is None:
            from .cerebro import _leer_clave
            self._clave_nube = _leer_clave(self.nombre_clave) or ""
        return self._clave_nube

    def nube_disponible(self) -> bool:
        return (self.motor_preferido != "local"
                and time.time() >= self._nube_caida_hasta
                and bool(self._clave()))

    def motor_actual(self) -> str:
        """Oído que se usará en el próximo turno: `local`, `nube` o `auto`."""
        return self.motor_preferido

    def cambiar_motor(self, motor: str) -> str:
        """Cambia el STT entre local, nube o automático.

        La transcripción es la entrada del cerebro: con `local` el audio no
        sale de casa (más lento); con `nube` se manda a Groq (más rápido y
        exacto); `auto` usa la nube y cae al local si falla. El cambio es
        inmediato, sin recargar Whisper: el modelo local ya está en memoria.
        """
        pedido = (motor or "").strip().lower()
        if pedido in ("local", "piper", "casa", "placa", "offline"):
            pedido = "local"
        elif pedido in ("nube", "internet", "online", "groq"):
            pedido = "nube"
        elif pedido in ("auto", "automatico", "automática"):
            pedido = "auto"
        else:
            return self.motor_preferido
        if pedido == "nube" and not self._clave():
            print("[Escucha] No hay clave para la nube; uso el oído local.")
            self.motor_preferido = "local"
            return "local"
        self.motor_preferido = pedido
        self._nube_caida_hasta = 0.0
        print(f"[Escucha] Motor STT cambiado a {pedido}")
        return pedido

    def _wav_en_memoria(self, audio: np.ndarray) -> io.BytesIO:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
        buffer.seek(0)
        buffer.name = "turno.wav"
        return buffer

    def _anotar_metadatos(self, segmentos) -> None:
        """Guarda las tres señales de calidad del último Whisper.

        Groq y faster-whisper las devuelven por segmento. Se usa el PEOR
        segmento (máximo no_speech/compresión, mínimo logprob): si una parte
        de la frase es ruido, no se deja pasar solo porque el resto sea buena.
        """
        self.ultimo_no_speech = None
        self.ultimo_avg_logprob = None
        self.ultimo_compresion = None
        if not segmentos:
            return
        no_speech = []
        logprobs = []
        compresiones = []
        for seg in segmentos:
            if isinstance(seg, dict):
                no_speech.append(seg.get("no_speech_prob"))
                logprobs.append(seg.get("avg_logprob"))
                compresiones.append(seg.get("compression_ratio"))
            else:
                no_speech.append(getattr(seg, "no_speech_prob", None))
                logprobs.append(getattr(seg, "avg_logprob", None))
                compresiones.append(getattr(seg, "compression_ratio", None))
        no_speech = [v for v in no_speech if isinstance(v, (int, float))]
        logprobs = [v for v in logprobs if isinstance(v, (int, float))]
        compresiones = [v for v in compresiones if isinstance(v, (int, float))]
        if no_speech:
            self.ultimo_no_speech = max(no_speech)
        if logprobs:
            self.ultimo_avg_logprob = min(logprobs)
        if compresiones:
            self.ultimo_compresion = max(compresiones)

    def _transcribir_nube(self, audio: np.ndarray) -> str:
        """Transcribe el audio en la nube (compatible OpenAI /audio/transcriptions)."""
        with self._wav_en_memoria(audio) as buffer:
            # `prompt` sesga la nube igual que `initial_prompt` al local: sin
            # esto, «¿qué día es mañana?» se transcribía «¿qué dirá es mañana?»
            # y la pregunta de fecha se iba al LLM (oído 25/10).
            # `verbose_json`: además del texto, Groq devuelve no_speech_prob,
            # avg_logprob y compression_ratio; son la señal para descartar
            # «Gracias por ver el video» sin castigar frases cortas reales.
            datos = {"model": self.modelo_nube, "language": self.idioma,
                     "response_format": "verbose_json", "temperature": "0"}
            if self.initial_prompt:
                datos["prompt"] = self.initial_prompt
            res = requests.post(
                f"{self.url_nube}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._clave()}"},
                files={"file": ("turno.wav", buffer, "audio/wav")},
                data=datos,
                timeout=(3.0, self.timeout_nube),
            )
        res.raise_for_status()
        cuerpo = res.json()
        self._anotar_metadatos(cuerpo.get("segments") or [])
        return (cuerpo.get("text") or "").strip()

    def transcribir(self, audio: np.ndarray) -> str:
        """
        Transcribe un array de audio (float32, 16 kHz) a texto.

        Intenta la nube primero (si está configurada y hay red) y cae al motor
        local sin cambiar nada más: mismo contrato, mismo volcado de corpus.
        """
        audio = self._normalizar(audio)
        if self.nube_disponible():
            inicio = time.time()
            try:
                texto = self._transcribir_nube(audio)
                if not texto:
                    raise RuntimeError("la nube devolvió texto vacío")
                self.ultima_latencia = time.time() - inicio
                self.ultimo_motor = "nube"
                self.ultimo_error_nube = ""
                if self.volcar_dir:
                    volcar_audio(self.volcar_dir, audio, texto, self.sample_rate)
                print(f"[Escucha] Transcripción (nube {self.ultima_latencia:.2f}s): '{texto}'")
                return texto
            except Exception as e:
                self.ultimo_error_nube = str(e)[:120]
                self._nube_caida_hasta = time.time() + self.reintento_nube_seg
                print(f"[Escucha] STT nube KO ({self.ultimo_error_nube}); "
                      f"transcribo en local durante {self.reintento_nube_seg:.0f}s")

        inicio = time.time()
        texto = self._transcribir_local(audio)
        self.ultima_latencia = time.time() - inicio
        self.ultimo_motor = "local"
        return texto

    def _transcribir_local(self, audio: np.ndarray) -> str:
        """Motor local (faster-whisper / openai-whisper), sin tocar la red."""
        if self.backend == "faster-whisper":
            extra = {"hotwords": self.hotwords} if self.hotwords else {}
            if self.initial_prompt:
                extra["initial_prompt"] = self.initial_prompt
            if self.vad_parameters:
                extra["vad_parameters"] = self.vad_parameters
            segmentos, _ = self.modelo_faster.transcribe(
                audio,
                language=self.idioma,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,
                without_timestamps=True,
                **extra,
            )
            segmentos = list(segmentos)
            self._anotar_metadatos(segmentos)
            texto = " ".join(seg.text.strip() for seg in segmentos).strip()
            if self.volcar_dir:
                volcar_audio(self.volcar_dir, audio, texto, self.sample_rate)
            print(f"[Escucha] Transcripción: '{texto}'")
            return texto

        # --- Backend openai-whisper (espera un archivo WAV en disco) ---
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = tmp.name

        try:
            audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())

            kwargs = {"language": self.idioma, "fp16": False}
            if self.initial_prompt:
                kwargs["initial_prompt"] = self.initial_prompt
            resultado = self.modelo.transcribe(temp_path, **kwargs)

            texto = resultado["text"].strip()
            if self.volcar_dir:
                volcar_audio(self.volcar_dir, audio, texto, self.sample_rate)
            print(f"[Escucha] Transcripción: '{texto}'")
            return texto

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def grabar_y_transcribir(self, duracion: float = 5.0) -> str:
        """
        Graba audio por duración fija y transcribe.
        """
        print(f"[Escucha] Grabando {duracion} segundos...")
        
        audio = sd.rec(
            int(duracion * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32
        )
        sd.wait()
        
        audio = audio.flatten()
        duracion_real = len(audio) / self.sample_rate
        print(f"[Escucha] Grabado: {duracion_real:.2f}s")
        
        return self.transcribir(audio)