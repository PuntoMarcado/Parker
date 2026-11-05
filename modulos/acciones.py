"""
modulos/acciones.py
===================
Órdenes que Parker ejecuta con su propio hardware, sin pasar por el modelo.

Motivo (oído en la placa el 25/10/2026): a «baja el volumen» contestaba con una
frase amable y no cambiaba nada; a «silba» decía «no puedo» o «ahora te silbo»
y no sonaba nada. Son cosas que dependen de Parker, no de su imaginación, así
que van por el **Sistema 1**: se reconocen aquí, se ejecutan al instante y se
confirman con una frase corta (0 ms de LLM).

Lo que se resuelve aquí:

* «sube / baja el volumen», «ponlo más alto / más bajo», «volumen al 40 %».
* «silencia», «muta», «apaga el sonido» y su vuelta («quita el silencio»).
* «silba», «prueba a silbar», «¿sabes silbar?»: silbido real por el altavoz
  (ver `modulos/sonidos.py`), no una promesa.

El volumen es la ganancia de la voz de Parker (`voz.volumen`, 0-1), que es todo
lo que suena por su altavoz. Se guarda en `parker.volumen.json` para que un
reinicio no lo devuelva al valor de fábrica.
"""

import difflib
import json
import random
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

# Ítem especial para la cola de voz: el orador lo cambia por audio de silbido.
# No es texto que se sintetice, por eso lleva un byte imposible en una frase.
SONIDO_SILBIDO = "\x00silbido"

# Números hablados que aparecen en las órdenes («al cien por cien»).
_NUMEROS_VOLUMEN = {
    "cero": 0, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "veinte": 20, "veinticinco": 25, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "maximo": 100, "minimo": 1,
}


