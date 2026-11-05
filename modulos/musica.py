"""
modulos/musica.py
=================
Música por orden de voz: buscar, poner y parar. **Sin clave de API**.

Pedido el 26/10/2026 («la música con API»). Aquí no hay catálogo propio: se
pregunta al servicio en el momento y se reproduce lo que devuelve. Con el
servicio elegido (Deezer, API pública sin registro) eso es el **adelanto de
30 s** de cada canción: es lo único que se puede poner hoy sin cuenta, sin
OAuth y sin tarjeta, y encaja con una placa que habla por un altavoz pequeño.
Para canciones enteras haría falta una cuenta de Spotify/Apple (OAuth desde la
placa) o descargar de YouTube, y eso es otra decisión, no un arreglo de esto.

Lo que hace este módulo, exactamente:

* **Reconocer la orden** (`procesar`): «pon música», «pon algo de Queen»,
  «pon la canción Bohemian Rhapsody», «para la música», «sube la música»,
  «¿qué está sonando?». Devuelve la frase de confirmación y la canción que hay
  que poner (o `None` si la orden era parar/subir).
* **Buscar** (`buscar`): búsqueda real por texto y, si no se dice nada concreto
  («pon música»), la lista de éxitos del momento.
* **Preparar el audio** (`preparar`): descarga el adelanto y lo decodifica en
  memoria con `ffmpeg` a mono 22050 Hz en coma flotante, que es lo que sabe
  reproducir la voz de Parker. **Sin ficheros temporales**: la tarjeta de la
  placa se lleva todo el desgaste que se pueda evitar.
* **Dejar que le hablen mientras suena** (`duck` + `OyenteMusica`): ver abajo.

### Oír por encima de la música (27/10/2026)

El problema real: con la música puesta, el micrófono oye el altavoz, así que
cualquier subida de nivel podía ser el estribillo o el dueño hablando. La
primera versión lo resolvía ignorando **todo** lo que no fuera una orden de
música; la consecuencia era que no se le podía decir «baja el volumen» con una
canción sonando, y que un turno nacido de la propia canción dejaba a Parker
sordo (no soltaba el turno).

Ahora hay dos piezas:

* **`MusicaParker.duck`**: baja la música a `duck_factor` (0,15) sin tocar el
  volumen que pidió el dueño. Quien escucha la pone mientras comprueba si hay
  una persona y mientras atiende el turno, y la quita al terminar.
* **`OyenteMusica`**: distingue la voz de la canción con un truco medible —
  **bajar la música y mirar**. Lo que venía del altavoz baja con ella; una
  persona, no. Así se abre turno solo cuando hay alguien hablando de verdad
  (y las órdenes de volumen/para/poner se atienden con la canción sonando).

No reproduce nada por sí solo ni crea hilos: eso vive en `parker.py`, que es
quien tiene el altavoz, la cara y el micrófono (mismo reparto que la agenda).
"""

import re
import subprocess
from collections import deque
from statistics import fmean
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

from modulos.agenda import _plano

BUSQUEDA_URL = "https://api.deezer.com/search"
EXITOS_URL = "https://api.deezer.com/chart/0/tracks"

# Frase con la que se pide música (el verbo solo no basta: «pon la mesa»).
_VERBO_PONER = (r"\b(?:pon|ponme|poner|reproduce|reproducir|toca|tocame|"
                r"escucha|escuchar|quiero oir|quiero escuchar|sintoniza|"
                r"ponme algo|pon algo)\b")
_MARCA_MUSICA = (r"\b(?:musica|musical|cancion|canciones|tema|temas|disco|"
                 r"discos|album|spotify|algo de|algo alegre|algo movido|"
                 r"algo tranquilo|algo suave|algo animado)\b")
# «pon a Queen», «pon lo de Queen»: el sitio de donde se saca el nombre.
_MARCA_ARTISTA = r"\b(?:de|del|por|a|lo de|la de|el de)\b"

