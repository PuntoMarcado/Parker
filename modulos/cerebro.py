"""
modulos/cerebro.py
==================
Procesa prompts, inyecta contexto (tiempo, recuerdos, historial, personalidad)
y gestiona la comunicación local con Ollama (Qwen / Llama).

El prompt de sistema ya no vive aquí: lo construye
`modulos/personalidad.py`, que es donde está definido quién es Parker (sus
gustos, sus sueños, sus manías y su ánimo del momento). Así la identidad se
puede editar, probar y versionar sin tocar la fontanería del LLM.
"""

import os
import re
import json
import time
import unicodedata
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Iterator, Optional, Tuple
from .memoria import MemoriaParker
from .hechos import HechosParker
from .personalidad import PersonalidadParker
from .version import etiqueta

FALLBACK_RESPUESTA = "[CARA:confundido] Vaya, me he despistado un segundo procesando la respuesta."

# --- Apoyo emocional (ESConv, 03/11/2026) ---------------------------------
# Parker es compañero de soporte, no asistente: cuando la persona está de
# bajón, el orden correcto es explorar (preguntar y reflejar lo que siente),
# consolar (validar) y solo al actuar (una sugerencia pequeña).
#
# Es una MÁQUINA DE ESTADOS simple dentro del cerebro, con un turno mínimo:
# nada de clasificadores ni modelos extra. Cambia de tema o agradece -> normal.
_APORTE_TRISTEZA = re.compile(
    r"\b(?:tristes?|de\s+baj[oó]n|cansad[oa]s?|"
    r"agobiad[oa]s?|agobio|estresad[oa]s?|estres|ansied|nervios[oa]s?|"
    r"sustad[oa]s?|llor(ando|ar|e|o)|l[aá]grimas|cabread[oa]s?|enfadad[oa]s?|"
    r"hastiad[oa]|harto|desanimad[oa]s?|solo\s+en\s+casa|mucho\s+solo|"
    r"suspend(?:ier|el)|fatal|horrible|no\s+puedo\s+m[aá]s"
    r"|estoy\s+(?:muy\s+)?mal|ha\s+ido\s+mal|he\s+ido\s+mal|"
    r"mal\s+d[ií]a|el\s+d[ií]a\s+mal)",
    re.IGNORECASE)

# Pide consejo ya: toca la etapa ACTUAR (antes solo se exploraba).
_APORTE_CONSEJO = re.compile(
    r"\b(?:qu[eé]\s+(?:puedo\s+)?hacer|qu[eé]\s+hago|algún\s+consejo|"
    r"dime\s+algo|no\s+s[eé]\s+qu[eé]\s+hacer|ay[úu]dame\s+a\s+decidir)",
    re.IGNORECASE)

# Señal de riesgo Grave: respuesta de contención determinista, sin LLM, y
# nunca consejos. El 024 es la línea de atención a la conducta suicida en
# España (24h, gratuita); el 112, urgencias.
_APORTE_RIESGO = re.compile(
    r"\b(?:suicid\w*|matarme|quitarme\s+la\s+vida|hacer(?:me)?\s+da[ñn]o|"
    r"no\s+quiero\s+(?:seguir\s+)?viv|quiero\s+desaparecer|no\s+aguanto\s+nada)",
    re.IGNORECASE)
_RESPUESTA_RIESGO = (
    "[CARA:carino] Eso que cuentas es muy grande y muy serio, y no es algo "
    "que te quiera acompañar yo sola. Si puedes, habla hoy mismo con alguien "
    "de tu confianza; si te sientes en urgencia, llama al 024 (es gratuito y "
    "atienden a toda hora) o al 112. Yo me quedo aquí contigo: ¿hay alguien "
    "cerca al que le puedas avisar ahora?")

# Si la persona pregunta por la última frase espontánea, el modelo necesita
# saber de dónde salió. Sin esto solo ve su propia frase en el historial (o
# ninguna) y se inventa el motivo.
_PREGUNTA_INICIATIVA = re.compile(
    r"\b(?:qu[eé] (?:me )?(?:has )?(?:dich[oa]|preguntado)|qu[eé] has dicho|"
    r"qu[eé] dijiste|qu[eé] me acabas de decir|a qu[eé] te refer[ií]as|"
    r"qu[eé] quer[ií]as decir|por qu[eé] (?:me )?(?:has )?(?:dich[oa]|preguntado)|"
    r"por qu[eé] dices eso|de qu[eé] (?:me )?hablabas|de qu[eé] hablas|"
    r"eso que has dicho|lo que has dicho|a qu[eé] viene eso|"
    r"qu[eé] significa eso|qu[eé] me estabas (?:diciendo|contando))\b",
    re.IGNORECASE)

# --- Español de España (01/11/2026) -------------------------------------
# El 2B local aprendió «qué onda», «carro» y compañía en su corpus y los
# suelta aunque el prompt pida España. El filtro es la última red: cambia
# solo palabras inequívocas, nunca conjugaciones ni gramática.
_REEMPLAZOS_ESPANA = (
    (r"\bqué onda\b", "qué tal"),
    (r"\bque onda\b", "qué tal"),
    (r"\bplaticar\b", "hablar"),
    (r"\bplatiqué\b", "hablé"),
    (r"\bplatico\b", "hablo"),
    (r"\bplaticando\b", "hablando"),
    (r"\bplaticamos\b", "hablamos"),
    (r"\bahorita\b", "ahora"),
    (r"\bchido\b", "genial"),
    (r"\bpadrísimo\b", "genial"),
    (r"\bcarro\b", "coche"),
    (r"\bcelular\b", "móvil"),
    (r"\bla computadora\b", "el ordenador"),
    (r"\buna computadora\b", "un ordenador"),
    (r"\bcomputadora\b", "ordenador"),
    (r"\bacá\b", "aquí"),
    (r"\ballá\b", "allí"),
    (r"\bfrijoles\b", "judías"),
)

# La clave de la API no se imprime nunca: solo se dice de dónde salió.
DIRECTORIO_RAIZ = Path(__file__).resolve().parents[1]


def _leer_clave(nombre: str) -> str:
    """Clave de la API: primero el .env del proyecto, después el entorno.

    En la placa el .env es la única fuente; en el PC puede haber una variable
    de entorno vieja en la sesión que dé 401 (visto 25/10). El .env manda.
    """
    ruta = DIRECTORIO_RAIZ / ".env"
    if ruta.exists():
        try:
            for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
                if linea.strip().startswith(f"{nombre}="):
                    valor = linea.split("=", 1)[1].strip().strip('"').strip("'")
                    if valor:
                        return valor
        except OSError:
            pass
    return os.getenv(nombre, "").strip()