def _plano(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios simples (para comparar patrones)."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9%]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # El STT confunde b/v a menudo («bolumen»); no cambia el significado.
    return t.replace("bolumen", "volumen")


# --- Cerebro por voz (nube / local) ----------------------------------------
# Pedido el 27/10/2026: «poder cambiar del cerebro de Groq al local y al revés
# por voz». Se reconoce aquí (sin LLM: 0 ms y no puede inventarse nada) y lo
# aplica parker.py, que es quien tiene el cerebro delante. `_plano` quita
# tildes, así que «¿qué cerebro usas?» y «que cerebro usas» son lo mismo.
_CEREBRO_ESTADO = re.compile(
    r"\b(?:que|con que|cual) (?:cerebro|motor)\b|"
    r"\b(?:estas|vas|piensas) (?:con|en) (?:el |la )?(?:local|de casa|nube|de internet|de la nube)\b|"
    r"\bdonde piensas\b|\bcomo (?:estas|vas) (?:de |con el )?(?:cerebro|motor)\b")
# Verbo de cambio + destino. «quiero»/«prefiero» solo valen si nombran el
# cerebro o el modo: «prefiero el local de la esquina» es una frase normal.
# «cambio el cerebro en local» (oído en la placa el 31/10) no encajaba: el
# verbo estaba en presente de tercera persona («cambia»), no en primera
# («cambio»), y entre «cerebro» y el destino había un «en». Se aceptan las dos
# formas, con o sin «cerebro» y con o sin preposición delante del destino.
_CEREBRO_LOCAL = re.compile(
    r"\b(?:cambia|cambio|cambiar|cambie|cambiate|cambiamos|pasate|ponte|pon|ponme|usa|tira|tiro|vuelve)\w*"
    r"(?:me|te)? (?:al |a |en |con el |con |de |el )?(?:cerebro )?"
    r"(?:en |a |al )?(?:local|de casa|de la placa|offline)\b|"
    r"\b(?:quiero|prefiero) (?:el |la )?(?:cerebro|modo) (?:local|de casa|de la placa)\b|"
    r"\bmodo local\b|\bcerebro (?:local|de casa)\b")
_CEREBRO_NUBE = re.compile(
    r"\b(?:cambia|cambio|cambiar|cambie|cambiate|cambiamos|pasate|ponte|pon|ponme|usa|tira|tiro|vuelve)\w*"
    r"(?:me|te)? (?:al |a |en |con el |con |de |el )?(?:cerebro )?"
    r"(?:en |a |al )?(?:de internet|internet|la nube|nube|online|de groq|groq|grok)\b|"
    r"\b(?:quiero|prefiero) (?:el |la )?(?:cerebro|modo) "
    r"(?:de internet|internet|la nube|nube|online|de groq|groq)\b|"
    r"\bmodo (?:nube|online|internet)\b|\bcerebro (?:de internet|online|de la nube)\b")
# Formas CORTAS (toda la frase es el destino, con verbo o sin él): el STT
# convierte «vuelve a la nube» en «voy a la nube» (oído en la placa el 27/10),
# así que «voy a la nube» y «a la nube» tienen que valer. Anclado al principio
# y al final: «vamos a la nube mañana» o «el local de la esquina» NO entran.
_CEREBRO_CORTO_LOCAL = re.compile(
    r"^(?:a |al |el |en |con el |para |pa )?(?:modo )?(?:cerebro )?"
    r"(?:local|de casa|de la placa)$|"
    r"^(?:voy|vamos|vuelvo|vuelve|ponte|pasate|quiero|prefiero)"
    r" (?:a |al |el |en |con el )?(?:el )?(?:local|la casa|de casa)$")
_CEREBRO_CORTO_NUBE = re.compile(
    r"^(?:a |al |el |en |con el |para |pa )?(?:modo )?(?:cerebro )?"
    r"(?:de internet|internet|la nube|nube|online|de groq|groq|grok)$|"
    r"^(?:voy|vamos|vuelvo|vuelve|ponte|pasate|quiero|prefiero)"
    r" (?:a |al |el |en |con el )?(?:la nube|nube|internet|el internet)$")
# Última red, la que de verdad salva las órdenes cortas por voz: el STT cambia
# los verbos («ponte» -> «jonte», «vuelve a la nube» -> «voy a dar nube», oídos
# en la placa el 27/10) pero casi nunca el destino. Así que una frase CORTA
# (hasta tres palabras delante) que TERMINA en el destino cuenta como orden:
#   «Jonte el local.»  -> local      «Voy a dar nube.» -> nube
# Las preguntas quedan fuera (llevan «?» o empiezan por qué/cómo/cuál...), así
# que «¿qué es la nube?» no cambia nada, y «vamos a la nube mañana» tampoco
# porque no termina en el destino.
_CEREBRO_TERMINA = re.compile(
    r"^(?:[\w%]+ ){0,3}(?:a |al |el |la |en |con el |para |pa |de ){0,2}"
    r"(?:modo )?(?:cerebro )?(?P<destino>local|de casa|de la placa|offline|"
    r"la nube|nube|internet|online|de groq|groq|grok)"
    r"(?: (?:otra vez|por favor|ya|ahora))?$")
_CEREBRO_PREGUNTA = re.compile(
    r"[?¿]|^(?:que|como|cual|cuales|donde|cuando|quien|por que|cuanto)\b")
# Último recurso, y el que más salva: el oído destroza estas frases cortas
# («Ponte en local» llegó como «Ponte en lo caldo», «ponte» como «Jonte», todas
# oídas en la placa el 27/10). Se compara la frase ENTERA (sin espacios) con
# las formas canónicas y se acepta si se parece lo bastante; solo si es corta,
# menciona algo del cerebro y no es una pregunta.
_CEREBRO_CANONICAS = {
    "local": ("ponte en local", "cambia al cerebro local", "usa el cerebro local",
              "cerebro local", "modo local", "cambiate al local", "vuelve al local",
              "usa el local", "cerebro de casa", "al local",
              "cambio el cerebro en local", "cambio el cerebro a local",
              "cambiar el cerebro a local", "cambiar a local", "cambio a local"),
    "nube": ("vuelve a la nube", "cambia al cerebro de internet",
             "usa el cerebro de internet", "cerebro de internet", "modo nube",
             "cambiate a la nube", "vuelve al cerebro online", "usa internet",
             "la nube", "cambio el cerebro a la nube", "cambio a la nube",
             "cambiar a la nube"),
    "auto": ("modo automatico", "ponte en automatico", "cambia a automatico",
             "decide tu"),
    "estado": ("que cerebro usas", "con que cerebro estas",
               "estas con el local", "donde piensas", "que cerebro tienes"),
}
_CEREBRO_CLAVES = ("local", "nube", "casa", "cerebro", "internet", "online",
                   "groq", "auto")
_CEREBRO_PARECIDO = 0.80   # medido con los fallos reales del oído: 0,85-0,92

def _cerebro_por_parecido(t: str) -> Optional[str]:
    """`local`/`nube`/`auto`/`estado` si la frase se parece a una canónica."""
    palabras = t.split()
    if len(palabras) > 6:
        return None
    junto = "".join(palabras)
    if not any(clave in junto for clave in _CEREBRO_CLAVES):
        return None
    mejor, puntuacion = None, 0.0
    for familia, canonicas in _CEREBRO_CANONICAS.items():
        for canonica in canonicas:
            r = difflib.SequenceMatcher(None, junto, canonica.replace(" ", "")).ratio()
            if r > puntuacion:
                mejor, puntuacion = familia, r
    return mejor if puntuacion >= _CEREBRO_PARECIDO else None
# «auto» solo con verbo de cambio o con la palabra «modo»: suelto ("el auto")
# significaría otra cosa y cambiaría el cerebro sin que nadie lo pida.
_CEREBRO_AUTO = re.compile(
    r"\bmodo (?:automatico|auto)\b|"
    r"\b(?:cambia|cambiate|pasate|ponte|pon|vuelve|usa)(?:me|te)? (?:al |a |en )?"
    r"(?:modo )?(?:automatico|auto)\b|\bdecide tu\b")


# --- Modo local completo, voz y oído (01/11/2026) ---------------------------
# «cambia la voz al local» se quedaba en el LLM y no cambiaba nada: solo
# existía el cambio de cerebro. Ahora hay tres órdenes independientes que se
# ejecutan sin modelo y se comprueban ANTES que el cerebro:
#   · modo completo: cerebro + oído + voz de una vez;
#   · voz: solo Piper / Edge;
#   · oído: solo Whisper local / nube.
# «modo local» / «modo online» cambian los TRES (cerebro, oído y voz); para
# cambiar solo el cerebro se dice «cerebro local» o «cambia el cerebro a
# local». «modo local completo», «todo local» y «desconecta internet» siguen
# valiendo.
_MODO_COMPLETO_LOCAL = re.compile(
    r"\bmodo (?:local|offline|sin internet|sin red) (?:completo|total|entero)\b|"
    r"\bmodo (?:local|offline|sin internet|sin red)\b|"
    r"\bmodo (?:completo|total|entero) (?:local|offline|sin internet|sin red)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w*"
    r" (?:a |al |en )?(?:modo )?(?:local|offline|sin internet|sin red)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w*"
    r" (?:todo|todo el sistema|el sistema|la conversacion) (?:a |al |en )?"
    r"(?:modo )?(?:local|offline|sin internet|sin red)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w*"
    r" (?:a |al |en )?(?:modo )?(?:local|offline|sin internet|sin red)"
    r" (?:completo|total|entero)\b|"
    r"\b(?:todo|toda la conversacion|el sistema) (?:a |al |en )?"
    r"(?:local|offline|sin internet|sin red)\b|"
    # «voz y cerebro local», «cerebro y voz en local»: dicho tal cual por el
    # dueño el 01/11, no estaba contemplado y solo cambiaba el cerebro.
    r"\b(?:voz|oido|oído|escucha) (?:y|mas|más) (?:el )?cerebro "
    r"(?:en |a |al )?(?:local|offline|sin internet|sin red)\b|"
    r"\bcerebro (?:y|mas|más) (?:la )?(?:voz|oido|oído) "
    r"(?:en |a |al )?(?:local|offline|sin internet|sin red)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w* "
    r"(?:en )?(?:local|offline|sin internet|sin red)(?: con| y) "
    r"(?:la voz|el oido|el oído|el cerebro)\b|"
    r"\bmodo (?:100%|cien por cien) local\b|"
    r"\bdesconecta (?:internet|la red|la nube|el internet)\b|"
    r"\bmodo (?:avion|sin red|sin internet)\b")
_MODO_COMPLETO_NUBE = re.compile(
    r"\bmodo (?:nube|internet|online) (?:completo|total|entero)\b|"
    r"\bmodo (?:nube|internet|online)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w*"
    r" (?:a |al |en )?(?:modo )?(?:nube|internet|online)\b|"
    r"\bmodo (?:completo|total|entero) (?:nube|internet|online)\b|"
    r"\b(?:vuelve|conecta|ponte|pasa|pasate|cambia|cambio|cambiar|usa|tira)\w*"
    r" (?:todo|todo el sistema|el sistema|la conversacion) (?:a |al |en )?"
    r"(?:la )?(?:nube|internet|online)\b|"
    r"\b(?:vuelve|conecta|ponte|pasa|pasate|cambia|cambio|cambiar|usa|tira)\w*"
    r" (?:a |al |en )?(?:la )?(?:nube|internet|online)"
    r" (?:completo|total|entero)\b|"
    r"\b(?:todo|toda la conversacion|el sistema) (?:a |al |en )?"
    r"(?:la )?(?:nube|internet|online)\b|"
    r"\bconecta (?:internet|la red|la nube|el internet)\b")
_MODO_COMPLETO_AUTO = re.compile(
    r"\bmodo (?:normal|habitual)\b|"
    r"\bmodo (?:automatico|auto) (?:completo|total|entero)\b|"
    r"\b(?:ponte|pasa|pasate|cambia|cambio|cambiar|pon|ponme|usa|tira|vuelve)\w*"
    r" (?:a |al |en )?(?:modo )?(?:automatico|auto)"
    r" (?:completo|total|entero)\b")
_VOZ_LOCAL = re.compile(
    r"\b(?:voz|timbre) (?:local|de casa|de la placa|piper|offline)\b|"
    r"\b(?:voz|timbre) (?:en|con) (?:local|piper)\b|"
    r"\b(?:usa|pon|cambia|cambio|cambiar|vuelve|tira|pasa)\w*"
    r" (?:la |tu )?(?:voz|timbre) (?:a |al |en )?(?:la )?(?:de |del )?"
    r"(?:local|piper|casa|placa)\b|"
    r"\b(?:habla|voz) con piper\b")
_VOZ_NUBE = re.compile(
    r"\b(?:voz|timbre) (?:nube|de internet|de la nube|edge|ximena|online)\b|"
    r"\b(?:voz|timbre) (?:en|con) (?:nube|internet|edge|ximena|online)\b|"
    r"\b(?:usa|pon|cambia|cambio|cambiar|vuelve|tira|pasa)\w*"
    r" (?:la |tu )?(?:voz|timbre) (?:a |al |en )?(?:la )?(?:de |del )?"
    r"(?:nube|internet|edge|ximena|online)\b|"
    r"\b(?:habla|voz) con (?:edge|ximena)\b")
_OIDO_LOCAL = re.compile(
    r"\b(?:oido|escucha|transcripcion|stt|whisper) (?:local|de casa|de la placa|offline)\b|"
    r"\b(?:transcribe|transcribir|escucha)\w* (?:con )?(?:whisper )?"
    r"(?:en )?(?:el )?(?:local|whisper local)\b|"
    r"\b(?:usa|pon|cambia|cambio|cambiar|vuelve|tira)\w*"
    r" (?:el |tu )?(?:oido|escucha|stt) (?:a |al |en )?(?:la )?(?:de |del )?"
    r"(?:local|casa|placa)\b")
_OIDO_NUBE = re.compile(
    r"\b(?:oido|escucha|transcripcion|stt|whisper) "
    r"(?:nube|de internet|de la nube|online|groq)\b|"
    r"\b(?:transcribe|transcribir|escucha)\w* (?:con )?(?:whisper )?"
    r"(?:en )?(?:la )?(?:nube|internet|online)\b|"
    r"\b(?:usa|pon|cambia|cambio|cambiar|vuelve|tira)\w*"
    r" (?:el |tu )?(?:oido|escucha|stt) (?:a |al |en )?(?:la )?(?:de |del )?"
    r"(?:nube|internet|online)\b")
_MODO_PREGUNTA = re.compile(
    r"^(?:que|como|cual|cuales|donde|cuando|quien|por que|cuanto)\b")


# --- Modo demo de la cara (02/11/2026) --------------------------------------
# «Parker, modo demo» / «muéstrame todas tus animaciones»: recorre la intro,
# las expresiones y los gestos del catálogo. Es una orden de datos, no una
# pregunta al modelo, y no toca cerebro, oído ni voz.
_DEMO_CARA_PARAR = re.compile(
    r"\b(?:para|parar|deten|detener|termina|terminar|sal|salir|cancela|cancelar|"
    r"quita|quitar|basta|suficiente)\w*\s+"
    r"(?:de\s+|del\s+|de\s+la\s+|la\s+|el\s+)?"
    r"(?:demo|demostracion|modo\s+demo)\b")
_DEMO_CARA = re.compile(
    r"\bmodo\s+(?:demo|demostracion)\b|"
    r"\b(?:demo|demostracion)\s+(?:de\s+|para\s+)?(?:la\s+)?"
    r"(?:cara|animaciones|expresiones|gestos)\b|"
    r"\b(?:muestra|muestrame|mostrar|ensena|ensename|ensenar|"
    r"puedes|podrias|haz|hazme|hacer|pon|ponme|poner|inicia|iniciar|"
    r"activa|activar|reproduce|reproducir|ejecuta|ejecutar|ver|veo)\w*\b"
    r"[^.]{0,48}\b(?:animaciones|expresiones|gestos)\b|"
    r"\btodas\s+(?:tus|las)\s+(?:animaciones|expresiones|gestos)\b|"
    r"\b(?:cara|carita)\s+(?:completa|entera|de\s+demo|de\s+demostracion)\b")


def interpretar_orden_demo_cara(texto: str) -> Optional[str]:
    """`iniciar`, `parar` o `None`: el modo demo de las animaciones faciales.

    Solo se dispara con una frase explícita: «modo demo», «muéstrame todas tus
    animaciones», «para la demo»... Una charla sobre la cara o una pregunta
    («¿qué animaciones tienes?») no arranca nada.
    """
    t = _plano(texto)
    if not t:
        return None
    if _DEMO_CARA_PARAR.search(t):
        return "parar"
    if _MODO_PREGUNTA.match(t):
        return None
    if _DEMO_CARA.search(t):
        return "iniciar"
    return None


def interpretar_orden_modo_completo(texto: str) -> Optional[str]:
    """`local`, `nube`, `auto` o `None`: cambiar cerebro + oído + voz juntos."""
    t = _plano(texto)
    if not t or _MODO_PREGUNTA.match(t):
        return None
    if _MODO_COMPLETO_LOCAL.search(t):
        return "local"
    if _MODO_COMPLETO_AUTO.search(t):
        return "auto"
    if _MODO_COMPLETO_NUBE.search(t):
        return "nube"
    return None


def interpretar_orden_voz(texto: str) -> Optional[str]:
    """`piper` (voz local), `edge` (voz de internet) o `None`."""
    t = _plano(texto)
    if not t or _MODO_PREGUNTA.match(t):
        return None
    if _VOZ_LOCAL.search(t):
        return "piper"
    if _VOZ_NUBE.search(t):
        return "edge"
    return None


def interpretar_orden_oido(texto: str) -> Optional[str]:
    """`local`, `nube`, `auto` o `None`: cambiar solo el STT.

    Una transcripción de ruido puede ser «oído local» a secas y cambiar el STT
    sin que nadie lo pida (visto en la placa el 01/11/2026). Para una orden
    tan corta se exige el nombre o un verbo («cambia el oído al local»); el
    resto de la conversación no se toca.
    """
    t = _plano(texto)
    if not t or _MODO_PREGUNTA.match(t):
        return None
    if not re.search(r"\b(?:parker|oye)\b", t) and not re.search(
            r"\b(?:usa|pon|cambia|cambio|cambiar|vuelve|tira|transcribe|escucha)\b",
            t):
        return None
    if _OIDO_LOCAL.search(t):
        return "local"
    if _OIDO_NUBE.search(t):
        return "nube"
    return None


def interpretar_orden_cerebro(texto: str) -> Optional[str]:
    """Qué pide el dueño: `local`, `nube`, `auto`, `estado` o `None`.

    `estado` es la pregunta («¿con qué cerebro estás?»), que se contesta sin
    LLM porque es un dato que Parker sabe con certeza; los otros tres son
    cambios, que se aplican al momento y se confirman en voz alta.
    """
    t = _plano(texto)
    if not t:
        return None
    # Una orden de modo completo/voz/oído no es una orden de cerebro: que no
    # se quede en «local» a medias si el reconocedor específico la deja pasar.
    if (_MODO_COMPLETO_LOCAL.search(t) or _MODO_COMPLETO_NUBE.search(t)
            or _MODO_COMPLETO_AUTO.search(t) or _VOZ_LOCAL.search(t)
            or _VOZ_NUBE.search(t) or _OIDO_LOCAL.search(t)
            or _OIDO_NUBE.search(t)):
        return None
    if _CEREBRO_ESTADO.search(t):
        return "estado"
    if _CEREBRO_LOCAL.search(t) or _CEREBRO_CORTO_LOCAL.match(t):
        return "local"
    if _CEREBRO_NUBE.search(t) or _CEREBRO_CORTO_NUBE.match(t):
        return "nube"
    if _CEREBRO_AUTO.search(t):
        return "auto"
    # Redes finales: frase corta que termina en el destino, y parecido global.
    # Las preguntas nunca cambian el cerebro («¿qué es la nube?»).
    if _CEREBRO_PREGUNTA.search(texto or "") or _CEREBRO_PREGUNTA.match(t):
        return None
    ultimo = _CEREBRO_TERMINA.match(t)
    if ultimo:
        destino = ultimo.group("destino")
        return "local" if destino in ("local", "de casa", "de la placa",
                                      "offline") else "nube"
    return _cerebro_por_parecido(t)


class AccionesParker:
    """Reconoce y ejecuta órdenes de volumen y silbido.

    `voz` es el `VozParker` real (o un doble en los tests). La clase no usa
    hardware directamente: solo cambia la ganancia de la voz y pide el sonido.
    """

    def __init__(self, voz=None, ruta_volumen: Optional[str] = None,
                 paso: float = 0.15, volumen_min: float = 0.01,
                 volumen_max: float = 1.0):
        self.voz = voz
        self.paso = float(paso)
        self.volumen_min = float(volumen_min)
        self.volumen_max = float(volumen_max)
        self.ruta_volumen = Path(ruta_volumen) if ruta_volumen else None
        self._volumen = float(getattr(voz, "volumen", 0.55) or 0.55)
        self._volumen_antes_silencio = self._volumen
        # Un silencio no sobrevive a un reinicio: es mejor que Parker vuelva a
        # hablar a que arranque mudo y parezca roto.
        self._cargar()

    # ------------------------------------------------------------------ estado

    def volumen_actual(self) -> float:
        if self.voz is not None:
            return max(0.0, min(1.0, float(getattr(self.voz, "volumen", self._volumen))))
        return self._volumen

    def porcentaje(self) -> int:
        return int(round(self.volumen_actual() * 100))

    def _fijar(self, valor: float, guardar: bool = True) -> None:
        anterior = self.volumen_actual()
        valor = max(self.volumen_min, min(self.volumen_max, float(valor)))
        self._volumen = valor
        if self.voz is not None:
            self.voz.volumen = valor
        if abs(valor - anterior) >= 0.005:
            print(f"[Acciones] Volumen {round(anterior * 100)} % -> "
                  f"{round(valor * 100)} %")
        if guardar:
            self._guardar()

    def _cargar(self) -> None:
        if not self.ruta_volumen or not self.ruta_volumen.exists():
            return
        try:
            datos = json.loads(self.ruta_volumen.read_text(encoding="utf-8"))
            valor = float(datos.get("volumen"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        self._fijar(valor, guardar=False)

    def _guardar(self) -> None:
        if not self.ruta_volumen:
            return
        try:
            self.ruta_volumen.write_text(
                json.dumps({"volumen": round(self._volumen, 3)}),
                encoding="utf-8")
        except OSError as e:
            print(f"[Acciones] No se pudo guardar el volumen: {e}")

    # -------------------------------------------------------------- reconocer

    def procesar(self, mensaje: str) -> Optional[Tuple[str, Optional[str]]]:
        """Devuelve `(frase, sonido)` si era una orden, o `None` si no lo era.

        `sonido` es `"silbido"` cuando además de hablar hay que silbar.
        """
        texto = _plano(mensaje)
        if not texto:
            return None

        # El orden importa: «quita el silencio» contiene «silencio».
        if self._es_quitar_silencio(texto):
            return self._quitar_silencio()
        # Preguntar el nivel se contesta con el dato real, no con el LLM:
        # oído 25/10: decía «al 75 %» cuando estaba al 50 %.
        if self._es_consulta_volumen(texto):
            return (f"Estoy al {self.porcentaje()} %.", None)
        if self._es_silencio(texto):
            return self._silenciar()
        if self._es_silbido(texto):
            return self._pedir_silbido(texto)
        return self._procesar_volumen(texto)

    @staticmethod
    def _es_quitar_silencio(texto: str) -> bool:
        return bool(re.search(
            r"\b(?:quita|quitar|desactiva|desactivar|saca|sacar) el silencio\b|"
            r"\bdesmutea\b|\bdesmutear\b|\bactiva el sonido\b|\bvuelve el sonido\b|"
            r"\bquita el mute\b", texto))

    @staticmethod
    def _es_consulta_volumen(texto: str) -> bool:
        return bool(re.search(
            r"\b(?:a )?que (?:nivel|volumen|porcentaje)\b[^.]{0,40}"
            r"\b(?:tu|tienes|estas|suenas|me oyes)\b|"
            r"\b(?:que|cual) (?:es )?tu volumen\b|"
            r"\bque volumen (?:tienes|hay|llevas)\b|"
            r"\bcomo (?:esta|tienes) (?:el )?volumen\b", texto))

    @staticmethod
    def _es_silencio(texto: str) -> bool:
        if re.search(r"\b(silencia|silencias|silenciate|mutea|mutealo|mute)\b",
                     texto):
            return True
        if re.search(r"\b(apaga|quita) el sonido\b|\bponlo sin sonido\b", texto):
            return True
        # «Silencio» a secas es una orden; dentro de una frase es un tema
        # («me gusta el silencio de la noche») y no debe apagar a Parker.
        return re.fullmatch(r"(oye |parker |por favor )*silencio( por favor)?",
                            texto) is not None

    @staticmethod
    def _es_silbido(texto: str) -> bool:
        """¿Le están pidiendo que silbe (o preguntando si sabe)?"""
        if not re.search(r"\bsilb", texto) and "silva" not in texto.split():
            return False
        # Hablar del silbido no es pedirlo: «no me gusta que silbes»,
        # «deja de silbar», «Silva es mi apellido».
        if re.search(r"\b(no me gusta|me molesta|me da igual|odio|cuando|deja de|"
                     r"apellido|se llama)\b", texto):
            return False
        # Peticiones explícitas, con su verbo.
        if re.search(r"\b(prueba|intenta|intentalo|puedes|podrias|sabes|haz|"
                     r"hazme|dame|vamos|quiero)\b[^.]{0,24}\bsilb", texto):
            return True
        palabras = texto.split()
        # «Silba», «silba, simplemente silba», «un silbido».
        if re.match(r"^(oye |parker |por favor )*"
                    r"(silba|silva|silbar|silbido|un silbido|hazlo)\b", texto):
            return True
        # Frases muy cortas que solo hablan de silbar («no puedes silbar»).
        return len(palabras) <= 5

    # --------------------------------------------------------------- ejecutar

    def _silenciar(self) -> Tuple[str, None]:
        self._volumen_antes_silencio = self.volumen_actual() or 0.55
        if self.voz is not None:
            self.voz.silenciado = True
        print(f"[Acciones] Silencio (volumen guardado {self.porcentaje()} %)")
        return "Silencio.", None

    def _quitar_silencio(self) -> Tuple[str, None]:
        if self.voz is not None:
            self.voz.silenciado = False
        self._fijar(self._volumen_antes_silencio or 0.55)
        return f"Ya te oigo. Volumen al {self.porcentaje()} %.", None

    @staticmethod
    def _pedido_absoluto(texto: str) -> Optional[int]:
        """Nivel pedido (0-100) o None.

        Acepta «volumen al 80 %» y, sobre todo, «bájalo al 33 %» sin la palabra
        volumen: el `%` ya deja claro que es un nivel. El `\b` final anterior
        fallaba justo cuando la frase acababa en «%», así que la orden se iba al
        LLM y este decía «bajando al 33 %» sin bajar nada (oído 25/10).
        """
        m = re.search(r"\bvolumen\s+(?:a|al|en)?\s*(\d{1,3})(?!\d)", texto)
        if m:
            return int(m.group(1))
        m = re.search(r"\b(?:al|a el)\s+(\d{1,3})\s*(?:%|por ciento|por cien)(?!\d)",
                      texto)
        if m:
            return int(m.group(1))
        # Números hablados: «al cien por cien», «volumen al ochenta», «al máximo».
        m = re.search(r"\bvolumen\s+(?:a|al|en)?\s*([a-z]+)", texto)
        if not m:
            m = re.search(r"\b(?:al|a el)\s+([a-z]+)"
                          r"(?:\s+por\s+(?:ciento|cien))?\b", texto)
        if m:
            return _NUMEROS_VOLUMEN.get(m.group(1))
        return None

    def _procesar_volumen(self, texto: str) -> Optional[Tuple[str, None]]:
        # Nivel exacto, con o sin la palabra «volumen».
        pedido = self._pedido_absoluto(texto)
        if pedido is not None and 0 <= pedido <= 100:
            self._fijar(pedido / 100.0)
            if re.search(r"\b(baja|bajas|bajalo|bajale|bajame|bajar|reduce|reducir)\b", texto):
                return (f"Bajado al {self.porcentaje()} %.", None)
            if re.search(r"\b(sube|subes|subelo|subele|subeme|subir|aumenta|aumentale)\b", texto):
                return (f"Subido al {self.porcentaje()} %.", None)
            return (f"Volumen al {self.porcentaje()} %.", None)

        # Sin la palabra «volumen», solo cuenta si el resto deja claro que habla
        # del sonido: «más alto/bajo» en una frase corta o un «sube/baja» a
        # secas. «Hoy estoy más bajo de ánimo» no es una orden de volumen.
        habla_de_sonido = ("volumen" in texto
                           or (len(texto.split()) <= 4
                               and re.search(r"\bmas (alto|bajo)\b", texto) is not None)
                           or re.search(r"\b(baja|sube)\s+(aun\s+)?(mas|un poco)\b",
                                        texto) is not None
                           or re.match(r"^(oye |parker |por favor )*(sube|baja|"
                                       r"subele|bajale|subelo|bajalo)$", texto) is not None)
        if not habla_de_sonido:
            return None

        if re.search(r"\bmas alto\b", texto):
            self._fijar(self.volumen_actual() + self.paso)
            return (f"Más alto: {self.porcentaje()} %.", None)
        if re.search(r"\bmas bajo\b", texto):
            self._fijar(self.volumen_actual() - self.paso)
            return (f"Más bajo: {self.porcentaje()} %.", None)
        if re.search(r"\b(baja|bajas|bajalo|bajale|bajame|bajar|reduce|reducir)\b", texto):
            self._fijar(self.volumen_actual() - self.paso)
            return (f"Bajado al {self.porcentaje()} %.", None)
        if re.search(r"\b(sube|subes|subelo|subele|subeme|subir|aumenta|aumentale)\b", texto):
            self._fijar(self.volumen_actual() + self.paso)
            return (f"Subido al {self.porcentaje()} %.", None)
        return None

    def _pedir_silbido(self, texto: str) -> Tuple[str, str]:
        if re.search(r"\b(puedes|podrias|sabes)\b", texto):
            frase = "Sí, con el altavoz; boca no tengo."
        else:
            frase = random.choice([
                "Toma, con el altavoz.",
                "Ahí va, aunque sea sin labios.",
                "Escucha.",
            ])
        return (frase, "silbido")
