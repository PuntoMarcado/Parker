"""
modulos/sonidos.py
==================
Efectos de sonido que Parker hace con su altavoz.

El primero es el **silbido**. En la placa (25/10/2026) Parker decía «no puedo
silbar» o «ahora te silbo» y no sonaba nada; su ficha incluso soñaba con
«aprender a silbar, aunque no tenga boca». El altavoz es su boca, así que aquí
se genera un silbido de verdad: una melodía corta de tonos casi puros con
vibrato y portamento, como un silbido humano.

Desde la agenda (26/10/2026) hay dos más, para que un aviso **se oiga**:

* `campana`: dos notas con caída (un aviso corto y amable).
* `despertador`: cuatro ráfagas de dos pitidos (lo que suena en una alarma,
  para que se oiga aunque estés en otra habitación).

Y desde la v6.8.1, `micro_listo`: dos notas ascendentes y cortas que suenan
cuando el micrófono USB termina de enumerar y Parker ya puede oír (la cara
aparece antes que el oído; sin señal no se sabe cuándo hablar).

No usa red ni modelos: es aritmética con numpy y se reproduce por la misma
salida que la voz (`VozParker.reproducir`).
"""

import numpy as np

SAMPLE_RATE = 22050


def _nota(f0: float, f1: float, duracion: float,
          sample_rate: int = SAMPLE_RATE, vibrato_hz: float = 5.5) -> np.ndarray:
    """Un tono con glide de `f0` a `f1`, vibrato suave y envolvente."""
    n = max(1, int(sample_rate * duracion))
    t = np.arange(n, dtype=np.float32) / sample_rate
    # Portamento: el silbido humano no salta de nota, se desliza.
    freq = f0 + (f1 - f0) * (t / max(duracion, 1e-6))
    freq = freq * (1.0 + 0.006 * np.sin(2 * np.pi * vibrato_hz * t))
    fase = 2 * np.pi * np.cumsum(freq) / sample_rate
    # Un armónico muy bajo da cuerpo sin dejar de sonar a silbido.
    onda = np.sin(fase) + 0.12 * np.sin(2 * fase)
    ataque = min(0.03, duracion / 4)
    caida = min(0.06, duracion / 3)
    envolvente = (np.minimum(1.0, t / ataque)
                  * np.minimum(1.0, (duracion - t) / caida))
    return (onda * np.clip(envolvente, 0.0, 1.0)).astype(np.float32)


def _pitido(frecuencia: float, duracion: float, caida: float = 0.35,
            sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Tono corto con ataque rápido y caída exponencial (suena a campana)."""
    n = max(1, int(sample_rate * duracion))
    t = np.arange(n, dtype=np.float32) / sample_rate
    envolvente = np.exp(-t / max(caida, 1e-6))
    envolvente *= np.minimum(1.0, t / 0.004)
    # El segundo armónico (×2,12) es lo que da timbre metálico a una campana.
    onda = (np.sin(2 * np.pi * frecuencia * t)
            + 0.35 * np.sin(2 * np.pi * frecuencia * 2.12 * t))
    return (onda * envolvente).astype(np.float32)


def _normalizar(audio: np.ndarray, volumen: float) -> np.ndarray:
    """Deja el pico exactamente en `volumen` (0-1), como `silbar`."""
    pico = float(np.max(np.abs(audio))) if audio.size else 0.0
    if pico > 0:
        audio = audio / pico * max(0.0, min(1.0, float(volumen)))
    return np.clip(audio, -1.0, 1.0).astype(np.float32)


def campana(volumen: float = 0.55, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """~1,2 s: «din-don» de dos notas, para avisar de algo puntual."""
    silencio = np.zeros(int(sample_rate * 0.05), dtype=np.float32)
    audio = np.concatenate([
        _pitido(880.0, 0.55, sample_rate=sample_rate),
        silencio,
        _pitido(659.25, 0.6, sample_rate=sample_rate),
    ])
    return _normalizar(audio, volumen)


def micro_listo(volumen: float = 0.35, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """~0,45 s: dos notas ascendentes, «ya te escucho».

    La cara aparece antes de que el micro USB termine de enumerar; este aviso
    suena justo cuando el oído queda abierto. Es distinto de `campana` (dos
    notas descendentes y más largas, la de la agenda) para no confundirlos.
    """
    silencio = np.zeros(int(sample_rate * 0.03), dtype=np.float32)
    audio = np.concatenate([
        _pitido(659.25, 0.18, caida=0.18, sample_rate=sample_rate),
        silencio,
        _pitido(987.77, 0.22, caida=0.20, sample_rate=sample_rate),
    ])
    return _normalizar(audio, volumen)


def despertador(volumen: float = 0.55, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """~3 s: cuatro ráfagas de dos pitidos, lo que suena en una alarma.

    Dura lo justo para reconocerlo desde otra habitación sin quedarse sonando
    para siempre: si el aviso de agenda suena, Parker además lo dice.
    """
    parte = np.concatenate([
        _pitido(1046.5, 0.16, caida=0.12, sample_rate=sample_rate),
        np.zeros(int(sample_rate * 0.05), dtype=np.float32),
        _pitido(1318.5, 0.20, caida=0.14, sample_rate=sample_rate),
    ])
    pausa = np.zeros(int(sample_rate * 0.28), dtype=np.float32)
    audio = np.concatenate([parte, pausa, parte, pausa, parte, pausa, parte])
    return _normalizar(audio, volumen)


def silbar(volumen: float = 0.55, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Devuelve ~2 s de silbido, con pico igual a `volumen` (0-1)."""
    melodia = [
        (880.0, 988.0, 0.18),    # la5 -> si5
        (988.0, 1175.0, 0.16),   # si5 -> re6
        (1175.0, 1175.0, 0.26),  # re6 sostenido
        (1175.0, 988.0, 0.20),   # re6 -> si5
        (988.0, 784.0, 0.42),    # si5 -> sol5, cierre
    ]
    silencio = np.zeros(int(sample_rate * 0.04), dtype=np.float32)
    partes = []
    for f0, f1, duracion in melodia:
        partes.append(_nota(f0, f1, duracion, sample_rate))
        partes.append(silencio)
    return _normalizar(np.concatenate(partes), volumen)
