"""
modulos/voz.py
==============
Síntesis de voz local usando Piper TTS con modelos ONNX optimizados.
Versión optimizada: Procesamiento 100% en RAM (sin archivos temporales).
"""

import os
import io
import wave
import sounddevice as sd
import numpy as np
from piper.voice import PiperVoice
from typing import Optional


class VozParker:
    """
    Motor de Text-to-Speech local con Piper ONNX.
    Procesa el audio directamente en memoria RAM.
    """

    def __init__(self, modelo_path: str, config_path: Optional[str] = None):
        if not os.path.exists(modelo_path):
            raise FileNotFoundError(f"Modelo no encontrado: {modelo_path}")

        if config_path is None:
            config_path = modelo_path + ".json"

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config no encontrado: {config_path}")

        print(f"[Voz] Cargando modelo Piper: {os.path.basename(modelo_path)}")
        self.voz = PiperVoice.load(modelo_path, config_path)
        self.sample_rate = self.voz.config.sample_rate
        print(f"[Voz] Modelo cargado. Sample rate: {self.sample_rate}Hz")

    def sintetizar(self, texto: str, 
                   velocidad: float = 1.0,
                   volumen: float = 0.9) -> np.ndarray:
        if not texto or not texto.strip():
            return np.array([])

        try:
            wav_io = io.BytesIO()
            
            with wave.open(wav_io, 'wb') as wav_file:
                self.voz.synthesize_wav(texto, wav_file)
            
            wav_io.seek(0)
            
            with wave.open(wav_io, 'rb') as wf:
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return np.array([])
                
                frames = wf.readframes(n_frames)
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            audio = audio * volumen

            if velocidad != 1.0:
                indices = np.round(np.arange(0, len(audio), velocidad)).astype(int)
                indices = indices[indices < len(audio)]
                audio = audio[indices]

            return audio

        except Exception as e:
            print(f"[Voz] Error en sintetizar: {e}")
            return np.array([])

    def hablar(self, texto: str, 
               velocidad: float = 1.0,
               volumen: float = 0.9,
               bloquear: bool = True):
        if not texto or not texto.strip():
            return

        print(f"[Voz] Hablando: '{texto[:60]}...'")

        audio_data = self.sintetizar(texto, velocidad, volumen)

        if len(audio_data) == 0:
            print("[Voz] Advertencia: no se genero audio")
            return

        try:
            sd.play(audio_data, self.sample_rate)

            if bloquear:
                sd.wait()
                print("[Voz] Reproduccion finalizada")

        except Exception as e:
            print(f"[Voz] Error al reproducir audio: {e}")

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