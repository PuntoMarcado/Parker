"""
modulos/voz.py
==============
Síntesis de voz local usando Piper TTS con modelos ONNX optimizados.
Versión optimizada: Procesamiento 100% en RAM (sin archivos temporales).
"""

import asyncio
import io
import os
import shutil
import subprocess
import threading
import time
import wave

import numpy as np
import sounddevice as sd
from piper.voice import PiperVoice
from typing import Optional

try:  # opcional: si no está instalado, Parker sigue con Piper
    import edge_tts
    _TIENE_EDGE = True
except Exception:
    edge_tts = None
    _TIENE_EDGE = False

try:  # piper >= 1.8: velocidad y volumen dentro del modelo
    from piper.config import SynthesisConfig
    _TIENE_SYNTHESIS_CONFIG = True
except Exception:  # piper antiguo: se usan los apaños de abajo
    SynthesisConfig = None
    _TIENE_SYNTHESIS_CONFIG = False


class VozParker:
    """
    Voz de Parker: Edge TTS (voz de Microsoft, natural) o Piper local.

    Edge es el motor preferido si está instalado y hay red; Piper se carga
    SIEMPRE como respaldo y entra solo si Edge falla (sin internet, voz no
    disponible, timeout). Así el cerebro puede ser el de la nube y la voz no
    deja a Parker mudo cuando se cae la conexión. Todo el audio se entrega en
    el mismo formato float32 mono y al mismo `sample_rate`, para que el
    reproductor y el look-ahead no se enteren de qué motor lo generó.
    """

    def __init__(self, modelo_path: str, config_path: Optional[str] = None,
                 velocidad: float = 1.0, volumen: float = 0.9,
                 motor: str = "piper", edge_voz: str = "es-ES-XimenaNeural",
                 edge_timeout: float = 8.0, edge_reintento_seg: float = 60.0,
                 edge_ffmpeg: str = "ffmpeg"):
        # Valores por defecto provenientes de config.yaml (voz.velocidad / voz.volumen)
        self.velocidad = velocidad
        self.volumen = volumen
        # «Silencia» no toca el modelo de voz: deja de sonar y ya está. Se
        # desactiva al decir «quita el silencio» (modulos/acciones.py).
        self.silenciado = False
        # Barge-in: `detener()` marca este evento y corta el stream. El bucle
        # de reproducción lo consulta; sin esto, `sd.wait()` puede quedarse
        # esperando aunque `sd.stop()` ya haya parado el altavoz (visto en la
        # placa el 01/11: Parker dejó de hablar y se quedó sorda).
        self._detener = threading.Event()

        self.motor = (motor or "piper").strip().lower()
        if self.motor not in ("piper", "edge"):
            self.motor = "piper"
        self.edge_voz = edge_voz or "es-ES-XimenaNeural"
        self.edge_timeout = max(2.0, float(edge_timeout))
        self.edge_reintento_seg = max(5.0, float(edge_reintento_seg))
        self.edge_ffmpeg = edge_ffmpeg or "ffmpeg"
        self._edge_fallo_hasta = 0.0
        self._edge_ultimo_error = ""
        self._edge_disponible = bool(
            _TIENE_EDGE and shutil.which(self.edge_ffmpeg))

        if self.motor == "edge" and not self._edge_disponible:
            print("[Voz] Edge TTS no disponible (falta edge-tts o ffmpeg); "
                  "uso Piper.")
            self.motor = "piper"

        if not os.path.exists(modelo_path):
            raise FileNotFoundError(f"Modelo no encontrado: {modelo_path}")

        if config_path is None:
            config_path = modelo_path + ".json"

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config no encontrado: {config_path}")

        print(f"[Voz] Cargando modelo Piper: {os.path.basename(modelo_path)}")
        self.voz = PiperVoice.load(modelo_path, config_path)
        self.sample_rate = self.voz.config.sample_rate
        if self.motor == "edge":
            print(f"[Voz] Motor: Edge TTS ({self.edge_voz}); "
                  f"respaldo Piper {self.sample_rate}Hz")
        else:
            print(f"[Voz] Motor: Piper local. Sample rate: {self.sample_rate}Hz")

    def motor_actual(self) -> str:
        """Motor que está sonando ahora: `piper` o `edge`."""
        return self.motor

    def preparar_turno(self) -> None:
        """Limpia el corte del turno anterior antes de empezar a hablar.

        `detener()` deja el evento marcado para que la frase en curso pare.
        Si no se limpia al empezar el turno siguiente, la primera síntesis
        nueva se descartaría sola y Parker se quedaría mudo tras un
        barge-in.
        """
        evento = getattr(self, "_detener", None)
        if evento is not None:
            evento.clear()

    def cambiar_motor(self, motor: str) -> str:
        """Cambia entre voz local (Piper) y voz de internet (Edge).

        Pedido el 01/11/2026: «cambia la voz al local» no hacía nada porque
        solo existía el cambio de cerebro. El modelo de voz ya está cargado
        (Piper se carga SIEMPRE), así que el cambio es inmediato y no toca la
        conversación. Devuelve el motor que ha quedado de verdad: si Edge no
        está instalado o falta ffmpeg, sigue en Piper sin romper el turno.
        """
        pedido = (motor or "").strip().lower()
        if pedido in ("local", "piper", "casa", "placa", "offline"):
            pedido = "piper"
        elif pedido in ("nube", "edge", "internet", "online", "ximena"):
            pedido = "edge"
        if pedido not in ("piper", "edge"):
            return self.motor
        if pedido == "edge" and not self._edge_disponible:
            print("[Voz] No puedo usar Edge (falta edge-tts o ffmpeg); "
                  "sigo con Piper.")
            self.motor = "piper"
            return self.motor
        self.motor = pedido
        self._edge_fallo_hasta = 0.0
        self._edge_ultimo_error = ""
        if pedido == "edge":
            print(f"[Voz] Motor cambiado a Edge TTS ({self.edge_voz})")
        else:
            print("[Voz] Motor cambiado a Piper local")
        return self.motor

    @staticmethod
    def _edge_rate(velocidad: float) -> str:
        """0.85 -> "-15%": Edge cambia el ritmo sin tocar el tono."""
        porcentaje = int(round((float(velocidad) - 1.0) * 100))
        return f"{max(-40, min(40, porcentaje)):+d}%"

    def _sintetizar_edge(self, texto: str, velocidad: float,
                         volumen: float) -> np.ndarray:
        """Texto -> PCM float32 usando la voz de Microsoft (MP3 + ffmpeg).

        Edge devuelve MP3; se decodifica a PCM con ffmpeg y se entrega al
        mismo `sample_rate` que Piper para que `reproducir()` no cambie. El
        volumen se aplica aquí, no en Edge, para que «baja el volumen» siga
        funcionando igual con los dos motores.
        """
        if not self._edge_disponible:
            raise RuntimeError("edge-tts o ffmpeg no disponibles")

        async def _recoger() -> bytes:
            comunicador = edge_tts.Communicate(
                texto, self.edge_voz, rate=self._edge_rate(velocidad))
            trozos = []
            async for trozo in comunicador.stream():
                if trozo.get("type") == "audio":
                    datos = trozo.get("data")
                    if datos:
                        trozos.append(datos)
            return b"".join(trozos)

        mp3 = asyncio.run(asyncio.wait_for(_recoger(),
                                           timeout=self.edge_timeout))
        if not mp3:
            raise RuntimeError("Edge no devolvió audio")

        orden = [self.edge_ffmpeg, "-hide_banner", "-loglevel", "error",
                 "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
                 "-ac", "1", "-ar", str(self.sample_rate), "pipe:1"]
        proceso = subprocess.run(orden, input=mp3, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 timeout=self.edge_timeout + 5)
        if proceso.returncode != 0 or not proceso.stdout:
            error = proceso.stderr.decode("utf-8", "ignore")[:160]
            raise RuntimeError(f"ffmpeg no pudo decodificar Edge: {error}")

        audio = (np.frombuffer(proceso.stdout, dtype=np.int16)
                 .astype(np.float32) / 32768.0)
        # Edge entrega la señal bastante más baja que Piper (pico ~0,28 con
        # volumen 0,55). Se normaliza por frase y luego se aplica el volumen
        # pedido: así «baja el volumen» suena igual de fuerte con los dos
        # motores y Ximena no queda como un susurro.
        pico = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if pico > 1e-6:
            audio = audio * min(4.0, 0.92 / pico)
        return np.clip(audio * volumen, -1.0, 1.0)

    def _sintetizar_piper(self, texto: str, velocidad: float,
                          volumen: float) -> np.ndarray:
        """Síntesis local con Piper (el cuerpo antiguo de `sintetizar`)."""
        try:
            wav_io = io.BytesIO()
            syn_config = None
            if _TIENE_SYNTHESIS_CONFIG:
                syn_config = SynthesisConfig(length_scale=1.0 / velocidad,
                                             volume=volumen)

            with wave.open(wav_io, 'wb') as wav_file:
                if syn_config is not None:
                    self.voz.synthesize_wav(texto, wav_file, syn_config=syn_config)
                else:
                    self.voz.synthesize_wav(texto, wav_file)

            wav_io.seek(0)

            with wave.open(wav_io, 'rb') as wf:
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return np.array([])

                frames = wf.readframes(n_frames)
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            if syn_config is None:
                # Piper antiguo: ganancia + interpolación (cambia el tono, pero
                # al menos evita el ruido del diezmado).
                audio = audio * volumen
                if velocidad != 1.0:
                    n = max(1, int(round(len(audio) / velocidad)))
                    audio = np.interp(np.linspace(0, len(audio) - 1, n),
                                      np.arange(len(audio)), audio).astype(np.float32)

            return np.clip(audio, -1.0, 1.0)

        except Exception as e:
            print(f"[Voz] Error en Piper: {e}")
            return np.array([])

    def _marcar_fallo_edge(self, error: Exception) -> None:
        """Evita pagar el timeout de Edge en cada frase durante un rato."""
        self._edge_fallo_hasta = time.time() + self.edge_reintento_seg
        mensaje = str(error)[:160]
        if mensaje != self._edge_ultimo_error:
            print(f"[Voz] Edge TTS falló ({mensaje}); uso Piper "
                  f"{self.edge_reintento_seg:.0f}s y reintento después.")
            self._edge_ultimo_error = mensaje

    def sintetizar(self, texto: str,
                   velocidad: Optional[float] = None,
                   volumen: Optional[float] = None) -> np.ndarray:
        """Texto -> audio float32 mono a `self.sample_rate`.

        `velocidad` es el ritmo: 1.0 normal, 0.85 más calmado. Con Piper se
        aplica con `length_scale` DENTRO del modelo (1/velocidad), no
        remuestreando: remuestrear alarga el audio y **baja el tono** (fallo
        corregido el 17/10/2026). Con Edge se pide como porcentaje de ritmo,
        que tampoco cambia el tono.

        `volumen` es una ganancia 0-1. En Piper va dentro del modelo, después
        de normalizar; en Edge se aplica al PCM ya decodificado. En ambos casos
        0.55 suena a conversación y no satura.
        """
        velocidad = self.velocidad if velocidad is None else velocidad
        volumen = self.volumen if volumen is None else volumen

        if not texto or not texto.strip():
            return np.array([])

        velocidad = max(0.5, min(1.5, float(velocidad or 1.0)))
        volumen = max(0.0, min(1.0, float(volumen or 1.0)))

        # Si el barge-in ya pidió parar, no se gasta ni un milisegundo en
        # sintetizar una frase que ya no se va a decir. `_detener` puede no
        # existir en objetos creados a medias (tests, arranques parciales):
        # en ese caso no hay corte pendiente, no se rompe la síntesis.
        evento = getattr(self, "_detener", None)
        if evento is not None and evento.is_set():
            return np.array([])

        if (self.motor == "edge" and self._edge_disponible
                and time.time() >= self._edge_fallo_hasta):
            try:
                audio = self._sintetizar_edge(texto, velocidad, volumen)
                if len(audio) > 0:
                    self._edge_ultimo_error = ""
                    return audio
                raise RuntimeError("Edge devolvió audio vacío")
            except Exception as e:
                self._marcar_fallo_edge(e)

        return self._sintetizar_piper(texto, velocidad, volumen)

    def hablar(self, texto: str,
               velocidad: Optional[float] = None,
               volumen: Optional[float] = None,
               bloquear: bool = True):
        if not texto or not texto.strip():
            return

        # Una llamada directa a `hablar()` es un turno nuevo: si venía de un
        # barge-in, se limpia el corte para no quedarse mudo.
        self.preparar_turno()
        print(f"[Voz] Hablando: '{texto[:60]}...'")

        audio_data = self.sintetizar(texto, velocidad, volumen)
        self.reproducir(audio_data, bloquear=bloquear)

    def reproducir(self, audio_data, bloquear: bool = True, forzar: bool = False):
        """Suena un buffer ya sintetizado.

        Separar sintetizar de reproducir es lo que permite el look-ahead del
        orador: mientras la frase n suena aquí, el otro hilo ya sintetiza la
        n+1 y el hueco muerto entre frases desaparece.

        `forzar=True` suena aunque la voz esté silenciada: lo usa la agenda
        (`parker._avisar_agenda`) para la campana de una alarma, que se pidió a
        propósito y tiene que oírse.
        """
        if audio_data is None or len(audio_data) == 0:
            print("[Voz] Advertencia: no se genero audio")
            return
        if getattr(self, "silenciado", False) and not forzar:
            print("[Voz] (silenciado; no suena)")
            return
        # Un audio que llega después de un barge-in ya no debe sonar. El
        # evento lo limpia `preparar_turno()` al empezar el siguiente turno;
        # limpiarlo aquí hacía que la frase sintetizada durante el corte
        # sonara igualmente (fallo del 01/11).
        evento = getattr(self, "_detener", None)
        if evento is not None and evento.is_set() and not forzar:
            print("[Voz] (audio descartado: turno interrumpido)")
            return

        # En la placa el altavoz y el micro comparten tarjeta: al abrir el
        # stream justo después de otro sonido, ALSA puede devolver «Device
        # unavailable» un instante. Dos reintentos cortos evitan perder la
        # frase (visto al probar Edge el 30/10).
        for intento in range(3):
            try:
                sd.play(audio_data, self.sample_rate)
                break
            except Exception as e:
                sd.stop()
                if intento == 2:
                    print(f"[Voz] Error al reproducir audio: {e}")
                    return
                time.sleep(0.15 * (intento + 1))

        if bloquear:
            # Antes era `sd.wait()`. En la placa, tras `sd.stop()` desde el
            # monitor de barge-in, se quedaba esperando para siempre y el turno
            # no soltaba `ocupado` (Parker dejaba de responder). Se consulta el
            # stream y el evento de corte cada 20 ms en su lugar.
            stream = None
            try:
                stream = sd.get_stream()
                while stream is not None and stream.active:
                    if evento is not None and evento.is_set():
                        break
                    time.sleep(0.02)
                if evento is not None and evento.is_set():
                    print("[Voz] Reproducción detenida")
                else:
                    print("[Voz] Reproduccion finalizada")
            except Exception as e:
                print(f"[Voz] Error al esperar el audio: {e}")
            finally:
                # Cerrar el stream de salida al terminar la frase. `sd.stop()`
                # lo paraba pero no siempre lo cerraba: el fd quedaba abierto y
                # otro proceso recibía «Device or resource busy».
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                if evento is not None:
                    evento.clear()

    def detener(self):
        """Corta la reproducción en curso (barge-in).

        Marca el evento que consulta `reproducir` y para el stream de salida.
        No cierra ni toca el micrófono: el InputStream del monitor es
        independiente. El evento se limpia al empezar la siguiente frase.
        """
        evento = getattr(self, "_detener", None)
        if evento is not None:
            evento.set()
        try:
            sd.stop()
            print("[Voz] Reproducción cortada por barge-in")
        except Exception as e:
            print(f"[Voz] No pude cortar la reproducción: {e}")

    def guardar_a_archivo(self, texto: str, 
                          ruta_salida: str,
                          velocidad: float = 1.0,
                          volumen: float = 1.0):
        audio_data = self.sintetizar(texto, velocidad, volumen)

        if len(audio_data) == 0:
            print(f"[Voz] Error: no se pudo generar audio para guardar")
            return

        try:
            audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            
            with wave.open(ruta_salida, 'wb') as wf_out:
                wf_out.setnchannels(1)
                wf_out.setsampwidth(2)
                wf_out.setframerate(self.sample_rate)
                wf_out.writeframes(audio_int16.tobytes())
                
            print(f"[Voz] Audio guardado: {ruta_salida}")
        except Exception as e:
            print(f"[Voz] Error al guardar archivo: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("TEST DE VOZ PARKER v5")
    print("=" * 50)

    MODELO = "./assets/voz/es_ES-davefx-medium.onnx"

    if os.path.exists(MODELO):
        try:
            voz = VozParker(MODELO)
            voz.hablar("Hola, soy Parker. Test de voz completado correctamente.", velocidad=1.0)
        except Exception as e:
            print(f"[ERROR] {e}")