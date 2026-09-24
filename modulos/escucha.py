"""
modulos/escucha.py
==================
Transcripción de voz a texto usando OpenAI Whisper de forma local.
"""

import whisper
import numpy as np
import sounddevice as sd
import tempfile
import wave
import os
from typing import Optional


class EscuchaParker:
    """
    Motor de Speech-to-Text local con Whisper.
    """
    
    def __init__(self, modelo: str = "base", idioma: str = "es"):
        print(f"[Escucha] Cargando modelo Whisper: {modelo}")
        self.modelo = whisper.load_model(modelo)
        self.idioma = idioma
        self.sample_rate = 16000
        print("[Escucha] Modelo cargado correctamente")
    
    def transcribir(self, audio: np.ndarray) -> str:
        """
        Transcribe un array de audio a texto usando Whisper.
        """
        # Guardar temporalmente como WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = tmp.name
        
        try:
            # Asegurar que el audio esté en el rango correcto [-1, 1]
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))
            
            # Convertir a int16 para WAV
            audio_int16 = (audio * 32767).astype(np.int16)
            
            # Guardar como WAV
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())
            
            # DEBUG: Verificar archivo
            with wave.open(temp_path, 'rb') as wf:
                frames = wf.getnframes()
                duracion = frames / self.sample_rate
                print(f"[Escucha] WAV: {frames} frames, {duracion:.2f}s")
            
            # Transcribir
            resultado = self.modelo.transcribe(
                temp_path,
                language=self.idioma,
                fp16=False
            )
            
            texto = resultado["text"].strip()
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