_PARAR = (r"\b(?:para|parar|parala|paralo|parame|quita|quitar|quitame|quitala|"
          r"corta|cortala|cortalo|apaga|apagala|apagalo|basta|vale ya)\b")
_PARAR_ESO = r"\b(?:eso|esto|la musica|el ruido|el audio)\b"

_VOLUMEN_MUSICA = (r"\b(?:musica|cancion|tema|audio|sonido)\b")
_SUBIR = r"\b(?:sube|subele|subir|mas alto|mas fuerte)\b"
_BAJAR = r"\b(?:baja|bajale|bajar|mas bajo|mas flojo)\b"
# Con la música sonando, «baja el volumen» a secas es la música: es lo que se
# está oyendo (27/10). «…de tu voz» sigue siendo de la voz, y sin música puesta
# la frase tampoco es de aquí (la resuelve `acciones.py`).
_PIDE_VOLUMEN = r"\bvolumen\b|\bmas (?:alto|fuerte|bajo|flojo)\b"
_MARCA_VOZ = r"\b(?:voz|hablar|habla)\b"

# 01/11: antes «que estas» a secas contaba como pregunta musical, así que
# «¿de qué estás hablando?» acababa en «la música está desactivada». Ahora se
# exige una palabra de música o una fórmula inequívoca («qué suena»).
_PREGUNTA = (
    r"\bque (?:cancion|musica|tema|disco|album)\b[^?]{0,40}"
    r"\b(?:suena|esta|es|oyes|pones|poniendo)\b|"
    r"\bque (?:es lo )?que suena\b|"
    r"\bque (?:se oye|esta sonando|estas poniendo)\b|"
    r"\bquien (?:canta|es)\b")

# Palabras que no forman parte del nombre de la canción ni del artista.
_RUIDO_CONSULTA = {
    "la", "el", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu",
    "pon", "ponme", "poner", "reproduce", "reproducir", "toca", "tocame",
    "escucha", "escuchar", "quiero", "oir", "sintoniza", "musica", "musical",
    "cancion", "canciones", "tema", "temas", "disco", "discos", "album",
    "algo", "de", "del", "por", "para", "que", "y", "a", "lo", "un", "poco",
    "parker", "oye", "eh", "vale", "venga", "porfa", "porfavor", "favor",
    "ahora", "mismo", "otra", "vez", "spotify", "eso", "esto",
}


def _consulta_de_texto(texto: str) -> str:
    """«pon música de Queen» -> «queen»; sin nombre concreto -> «» (éxitos)."""
    palabras = [p for p in re.split(r"\W+", texto) if p]
    utiles = [p for p in palabras if p not in _RUIDO_CONSULTA and len(p) > 1]
    return " ".join(utiles[:6])


