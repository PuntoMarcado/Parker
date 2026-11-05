"""modulos/barge_in.py
====================
Decide si lo que se oye mientras Parker habla es una ORDEN DE PARADA o es el
eco de su propia voz.

Por qué existe (01/11/2026)
---------------------------
Parker no escucha mientras habla: el bucle principal está ocupado sintetizando
y reproduciendo. Para poder interrumpirle hace falta un monitor aparte, pero el
micro USB está pegado al altavoz y oye la propia voz de Parker. Sin separar
«voz de Parker» de «persona que quiere cortar», el monitor pararía solo.

Las dos reglas son deliberadamente conservadoras:

* Solo se acepta una parada si aparece el nombre («Parker», «oye Parker») y una
  palabra de corte («para», «cállate», «basta», «silencio»). «Parker, ¿para qué
  sirve?» no es una orden.
* Si la transcripción se parece a lo que Parker está diciendo, se trata como
  eco y no se hace nada. La comparación es de texto, no de audio: no necesita
  modelos nuevos ni cancelación de eco.

No sustituye al VAD ni al STT: es una capa de decisión pequeña y testeable.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable

# Palabras con las que la persona puede pedir que Parker se calle. Van después
# del nombre; «para» seguido de «qué/dónde/cuándo/como/si» es una pregunta, no
# una orden.
_NOMBRE = r"(?:parker|parque|parke|parkel)"
_CORTE = (r"(?:para(?!\s+(?:que|donde|cuando|como|si)\b)|parate|parar|"
          r"calla|callate|silencio|basta)")
_ORDEN = re.compile(
    rf"\b(?:oye\s+)?{_NOMBRE}\b[^\n]{{0,40}}\b{_CORTE}\b",
    re.IGNORECASE,
)


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y sin signos: estable para comparar."""
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9ñ ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def parece_orden_de_parada(texto: str) -> bool:
    """¿La transcripción pide cortar a Parker, no solo menciona «para»?"""
    normal = normalizar(texto)
    if not normal:
        return False
    return bool(_ORDEN.search(normal))


def es_eco_de_lo_hablado(texto: str, hablados: Iterable[str],
                         umbral: float = 0.55) -> bool:
    """¿La transcripción se parece a algo que Parker está diciendo?

    `hablados` son las frases que el hilo de reproducción ya ha puesto en el
    altavoz (las últimas). Con 0.55 se toleran palabras cambiadas por Whisper
    sin confundir una frase corta del usuario con la respuesta de Parker.
    """
    normal = normalizar(texto)
    if len(normal) < 6:
        return False
    for dicho in hablados:
        otro = normalizar(dicho)
        if len(otro) < 6:
            continue
        if SequenceMatcher(None, normal, otro).ratio() >= umbral:
            return True
    return False
