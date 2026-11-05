"""modulos/filtro_stt.py
======================
Descarta transcripciones que no son voz útil.

Por qué existe (01/11/2026)
---------------------------
Whisper, sobre todo con audio de sala y el micro pegado al altavoz, inventa
frases cuando no hay voz clara: «Gracias por ver el video», «¡Ah! ¡Ah! ¡Ah!»,
«Suscríbete al canal». El VAD ya filtra parte, pero no toda; el resultado era
que Parker contestaba a ruido como si fuera una persona.

El filtro es deliberadamente **conservador**: solo tira lo que tiene una señal
clara de basura. No intenta adivinar el sentido ni corrige la frase; para eso
está el cerebro. Así una respuesta corta legítima («sí», «no», «vale», «hola
Parker») sigue pasando.

Las métricas `no_speech_prob`, `avg_logprob` y `compression_ratio` las devuelve
Whisper (local y nube en `verbose_json`). Cuando no están, se usan solo las
reglas de texto.
"""

import re
import unicodedata
from typing import Optional

# Frases que Whisper inventa con silencio, música o ruido. Se comparan sin
# tildes ni signos. No se incluyen saludos normales («hola», «gracias»): esos
# pueden ser una respuesta real.
_ALUCINACIONES = (
    "gracias por ver el video",
    "gracias por ver el vídeo",
    "no olvides suscribirte",
    "suscribete al canal",
    "suscríbete al canal",
    "dale like",
    "hasta la proxima",
    "hasta la próxima",
    "subtitulos realizados por",
    "subtítulos realizados por",
    "www punto",
)

# Interjecciones que Whisper repite cuando oye un golpe o la cola del altavoz.
_INTERJECCIONES = {"ah", "eh", "oh", "uh", "mmm", "mm", "hum", "hmm"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9ñ ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def es_alucinacion_conocida(texto: str) -> bool:
    """¿Es una de las frases que Whisper inventa sobre ruido?"""
    normal = _normalizar(texto)
    if not normal:
        return False
    for frase in _ALUCINACIONES:
        if normal == frase or normal.startswith(frase + " "):
            return True
    return False


def es_repeticion_sin_sentido(texto: str) -> bool:
    """¿La transcripción es la misma palabra/golpe repetido?

    «¡Ah! ¡Ah! ¡Ah!» o «la la la la» no son una frase. Se exige que la palabra
    repetida sea una interjección o que haya al menos cuatro repeticiones, para
    no tirar un «sí, sí, sí» dicho con énfasis.
    """
    normal = _normalizar(texto)
    palabras = normal.split()
    if len(palabras) < 3:
        return False
    if len(set(palabras)) == 1:
        return palabras[0] in _INTERJECCIONES or len(palabras) >= 5
    # Repetición dominante: 4 de 5 palabras iguales, por ejemplo.
    if len(palabras) >= 5:
        from collections import Counter
        _, veces = Counter(palabras).most_common(1)[0]
        if veces / len(palabras) >= 0.75:
            return True
    # Bloque corto repetido: «oído local, oído local, oído local» es la cola
    # del altavoz, no una frase. Se exige el bloque completo tres veces para
    # no tirar un «no, no» ni un «muy bien, muy bien» dicho con énfasis.
    for tam in range(2, min(4, len(palabras) // 3) + 1):
        if len(palabras) % tam == 0:
            bloque = palabras[:tam]
            if all(palabras[i:i + tam] == bloque
                   for i in range(0, len(palabras), tam)):
                return True
    return False


def es_transcripcion_dudosa(texto: str,
                            no_speech: Optional[float] = None,
                            avg_logprob: Optional[float] = None,
                            compression_ratio: Optional[float] = None) -> bool:
    """Decide si una transcripción debe ignorarse antes de llamar al cerebro.

    Los umbrales son altos a propósito: `no_speech` de 0,8 o `avg_logprob` de
    -1,5 son señales fuertes, no una simple duda. Un falso descarte deja a
    Parker sin oír una frase; un falso positivo le hace contestar a la tele.
    """
    if not (texto or "").strip():
        return True
    normal = _normalizar(texto)
    # Un «ah», «eh», «mmm» suelto es un golpe o la cola del altavoz, no una
    # frase: no merece despertar al cerebro (visto en la placa el 01/11).
    if normal in _INTERJECCIONES:
        return True
    if es_alucinacion_conocida(texto):
        return True
    if es_repeticion_sin_sentido(texto):
        return True
    if no_speech is not None and no_speech >= 0.80:
        return True
    if compression_ratio is not None and compression_ratio >= 3.0:
        return True
    if avg_logprob is not None and avg_logprob <= -1.5:
        # Solo se usa como confirmación: una frase normal no baja de -1,5.
        return True
    return False
