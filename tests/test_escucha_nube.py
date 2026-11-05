"""
tests/test_escucha_nube.py
==========================
Pruebas del motor de transcripción con nube (v6.1).

Motivo: la transcripción es la ENTRADA del cerebro. Medido en la placa con la
misma frase de 6,1 s grabada por el micro USB (25/10):

    local faster-whisper base   -> 4,31 s y «en al médico» (un error)
    nube whisper-large-v3-turbo -> 0,68 s y texto exacto

Se comprueba:
  1. Con nube disponible, transcribe la nube (y no el local).
  2. Si la nube falla, ese turno lo transcribe el local.
  3. Tras fallar no se reintenta en cada frase (circuit breaker de 60 s).
  4. Con `motor: "local"` no se toca la red: el audio no sale de casa.
  5. El WAV que se envía es mono, 16 kHz y PCM16 (lo que espera la API).

No hace red: se sustituye `escucha.requests.post`.
"""

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import modulos.escucha as modulo  # noqa: E402
from modulos.escucha import EscuchaParker  # noqa: E402


class RespuestaFalsa:
    def __init__(self, texto: str, segmentos=None):
        self._texto = texto
        self._segmentos = segmentos or []

    def raise_for_status(self):
        pass

    def json(self):
        return {"text": self._texto, "segments": self._segmentos}


def _escucha(motor: str = "auto", initial_prompt=None) -> EscuchaParker:
    """Instancia sin cargar Whisper (el local se simula en cada test)."""
    escucha = EscuchaParker(idioma="es", backend="faster-whisper", motor=motor,
                            initial_prompt=initial_prompt,
                            cargar_modelo=False)
    escucha._clave_nube = "clave-de-prueba"
    # El motor local se sustituye: aquí solo interesa el enrutado.
    escucha._transcribir_local = lambda audio: "texto local"
    return escucha


def _audio(segundos: float = 1.0) -> np.ndarray:
    t = np.arange(int(16000 * segundos)) / 16000.0
    return (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_nube_transcribe():
    escucha = _escucha()
    capturado = {}

    def post_falso(url, headers=None, files=None, data=None, timeout=None):
        capturado["url"] = url
        capturado["modelo"] = data["model"]
        capturado["idioma"] = data["language"]
        capturado["prompt"] = data.get("prompt")
        # Comprobar el WAV que se manda: 16 kHz, mono, PCM16.
        fichero = files["file"][1]
        with wave.open(fichero, "rb") as w:
            capturado["formato"] = (w.getframerate(), w.getnchannels(), w.getsampwidth())
        return RespuestaFalsa("Hola Parker, ¿me oyes?")

    original = modulo.requests.post
    modulo.requests.post = post_falso
    try:
        texto = escucha.transcribir(_audio())
    finally:
        modulo.requests.post = original

    assert texto == "Hola Parker, ¿me oyes?", texto
    assert escucha.ultimo_motor == "nube", escucha.ultimo_motor
    assert capturado["url"].endswith("/audio/transcriptions"), capturado["url"]
    assert capturado["modelo"] == "whisper-large-v3-turbo", capturado["modelo"]
    assert capturado["idioma"] == "es", capturado["idioma"]
    assert capturado["formato"] == (16000, 1, 2), capturado["formato"]
    # Sin prompt: con audio poco claro Whisper devolvía el prompt como si
    # fuera voz («Parker se escribe Parker.»). El nombre lo cubre hotwords.
    assert capturado["prompt"] is None, capturado["prompt"]
    print("[OK] la nube transcribe sin prompt y el WAV va en 16 kHz mono PCM16")


def test_respaldo_local_y_circuit_breaker():
    escucha = _escucha()
    llamadas = {"nube": 0}

    def post_falso(*a, **k):
        llamadas["nube"] += 1
        raise ConnectionError("sin internet")

    original = modulo.requests.post
    modulo.requests.post = post_falso
    try:
        texto1 = escucha.transcribir(_audio())
        texto2 = escucha.transcribir(_audio())
    finally:
        modulo.requests.post = original

    assert texto1 == "texto local" and texto2 == "texto local"
    assert escucha.ultimo_motor == "local", escucha.ultimo_motor
    assert llamadas["nube"] == 1, llamadas      # el 2º turno ya no lo intenta
    assert "sin internet" in escucha.ultimo_error_nube
    print("[OK] si la nube cae, transcribe el local y no reintenta en cada frase")


def test_motor_local_no_sale_de_casa():
    escucha = _escucha(motor="local")
    llamado = {"post": 0}

    def post_falso(*a, **k):
        llamado["post"] += 1
        raise AssertionError("no debía llamarse a la red")

    original = modulo.requests.post
    modulo.requests.post = post_falso
    try:
        texto = escucha.transcribir(_audio())
    finally:
        modulo.requests.post = original

    assert texto == "texto local", texto
    assert llamado["post"] == 0
    print("[OK] con motor «local» el audio no sale del dispositivo")


def test_sin_clave_usa_local():
    escucha = _escucha()
    escucha._clave_nube = ""
    assert escucha.nube_disponible() is False
    assert escucha.transcribir(_audio()) == "texto local"
    print("[OK] sin clave de API transcribe en local")


def test_metadatos_verbose_json():
    """La nube devuelve las señales que usa el filtro de ruido."""
    escucha = _escucha()

    def post_falso(*a, **k):
        return RespuestaFalsa(
            "texto raro",
            segmentos=[
                {"no_speech_prob": 0.91, "avg_logprob": -0.2,
                 "compression_ratio": 1.1},
                {"no_speech_prob": 0.2, "avg_logprob": -1.7,
                 "compression_ratio": 2.0},
            ],
        )

    original = modulo.requests.post
    modulo.requests.post = post_falso
    try:
        texto = escucha.transcribir(_audio())
    finally:
        modulo.requests.post = original

    assert texto == "texto raro", texto
    assert escucha.ultimo_no_speech == 0.91, escucha.ultimo_no_speech
    assert escucha.ultimo_avg_logprob == -1.7, escucha.ultimo_avg_logprob
    assert escucha.ultimo_compresion == 2.0, escucha.ultimo_compresion
    print("[OK] la nube entrega no_speech/logprob/compresión al filtro")


def main():
    test_nube_transcribe()
    test_respaldo_local_y_circuit_breaker()
    test_motor_local_no_sale_de_casa()
    test_sin_clave_usa_local()
    test_metadatos_verbose_json()
    print("\nSTT con nube: 5/5 en verde.")


if __name__ == "__main__":
    main()