def limpiar_marcado(texto: str) -> str:
    """Quita marcado que NO se debe pronunciar.

    Con el cerebro de la nube llegó vocabulario nuevo al texto hablado (25/10):
    tokens de canal tipo `<|channel|>`, entidades HTML (`&quot;`), vallas de
    código y corchetes varios. Piper lo leería letra a letra («quoted»,
    «barra vertical»…).
    """
    if not texto:
        return texto
    # Formato harmony de gpt-oss: `<|channel|>final<|message|>`. Si solo se
    # quitan los tokens, la palabra «final» se queda y se pronuncia.
    texto = re.sub(r"<\|channel\|>\s*(?:analysis|final|commentary)\s*(?:<\|message\|>)?",
                   " ", texto, flags=re.IGNORECASE)
    # Tokens de control de gpt-oss/llama: <|channel|>, <|start|>, <|message|>
    texto = re.sub(r"<\|[^|>]{1,40}\|>", " ", texto)
    texto = re.sub(r"\|>", " ", texto)          # resto huérfano del token
    # Modelos con «thinking» (Qwen3.5): si el bloque se cuela, no se lee.
    texto = re.sub(r"<think\b[^>]*>.*?</think>", " ", texto,
                   flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"^\s*.*?</think>\s*", " ", texto,
                   flags=re.DOTALL | re.IGNORECASE)
    # Entidades HTML
    for entidad, real in (("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
                          ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&nbsp;", " "), ("&hellip;", "…")):
        texto = texto.replace(entidad, real)
    # Respuestas envueltas en JSON: si hay una clave con el texto hablado, se
    # queda SOLO su valor; el resto de claves no se pronuncian.
    envuelto = re.search(
        r'\{\s*"(?:texto|respuesta|mensaje|content|respuesta_hablada)"\s*:\s*"(.*?)"',
        texto, flags=re.DOTALL | re.IGNORECASE)
    if envuelto:
        texto = envuelto.group(1)

    # Vallas de código: si dentro hay JSON o etiquetas, NO se pronuncia nada de
    # eso (Piper diría «comillas, dos puntos, llave»); si es texto normal, se
    # conserva el contenido y solo caen las vallas.
    def _sin_valla(m):
        cuerpo = m.group(1)
        if re.search(r"[{}]|\"[A-Za-z_]+\"\s*:", cuerpo):
            return " "
        return " " + cuerpo + " "

    texto = re.sub(r"```[A-Za-z]*\s*(.*?)```", _sin_valla, texto, flags=re.DOTALL)
    # Objetos JSON sueltos (sin vallas): {"cara": "feliz"}
    texto = re.sub(r"\{\s*\"[^\"]{1,20}\"\s*:\s*\"?[^\"}]{0,60}\"?\s*\}", " ", texto)
    texto = texto.replace("`", "")
    # Corchetes de cualquier tipo: [CARA:feliz], [Tutéame...], [1]
    texto = re.sub(r"\[[^\]\n]{1,60}\]", " ", texto)
    # Etiquetas de ancho completo tipo 【CARA:feliz】
    texto = re.sub(r"[【〔《][^】〕》\n]{1,60}[】〕》]", " ", texto)
    # Carácter de reemplazo (U+FFFD, el «¿» roto) y controles invisibles
    texto = texto.replace("\ufffd", "")
    texto = "".join(c for c in texto
                    if c == "\n" or not unicodedata.category(c).startswith("C"))
    # Emojis y símbolos decorativos (2B los añade): el TTS los leería o los
    # convertiría en ruido. Se quitan solo los «Symbol, other»; € o % siguen.
    texto = "".join(c for c in texto
                    if c == "\n" or unicodedata.category(c) != "So")
    # Última red contra el español latinoamericano del modelo pequeño.
    for patron, reemplazo in _REEMPLAZOS_ESPANA:
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    return texto


def quitar_fugas_prompt(texto: str) -> str:
    """Quita frases de estado interno que el modelo copia del prompt.

    Visto en la placa el 30/10: a «cambia la hora del dentista» el modelo
    contestó con la línea del vínculo, literal:
    «100% (desde hace 12 días, 231 charlas). Estás hablando con Alan. mucha
    confianza.» El TTS lo leyó como tres frases. Aquí se eliminan las
    oraciones que son estado interno y, si no queda nada, se pide repetir.
    """
    if not texto:
        return texto

    # 1) LÍNEAS de estado. El 01/11 el 3B contestó con el bloque del prompt
    # pegado delante de la frase real:
    #     energía baja, curiosidad media, cariño alto
    #     Pauta de trato: de amigos: puedes bromear un poco
    #     Hey Piper, ...
    # El filtro anterior solo miraba oraciones terminadas en punto, así que
    # esas dos líneas (sin punto) se colaban hasta el TTS. Se quitan por línea
    # y también las etiquetas que el modelo pega en medio del texto.
    patrones_linea = (
        r"^(?:ánimo|animo)\s*:?[^.\n]*[.:]?",
        r"^energ[ií]a\s+(?:alta|media|baja)\s*,\s*"
        r"curiosidad\s+(?:alta|media|baja)\s*,\s*"
        r"cari[ñn]o\s+(?:alta|alto|media|medio|baja|bajo)[^\n]*",
        r"^pauta de trato[^.\n]*[.:]?",
        r"^trato\s*:[^.\n]*[.:]?",
        r"^v[ií]nculo\s*:\s*\d{1,3}%[^.\n]*[.:]?",
        r"^\d{1,3}%\s*\(desde [^)]*\)[^.\n]*[.:]?",
        r"^estás hablando con [A-ZÁÉÍÓÚÑ][\wáéíóúñ]+[.:]?",
        r"^hora\s*:\s*\d{1,2}:\d{2}[^\n]*",
        r"^recuerdos\s*:[^.\n]*[.:]?",
        r"^contexto adicional\s*:?[^.\n]*[.:]?",
    )
    lineas = []
    for linea in texto.splitlines():
        limpia = linea
        for patron in patrones_linea:
            # Se quita SOLO la etiqueta, no la frase que venga detrás en la
            # misma línea: «Estás hablando con Alan. Hola.» conserva «Hola.».
            limpia = re.sub(patron, " ", limpia, flags=re.IGNORECASE)
        if limpia.strip():
            lineas.append(limpia)
    texto = "\n".join(lineas)

    # 2) Las mismas etiquetas pegadas a una frase, sin salto de línea.
    patrones_inline = (
        r"energ[ií]a\s+(?:alta|media|baja)\s*,\s*curiosidad\s+"
        r"(?:alta|media|baja)\s*,\s*cari[ñn]o\s+"
        r"(?:alta|alto|media|medio|baja|bajo)",
        r"pauta de trato(?:\s*\(no la menciones\))?\s*:[^.\n]*[.:]?",
        r"v[ií]nculo\s*:\s*\d{1,3}%[^.\n]*[.:]?",
        r"\d{1,3}%\s*\(desde [^)]*\)[^.\n]*[.:]?",
        r"estás hablando con [A-ZÁÉÍÓÚÑ][\wáéíóúñ]+[^.\n]*[.:]?",
        r"hora\s*:\s*\d{1,2}:\d{2}[^.\n]*",
    )
    for patron in patrones_inline:
        texto = re.sub(patron, " ", texto, flags=re.IGNORECASE)

    # 3) Oraciones completas de estado (lo que ya cubría el filtro antiguo).
    oraciones = re.split(r"(?<=[.!?…])\s+", texto)
    estado = re.compile(
        r"(?:pauta de trato[^.!?]*"
        r"|trato:\s*[^.!?]*"
        r"|vínculo:\s*\d{1,3}%[^.!?]*"
        r"|\d{1,3}%\s*\(desde [^)]*\)"
        r"|estás hablando con [A-ZÁÉÍÓÚÑ][\wáéíóúñ]+"
        r"|no finjas que os conocéis de antes"
        r"|sin confianzas que no tocan"
        r"|puedes ser cálido"
        r"|sois amigos: puedes bromear"
        r"|mucha confianza)[.!?]?$",
        re.IGNORECASE)
    limpias = [o for o in oraciones if not estado.match(o.strip())]
    limpio = " ".join(limpias).strip()
    # Huecos que dejan las etiquetas al desaparecer.
    limpio = re.sub(r"\n{3,}", "\n\n", limpio)
    limpio = re.sub(r"[ \t]{2,}", " ", limpio).strip()
    if not limpio:
        return "Perdona, me he liado. ¿Me lo repites?"
    return limpio


def _texto_de_linea(linea: bytes) -> str:
    """Decodifica una línea del stream SIEMPRE como UTF-8 por defecto.

    Groq (y casi cualquier API compatible OpenAI) responde SSE con
    `content-type: text/event-stream` **sin charset**; `requests` entonces
    asume ISO-8859-1 y `iter_lines(decode_unicode=True)` convierte «¿Qué» en
    «Â¿QuÃ©» (visto 25/10). Eso se colaba hasta Piper, que intentaba leer
    «Â» y «Ã» como letras.
    """
    try:
        return linea.decode("utf-8")
    except UnicodeDecodeError:
        return linea.decode("latin-1", errors="replace")


# Modelos del proveedor que NO sirven para conversar (voz, transcripción,
# moderación, imagen...). Se usan al elegir sustituto si retiran el nuestro.
_NO_SON_TEXTO = re.compile(r"whisper|tts|audio|speech|embed|guard|moderation|"
                           r"vision|dall|image|rerank|safety", re.IGNORECASE)


# --- Modo del cerebro (nube / local), cambiable por voz ----------------------
# Pedido el 27/10/2026: poder pasar de la nube al local y al revés hablando, y
# que Parker avise por voz cuando la nube falla. `auto` es lo de siempre (nube
# primaria, local de respaldo); `local` no intenta la nube ni una vez (ni paga
# los 3 s de timeout); `nube` la usa a la fuerza y avisa si no llega.
MODOS_CEREBRO = ("auto", "nube", "local")


def _parece_sin_internet(error: str) -> bool:
    """¿El fallo es de red (no hay internet) o del proveedor?

    Cambia el aviso que se dice en voz alta: no es lo mismo «me he quedado sin
    internet» que «me están frenando por pedir demasiado seguido» (429) o «el
    servicio no contesta».
    """
    bajo = (error or "").lower()
    return any(x in bajo for x in ("connection", "timed out", "timeout",
                                   "nameresolution", "unreachable", "getaddrinfo",
                                   "max retries", "ssl", "sin internet"))


def _es_modelo_de_texto(nombre: str) -> bool:
    """¿Es un modelo de conversación? (descarta voz, imagen y moderación)."""
    return bool(nombre) and not _NO_SON_TEXTO.search(nombre)


def _recortar_ultima_oracion(texto: str) -> str:
    """Deja solo las frases COMPLETAS de `texto`.

    Cuando el orador cierra el stream al llegar a su límite de frases
    (estilo Rocky), el último trozo llega a media palabra: ese fragmento no
    debe sonar ni guardarse en el historial como si se hubiera dicho.
    """
    if not texto:
        return texto
    fin = None
    for m in re.finditer(r"[.!?…]+[\"'»)’”]*", texto):
        fin = m.end()
    return texto[:fin].strip() if fin else ""


class CerebroParker:
    """
    Motor cognitivo de Parker v5 ejecutado de forma 100% local con Ollama.

    La personalidad es un componente aparte (`PersonalidadParker`) que aporta
    el prompt de sistema y, cuando Parker toma la iniciativa, la instrucción
    interna (contar algo suyo, preguntar por algo pequeño, etc.). Si no se pasa
    ninguna, se usa el perfil por defecto: así los tests y cualquier uso suelto
    del cerebro siguen funcionando igual.
    """

    def __init__(self, config_llama: Optional[Dict] = None,
                 memoria: Optional[MemoriaParker] = None,
                 personalidad: Optional[PersonalidadParker] = None,
                 config_memoria: Optional[Dict] = None,
                 config_online: Optional[Dict] = None,
                 hechos: Optional[HechosParker] = None):
        self.historial: List[Dict[str, str]] = []
        # Último mensaje limpio de la persona y última frase espontánea de
        # Parker. La segunda solo se usa si preguntan por ella; así no se
        # arrastra como si fuera un turno normal de conversación.
        self.ultimo_mensaje_usuario = ""
        # Recuerdos que se inyectaron en ESTE turno. El filtro de invenciones
        # solo puede dejar pasar «me contaste…» si hay un recuerdo real detrás.
        self._recuerdos_turno = ""
        self._ultima_iniciativa: Optional[Dict] = None
        # Mensajes (no turnos) que se reenvían al modelo. Dos intercambios dan
        # continuidad temática sin dejar que el prompt crezca sin límite.
        self.max_historial = int((config_llama or {}).get("historial_mensajes", 4))

        # La cantidad y el umbral de recuerdos se leen de config.yaml.
        cfg_mem = config_memoria or {}
        self.solo_recuerdos_usuario = bool(cfg_mem.get("solo_recuerdos_usuario", True))
        self.max_char_turno_reciente = int(cfg_mem.get("max_char_turno_reciente", 100))
        self.top_k_recuerdos = int(cfg_mem.get("top_k_recuerdos", 2))
        self.umbral_relevancia = float(cfg_mem.get("umbral_relevancia", 0.5))
        self.max_caracteres_recuerdo = int(cfg_mem.get("max_caracteres_recuerdo", 150))

        self.memoria = memoria or MemoriaParker()
        self.personalidad = personalidad or PersonalidadParker()
        self.config = config_llama or {}
        # Hechos exactos de la persona (tabla SQLite de slots): entran en el
        # system ESTABLE para que no paguen prefill por turno. None en tests.
        self.hechos = hechos
        # Estado del apoyo emocional: se avanza turno a turno y solo durante
        # la sesión en curso (un reinicio lo deja en normal, sin drama).
        self._apoyo = {"etapa": "normal", "ronda": 0}
        # La última frase espontánea también está en la ficha persistida: así
        # se puede explicar aunque Parker se haya reiniciado entre la frase y
        # la pregunta (antes, tras un reinicio, el modelo se inventaba el motivo).
        try:
            guardada = self.personalidad.leer_iniciativa()
            if isinstance(guardada, dict):
                self._ultima_iniciativa = guardada
        except Exception:
            pass

        self.host = self.config.get("host", "http://localhost:11434").rstrip("/")
        self.modelo = self.config.get("modelo", "qwen2.5:3b")
        self.max_tokens = self.config.get("max_tokens", 160)
        self.temperature = self.config.get("temperature", 0.45)
        self.repeat_penalty = float(self.config.get("repeat_penalty", 1.15))
        self.repeat_last_n = int(self.config.get("repeat_last_n", 128))
        self.precalentar_turno_activo = bool(self.config.get("precalentar_turno", False))
        # Ventana de contexto: 1024-2048 basta para respuestas cortas de voz y
        # reduce mucho la latencia y la RAM en la SBC.
        self.num_ctx = self.config.get("num_ctx", 1024)
        # Hilos de inferencia (en RK3588: 4xA76 + 4xA55; prueba 4-6).
        self.num_thread = self.config.get("num_thread")
        # Clave para no pagar el reload del modelo: Ollama descarga a los 5 min.
        self.keep_alive = self.config.get("keep_alive", "24h")
        # Qwen3.5 razona por defecto; en voz eso son segundos de silencio y
        # tokens que no se oyen. Se pide explícitamente no pensar.
        self.sin_pensar = bool(self.config.get("sin_pensar", False))

        # --- Cerebro doble: nube (primario) + local (respaldo) ---
        # El local ya no es el que piensa: escucha, transcribe, habla y recuerda
        # siguen siendo locales (privacidad y funcionamiento sin internet).
        # La nube solo sustituye la parte lenta: generar la frase.
        cfg_on = dict(config_online or {})
        self.online_activo = bool(cfg_on.get("activo", False))
        self.online_url = str(cfg_on.get("base_url",
                                         "https://api.groq.com/openai/v1")).rstrip("/")
        self.online_modelo = str(cfg_on.get("modelo", "openai/gpt-oss-20b"))
        self.online_max_tokens = int(cfg_on.get("max_tokens", self.max_tokens))
        self.online_temperature = float(cfg_on.get("temperature", 0.6))
        self.online_reasoning = cfg_on.get("reasoning_effort", "low")
        self.online_timeout_conexion = float(cfg_on.get("timeout_conexion", 3.0))
        self.online_timeout_lectura = float(cfg_on.get("timeout_lectura", 10.0))
        self.online_reintento_seg = float(cfg_on.get("reintento_seg", 60.0))
        # Si el proveedor retira el modelo configurado, Parker elige otro solo
        # (pedido el 26/10/2026: «Groq cambia sus modelos cada cierto tiempo»).
        self.online_modelos_alternativos = [str(m) for m in
                                            (cfg_on.get("modelos_alternativos") or [])]
        self.online_nombre_clave = str(cfg_on.get("api_key_env", "GROQ_API_KEY"))
        self.online_api_key = _leer_clave(self.online_nombre_clave) if self.online_activo else ""
        self._online_caido_hasta = 0.0
        self.online_ultimo_error = ""
        self.usos_nube = 0
        self.usos_local = 0

        # --- Modo elegido (por voz o en config.yaml) y avisos por voz ---
        self.modo = str(cfg_on.get("modo_inicial", "auto")).strip().lower()
        if self.modo not in MODOS_CEREBRO:
            self.modo = "auto"
        self.avisar_por_voz = bool(cfg_on.get("avisar_por_voz", True))
        self._avisos: List[str] = []
        self._aviso_caida_dado = False
        self._aviso_vuelta_pendiente = False
        ruta_modo = cfg_on.get("ruta_estado")
        self.ruta_modo: Optional[Path] = None
        if ruta_modo:
            r = Path(str(ruta_modo)).expanduser()
            self.ruta_modo = r if r.is_absolute() else (Path(__file__).resolve().parents[1] / r)
        self._leer_modo_guardado()
        if self.online_activo and not self.online_api_key:
            print(f"[Cerebro] AVISO: falta {self.online_nombre_clave} en .env; "
                  "sigo con el cerebro local (funciona igual, más lento).")
            self.online_activo = False

        if self.online_activo:
            print(f"[Cerebro] {etiqueta()} | primario NUBE ({self.online_modelo} "
                  f"en {self.online_url}) + respaldo LOCAL ({self.modelo}) | "
                  f"modo {self.modo}")
        else:
            print(f"[Cerebro] {etiqueta()} | LOCAL ({self.modelo} en {self.host}); "
                  "nube apagada")

    # ------------------------------------------------------------- apoyo ---
    def _system_estable(self) -> str:
        """System prompt estable: identidad + datos exactos de la persona.

        El bloque de hechos va aquí y NO en el volátil: cambia pocas veces al
        día (cuando la persona dice un dato), así que el caché de prefijo solo
        se paga ese día, no en cada turno. Es la pieza que baja el primer
        token del modo local (junto con históricos del prefijo, ya hechos).
        """
        identidad = self.personalidad.identidad()
        if self.hechos is None:
            return identidad
        try:
            bloque = self.hechos.bloque_prompt()
        except Exception as e:
            # Un hecho que no deja construir el bloque no puede tumbar el
            # turno: se loga y se sigue sin datos.
            print(f"[Hechos] Bloque no disponible ({e}); sigo sin datos")
            return identidad
        if not bloque:
            return identidad
        return identidad + "\n\n" + bloque

    def _avanzar_apoyo(self, mensaje_usuario: str) -> None:
        """Actualiza la etapa de apoyo según lo último que dijo la persona.

        - Frase de bajón           -> explorar (preguntar y reflejar, SIN consejos)
        - Dos seguidas de bajón    -> consolar (validar, algo tuyo, sin preguntar por preguntar)
        - Pide consejo explícito   -> actuar (UNA sugerencia pequeña y realista)
        - Cambia de tema / agradece -> normal (se sale del modo apoyo)
        """
        texto = (mensaje_usuario or "").strip()
        if not texto:
            return
        if re.search(r"(?:gracias\s+.*\s+(?:mejor|cariño|bien)|ya\s+(?:me\s+)?siento\s+mejor)",
                     texto, re.IGNORECASE):
            self._apoyo = {"etapa": "normal", "ronda": 0}
            print("[Apoyo] sale del modo apoyo (mejora: sigue rodando normal)")
        if _APORTE_TRISTEZA.search(texto):
            etapa = self._apoyo["etapa"]
            if etapa == "normal":
                self._apoyo = {"etapa": "explorar", "ronda": 1}
                print("[Apoyo] etiqueta explorar (primera señal de bajón)")
            elif etapa == "explorar":
                self._apoyo["ronda"] += 1
                if self._apoyo["ronda"] >= 2:
                    self._apoyo["etapa"] = "consolar"
                    self._apoyo["ronda"] = 1
                    print("[Apoyo] switchea a consolar (sigue el bajón)")
            elif etapa == "consolar" and _APORTE_CONSEJO.search(texto):
                # Solo se entra a actuar si la persona pide consejo ya, no en
                # cada turno: Baymax no suelta recetas solo porque sí.
                self._apoyo["etapa"] = "actuar"
                print("[Apoyo] switchea a actuar (pide consejo explícito)")
            elif etapa == "actuar" and _APORTE_CONSEJO.search(texto):
                # Pide otra idea estando ya en actuar: se queda en actuar (la
                # próxima respuesta dará otra sugerencia pequeña).
                print("[Apoyo] sigue en actuar (otra sugerencia)")
            return
            # No hay señal de bajón. Pero "¿qué hago?" sin tristeza en la frase
            # TAMBIÉN puede pedir consejo dentro del apoyo (p. ej. "¿qué hago?").
        if (_APORTE_CONSEJO.search(texto)
                and self._apoyo["etapa"] in ("consolar", "actuar")):
            self._apoyo["etapa"] = "actuar"
            print("[Apoyo] switchea a actuar (pide consejo explícito)")
            return
        # No hay señal de bajón ni pedido de consejo: si el tema cambia, se sale.
        if self._apoyo["etapa"] != "normal":
            self._apoyo = {"etapa": "normal", "ronda": 0}
            print("[Apoyo] sale del modo apoyo (cambio de tema)")

    def _instruccion_apoyo(self) -> str:
        """Pista del turno según la etapa de apoyo ("" si no aplica).

        Se inyecta en el bloque volátil (la instrucción conversacional).
        Cambia por etapa, no por turno: explorar/consolar son otra cosa que
        «contestar a lo último y seguir el mismo tema».
        """
        etapa = self._apoyo.get("etapa", "normal")
        if etapa == "explorar":
            return ("MODO APOYO (explorar): Tu amigo está de bajón. NO des consejos "
                    "ni mejoras todavía. Refleja con TUS PALABRAS lo que le pasa "
                    "(cómo se nota que le pesa) y haz UNA sola pregunta suave y "
                    "abierta, sobre eso exactamente. Nada de listas ni «te recomiendo».")
        if etapa == "consolar":
            return ("MODO APOYO (consolar): sigue sin consejos. Valida lo que siente "
                    "(sin repetirlo literal), si te lleva cuenta di un recuerdo tuyo "
                    "parecido en una frase. No re-preguntes si no hace falta; una sola, "
                    "como quien acompaña, para no sonar a queja.")
        if etapa == "actuar":
            return ("MODO APOYO (actuar): ahora sí, UNA sugerencia muy pequeña y "
                    "realista (una frase), seguida de cariño. Sin listas, sin «deberías», "
                    "sin prometer que va a arreglarse nada.")
        return ""

    def _es_crisis(self, mensaje: str) -> bool:
        return bool(_APORTE_RIESGO.search(mensaje or ""))

    def _componer_prompt(self, mensaje_usuario: str,
                         recuerdos: str = "",
                         contexto_extra: str = "") -> Tuple[List[Dict[str, str]], str]:
        """Devuelve (mensajes, contenido_usuario enviado).

        El segundo valor es el texto EXACTO del mensaje de usuario, con el
        bloque volátil incluido. Hay que guardarlo así en el historial: si se
        guardara solo la pregunta limpia, el prefijo dejaría de coincidir con
        el de la petición anterior y Ollama tendría que reprocesar todo el
        historial en cada turno (medido en la placa: ~2-3 s de más).
        """
        fecha_hora = self._fecha_hora()
        self._recuerdos_turno = recuerdos
        contexto_extra = self._contexto_iniciativa(mensaje_usuario, contexto_extra)

        # Identidad + datos exactos (estables, cacheables) en el sistema;   
        # ánimo, fecha y recuerdos (volátiles) pegados al mensaje del usuario. 
        # Ese orden es lo que mantiene el primer token bajo: si el ánimo fuera 
        # al sistema, el historial se reprocesaría entero en cada frase.
        system = self._system_estable()
        base_volatil = self.personalidad.contexto_volatil(fecha_hora, "", contexto_extra)
        recuerdos_prompt = f"Recuerdos: {recuerdos}" if recuerdos else ""
        partes_volatiles = [base_volatil, self._instruccion_conversacion()]
        if recuerdos_prompt:
            partes_volatiles.append(recuerdos_prompt)
        volatil = "\n".join(partes_volatiles)
        contenido_usuario = f"{volatil}\n\n{mensaje_usuario}"

        mensajes = [{"role": "system", "content": system}]
        mensajes.extend(self.historial[-self.max_historial:])
        mensajes.append({"role": "user", "content": contenido_usuario})
        return mensajes, contenido_usuario

    def _iniciativa_vigente(self) -> Optional[Dict]:
        """La última frase espontánea que Parker puede explicar.

        Primero la de esta sesión; si el proceso se ha reiniciado, la que
        quedó guardada en la ficha. Sin dato no se inventa nada.
        """
        if isinstance(self._ultima_iniciativa, dict) and self._ultima_iniciativa.get("texto"):
            return self._ultima_iniciativa
        try:
            guardada = self.personalidad.leer_iniciativa()
        except Exception:
            return None
        if isinstance(guardada, dict) and guardada.get("texto"):
            self._ultima_iniciativa = guardada
            return guardada
        return None

    def _contexto_iniciativa(self, mensaje_usuario: str, contexto_extra: str = "") -> str:
        """Añade el motivo de la última frase espontánea si preguntan por ella.

        Solo durante 15 minutos y solo si la pregunta la menciona. Así el
        prompt normal no crece ni el modelo recibe permiso para inventar una
        historia sobre algo que dijo antes.
        """
        ultima = self._iniciativa_vigente()
        if not isinstance(ultima, dict) or not ultima.get("texto"):
            return contexto_extra
        if time.time() - float(ultima.get("ts") or 0.0) > 900.0:
            return contexto_extra
        if not _PREGUNTA_INICIATIVA.search(mensaje_usuario or ""):
            return contexto_extra

        motivos = {
            "contar": "querías contarle algo concreto de tu ficha",
            "preguntar": "querías preguntarle por algo pequeño de su día",
            "proponer": "le propusiste algo sencillo para hacer juntos",
            "eco": "te acordaste de algo que te había contado antes",
        }
        motivo = motivos.get(str(ultima.get("brazo") or ""),
                             "tomarías la iniciativa para hablar un poco")
        nota = (f"NOTA FINAL: la persona pregunta por tu frase espontánea "
                f"«{ultima['texto']}». Respuesta correcta: la dijiste porque "
                f"{motivo}. Explícalo en primera persona, sin repetir la "
                "pregunta ni inventar otro motivo.")
        return (contexto_extra + "\n\n" + nota).strip() if contexto_extra else nota

    def respuesta_iniciativa(self, mensaje: str) -> Optional[str]:
        """Contesta «¿qué me has dicho?» sin LLM: frase + motivo real.

        El modelo de nube recibía el motivo, pero a veces repetía la pregunta
        en vez de explicarla. Esta respuesta es determinista: no inventa y no
        gasta una llamada.
        """
        ultima = self._iniciativa_vigente()
        if not isinstance(ultima, dict) or not ultima.get("texto"):
            return None
        if time.time() - float(ultima.get("ts") or 0.0) > 900.0:
            return None
        if not _PREGUNTA_INICIATIVA.search(mensaje or ""):
            return None
        # Sin el punto final: al citarlo quedaría «…día.». y se ve sucio.
        texto = str(ultima["texto"]).strip().rstrip(".")
        brazo = str(ultima.get("brazo") or "")
        if brazo == "preguntar":
            return (f"Te pregunté: «{texto}». Lo hice porque quería saber cómo "
                    "va tu día.")
        if brazo == "proponer":
            return (f"Te propuse: «{texto}». Era para hacer algo juntos un rato.")
        if brazo == "eco":
            return (f"Te recordé: «{texto}». Me acordé de algo que me habías "
                    "contado antes.")
        if brazo == "contar":
            return (f"Te contaba: «{texto}». Me apetecía compartir algo mío "
                    "contigo.")
        return (f"Te dije: «{texto}». Lo dije para tomar la iniciativa y "
                "hablar un poco contigo.")

    def _construir_prompt(self, mensaje_usuario: str,
                           recuerdos: str = "",
                           contexto_extra: str = "") -> List[Dict[str, str]]:
        return self._componer_prompt(mensaje_usuario, recuerdos, contexto_extra)[0]

    def respuesta_directa(self, mensaje: str) -> Optional[str]:
        """Resuelve datos fiables (fecha, hora e identidad) sin pasar por el LLM."""
        # RIESGO: la señal más importante de todas se contesta determinista,
        # con contención y derivación, nunca con el modelo (que improvisa).
        if self._es_crisis(mensaje):
            print("[Cerebro] Señal de riesgo: contención determinista, sin LLM")
            return _RESPUESTA_RIESGO
        respuesta_fecha = self._responder_fecha(mensaje)
        if respuesta_fecha is not None:
            return respuesta_fecha
        respuesta_hora = self._responder_hora(mensaje)
        if respuesta_hora is not None:
            return respuesta_hora
        respuesta_iniciativa = self.respuesta_iniciativa(mensaje)
        if respuesta_iniciativa is not None:
            return respuesta_iniciativa
        return self.personalidad.respuesta_directa(mensaje)

    @staticmethod
    def _normalizar_texto(mensaje: str) -> str:
        texto = unicodedata.normalize("NFD", (mensaje or "").lower())
        return "".join(c for c in texto if unicodedata.category(c) != "Mn")

    @classmethod
    def _es_pregunta_fecha(cls, mensaje: str) -> bool:
        texto = cls._normalizar_texto(mensaje)
        texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
        # La última forma cubre la transcripción observada de Whisper
        # "que diria soy" al preguntar oralmente "qué día es hoy".
        # «día» se transcribe a veces como «dirá/dira» (nube 25/10: «¿qué dirá
        # es mañana?»). Se exige el verbo detrás para no confundir «¿qué dirá
        # Parker mañana?» (qué va a decir) con una pregunta de fecha.
        patrones = (
            r"\b(?:que|cual) dia(?: de la semana)?(?: es(?: hoy)?| de hoy| hoy| tenemos(?: hoy)?| estamos(?: hoy)?| cae hoy| toca hoy| sera(?: manana| pasado manana)?| fue(?: ayer)?)?\b",
            r"\b(?:que|cual) di(?:ra|ria) (?:es|sera|fue)\b",
            r"\ben que dia (?:estamos|estamos hoy|cae hoy)\b",
            r"\b(?:que|cual) fecha (?:es(?: hoy)?|de hoy|hoy|tenemos(?: hoy)?)\b",
            # Whisper llegó a transcribir «qué día es hoy» como «que diría soy».
            r"\bque diria soy\b",
        )
        return any(re.search(patron, texto) for patron in patrones)

    # Números escritos que Whisper deja en letras («en siete días»).
    _NUMEROS = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
                "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
                "diez": 10, "once": 11, "doce": 12, "trece": 13,
                "catorce": 14, "quince": 15, "veinte": 20, "treinta": 30}
    _DIAS_SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
                    "viernes": 4, "sabado": 5, "domingo": 6}

    @classmethod
    def _desplazamiento_dias(cls, mensaje: str,
                            ahora: Optional[datetime] = None) -> int:
        """Días entre hoy y el día preguntado (0 = hoy, 1 = mañana, -1 = ayer).

        Antes cualquier pregunta con «día» devolvía la fecha de HOY, así que a
        «¿qué día es mañana?» o «¿qué día será en 7 días?» Parker contestaba
        «Hoy es domingo, 25 de octubre» (oído en la placa 25/10). Es un dato
        que Parker sabe con certeza y no debe pasar por el modelo.
        """
        texto = cls._normalizar_texto(mensaje)
        texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
        if re.search(r"\bpasado manana\b", texto):
            return 2
        if re.search(r"\bmanana\b", texto):
            return 1
        if re.search(r"\banteayer\b|\bantes de ayer\b", texto):
            return -2
        if re.search(r"\bayer\b", texto):
            return -1
        # «en 7 días», «dentro de dos semanas»
        m = re.search(r"\b(?:en|dentro de)\s+(\d{1,2}|[a-z]+)\s+(dias?|semanas?)\b",
                      texto)
        if m:
            n = (int(m.group(1)) if m.group(1).isdigit()
                 else cls._NUMEROS.get(m.group(1), 0))
            if n:
                return n * (7 if m.group(2).startswith("semana") else 1)
        if re.search(r"\b(?:la )?(?:proxima|siguiente) semana\b|\bsemana que viene\b",
                     texto):
            return 7
        # «el próximo lunes», «el martes que viene»
        m = re.search(r"\b(?:el )?(?:proximo|siguiente)\s+"
                      r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b",
                      texto)
        if not m:
            m = re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+"
                          r"que viene\b", texto)
        if m:
            hoy = (ahora or datetime.now()).weekday()
            delta = (cls._DIAS_SEMANA[m.group(1)] - hoy) % 7
            return delta or 7
        return 0

    @classmethod
    def _respuesta_fecha(cls, ahora: datetime, dias: int = 0,
                         modo: Optional[str] = None) -> str:
        """`modo` distingue «mañana» de «el próximo lunes»: los dos suman días,
        pero decir «pasado mañana» para un lunes sería mentir."""
        dias_semana = ("lunes", "martes", "miércoles", "jueves", "viernes",
                       "sábado", "domingo")
        meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        fecha = ahora + timedelta(days=int(dias))
        base = (f"{dias_semana[fecha.weekday()]}, {fecha.day} de "
                f"{meses[fecha.month - 1]} de {fecha.year}")
        if modo == "manana":
            return f"Mañana será {base}."
        if modo == "pasado":
            return f"Pasado mañana será {base}."
        if modo == "ayer":
            return f"Ayer fue {base}."
        if modo == "anteayer":
            return f"Anteayer fue {base}."
        if dias == 0:
            return f"Hoy es {base}."
        if dias > 0:
            return f"En {dias} día{'s' if dias != 1 else ''} será {base}."
        return f"Hace {abs(dias)} día{'s' if abs(dias) != 1 else ''} fue {base}."

    def _responder_fecha(self, mensaje: str,
                         ahora: Optional[datetime] = None) -> Optional[str]:
        if not self._es_pregunta_fecha(mensaje):
            return None
        # Usa el reloj local configurado en la placa y una tabla propia para no
        # depender del idioma instalado en el sistema.
        ahora = ahora or datetime.now()
        dias = self._desplazamiento_dias(mensaje, ahora)
        texto = re.sub(r"[^a-z0-9]+", " ", self._normalizar_texto(mensaje))
        modo = None
        if dias == 2 and re.search(r"\bpasado manana\b", texto):
            modo = "pasado"
        elif dias == 1 and re.search(r"\bmanana\b", texto):
            modo = "manana"
        elif dias == -2 and re.search(r"\banteayer\b|\bantes de ayer\b", texto):
            modo = "anteayer"
        elif dias == -1 and re.search(r"\bayer\b", texto):
            modo = "ayer"
        return self._respuesta_fecha(ahora, dias, modo)

    @classmethod
    def _es_pregunta_hora(cls, mensaje: str) -> bool:
        texto = cls._normalizar_texto(mensaje)
        texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
        # El lookbehind evita «¿a qué hora es la cita?»: ahí no se pregunta la
        # hora actual, y contestar «son las 19 y 5» sería no entender nada.
        return bool(re.search(
            r"(?<!a )\b(?:que|cual) hora (?:es|son|tenemos|es ahora)\b|"
            r"\btienes (?:la )?hora\b|\bdime la hora\b",
            texto))

    @staticmethod
    def _respuesta_hora(ahora: datetime) -> str:
        h, m = ahora.hour, ahora.minute
        h12 = h % 12 or 12
        if 6 <= h < 12:
            tramo = "de la mañana"
        elif 12 <= h < 20:
            tramo = "de la tarde"
        elif 20 <= h < 24:
            tramo = "de la noche"
        else:
            tramo = "de la madrugada"
        if m == 0:
            minutos = "en punto"
        elif m == 15:
            minutos = "y cuarto"
        elif m == 30:
            minutos = "y media"
        elif m == 45:
            minutos = "y cuarenta y cinco"
        else:
            minutos = f"y {m}"
        verbo = "Es la" if h12 == 1 else "Son las"
        return f"{verbo} {h12} {minutos} {tramo}."

    def _responder_hora(self, mensaje: str,
                        ahora: Optional[datetime] = None) -> Optional[str]:
        if not self._es_pregunta_hora(mensaje):
            return None
        return self._respuesta_hora(ahora or datetime.now())

    @staticmethod
    def _fecha_hora() -> str:
        """Formato corto y estable: se usa para calentar el prefijo y luego
        para el prompt real, así ambos coinciden token a token."""
        return datetime.now().strftime("%a %d/%m %H:%M")

    def _instruccion_conversacion(self) -> str:
        """Pista breve según si estamos empezando o ya hablando de un tema.

        Con el modo de apoyo activo, su instrucción va delante (es lo que
        cambia de verdad cómo hay que contestar en ese turno).
        """
        apoyo = self._instruccion_apoyo()
        if self.historial:
            base = ("Conversación en curso: contesta a lo último y sigue el mismo tema. "
                    "No saludes ni preguntes cómo está de nuevo.")
        else:
            base = ("Inicio de conversación: contesta al saludo una vez, sin saludo efusivo "
                    "ni frase de plantilla.")
        return f"{apoyo}\n{base}" if apoyo else base

    def _mensajes_prefijo(self) -> List[Dict[str, str]]:
        """Prompt hasta el bloque volátil (ánimo + hora), sin recuerdos ni pregunta.

        Es el prefijo exacto que compartirá el prompt real cuando llegue el
        texto del usuario.
        """
        base_volatil = self.personalidad.contexto_volatil(self._fecha_hora())
        volatil = f"{base_volatil}\n{self._instruccion_conversacion()}"
        mensajes = [{"role": "system", "content": self._system_estable()}]
        mensajes.extend(self.historial[-self.max_historial:])
        # Sin el "\n\n" final: así este texto es prefijo LITERAL del mensaje
        # real (que continúa con "\nRecuerdos: ..."), que es lo que exige el
        # caché de prefijo de Ollama.
        mensajes.append({"role": "user", "content": volatil})
        return mensajes

    def precalentar_turno(self, timeout: float = 30.0) -> None:
        """Deja cacheado en Ollama el prefijo del próximo turno.

        Se llama mientras Whisper transcribe (~1,5 s), así que su coste no se
        suma a la respuesta. Medido en la placa: el primer token pasa de
        2,0-2,5 s a 0,6-1,3 s, porque el prompt real solo evalúa los recuerdos
        y la pregunta.
        """
        if not self.precalentar_turno_activo:
            return
        # Con la nube de primaria no hay prefijo que cachear en Ollama: calentar
        # aquí solo gastaría CPU mientras la persona habla (y el turno no lo usa).
        if self._online_disponible():
            return
        try:
            payload = self._payload(self._mensajes_prefijo(), stream=False)
            payload["options"] = dict(payload["options"], num_predict=1, temperature=0)
            t0 = time.time()
            requests.post(f"{self.host}/api/chat", json=payload, timeout=timeout)
            # Traza en el log: así se ve en cada turno que el prefijo se pagó
            # mientras la persona hablaba (medido: 8,94 s → 0,64 s de TTFB).
            print(f"[Latencia] Prefijo precalentado en {time.time() - t0:.2f}s "
                  f"(mientras hablabas; el turno solo evalúa recuerdos + pregunta)")
        except Exception as e:
            # Nunca debe romper el turno: es solo un atajo de latencia.
            print(f"[Cerebro] No se pudo precalentar el turno: {e}")

    def pensar(self, mensaje_usuario: str,
               recuerdos: str = "",
               contexto_extra: str = "") -> Tuple[str, List[str]]:
        try:
            self._avanzar_apoyo(mensaje_usuario)
        except Exception:
            pass
        mensajes, contenido_usuario = self._componer_prompt(mensaje_usuario, recuerdos, contexto_extra)

        respuesta_raw = self._llamar(mensajes)
        respuesta_limpia, etiquetas = self._limpiar_respuesta(respuesta_raw)

        self.historial.append({"role": "user", "content": contenido_usuario})
        self.historial.append({"role": "assistant", "content": respuesta_limpia})
        if len(self.historial) > self.max_historial * 2:
            self.historial = self.historial[-self.max_historial * 2:]

        return respuesta_limpia, etiquetas

    @staticmethod
    def _merece_recuerdo(texto: str) -> bool:
        """Guardar hechos/experiencias de la persona, no saludos o charla vacía.

        Chroma persistía cada "hola" y "¿qué tal?"; al recuperar esas frases
        reaparecían saludos de plantilla y recuerdos irrelevantes. Esta regla
        conserva datos que sí sirven para recordar y evita meter transcripción
        corta o ruido de micrófono en la memoria a largo plazo.
        """
        limpio = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ¿? ]+", " ", texto or "", flags=re.UNICODE)
        palabras = limpio.lower().split()
        if "?" in limpio or limpio.strip().startswith(("¿", "como ", "cómo ", "qué ", "quién ", "dónde ")):
            # Las preguntas factuales/identidad no son recuerdos del usuario.
            return False
        planos = {
            "estoy bien", "todo bien", "hola parker como estas", "hola parker qué tal",
            "hola parker como estas hoy", "estoy encantado de verte", "gracias por preguntar",
        }
        normalizado = " ".join(palabras)
        if normalizado in planos:
            return False
        indicadores = re.compile(
            r"\b(me llamo|mi nombre|me gusta|no me gusta|quiero|me gustaría|tengo|"
            r"vivo|trabajo|mi hermana|mi hermano|mi madre|mi padre|mi familia|"
            r"ayer|hoy he|la semana pasada|el otro día|me pasó|me han|fui a|voy a|"
            r"estuve|nací|estudio|aprendí|aprendi)\b", re.IGNORECASE)
        tiene_hecho = bool(indicadores.search(texto))
        if len(palabras) < 5 and not tiene_hecho:
            return False
        return tiene_hecho or (5 <= len(palabras) <= 40 and len(texto) <= 260)

    def hablar_stream(self, mensaje_usuario: str, top_k: Optional[int] = None,
                      umbral: Optional[float] = None,
                      contexto_extra: str = "") -> Iterator[str]:
        """
        Versión en streaming de `hablar`: devuelve un iterador que produce
        fragmentos de texto a medida que el modelo los genera.

        Permite empezar a sintetizar/reproducir la primera frase mientras el
        modelo todavía está redactando el resto (latencia percibida ≈ TTFB).
        La memoria se guarda al terminar de generar, mientras ya suena el audio.
        """
        # Se guarda limpio para que el «eco» de una iniciativa pueda citar a la
        # persona y no el prompt volátil entero.
        self.ultimo_mensaje_usuario = mensaje_usuario
        # El apoyo emocional se evalúa ANTES de componer: la etapa define el
        # turno (explorar/consolar/actuar táctil).
        try:
            self._avanzar_apoyo(mensaje_usuario)
        except Exception:
            pass
        # Si dice su nombre, se aprende antes de construir el prompt: así esta
        # misma respuesta ya lo sabe (y "¿cómo me llamo?" deja de ser una lotería).
        self.personalidad.registrar_nombre(mensaje_usuario)
        recuerdos = self.memoria.recuperar_recuerdos_formateados(
            mensaje_usuario,
            top_k=self.top_k_recuerdos if top_k is None else top_k,
            umbral=self.umbral_relevancia if umbral is None else umbral,
            max_caracteres=self.max_caracteres_recuerdo,
        )
        mensajes, contenido_usuario = self._componer_prompt(mensaje_usuario, recuerdos, contexto_extra)

        partes: List[str] = []
        cerrado_a_mitad = False
        try:
            for delta in self._llamar_stream(mensajes):
                partes.append(delta)
                yield delta
        except GeneratorExit:
            # El orador cerró el stream al llegar a su límite de frases:
            # marca para no arrastrar el fragmento final al historial.
            cerrado_a_mitad = True
            raise
        finally:
            respuesta_raw = "".join(partes)
            if not respuesta_raw:
                return
            respuesta_limpia, etiquetas = self._limpiar_respuesta(
                respuesta_raw, cerrado_a_mitad=cerrado_a_mitad)
            if not respuesta_limpia:
                return

            # La conversación deja huella en su ánimo (energía, curiosidad, cariño)
            emocion = self._emocion_de_etiquetas(etiquetas)
            try:
                self.personalidad.registrar_interaccion(emocion)
            except Exception as e:
                print(f"[Personalidad] No pude actualizar el ánimo: {e}")

            self.historial.append({"role": "user", "content": contenido_usuario})
            # Guardar en contexto la respuesta limpia, no su envoltura de stream.
            # Así una frase de saludo eliminada del audio tampoco se arrastra al
            # siguiente prompt como ejemplo que el modelo vuelva a imitar.
            self.historial.append({"role": "assistant", "content": respuesta_limpia})
            if len(self.historial) > self.max_historial * 2:
                self.historial = self.historial[-self.max_historial * 2:]

            if self._merece_recuerdo(mensaje_usuario):
                try:
                    texto_memoria = (f"Usuario: {mensaje_usuario}" if self.solo_recuerdos_usuario
                                     else f"Usuario: {mensaje_usuario}\nParker: {respuesta_limpia}")
                    self.memoria.guardar_recuerdo(
                        texto_memoria,
                        tipo="interaccion",
                        texto_embedding=mensaje_usuario
                    )
                except Exception as e:
                    print(f"[Memoria] No se pudo guardar el recuerdo: {e}")
            # Hechos exactos («mi dentista se llama Puig») van a su tabla, no
            # solo al recuerdo conversacional: así las preguntas cortas de
            # datos ya se contestan, aunque el embedding las pierda.
            if self.hechos is not None:
                try:
                    nuevos = self.hechos.actualizar_desde_texto(mensaje_usuario)
                    if nuevos:
                        print(f"[Hechos] nuevos/cambiados: {nuevos} dato(s)")
                except Exception as e:
                    print(f"[Hechos] No pude extraer hechos: {e}")

    # 01/11: los modelos inventaban actividades y recuerdos que no existen
    # («he estado escuchando graves», «la receta de pasta que te mencioné»).
    # El prompt lo prohíbe, pero un 2B/20B lo ignora: esto lo corta sí o sí.
    _ACTIVIDAD_INVENTADA = re.compile(
        r"\b(?:he|acabo de|estuve|me he pasado)\s+(?:estado\s+)?"
        r"(?:escuchando|reproduciendo|afinando|tocando|guardando|apuntando|"
        r"creando|programando)\b"
        r"|\b(?:he|acabo de)\s+(?:escuchado|reproducido|puesto)\s+"
        r"(?:una|un|el|la|los|las|unos|unas)?\s*"
        r"(?:cancion|música|musica|disco|tema|graves|sintetizador|altavoz)\b"
        r"|\b(?:he|acabo de)\s+(?:guardado|apuntado|creado|afinado|programado)\b",
        re.IGNORECASE)
    _RECUERDO_INVENTADO = re.compile(
        r"\b(?:que|como)\s+te\s+(?:mencion|cont|dije|coment|habl)\w*"
        r"|\b(?:la|una)\s+(?:receta|cancion|canción|conversacion|conversación|"
        r"cosa)\s+que\s+te\s+(?:mencion|cont|dije|coment|habl)\w*",
        re.IGNORECASE)

    def _quitar_inventos(self, texto: str) -> str:
        """Quita frases que afirman algo que Parker no ha hecho ni vivido."""
        if not texto:
            return texto
        patrones = [self._ACTIVIDAD_INVENTADA]
        # Sin recuerdos inyectados, cualquier «que te mencioné/conté» es falso.
        if not getattr(self, "_recuerdos_turno", ""):
            patrones.append(self._RECUERDO_INVENTADO)
        oraciones = re.split(r"(?<=[.!?…])\s+", texto)
        limpias = []
        for oracion in oraciones:
            if any(p.search(oracion) for p in patrones):
                print(f"[Cerebro] (frase inventada, no se dice) {oracion[:120]!r}")
                continue
            limpias.append(oracion)
        limpio = " ".join(limpias).strip()
        # Si todo era invención, mejor reconocerlo que quedarse en silencio.
        return limpio or "Perdona, me he liado. ¿Me lo repites?"

    def _limpiar_respuesta(self, respuesta_raw: str,
                           cerrado_a_mitad: bool = False) -> Tuple[str, List[str]]:
        """Cadena ÚNICA de limpieza de una respuesta del modelo.

        Antes vivía solo en `hablar_stream`, y `hablar()` (la vía síncrona que
        usan el chequeo de identidad y la proactiva) devolvía el texto con
        vocativos erróneos, etiquetas de rol y cierres de asistente (visto en
        la placa 24/10: «eres tú… ¡Parker!», «Alan: Claro…»).
        """
        # Aviso útil: si el modelo escribió marcado raro, dejarlo en el log con
        # el texto exacto (así se diagnostica sin adivinar qué se oyó).
        if re.search(r"<\|[^|>]{1,40}\|>|&quot;|```|【", respuesta_raw):
            print(f"[Cerebro] (marcado en la respuesta, ya corregido) {respuesta_raw[:140]!r}")

        limpia, etiquetas = self._extraer_etiquetas(respuesta_raw)
        if cerrado_a_mitad:
            limpia = _recortar_ultima_oracion(limpia)
        limpia = self.personalidad.limpiar_frases_plantilla(
            limpia, conversacion_en_curso=bool(self.historial))
        # Frases meta («déjame analizar…»): no se dicen ni se refuerzan.
        limpia = self.personalidad.quitar_frases_meta(limpia)
        # Actividades y recuerdos inventados: se descartan antes de guardarlos.
        limpia = self._quitar_inventos(limpia)
        # Nombres ajenos e invertidos («eres tú, Piper», «Soy Alan»).
        limpia = self.personalidad.corregir_nombre(limpia)
        return limpia, etiquetas

    def hablar(self, mensaje_usuario: str, top_k: Optional[int] = None,
               umbral: Optional[float] = None,
               contexto_extra: str = "") -> Tuple[str, List[str]]:
        """Versión síncrona (sin streaming) de `hablar_stream`."""
        respuesta_raw = "".join(self.hablar_stream(mensaje_usuario, top_k, umbral, contexto_extra))
        return self._limpiar_respuesta(respuesta_raw)

    def registrar_suceso(self, respuesta: str,
                         mensaje_usuario: Optional[str] = None) -> None:
        """Apunta en el historial algo resuelto sin LLM (agenda, aviso que suena).

        La agenda (alarmas, temporizadores, citas) contesta sin pasar por el
        modelo, así que este no se entera de nada. Sin registrarlo, al preguntar
        por la alarma recién puesta el modelo diría que él no pone alarmas.
        """
        if not respuesta:
            return
        if mensaje_usuario:
            self.historial.append({"role": "user", "content": mensaje_usuario})
        self.historial.append({"role": "assistant", "content": respuesta})
        if len(self.historial) > self.max_historial * 2:
            self.historial = self.historial[-self.max_historial * 2:]

    def hablar_proactivo(self, instruccion_interna: Optional[str] = None,
                          brazo: Optional[str] = None) -> Tuple[str, List[str]]:
        """Parker toma la iniciativa con una frase concreta, no inventada.

        Si se pasa `brazo`, la frase sale de `PersonalidadParker.semilla_iniciativa()`:
        un gusto real, una pregunta por la comida o el descanso, una propuesta
        sencilla o un recuerdo que la persona contó. No se llama al modelo para
        que improvise imágenes poéticas: eso era lo que producía «el zumbido de
        la caja» y «concierto de lluvia».

        Si no se pasa `brazo`, se conserva la vía antigua con instrucción libre
        para pruebas manuales.
        """
        # La iniciativa libre no inyecta recuerdos: que no reutilice los del
        # turno anterior para justificar una confidencia inventada.
        if not brazo:
            self._recuerdos_turno = ""
        if brazo:
            semilla = self.personalidad.semilla_iniciativa(
                brazo, self.ultimo_mensaje_usuario)
            if not semilla:
                return "", []
            self._ultima_iniciativa = {
                "texto": semilla, "brazo": brazo, "ts": time.time(),
            }
            try:
                self.personalidad.guardar_iniciativa(semilla, brazo)
            except Exception:
                pass
            emocion = {"contar": "feliz", "preguntar": "neutral",
                       "proponer": "feliz", "eco": "pensando"}.get(brazo, "neutral")
            return semilla, [f"[CARA:{emocion}]"]

        ahora = datetime.now()
        fecha_hora = ahora.strftime("%A %d/%m/%Y, %H:%M")

        if not instruccion_interna:
            instruccion_interna = self.personalidad.instruccion_proactiva()

        system = self._system_estable()
        volatil = self.personalidad.contexto_volatil(fecha_hora)
        arranque = (f"SITUACIÓN: {instruccion_interna}\n"
                    "Inicia tú la conversación con un mensaje breve y espontáneo. "
                    "No inventes imágenes ni datos que no estén en tu ficha.")
        mensajes = [{"role": "system", "content": system}]
        mensajes.extend(self.historial[-self.max_historial:])
        mensajes.append({"role": "user", "content": f"{volatil}\n\n{arranque}"})

        respuesta_raw = self._llamar(mensajes)
        respuesta_limpia, etiquetas = self._limpiar_respuesta(respuesta_raw)
        if not respuesta_limpia:
            return "", []
        self._ultima_iniciativa = {
            "texto": respuesta_limpia, "brazo": "libre", "ts": time.time(),
        }
        try:
            self.personalidad.guardar_iniciativa(respuesta_limpia, "libre")
        except Exception:
            pass
        # No se guarda como turno de conversación: era una iniciativa, no una
        # respuesta a algo que la persona hubiera dicho.
        return respuesta_limpia, etiquetas

    def _online_disponible(self) -> bool:
        """¿Se puede intentar la nube ahora mismo?

        Tras un fallo se deja de intentar `reintento_seg` segundos: así una
        caída de internet no cuesta 3 s de espera en CADA turno (circuit
        breaker). Pasado ese plazo se vuelve a probar sola. En modo `local` ni
        se intenta (como si la nube estuviera apagada, pero sin tocar config).
        """
        return (self.modo != "local" and self.online_activo
                and bool(self.online_api_key)
                and time.time() >= self._online_caido_hasta)

    def _marcar_online_caido(self, motivo: object) -> None:
        self._online_caido_hasta = time.time() + self.online_reintento_seg
        self.online_ultimo_error = str(motivo)[:160]
        print(f"[Cerebro] Nube KO ({self.online_ultimo_error}); uso el cerebro "
              f"local durante {self.online_reintento_seg:.0f}s")
        # Aviso por voz UNA vez por caída: si se dijera en cada turno, Parker
        # repetiría la misma queja mientras dure el problema.
        if not self._aviso_caida_dado:
            self._aviso_caida_dado = True
            self._aviso_vuelta_pendiente = True
            if "429" in self.online_ultimo_error:
                self._avisar("Me están frenando por pedir demasiado seguido; un "
                             "rato con el cerebro de casa y vuelvo.")
            elif _parece_sin_internet(self.online_ultimo_error):
                self._avisar("Me he quedado sin internet, así que sigo con el "
                             "cerebro de casa: te oigo igual, pero pensaré más "
                             "despacio.")
            else:
                self._avisar("El cerebro de internet no me contesta; sigo un "
                             "rato con el de casa.")

    # ------------------------------------------------------------ modo y avisos
    def _leer_modo_guardado(self) -> None:
        """Recupera el modo elegido por voz en el arranque anterior.

        Se guarda en `parker.cerebro.json`: si alguien lo dejó en local porque
        el internet va mal, un reinicio no debería devolverlo a la nube sin
        avisar. `config.yaml → online.modo_inicial` es solo el punto de partida.
        """
        if not self.ruta_modo or not self.ruta_modo.exists():
            return
        try:
            datos = json.loads(self.ruta_modo.read_text(encoding="utf-8"))
        except Exception:
            return
        guardado = str(datos.get("modo", "")).strip().lower()
        if guardado in MODOS_CEREBRO:
            self.modo = guardado

    def _guardar_modo(self) -> None:
        if not self.ruta_modo:
            return
        try:
            self.ruta_modo.parent.mkdir(parents=True, exist_ok=True)
            self.ruta_modo.write_text(
                json.dumps({"modo": self.modo}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception as e:
            print(f"[Cerebro] No se pudo guardar el modo: {e}")

    def modo_actual(self) -> str:
        return self.modo

    def frase_modo(self) -> str:
        """Cómo contar por voz con qué cerebro está pensando ahora mismo."""
        estado = self.estado_cerebro()
        if estado["motor"] == "local":
            if not self.online_activo:
                return ("Estoy con el cerebro de casa porque la nube está "
                        "apagada en la configuración.")
            if self.modo == "local":
                return (f"Estoy con el cerebro de casa ({self.modelo}), que me "
                        "lo pediste tú. Dime «vuelve a la nube» cuando quieras.")
            return (f"Estoy con el cerebro de casa ({self.modelo}): ahora mismo "
                    "no me llega internet.")
        if self.modo == "nube":
            return (f"Estoy con el de internet ({self.online_modelo}), a la "
                    "fuerza: si falla te lo digo.")
        return (f"Estoy con el de internet ({self.online_modelo}), y tengo el de "
                "casa listo por si falla.")

    def cambiar_modo(self, modo: str, motivo: str = "voz") -> str:
        """Cambia de cerebro y devuelve la frase que Parker debe decir.

        `motivo` solo cambia el log: al restaurar el modo guardado en un
        reinicio no fue «por voz» y decirlo así confundía al leer el registro.
        """
        pedido = str(modo or "").strip().lower()
        if pedido not in MODOS_CEREBRO:
            return f"No conozco ese cerebro. Ahora mismo: {self.frase_modo()}"
        if pedido == "nube" and not self.online_activo:
            return ("No puedo ponerme en la nube: está apagada en la "
                    "configuración. Sigo con el de casa.")
        antes = self.modo
        self.modo = pedido
        self._guardar_modo()
        print(f"[Cerebro] Modo {antes} -> {pedido} (por {motivo})")
        if pedido == "local":
            self._online_caido_hasta = 0.0
            return (f"Vale, me pongo en local: pienso con {self.modelo} aquí "
                    "dentro. Más lento, pero sin depender de internet.")
        if pedido == "nube":
            self._online_caido_hasta = 0.0
            self._aviso_caida_dado = False
            return ("Vale, tiro de internet. Si no me llega, te lo digo y me "
                    "quedo con el local.")
        self._aviso_caida_dado = False
        return ("Vale, en automático: internet mientras haya, y el de casa "
                "cuando falle.")

    def tomar_avisos(self) -> List[str]:
        """Se lleva los avisos pendientes para decirlos por voz (y los vacía)."""
        avisos, self._avisos = self._avisos, []
        return avisos

    def _avisar(self, frase: str) -> None:
        if self.avisar_por_voz and frase:
            self._avisos.append(frase)

    def estado_cerebro(self) -> Dict[str, object]:
        """Resumen para el log, la cara y los tests."""
        if self.modo == "local" or not self.online_activo:
            motor = "local"
        elif time.time() < self._online_caido_hasta:
            motor = "local (nube KO)"
        else:
            motor = "nube"
        return {
            "motor": motor,
            "modelo": self.online_modelo if motor.startswith("nube") else self.modelo,
            "modo": self.modo,
            "usos_nube": self.usos_nube,
            "usos_local": self.usos_local,
            "error": self.online_ultimo_error,
        }

    def _payload_online(self, mensajes: List[Dict], stream: bool) -> Dict:
        cuerpo = {
            "model": self.online_modelo,
            "messages": mensajes,
            "max_tokens": self.online_max_tokens,
            "temperature": self.online_temperature,
            "stream": stream,
        }
        # Los gpt-oss razonan en un canal aparte: con esfuerzo bajo y sin
        # devolverlo, la primera palabra llega antes (medido 25/10: 0,56 s).
        if self.online_reasoning and "gpt-oss" in self.online_modelo:
            cuerpo["reasoning_effort"] = self.online_reasoning
            cuerpo["include_reasoning"] = False
        return cuerpo

    def _cabeceras_online(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.online_api_key}",
                "Content-Type": "application/json"}

    def revisar_modelo_online(self, timeout: float = 6.0) -> Optional[str]:
        """Comprueba que el modelo configurado sigue existiendo en la nube.

        Pedido el 26/10/2026: «cada cierto tiempo Groq cambia sus modelos; si
        desclasifica el que usamos, no podemos quedarnos sin cerebro online».
        Se pide la lista real (`/models`) y, si el nuestro ya no está, se elige
        el primero de `online.modelos_alternativos` que siga disponible; en su
        defecto, el primer modelo de TEXTO de la lista (el proveedor también
        sirve voz y transcripción, que aquí no valen). Devuelve el nombre
        elegido o `None` si no había nada que cambiar.
        """
        if self.modo == "local" or not self.online_activo:
            return None
        try:
            res = requests.get(f"{self.online_url}/models",
                               headers=self._cabeceras_online(), timeout=timeout)
            res.raise_for_status()
            datos = res.json().get("data") or []
        except Exception as e:
            print(f"[Cerebro] No pude comprobar los modelos del proveedor: {e}")
            return None
        disponibles = [str(m.get("id") or "") for m in datos if isinstance(m, dict)]
        if not disponibles or self.online_modelo in disponibles:
            return None
        candidatos = [m for m in self.online_modelos_alternativos if m in disponibles]
        if not candidatos:
            candidatos = [m for m in disponibles if _es_modelo_de_texto(m)]
        if not candidatos:
            print(f"[Cerebro] AVISO: «{self.online_modelo}» ya no está en el "
                  "proveedor y no veo ningún modelo de texto al que pasar.")
            return None
        anterior = self.online_modelo
        self.online_modelo = candidatos[0]
        print(f"[Cerebro] «{anterior}» ya no está en el proveedor; uso "
              f"«{self.online_modelo}». Apúntalo en config.yaml (online.modelo) "
              "si quieres que quede fijo.")
        return self.online_modelo

    def _llamar_online_stream(self, mensajes: List[Dict]) -> Iterator[str]:
        """Streaming de la API compatible OpenAI (SSE). Lanza si algo falla."""
        url = f"{self.online_url}/chat/completions"
        with requests.post(
            url,
            json=self._payload_online(mensajes, stream=True),
            headers=self._cabeceras_online(),
            stream=True,
            timeout=(self.online_timeout_conexion, self.online_timeout_lectura),
        ) as res:
            res.raise_for_status()
            # Los bytes se decodifican a mano (UTF-8): NO se usa
            # `decode_unicode=True`, que aquí aplicaría ISO-8859-1.
            res.encoding = "utf-8"
            for linea in res.iter_lines(decode_unicode=False):
                if not linea:
                    continue
                texto_linea = _texto_de_linea(linea)
                if not texto_linea.startswith("data:"):
                    continue
                dato = texto_linea[5:].strip()
                if dato == "[DONE]":
                    break
                try:
                    evento = json.loads(dato)
                except json.JSONDecodeError:
                    continue
                if evento.get("error"):
                    raise RuntimeError(str(evento["error"].get("message", "error API")))
                eleccion = (evento.get("choices") or [{}])[0]
                trozo = (eleccion.get("delta") or {}).get("content")
                if trozo:
                    yield trozo

    def _llamar_stream(self, mensajes: List[Dict]) -> Iterator[str]:
        """Streaming con respaldo: nube si hay internet, local si falla.

        Si la nube falla ANTES de decir nada, el mismo turno se contesta con el
        cerebro local y nadie nota el cambio. Si falla a mitad de frase, se
        corta ahí: repetir la respuesta entera sonaría peor que acabar pronto.
        """
        if self._online_disponible():
            generado = False
            try:
                for trozo in self._llamar_online_stream(mensajes):
                    generado = True
                    yield trozo
                if generado:
                    self.usos_nube += 1
                    if self._aviso_vuelta_pendiente:
                        self._aviso_vuelta_pendiente = False
                        self._aviso_caida_dado = False
                        self._avisar("Ya tengo internet otra vez: vuelvo al "
                                     "cerebro de la nube.")
                    self.online_ultimo_error = ""
                    return
                raise RuntimeError("la nube no devolvió texto")
            except GeneratorExit:
                raise
            except Exception as e:
                self._marcar_online_caido(e)
                if generado:
                    return

        self.usos_local += 1
        for trozo in self._llamar_ollama_stream(mensajes):
            yield trozo

    def _llamar(self, mensajes: List[Dict]) -> str:
        return "".join(self._llamar_stream(mensajes))

    def _payload(self, mensajes: List[Dict], stream: bool) -> Dict:
        opciones = {
            "temperature": self.temperature,
            "num_predict": self.max_tokens,
            "num_ctx": self.num_ctx,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
        }
        if self.num_thread:
            opciones["num_thread"] = self.num_thread
        cuerpo = {
            "model": self.modelo,
            "messages": mensajes,
            "options": opciones,
            "keep_alive": self.keep_alive,
            "stream": stream,
        }
        if self.sin_pensar:
            cuerpo["think"] = False
        return cuerpo

    def _llamar_ollama_stream(self, mensajes: List[Dict]) -> Iterator[str]:
        """Devuelve la respuesta de Ollama fragmento a fragmento (NDJSON)."""
        url = f"{self.host}/api/chat"
        generado = False
        try:
            with requests.post(
                url,
                json=self._payload(mensajes, stream=True),
                stream=True,
                timeout=(5, 60),
            ) as res:
                res.raise_for_status()
                for linea in res.iter_lines(decode_unicode=True):
                    if not linea:
                        continue
                    try:
                        data = json.loads(linea)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        generado = True
                        yield delta
                    if data.get("done"):
                        break
        except Exception as e:
            print(f"[Cerebro Local] Error en Ollama: {e}")

        if not generado:
            yield FALLBACK_RESPUESTA

    def _llamar_ollama(self, mensajes: List[Dict]) -> str:
        return "".join(self._llamar_ollama_stream(mensajes))

    def calentar(self, timeout: float = 180.0) -> float:
        """Deja listo el cerebro ANTES de la primera pregunta real.

        Con la nube de primaria, «listo» es comprobar que la clave y la red
        funcionan (si fallan, se avisa y queda el local). Sin nube, carga el
        modelo en memoria de Ollama (10-40 s en la placa).
        Devuelve los segundos que tardó (0 si algo falló).
        """
        if self._online_disponible():
            # Antes de gastar el primer turno: ¿sigue existiendo el modelo?
            self.revisar_modelo_online()
            t0 = time.time()
            try:
                peticion = [{"role": "system", "content": "Responde solo: ok"},
                            {"role": "user", "content": "hola"}]
                cuerpo = self._payload_online(peticion, stream=False)
                cuerpo["max_tokens"] = 8
                res = requests.post(f"{self.online_url}/chat/completions",
                                    json=cuerpo, headers=self._cabeceras_online(),
                                    timeout=(5, 20))
                res.raise_for_status()
                print(f"[Cerebro] Nube lista en {time.time() - t0:.2f}s "
                      f"({self.online_modelo})")
                return time.time() - t0
            except Exception as e:
                self._marcar_online_caido(e)
                self.usos_local += 1
                return self._calentar_local(timeout)
        return self._calentar_local(timeout)

    def _calentar_local(self, timeout: float = 180.0) -> float:
        t0 = time.time()
        # Con el system REAL (identidad + hechos): así el caché de prefijo de
        # Ollama queda preparado con el bloque estable exacto que usará el
        # primer turno; si se calentara con la identidad sola, el primer turno
        # pagaría de nuevo los datos añadidos.
        mensajes = [{"role": "system", "content": self._system_estable()},
                    {"role": "user", "content": "hola"}]
        payload = self._payload(mensajes, stream=False)
        payload["options"] = dict(payload["options"], num_predict=1, temperature=0)
        try:
            requests.post(f"{self.host}/api/chat", json=payload, timeout=timeout)
        except Exception as e:
            print(f"[Cerebro] No se pudo precalentar el modelo: {e}")
            return 0.0
        return time.time() - t0

    @staticmethod
    def _emocion_de_etiquetas(etiquetas: List[str]) -> str:
        """`['[CARA:feliz]']` -> `'feliz'` (para el ánimo de la personalidad)."""
        for etiqueta in etiquetas or []:
            m = re.match(r"\[\s*CARA\s*:\s*([^\]]*)\]", etiqueta, re.IGNORECASE)
            if m:
                return m.group(1).strip().lower() or "neutral"
        return "neutral"

    def _extraer_etiquetas(self, texto: str) -> Tuple[str, List[str]]:
        # A-Za-z y espacios: qwen2.5:1.5b escribe a veces "[Cara: neutral]"
        patron = r'\[\s*([A-Za-z_]+)\s*:\s*([^\]]*)\]'
        etiquetas = re.findall(patron, texto)
        etiquetas_completas = [f"[{nombre}:{contenido}]" for nombre, contenido in etiquetas]
        texto_limpio = re.sub(patron, '', texto)
        texto_limpio = re.sub(r'\n\s*\n', '\n', texto_limpio)
        # Markdown de los modelos pequeños ("**cariño**" se oiría con asteriscos)
        texto_limpio = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", texto_limpio)
        texto_limpio = texto_limpio.replace("**", "").replace("__", "").replace("`", "")
        # Signos que quedan huérfanos al quitar la etiqueta del medio
        texto_limpio = re.sub(r"\s+([.,;:!?])", r"\1", texto_limpio)
        texto_limpio = re.sub(r",\s*([.!?])", r"\1", texto_limpio)
        texto_limpio = texto_limpio.strip()
        # Etiqueta SIN corchetes en cualquier posición ("CARA:pensando." o
        # "…y no sé qué decir. cara:bien"): los modelos pequeños la escriben y
        # sin este barrido se cuela en el texto hablado/historial (placa 24/10).
        texto_limpio = re.sub(r"\[?\bCARA\s*:\s*[A-Za-zÁÉÍÓÚáéíóúñÑ]{1,20}\]?",
                              "", texto_limpio, flags=re.IGNORECASE)
        # Notas entre corchetes que el 3b añade al empezar ("[Tutéame como
        # siempre]", visto en la placa 24/10): no son habla, son instrucciones
        # que el modelo repite, y el TTS las leería tal cual.
        texto_limpio = re.sub(r"\[[^\]\n]{1,60}\]", "", texto_limpio)
        # Etiqueta de interlocutor al empezar («Alan: Claro…»): el 3b la copia
        # de los ejemplos del prompt (visto en la placa 24/10).
        texto_limpio = re.sub(r"^\s*[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{1,15}:\s+", "", texto_limpio)
        texto_limpio = re.sub(r"^[.,;:]+\s*", "", texto_limpio)
        texto_limpio = re.sub(r"[ \t]{2,}", " ", texto_limpio).strip()
        # Cópula duplicada al presentarse: el 3b junta el "Soy" de la respuesta
        # con el "Eres Parker" del prompt y dice "Soy Eres Parker" (placa 24/10).
        texto_limpio = re.sub(r"\b([Ss]oy)\s+[Ee]res\b", r"\1", texto_limpio)
        # Último barrido: tokens de canal, entidades, corchetes y vallas.
        texto_limpio = limpiar_marcado(texto_limpio)
        texto_limpio = quitar_fugas_prompt(texto_limpio)
        texto_limpio = re.sub(r"[ \t]{2,}", " ", texto_limpio).strip()
        return texto_limpio, etiquetas_completas