class MusicaParker:
    """Busca y trae la música que se le pide (adelantos de 30 s, sin clave)."""

    def __init__(self, volumen: float = 0.7, timeout: float = 6.0,
                 max_segundos: float = 40.0, sample_rate: int = 22050,
                 duck_factor: float = 0.15):
        self.volumen = float(volumen)
        self.silencio = False
        # «Duck»: bajar la música mientras se comprueba/atiende una voz. No
        # toca `volumen` (lo que pidió el dueño): solo se aplica mientras está
        # activo. Ver `OyenteMusica` y `parker._duck_musica`.
        self.duck = False
        self.duck_factor = max(0.0, min(1.0, float(duck_factor)))
        self.timeout = float(timeout)
        # Tope de seguridad: si el servicio devolviera algo larguísimo, no se
        # convierte el altavoz en una radio que nadie puede parar.
        self.max_segundos = float(max_segundos)
        self.sample_rate = int(sample_rate)
        self.ultima: Dict = {}
        # Resto de resultados de la última búsqueda: se encadenan después del
        # tema pedido (si no, tras 30 s Parker se quedaría callado a medias).
        self.cola: List[Dict] = []

    # --------------------------------------------------------------- volumen

    @staticmethod
    def _porcentaje_de(volumen: float) -> int:
        return max(1, min(100, int(round(volumen * 100))))

    def porcentaje(self) -> int:
        return self._porcentaje_de(self.volumen)

    def ganancia_objetivo(self) -> float:
        """Ganancia que toca AHORA (volumen, silencio y «duck» a la vez).

        El hilo que suena la pide en cada bloque de 0,25 s y va acercándose
        (así el cambio de volumen y el «duck» no dan un golpe en el altavoz).
        """
        if self.silencio:
            return 0.0
        return self.volumen * (self.duck_factor if self.duck else 1.0)

    def cambiar_volumen(self, delta: float) -> int:
        """Sube o baja el volumen de la música (independiente del de la voz)."""
        self.silencio = False
        self.volumen = max(0.05, min(1.0, self.volumen + delta))
        return self.porcentaje()

    def silenciar(self) -> None:
        self.silencio = True

    def quitar_silencio(self) -> int:
        self.silencio = False
        return self.porcentaje()

    # ---------------------------------------------------------------- órdenes

    def procesar(self, mensaje: str, sonando: bool = False) -> Optional[Tuple[str, Optional[str], Optional[Dict]]]:
        """`(frase, orden, cancion)` si era una orden de música, o `None`.

        Órdenes: `poner` (con `cancion`), `parar`, `subir`, `bajar`,
        `silencio`, `quitar_silencio` y `preguntar` (qué suena).

        `sonando=True` (lo pone parker cuando hay una canción puesta) admite
        además el volumen a secas: «baja el volumen» con música suena es la
        música; «baja el volumen de tu voz» sigue siendo de la voz.
        """
        texto = _plano(mensaje)
        if not texto:
            return None

        if re.search(_PREGUNTA, texto) and not re.search(_VERBO_PONER, texto):
            return (self.que_suena(), "preguntar", None)

        if (re.search(_PARAR, texto)
                and (re.search(_MARCA_MUSICA, texto) or re.search(_PARAR_ESO, texto))):
            return ("Vale, quito la música.", "parar", None)

        es_volumen = (bool(re.search(_VOLUMEN_MUSICA, texto))
                      or (sonando and re.search(_PIDE_VOLUMEN, texto)
                          and not re.search(_MARCA_VOZ, texto)))
        if es_volumen and re.search(_SUBIR, texto):
            return (f"Subo la música al {self.cambiar_volumen(0.15)} %.", "subir", None)
        if es_volumen and re.search(_BAJAR, texto):
            return (f"Bajo la música al {self.cambiar_volumen(-0.15)} %.", "bajar", None)

        if not re.search(_VERBO_PONER, texto):
            return None
        if not (re.search(_MARCA_MUSICA, texto) or re.search(_MARCA_ARTISTA, texto)):
            return None
        # «pon la mesa», «pon el despertador a las 7»: eso no es música.
        if re.search(r"\b(?:mesa|despertador|alarma|temporizador|recordatorio|"
                     r"cita|lampara|luz|tele|television)\b", texto):
            return None

        consulta = _consulta_de_texto(texto)
        cancion = self.buscar(consulta)
        if not cancion:
            if consulta:
                return (f"No encuentro «{consulta}» en el servicio de música.",
                        "poner", None)
            return ("No he podido buscar música ahora mismo.", "poner", None)
        # Se recuerda cuál es «la que suena» (aunque el final lo confirme
        # parker): así «¿qué está sonando?» contesta con el dato real.
        self.ultima = cancion
        return (f"Pongo {cancion['titulo']}, de {cancion['artista']}. "
                "(Es un adelanto de 30 segundos.)", "poner", cancion)

    def que_suena(self) -> str:
        if not self.ultima:
            return "No estoy poniendo nada."
        return (f"Suena {self.ultima.get('titulo')}, de "
                f"{self.ultima.get('artista')}.")

    # ----------------------------------------------------------------- datos

    def buscar(self, consulta: str = "", limite: int = 8) -> Optional[Dict]:
        """Primera canción que devuelve el servicio para lo que se pida.

        Sin consulta («pon música») devuelve el primer puesto de la lista de
        éxitos: así «pon música» pone algo de verdad en vez de no hacer nada.
        """
        if consulta:
            url = BUSQUEDA_URL
            params = {"q": consulta, "limit": max(1, int(limite))}
        else:
            url = EXITOS_URL
            params = {"limit": max(1, int(limite))}
        try:
            res = requests.get(url, params=params, timeout=self.timeout)
            res.raise_for_status()
            datos = res.json()
        except Exception as e:
            print(f"[Música] No pude buscar «{consulta or 'éxitos'}»: {e}")
            return None
        pistas = [p for p in (self._de_pista(x) for x in (datos.get("data") or [])) if p]
        if not pistas:
            print(f"[Música] Sin resultados para «{consulta or 'éxitos'}»")
            return None
        self.cola = pistas[1:]
        return pistas[0]

    def pistas_de(self, consulta: str = "", limite: int = 8) -> List[Dict]:
        """Todas las pistas válidas de una búsqueda (para encadenar temas)."""
        if consulta:
            url, params = BUSQUEDA_URL, {"q": consulta, "limit": max(1, int(limite))}
        else:
            url, params = EXITOS_URL, {"limit": max(1, int(limite))}
        try:
            res = requests.get(url, params=params, timeout=self.timeout)
            res.raise_for_status()
            datos = res.json()
        except Exception as e:
            print(f"[Música] No pude buscar «{consulta or 'éxitos'}»: {e}")
            return []
        return [p for p in (self._de_pista(x) for x in (datos.get("data") or [])) if p]

    @staticmethod
    def _de_pista(pista: Dict) -> Optional[Dict]:
        """Normaliza una pista del servicio (solo lo que se usa aquí)."""
        if not isinstance(pista, dict):
            return None
        url = (pista.get("preview") or "").strip()
        titulo = (pista.get("title") or pista.get("title_short") or "").strip()
        if not url or not titulo:
            return None
        artista = ((pista.get("artist") or {}).get("name") or "").strip()
        return {"titulo": titulo, "artista": artista or "desconocido",
                "url": url, "id": str(pista.get("id") or ""),
                "segundos": int(pista.get("duration") or 30)}

    # ------------------------------------------------------------------ audio

    def preparar(self, cancion: Dict, timeout: float = 20.0):
        """Descarga el adelanto y lo decodifica a `(float32 mono, sample_rate)`.

        Se usa `ffmpeg` (ya instalado en la placa para otras cosas) y se hace
        todo por tuberías, sin escribir nada en la tarjeta. Devuelve `None` si
        no hay internet, no hay `ffmpeg` o el audio no se puede decodificar.
        """
        url = (cancion or {}).get("url")
        if not url:
            return None
        try:
            res = requests.get(url, timeout=self.timeout + timeout)
            res.raise_for_status()
            crudo = res.content
        except Exception as e:
            print(f"[Música] No pude descargar la canción: {e}")
            return None
        if not crudo:
            return None
        try:
            proceso = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "s16le",
                 "-ac", "1", "-ar", str(self.sample_rate), "pipe:1"],
                input=crudo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except FileNotFoundError:
            print("[Música] No hay ffmpeg en esta máquina: no puedo decodificar.")
            return None
        except Exception as e:
            print(f"[Música] Error al decodificar: {e}")
            return None
        if proceso.returncode != 0 or not proceso.stdout:
            error = (proceso.stderr or b"").decode("utf-8", "replace")[:120]
            print(f"[Música] ffmpeg falló ({error})")
            return None
        audio = np.frombuffer(proceso.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        tope = int(self.max_segundos * self.sample_rate)
        return (audio[:tope], self.sample_rate)

    def ganancia(self, audio: np.ndarray, ganancia: Optional[float] = None) -> np.ndarray:
        """Aplica la ganancia al búfer (0 = silencio).

        Sin `ganancia`, la que toca ahora mismo (`ganancia_objetivo`). Con
        `ganancia`, la que lleve el hilo de reproducción en su rampa: así el
        «duck» y los cambios de volumen entran suaves.
        """
        if audio is None or len(audio) == 0:
            return audio
        factor = self.ganancia_objetivo() if ganancia is None else float(ganancia)
        factor = max(0.0, min(1.0, factor))
        return np.clip(audio * factor, -1.0, 1.0)


class OyenteMusica:
    """Distingue una PERSONA de la propia canción cuando algo suena más alto.

    El truco es **bajar la música y mirar**: lo que venía del altavoz baja con
    ella; la voz de una persona, no. Quien escucha (el bucle de `parker.py`)
    llama a `observar()` con el nivel del micrófono bloque a bloque:

    1. `"probar"`: algo sobresale del nivel de la canción (`factor_disparo`
       sobre el piso aprendido). Quien escucha baja la música (`duck`) y espera
       a que se note (`retardo_seg`).
    2. `"voz"` o `"musica"`: con la ventana ya en la mano, si el nivel siguió
       alto es una persona; si bajó como bajó la música, era la canción.

    El piso sigue al nivel oído (sube rápido con `alpha_subida`, baja despacio
    con `alpha_bajada`) y **se congela mientras algo sobresale**: si subiera con
    la propia voz, el umbral la alcanzaría y no dispararía nunca. Medido en la placa el 27/10, la canción deja 0,0108 de
    mediana con picos de 0,037, y una voz normal ronda 0,05: con
    `factor_disparo` en 1,5 se oyen todas las frases (10 de 10, y 8 de 10 de una
    voz floja). Medido en la placa el 27/10: la canción sola provoca 2 bajadas
    breves en 24 s (sin abrir turno). Mejor eso que no oír.

    Y para no bajar la música en cada pasaje fuerte, el disparo pide además
    superar el **máximo de los últimos segundos** (`ventana_reciente_seg`): una
    canción no se supera a sí misma (su pasaje fuerte es su propio máximo), pero
    una voz por encima sí. Medido en la placa el 27/10 con «Bohemian Rhapsody»:
    con esto la música se baja 2 veces en 24 s (antes 6), siempre para comprobar
    y volver, sin abrir ningún turno; y la voz (0,05 frente a picos de 0,037)
    sigue disparando con margen.

    La comparación final también mira cuánto cayó respecto al disparo
    (`factor_resto`): una canción que estaba por encima del piso aprendido
    tiene que caer de forma proporcional, y cae (el «duck» la multiplica).

    Tras decidir que era la canción hay un **enfriamiento** (`enfriamiento_seg`)
    sin disparar: mientras suena, el piso termina de ponerse al día con el
    estribillo y la música no se queda subiendo y bajando cada segundo.
    """

    def __init__(self, factor_disparo: float = 1.5, factor_voz: float = 0.35,
                 factor_resto: float = 0.4, retardo_seg: float = 0.55,
                 ventana_seg: float = 0.3, chunk_seg: float = 0.064,
                 alpha_subida: float = 0.15, alpha_bajada: float = 0.08,
                 umbral_min: float = 0.02, ventana_reciente_seg: float = 3.0,
                 factor_reciente: float = 1.15,
                 seguidos: int = 2, enfriamiento_seg: float = 2.0):
        self.factor_disparo = float(factor_disparo)
        self.factor_voz = float(factor_voz)
        self.factor_resto = float(factor_resto)
        self.retardo_chunks = max(0, int(round(retardo_seg / chunk_seg)))
        self.ventana_chunks = max(1, int(round(ventana_seg / chunk_seg)))
        # Tras decidir «era la canción» se espera un poco sin disparar: el piso
        # se pone al día con el estribillo y no se queda bajando y subiendo la
        # música cada segundo (medido en simulación: 75 avisos -> 1 por subida).
        self.enfriamiento_chunks = max(0, int(round(enfriamiento_seg / chunk_seg)))
        # El piso sube deprisa (aprende un estribillo en cuanto aparece) y baja
        # despacio: si bajara a la misma velocidad, cada pasaje fuerte volvería
        # a dispararse (medido en la placa el 27/10: 5 comprobaciones en 22 s de
        # «Bohemian Rhapsody» con una sola velocidad).
        self.alpha_subida = float(alpha_subida)
        self.alpha_bajada = float(alpha_bajada)
        self.umbral_min = float(umbral_min)
        # Máximo de los últimos segundos: lo que no lo supere es la propia
        # canción repitiendo su pasaje fuerte.
        self.factor_reciente = float(factor_reciente)
        self.recientes: deque = deque(
            maxlen=max(2, int(round(ventana_reciente_seg / chunk_seg))))
        self.seguidos = max(1, int(seguidos))
        self.piso = float(umbral_min)
        self._estado = "espera"
        self._seguidos = 0
        self._n = 0
        self._bloqueo = 0
        self._ventana: List[float] = []
        self._nivel_disparo = 0.0
        self._previos: deque = deque(maxlen=3)

    @property
    def probando(self) -> bool:
        """¿Está en la comprobación (la música debería estar bajada)?"""
        return self._estado == "probar"

    def _mover_piso(self, rms: float) -> None:
        """Acerca el piso al nivel oído: deprisa al subir, despacio al bajar."""
        alfa = self.alpha_subida if rms > self.piso else self.alpha_bajada
        self.piso = (1.0 - alfa) * self.piso + alfa * rms

    def reiniciar(self) -> None:
        """Vuelve a esperar (conserva el piso aprendido)."""
        self._estado = "espera"
        self._seguidos = 0
        self._n = 0
        self._ventana = []
        self._nivel_disparo = 0.0

    def observar(self, rms: float) -> str:
        """Una lectura del micrófono -> `nada`, `probar`, `voz` o `musica`."""
        rms = float(rms)
        if self._estado == "espera":
            umbral = max(self.umbral_min,
                         self.piso * self.factor_disparo,
                         (max(self.recientes) if self.recientes else 0.0)
                         * self.factor_reciente)
            if self._bloqueo > 0:
                # Enfriamiento tras un falso aviso: aquí sí se aprende, que es
                # lo que pone al día el piso y el máximo con el estribillo.
                self._bloqueo -= 1
                self._seguidos = 0
                self._mover_piso(rms)
                self.recientes.append(rms)
                return "nada"
            if rms > umbral:
                # Candidato: NI el piso NI el máximo reciente se mueven con él.
                # Si subieran con la propia voz, el umbral la alcanzaría y no
                # dispararía nunca (medido: la voz quedaba ignorada).
                self._seguidos += 1
                self._previos.append(rms)
            else:
                self._seguidos = 0
                self._mover_piso(rms)
                self.recientes.append(rms)
            if self._seguidos >= self.seguidos:
                # Nivel del disparo: con él se compara después, porque la
                # música baja con el «duck» y una persona no.
                self._nivel_disparo = max(self._previos) if self._previos else rms
                self._estado = "probar"
                self._n = 0
                self._ventana = []
                return "probar"
            return "nada"

        self._n += 1                # bloques de margen para que el «duck» se note
        if self._n <= self.retardo_chunks:
            return "nada"
        self._ventana.append(rms)
        if len(self._ventana) < self.ventana_chunks:
            return "nada"
        media = fmean(self._ventana)
        umbral_voz = max(self.piso * self.factor_voz,
                         self._nivel_disparo * self.factor_resto)
        self.reiniciar()
        if media > umbral_voz:
            # Turno real: la memoria del máximo reciente se vacía para que la
            # frase siguiente (que puede ser más floja) vuelva a disparar.
            self.recientes.clear()
            return "voz"
        self._bloqueo = self.enfriamiento_chunks
        return "musica"
