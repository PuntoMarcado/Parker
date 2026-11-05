"""
modulos/agenda.py
=================
Alarmas, temporizadores y calendario local: lo que Parker apunta y avisa.

Pedido el 26/10/2026: Parker conversa muy bien, pero no «hace» nada útil con el
tiempo. Aquí viven las tres cosas que sí puede cumplir con su hardware:

* **Temporizador**: «pon un temporizador de 10 minutos», «avísame en media hora».
* **Alarma**: «pon una alarma a las 7:30», «despiértame a las siete y media».
* **Calendario**: «apunta que el viernes a las 5 tengo al dentista»,
  «¿qué tengo mañana?», «¿qué tengo esta semana?», «¿qué alarmas tengo?».

Igual que el volumen (`modulos/acciones.py`), esto es Sistema 1: se reconoce sin
LLM y se contesta al instante con una frase corta. Cuando llega la hora, el aviso
**suena de verdad** (campana por el altavoz + frase hablada): lo dispara el hilo
`parker._loop_agenda`, que es el único que toca audio y pantalla.

Este módulo es lógica pura: no usa audio, ni red, ni `now()` implícito (todo
recibe `ahora`), así que se prueba entero con horas fijas.

Reglas de interpretación (para que no haya sorpresas):

* **Alarma**: se elige la PRÓXIMA vez que sean esas horas. A las 16:00, «a las 7»
  es mañana a las 7:00 (y la confirmación lo dice en palabras). «de la mañana»,
  «de la tarde» y «de la noche» mandan sobre eso.
* **Cita**: una hora de 1 a 7 se entiende de la tarde (17:00) y de 8 a 11 de la
  mañana, porque es lo normal en una cita. La confirmación dice la hora en
  palabras, así que el dueño oye si se ha entendido y puede corregir.
* Una cita sin hora avisa a `agenda.hora_citas` (09:00 por defecto).
* Los avisos repetidos («todas las mañanas») **todavía no** se repiten: se pone
  la próxima vez y la propia confirmación lo dice.
"""

import json
import math
import re
import time
import unicodedata
from datetime import date, datetime, time as hora_del_dia, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ALARMA = "alarma"
TEMPORIZADOR = "temporizador"
CITA = "cita"

# Números que Whisper deja en letras («en cinco minutos»).
_UNIDADES = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100,
}

_PALABRAS_1_29 = {
    1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis",
    7: "siete", 8: "ocho", 9: "nueve", 10: "diez", 11: "once", 12: "doce",
    13: "trece", 14: "catorce", 15: "quince", 16: "dieciseis",
    17: "diecisiete", 18: "dieciocho", 19: "diecinueve", 20: "veinte",
    21: "veintiuno", 22: "veintidos", 23: "veintitres", 24: "veinticuatro",
    25: "veinticinco", 26: "veintiseis", 27: "veintisiete", 28: "veintiocho",
    29: "veintinueve", 30: "treinta",
}
_PALABRAS_DECENAS = {4: "cuarenta", 5: "cincuenta", 6: "sesenta",
                     7: "setenta", 8: "ochenta", 9: "noventa"}

_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
          "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}
_MESES_TEXTO = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre")
_DIAS_SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
                "viernes": 4, "sabado": 5, "domingo": 6}
_DIAS_TEXTO = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado",
               "domingo")

# Unidades de duración y su valor en segundos.
_UNIDADES_SEG = {"minuto": 60, "minutos": 60, "min": 60, "mins": 60, "m": 60,
                 "segundo": 1, "segundos": 1, "seg": 1, "segs": 1, "s": 1,
                 "hora": 3600, "horas": 3600, "h": 3600}

# Verbos que piden apuntar algo en el calendario o avisar de algo.
_VERBO_ALARMA = r"(?:alarma|alarmas|despertador|despiertame|despertarme)"
_VERBO_APUNTE = (r"(?:apunta|apuntame|apuntalo|anota|anotame|anotalo|guarda|"
                 r"guardame|agenda|agendame|agendalo|apunta en el calendario|"
                 r"apuntalo en el calendario|tengo una cita|tengo cita)")
_VERBO_AVISO = (r"(?:avisame|avisa me|avisame luego|me avisas|avisa|recuerdame|"
                r"recuerda me|acuérdate|acuerdate|recuerda)")

_MARCA_CONSULTA = (
    r"\b(?:que|cuales) (?:tengo|hay)\b|\bque (?:tengo|hay) (?:hoy|manana)\b|"
    r"\bque (?:alarma|alarmas|recordatorio|recordatorios|temporizador|"
    r"temporizadores|cita|citas) tengo\b|"
    r"\btengo algo\b|\btengo alguna\b|\btengo algo apuntado\b|"
    r"\balgo apuntado\b|\bque me queda\b|\bque tengo pendiente\b|"
    r"\b(alarmas?|recordatorios?|temporizador(?:es)?|citas?)\b[^.]{0,24}"
    r"\b(?:tengo|hay|puestas?|apuntadas?|pendientes?)\b")

_MARCA_BORRAR = (r"\b(?:borra|borrar|borrala|borralo|quita|quitar|quitala|"
                 r"quitalo|cancela|cancelar|cancelala|cancelalo|elimina|"
                 r"eliminar|anula|anular|olvida|olvidar|desactiva|desactivar)\b")

_VERBO_BORRAR = (r"(?:borra|borrar|borrala|borralo|quita|quitar|quitala|"
                 r"quitalo|cancela|cancelar|elimina|eliminar|anula|anular|"
                 r"olvida|olvidar)")

# Reprogramar una cita o una alarma ya existente: «cambia la hora del dentista
# de mañana a las 6», «mueve la alarma de las 7 a las 8». No incluye «pon»
# (eso crea una nueva) ni «borra» (eso la quita).
_MARCA_REPROGRAMAR = (r"\b(?:cambia|cambiar|cambiale|cambiarle|mueve|mover|"
                      r"mueveme|adelanta|adelantar|atrasa|atrasar|reprograma|"
                      r"reprogramar|modifica|modificar|actualiza|actualizar)\b")

# Palabras que no identifican la materia del aviso (verbos, tipos, fechas y
# conectores). Las que quedan («dentista», «fisio», «coche»…) son la pista.
_PALABRAS_REPROGRAMAR = {
    "cambia", "cambiar", "cambiale", "cambiarle", "mueve", "mover", "mueveme",
    "adelanta", "adelantar", "atrasa", "atrasar", "reprograma", "reprogramar",
    "modifica", "modificar", "actualiza", "actualizar", "hora", "horas",
    "cita", "citas", "alarma", "alarmas", "temporizador", "temporizadores",
    "recordatorio", "recordatorios", "manana", "tarde", "noche", "mediodia",
    "hoy", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
    "domingo", "para", "desde", "hasta", "parker", "oye", "por", "favor",
    "la", "el", "los", "las", "una", "un", "que", "y", "a", "en", "mi",
    "me", "te", "del", "de", "lo", "le", "se", "con", "al", "es", "son",
    "como", "puedes", "quiero", "otra", "vez",
}

# Habla de repetir: se avisa de que todavía no se repite solo.
_MARCA_REPETIR = (r"\btodos los dias\b|\btodas las mananas\b|\btodas las tardes\b|"
                  r"\btodas las noches\b|\bde lunes a viernes\b|\btodos los lunes\b|"
                  r"\bde lunes a domingo\b|\bcada dia\b|\bcada manana\b")

# Conectores que se quitan del principio del texto apuntado. El grupo acaba en
# final de frase para que «pon una alarma» no deje «una» como materia.
_RUIDO_INICIAL = (r"^(?:que|de|del|para|a|al|el|la|los|las|un|una|me|te|mi|y|"
                  r"parker|oye|por favor|apunta|apuntame|apuntalo|anota|anotame|"
                  r"anotalo|guarda|guardame|agenda|agendame|agendalo|recuerdame|"
                  r"acuérdate|acuerdate|avisame|pon|ponme|pone|pones|ponle|ponlo|"
                  r"ponla|poner|programa|programame|haz|hazme|"
                  r"es|tengo|tenia|tenía|hay|en|"
                  # Muletillas que el STT cuela delante y acababan dentro del
                  # titular: «Porque apunta un litro de agua» (placa 26/10).
                  r"porque|pues|es que|mira|veras|verás|bueno|venga|vale|"
                  r"eh|em|esto|o sea)(?:\s+|$)")

_UNIDAD_TEXTO = r"(minutos?|mins?|min|m|segundos?|segs?|seg|s|horas?|h)"

_DURACION_PATRONES = (
    rf"(?:en|dentro de)\s+(\d{{1,3}}|[a-z]+(?:\s+y\s+[a-z]+)?)\s*{_UNIDAD_TEXTO}\b",
    rf"temporizador\s+(?:de\s+|para\s+)?(\d{{1,3}}|[a-z]+(?:\s+y\s+[a-z]+)?)\s*{_UNIDAD_TEXTO}\b",
    rf"(?:pon|ponme|poner|programa|hazme)\s+(?:un\s+)?(?:temporizador\s+)?"
    rf"(?:de\s+)?(\d{{1,3}}|[a-z]+(?:\s+y\s+[a-z]+)?)\s*{_UNIDAD_TEXTO}\b",
)


def _duracion(texto: str) -> Optional[Tuple[int, str]]:
    """Segundos de un temporizador, con el trozo de texto que lo dice.

    «en 10 minutos», «temporizador de media hora», «un minuto y medio».
    """
    for patron, segundos in (
        (r"\bmedia hora\b", 1800),
        (r"\bhora y media\b", 5400),
        (r"\b(?:un )?cuarto de hora\b", 900),
        (r"\btres cuartos de hora\b", 2700),
    ):
        encontrado = re.search(patron, texto)
        if encontrado:
            return (segundos, encontrado.group(0))
    for patron in _DURACION_PATRONES:
        match = re.search(patron, texto)
        if not match:
            continue
        cantidad = _numero(match.group(1))
        unidad = _UNIDADES_SEG.get(match.group(2))
        if cantidad is None or unidad is None or cantidad <= 0:
            continue
        segundos = cantidad * unidad
        trozo = match.group(0)
        # «minuto y medio» son 90 s, no 60 (la mitad del minuto siguiente).
        if re.search(r"\by medio\b", texto[match.end():match.end() + 10]):
            segundos += unidad // 2
            trozo += " y medio"
        if segundos > 12 * 3600:
            continue
        return (int(segundos), trozo)
    return None


def _duracion_suelta(texto: str) -> Optional[Tuple[int, str]]:
    """Duración sin verbo de temporizador: «diez minutos», «media hora».

    La usa `modulos/rutinas.py` para «cállate diez minutos», donde no hay ni
    «en» ni «temporizador» que valgan de pista.
    """
    for patron, segundos in (
        (r"\bmedia hora\b", 1800),
        (r"\bhora y media\b", 5400),
        (r"\b(?:un )?cuarto de hora\b", 900),
        (r"\bmedio minuto\b", 30),
    ):
        encontrado = re.search(patron, texto)
        if encontrado:
            return (segundos, encontrado.group(0))
    match = re.search(r"\b(\d{1,3}|[a-z]+(?:\s+y\s+[a-z]+)?)"
                      r"\s*(minutos?|mins?|min|m|segundos?|segs?|seg|s|horas?|h)\b",
                      texto)
    if not match:
        return None
    cantidad = _numero(match.group(1))
    unidad = _UNIDADES_SEG.get(match.group(2))
    if cantidad is None or unidad is None or cantidad <= 0:
        return None
    segundos = int(cantidad * unidad)
    trozo = match.group(0)
    if re.search(r"\by medio\b", texto[match.end():match.end() + 10]):
        segundos += unidad // 2
        trozo += " y medio"
    if segundos <= 0 or segundos > 12 * 3600:
        return None
    return (segundos, trozo)


def _plano(texto: str) -> str:
    """Minúsculas, sin acentos, «7.30» y «7h30» como «7:30» (para comparar).

    Además arregla el apóstrofo que a veces escribe el STT en español
    («un litro d'agua» → «un litro de agua», placa 26/10): sin esto, el
    contador se quedaba con el nombre de la unidad («litro») en vez del de la
    cosa («agua») y salía uno nuevo cada vez.
    """
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"\b(\d{1,2})[.h](\d{2})\b", r"\1:\2", t)
    t = re.sub(r"\b(?:d|de|des)'\s*", "de ", t)     # d'agua -> de agua
    t = re.sub(r"\bl'\s*", "el ", t)                # l'otro -> el otro
    t = re.sub(r"'", " ", t)
    t = re.sub(r"[^a-z0-9:%/]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _numero(token: str) -> Optional[int]:
    """«35» o «treinta y cinco» -> 35. `None` si no es un número."""
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    total = 0
    encontrado = False
    for parte in token.split(" y "):
        parte = parte.strip()
        if parte in ("media", "medio"):
            return None
        if parte.startswith("ciento"):
            total += 100
            encontrado = True
            parte = parte[len("ciento"):].strip()
            if not parte:
                continue
        valor = _UNIDADES.get(parte)
        if valor is None:
            return None
        total += valor
        encontrado = True
    return total if encontrado else None


def _numero_a_palabras(n: int) -> str:
    """Cómo se dice un número en voz alta (0-99; fuera de rango, en dígitos)."""
    n = int(n)
    if n == 0:
        return "cero"
    if n == 100:
        return "cien"
    if n in _PALABRAS_1_29:
        return _PALABRAS_1_29[n]
    if 30 <= n <= 99:
        decena, resto = (n // 10) * 10, n % 10
        base = _PALABRAS_DECENAS.get(decena // 10, str(decena))
        # «cuarenta» no está en _PALABRAS_1_29: se añade aquí.
        if decena == 30:
            base = "treinta"
        return base if not resto else f"{base} y {_PALABRAS_1_29[resto]}"
    return str(n)


def _hora_hablada(momento: datetime) -> str:
    """«las siete y media de la tarde»: lo que Parker dice, no «19:30»."""
    h, m = momento.hour, momento.minute
    if h >= 20:
        sufijo = " de la noche"
    elif h == 12:
        sufijo = " del mediodía"
    elif h >= 13:
        sufijo = " de la tarde"
    else:
        sufijo = ""
    h12 = h % 12 or 12
    if m == 45:
        return (f"las {_numero_a_palabras((h12 % 12) + 1)} menos cuarto"
                f"{sufijo}")
    if m == 30:
        return f"las {_numero_a_palabras(h12)} y media{sufijo}"
    if m == 15:
        return f"las {_numero_a_palabras(h12)} y cuarto{sufijo}"
    if m == 0:
        return f"las {_numero_a_palabras(h12)} en punto{sufijo}"
    return f"las {_numero_a_palabras(h12)} y {_numero_a_palabras(m)}{sufijo}"


def _limpiar_payload(texto: str, quitar: Optional[List[str]] = None) -> str:
    """Deja el «qué» de la orden: quita el tiempo dicho y los conectores.

    `quitar` son expresiones regulares (los trozos literales van con
    `re.escape` desde quien llama).
    """
    for patron in (quitar or []):
        if patron:
            texto = re.sub(patron, " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .,:;¡!¿?")
    while True:
        nuevo = re.sub(_RUIDO_INICIAL, "", texto)
        if nuevo == texto:
            break
        texto = nuevo
    return texto.strip(" .,:;¡!¿?")


# Palabras que no aportan nada en el titular del calendario.
_PARADAS_TITULO = {
    "de", "del", "con", "a", "al", "en", "para", "por", "el", "la", "lo",
    "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu", "tus",
    "su", "sus", "que", "y", "o", "u", "e", "es", "son", "esta", "este",
    "tengo", "tiene", "hay", "me", "te", "se", "le", "les", "voy", "vamos",
}


def _titulo(texto: str, max_palabras: int = 6) -> str:
    """Titular corto del calendario: «tengo cita con el dentista» -> «cita dentista».

    Pedido el 26/10/2026: al preguntar por una cita Parker repetía la frase
    entera que se le dijo. El titular es lo que se guarda, se lee y se suelta
    en el aviso.
    """
    texto = re.sub(r"\s+", " ", (texto or "")).strip(" .,:;¡!¿?")
    if not texto:
        return ""
    palabras = [p for p in texto.split() if _plano(p) not in _PARADAS_TITULO]
    if not palabras:
        return " ".join(texto.split()[:max_palabras])
    return " ".join(palabras[:max_palabras])


class AgendaParker:
    """Alarmas, temporizadores y citas, con aviso real (campana + voz).

    Es lógica pura: el módulo no reproduce nada. `parker._loop_agenda` pregunta
    `vencidos()` cada segundo y se encarga del altavoz y de la cara.
    """

    def __init__(self, ruta_agenda: Optional[str] = None,
                 hora_citas: str = "09:00", dias_conservar: int = 30,
                 caducidad_horas: float = 12.0):
        self.ruta_agenda = Path(ruta_agenda) if ruta_agenda else None
        self.hora_citas = self._leer_hora_citas(hora_citas)
        self.dias_conservar = int(dias_conservar)
        # Un aviso que venció hace mucho (la placa estuvo apagada, por ejemplo)
        # NO se suelta al arrancar: visto en la placa el 26/10, Parker volvió y
        # soltó un temporizador de la sesión anterior. Dentro de la caducidad sí
        # se avisa, porque es lo que el dueño quería que le recordaran.
        self.caducidad_seg = float(caducidad_horas) * 3600.0
        self.avisos: List[Dict] = []
        self._cargar()

    # ------------------------------------------------------------------ estado

    @staticmethod
    def _leer_hora_citas(texto: str) -> Tuple[int, int]:
        match = re.match(r"\s*(\d{1,2})[:.](\d{2})", str(texto or ""))
        if not match:
            return (9, 0)
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return (h, m)
        return (9, 0)

    def _cargar(self) -> None:
        if not self.ruta_agenda or not self.ruta_agenda.exists():
            return
        try:
            datos = json.loads(self.ruta_agenda.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError("la agenda no es un objeto")
            avisos = datos.get("avisos") or []
            if not isinstance(avisos, list):
                raise ValueError("los avisos no son una lista")
        except (OSError, ValueError, TypeError):
            # JSON truncado, lista en vez de objeto, permisos... Parker arranca
            # igual con la agenda vacía en vez de quedarse sin voz.
            print("[Agenda] No pude leer la agenda guardada; empiezo vacía.")
            return
        limpios = []
        for a in avisos:
            if (not isinstance(a, dict)
                    or a.get("tipo") not in (ALARMA, TEMPORIZADOR, CITA)):
                continue
            try:
                ts = float(a["ts"])
            except (KeyError, TypeError, ValueError):
                continue            # una entrada corrupta no tumba la agenda entera
            # NaN/infinito y fechas imposibles (año 2000-2100) también se
            # descartan: `datetime.fromtimestamp` lanzaría en pleno bucle.
            if not math.isfinite(ts) or not 946684800 <= ts <= 4102444800:
                continue
            limpios.append(a)
        if len(limpios) != len(avisos):
            print(f"[Agenda] {len(avisos) - len(limpios)} avisos corruptos "
                  "descartados al cargar.")
        self.avisos = limpios
        self._purgar()

    def _guardar(self) -> None:
        """Escritura atómica: un corte de luz no deja el JSON a medias.

        Se escribe en `.tmp` y se renombra encima. Antes, si la placa se apagaba
        justo mientras guardaba, el fichero podía quedar truncado y la agenda
        se perdía al arrancar (el `_cargar` la descartaba entera).
        """
        if not self.ruta_agenda:
            return
        try:
            self.ruta_agenda.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta_agenda.with_name(self.ruta_agenda.name + ".tmp")
            temporal.write_text(
                json.dumps({"version": 1, "avisos": self.avisos},
                           ensure_ascii=False, indent=1),
                encoding="utf-8")
            temporal.replace(self.ruta_agenda)
        except OSError as e:
            print(f"[Agenda] No se pudo guardar la agenda: {e}")

    def _purgar(self, ahora: Optional[datetime] = None) -> None:
        """Tira los avisos ya pasados hace días: la tarjeta es para los recuerdos."""
        limite = (ahora or datetime.now()) - timedelta(days=self.dias_conservar)
        antes = len(self.avisos)
        self.avisos = [a for a in self.avisos
                       if datetime.fromtimestamp(float(a["ts"])) >= limite]
        if len(self.avisos) != antes:
            print(f"[Agenda] {antes - len(self.avisos)} avisos viejos olvidados "
                  f"(más de {self.dias_conservar} días)")

    def _nuevo_id(self) -> str:
        return f"{int(time.time() * 1000) % 10 ** 9}-{len(self.avisos)}"

    def _anadir(self, tipo: str, cuando: datetime, texto: str,
                duracion_seg: Optional[int] = None,
                ahora: Optional[datetime] = None,
                dicho: Optional[str] = None) -> Dict:
        aviso = {
            "id": self._nuevo_id(),
            "tipo": tipo,
            "ts": cuando.timestamp(),
            "texto": texto,
            "avisado": False,
            "creado": (ahora or datetime.now()).timestamp(),
        }
        if duracion_seg:
            aviso["duracion_seg"] = int(duracion_seg)
        # Lo que se dijo tal cual («tengo cita con el dentista»), solo para poder
        # revisarlo después: lo que se lee y se dice es el `texto` corto.
        if dicho and dicho != texto:
            aviso["dicho"] = dicho
        self.avisos.append(aviso)
        self._guardar()
        return aviso

    # ------------------------------------------------------------- para el hilo

    def vencidos(self, ahora: Optional[datetime] = None) -> List[Dict]:
        """Avisos cuya hora ya llegó y que aún no han sonado.

        Los que vencieron hace más de `caducidad_seg` se descartan sin sonar (y
        sin volver a mirarlos): si la placa estuvo días apagada, un «sacar la
        ropa» de la semana pasada sonaría solo al encender.
        """
        t = (ahora or datetime.now()).timestamp()
        vencidos: List[Dict] = []
        for aviso in self.avisos:
            if aviso.get("avisado") or float(aviso["ts"]) > t:
                continue
            if t - float(aviso["ts"]) > self.caducidad_seg:
                aviso["avisado"] = True
                aviso["caducado_ts"] = t
                horas = (t - float(aviso["ts"])) / 3600.0
                print(f"[Agenda] Aviso de hace {horas:.0f} h descartado (caducó): "
                      f"«{aviso.get('texto') or aviso.get('tipo')}»")
                self._guardar()
                continue
            vencidos.append(aviso)
        return vencidos

    def marcar_avisado(self, aviso: Dict,
                       ahora: Optional[datetime] = None) -> None:
        aviso["avisado"] = True
        aviso["avisado_ts"] = (ahora or datetime.now()).timestamp()
        self._guardar()

    def proximos(self, limite: int = 3,
                 ahora: Optional[datetime] = None) -> List[Dict]:
        t = (ahora or datetime.now()).timestamp()
        pendientes = [a for a in self.avisos if float(a["ts"]) >= t - 60]
        return sorted(pendientes, key=lambda a: float(a["ts"]))[:limite]

    def del_dia(self, dia: date, ahora: Optional[datetime] = None) -> List[Dict]:
        inicio = datetime.combine(dia, hora_del_dia(0, 0)).timestamp()
        fin = datetime.combine(dia, hora_del_dia(23, 59, 59)).timestamp()
        return sorted([a for a in self.avisos if inicio <= float(a["ts"]) <= fin],
                      key=lambda a: float(a["ts"]))

    def frase_aviso(self, aviso: Dict) -> str:
        """Lo que Parker dice cuando el aviso suena (o al probarlo)."""
        texto = (aviso.get("texto") or "").strip()
        tipo = aviso.get("tipo")
        if tipo == TEMPORIZADOR:
            segundos = int(aviso.get("duracion_seg") or 0)
            frase = f"¡Bip, bip! Han pasado {_duracion_hablada(segundos)}."
        elif tipo == ALARMA:
            frase = f"¡Riiing! Son {_hora_hablada(datetime.fromtimestamp(float(aviso['ts'])))}."
        else:
            frase = (f"Te aviso: {_hora_hablada(datetime.fromtimestamp(float(aviso['ts'])))}.")
        return f"{frase} {texto}." if texto else frase

    # --------------------------------------------------------------- reconocer

    def procesar(self, mensaje: str,
                 ahora: Optional[datetime] = None) -> Optional[str]:
        """Devuelve la frase de respuesta si era una orden de agenda, o `None`."""
        texto = _plano(mensaje)
        if not texto:
            return None
        ahora = ahora or datetime.now()
        # Reprogramar va ANTES de crear: «cambia la hora del dentista» no debe
        # acabar como una cita nueva ni llegar al LLM (30/10).
        respuesta = self._reprogramar(texto, ahora)
        if respuesta is not None:
            return respuesta
        for paso in (self._consultar, self._borrar):
            respuesta = paso(texto, ahora)
            if respuesta is not None:
                return respuesta
        return self._crear(texto, ahora)

    # ---------------------------------------------------------------- consultar

    def _consultar(self, texto: str, ahora: datetime) -> Optional[str]:
        # Una ORDEN puede sonar a pregunta: «apunta el viernes a las 9 que
        # tengo cita con el dentista» contiene «que tengo» y se contestaba
        # «no tienes nada apuntado» (visto el 26/10 al probarlo). Si empieza
        # por verbo de apunte y lleva hora, es una orden, no una consulta.
        if self._hora_del_texto(texto) is not None and re.match(
                rf"^(?:{_VERBO_APUNTE}|{_VERBO_AVISO}|{_VERBO_ALARMA})\b",
                re.sub(r"^(?:parker|oye|eh|vale|venga|anda|por favor)\s+", "", texto)):
            return None
        if not re.search(_MARCA_CONSULTA, texto):
            return None
        if re.search(r"\besta semana\b|\blos proximos dias\b|\besta semanita\b",
                     texto):
            return self._resumen_semana(ahora, desde_hoy=True)
        if re.search(r"\bla semana que viene\b|\bla proxima semana\b|"
                     r"\bsemana que viene\b", texto):
            return self._resumen_semana(ahora, desde_hoy=False)
        fecha = self._fecha_del_texto(texto, ahora)
        if fecha is not None:
            return self._resumen_dia(fecha[0], ahora)
        if re.search(r"\b(?:alarma|alarmas|recordatorio|recordatorios|"
                     r"temporizador|temporizadores)\b", texto):
            return self._resumen_avisos(ahora)
        return None

    @staticmethod
    def _unir(frases: List[str]) -> str:
        if not frases:
            return ""
        if len(frases) == 1:
            return frases[0]
        return ", ".join(frases[:-1]) + " y " + frases[-1]

    def _descripcion(self, aviso: Dict, ahora: datetime) -> str:
        momento = datetime.fromtimestamp(float(aviso["ts"]))
        texto = (aviso.get("texto") or "").strip()
        if aviso.get("tipo") == CITA:
            cuerpo = self._cuando_hablado(momento, ahora)
        else:
            cuerpo = _hora_hablada(momento)
        return f"{cuerpo}, {texto}" if texto else cuerpo

    def _cuando_hablado(self, momento: datetime, ahora: datetime) -> str:
        """«mañana a las siete en punto», «el viernes a las cinco de la tarde»."""
        dia_relativo = {
            ahora.date(): "hoy",
            (ahora + timedelta(days=1)).date(): "mañana",
            (ahora + timedelta(days=2)).date(): "pasado mañana",
        }.get(momento.date())
        if dia_relativo:
            return f"{dia_relativo} a {_hora_hablada(momento)}"
        dia = (f"el {_DIAS_TEXTO[momento.weekday()]} {momento.day} de "
               f"{_MESES_TEXTO[momento.month - 1]}")
        return f"{dia} a {_hora_hablada(momento)}"

    def _resumen_dia(self, dia: date, ahora: datetime) -> str:
        etiqueta = {ahora.date(): "Hoy", (ahora + timedelta(days=1)).date(): "Mañana",
                    (ahora + timedelta(days=2)).date(): "Pasado mañana"}.get(dia)
        if not etiqueta:
            etiqueta = f"El {_DIAS_TEXTO[dia.weekday()]} {dia.day} de {_MESES_TEXTO[dia.month - 1]}"
        del_dia = self.del_dia(dia, ahora)
        if not del_dia:
            return f"{etiqueta} no tienes nada apuntado."
        frases = [self._descripcion(a, ahora) for a in del_dia[:4]]
        resto = len(del_dia) - len(frases)
        cola = f" y {resto} más" if resto else ""
        return f"{etiqueta} tienes: {self._unir(frases)}{cola}."

    def _resumen_semana(self, ahora: datetime, desde_hoy: bool) -> str:
        if desde_hoy:
            inicio = ahora.date()
            etiqueta = "Esta semana"
        else:
            inicio = ahora.date() + timedelta(days=7 - ahora.weekday())
            etiqueta = "La semana que viene"
        fin = inicio + timedelta(days=6 - inicio.weekday())
        dentro = [a for a in self.avisos
                  if inicio <= datetime.fromtimestamp(float(a["ts"])).date() <= fin]
        if not dentro:
            return f"{etiqueta} no tienes nada apuntado."
        dentro.sort(key=lambda a: float(a["ts"]))
        frases = [self._descripcion(a, ahora) for a in dentro[:4]]
        resto = len(dentro) - len(frases)
        cola = f" y {resto} más" if resto else ""
        return f"{etiqueta}: {self._unir(frases)}{cola}."

    def _resumen_avisos(self, ahora: datetime) -> str:
        pendientes = [a for a in self.proximos(4, ahora) if a.get("tipo") != CITA]
        if not pendientes:
            return "No tienes ninguna alarma ni temporizador puestos."
        frases = []
        for aviso in pendientes:
            momento = datetime.fromtimestamp(float(aviso["ts"]))
            texto = (aviso.get("texto") or "").strip()
            cuerpo = (f"{aviso.get('tipo', 'aviso')} para "
                      f"{self._cuando_hablado(momento, ahora)}")
            frases.append(f"{cuerpo}: {texto}" if texto else cuerpo)
        return f"Tienes {self._unir(frases)}."

    # -------------------------------------------------------------- reprogramar

    @staticmethod
    def _horas_del_texto(texto: str) -> List[Tuple[int, int, Optional[bool], str]]:
        """Todas las horas dichas, en orden.

        «cambia la alarma de las 7 a las 8» tiene dos: la vieja (para encontrar
        la alarma) y la nueva (la que se pone). «cambia el dentista a las 6»
        tiene una: la nueva.
        """
        horas = []
        for m in re.finditer(r"\ba las?\s+(?:\d{1,2}|[a-z]+)", texto):
            hora = AgendaParker._hora_del_texto(texto[m.start():m.start() + 80])
            if hora is not None and hora not in horas:
                horas.append(hora)
        return horas

    @staticmethod
    def _clave_aviso(aviso: Dict) -> str:
        """Texto del aviso en plano, para buscar «dentista» o «fisio»."""
        return _plano((aviso.get("texto") or "") + " " + (aviso.get("dicho") or ""))

    def _reprogramar(self, texto: str, ahora: datetime) -> Optional[str]:
        """Cambia la hora de una cita/alarma existente, sin duplicarla.

        Solo actúa si hay un verbo de cambio, una hora nueva y una pista de qué
        aviso se cambia (tipo o materia). Así no secuestra «cambia el volumen»
        ni «cambia el cerebro al local», que van por otros módulos.
        """
        if not re.search(_MARCA_REPROGRAMAR, texto):
            return None

        tipo = None
        if re.search(r"\balarmas?\b|\bdespertador\b", texto):
            tipo = ALARMA
        elif re.search(r"\btemporizador(?:es)?\b", texto):
            tipo = TEMPORIZADOR
        elif re.search(r"\bcitas?\b|\bcalendario\b", texto):
            tipo = CITA

        # Avisos que aún pueden cambiarse: los no avisados y no caducados.
        limite = (ahora - timedelta(hours=12)).timestamp()
        pendientes = [a for a in self.avisos
                      if not a.get("avisado") and float(a["ts"]) >= limite]

        palabras = {p for p in re.findall(r"[a-z0-9]{4,}", texto)
                    if p not in _PALABRAS_REPROGRAMAR and not p.isdigit()}
        coincidencias = [a for a in pendientes
                         if any(p in self._clave_aviso(a) for p in palabras)]
        horas = self._horas_del_texto(texto)

        if not horas:
            if tipo or coincidencias:
                return "Dime a qué hora la cambio."
            return None

        nueva = horas[-1]
        vieja = horas[0] if len(horas) > 1 else None

        if tipo:
            del_tipo = [a for a in pendientes if a.get("tipo") == tipo]
            if del_tipo:
                pendientes = del_tipo
            candidatos = coincidencias or []
        else:
            candidatos = coincidencias

        if not candidatos and tipo:
            candidatos = pendientes
        if not candidatos:
            if tipo or palabras:
                return "No encuentro esa cita en la agenda."
            return None

        # «de las 7 a las 8»: la primera hora identifica la alarma actual.
        if vieja is not None:
            h, _, _, _ = vieja
            por_hora = [a for a in candidatos
                        if datetime.fromtimestamp(float(a["ts"])).hour == h]
            if por_hora:
                candidatos = por_hora

        # Si sigue habiendo varios y nada los distingue, no se cambia uno al
        # azar: se pregunta. Antes «cambia la alarma a las 8» podía mover la
        # que no era (con dos alarmas puestas).
        if len(candidatos) > 1 and not coincidencias:
            nombre = {CITA: "citas", ALARMA: "alarmas",
                      TEMPORIZADOR: "temporizadores"}.get(tipo, "avisos")
            return (f"Tienes {len(candidatos)} {nombre}. ¿Cuál quiero cambiar? "
                    "Puedes decirme la hora que tiene ahora.")

        candidatos.sort(key=lambda a: abs(float(a["ts"]) - ahora.timestamp()))
        aviso = candidatos[0]

        h, m, pm, _ = nueva
        fecha = self._fecha_del_texto(texto, ahora)
        if fecha is not None:
            momento = self._momento_cita(h, m, fecha[0], pm)
        elif aviso.get("tipo") == ALARMA:
            momento = self._momento_alarma(h, m, ahora, pm)
        else:
            dia = datetime.fromtimestamp(float(aviso["ts"])).date()
            momento = self._momento_cita(h, m, dia, pm)
            if momento <= ahora:
                momento += timedelta(days=1)

        aviso["ts"] = momento.timestamp()
        aviso["avisado"] = False
        for clave in ("avisado_ts", "caducado_ts"):
            aviso.pop(clave, None)
        aviso["reprogramado_ts"] = ahora.timestamp()
        self._guardar()

        nombre = {CITA: "cita", ALARMA: "alarma",
                  TEMPORIZADOR: "temporizador"}.get(aviso.get("tipo"), "aviso")
        etiqueta = (aviso.get("texto") or "").strip()
        detalle = f" «{etiqueta}»" if etiqueta else ""
        return (f"Cambiada la {nombre}{detalle} a "
                f"{self._cuando_hablado(momento, ahora)}.")

    # -------------------------------------------------------------------- borrar

    def _borrar(self, texto: str, ahora: datetime) -> Optional[str]:
        if not re.search(_MARCA_BORRAR, texto) or not self.avisos:
            return None
        tipos = []
        if re.search(r"\balarmas?\b|\bdespertador\b", texto):
            tipos.append(ALARMA)
        if re.search(r"\btemporizador(?:es)?\b", texto):
            tipos.append(TEMPORIZADOR)
        if re.search(r"\bcitas?\b|\bcalendario\b", texto):
            tipos.append(CITA)
        todos = re.search(r"\btodo\b|\btodas\b|\btodos los avisos\b|"
                          r"\bmis avisos\b|\btodos\b", texto)
        if not tipos and not todos:
            return None
        busca = self._texto_buscado(texto)
        por_tipo = [a for a in self.avisos if not tipos or a.get("tipo") in tipos]
        candidatos = [a for a in por_tipo
                      if not busca or busca in (a.get("texto") or "").lower()]
        if not candidatos and busca:
            # «Borra la alarma de las siete»: no hay texto que case, pero el
            # tipo lo deja claro; se borra el del tipo pedido.
            candidatos = por_tipo
        if not candidatos:
            return "No encuentro nada de eso apuntado."
        # «Borra la alarma» con dos puestas no debe borrar las dos por error:
        # se pregunta, y «borra todas las alarmas» sigue funcionando.
        if len(candidatos) > 1 and not busca and not todos:
            return (f"Tienes {len(candidatos)} avisos de ese tipo. ¿Cuál borro? "
                    "Si quieres, di «borra todas las alarmas».")
        for aviso in candidatos:
            self.avisos.remove(aviso)
        self._guardar()
        if len(candidatos) == 1:
            texto_aviso = (candidatos[0].get("texto") or "").strip()
            detalle = f" «{texto_aviso}»" if texto_aviso else ""
            return f"Borrado: {candidatos[0].get('tipo')}{detalle}."
        return f"He borrado {len(candidatos)} avisos."

    @staticmethod
    def _texto_buscado(texto: str) -> str:
        """Materia del aviso, para borrar «el del médico» y no todo."""
        match = re.search(r"\b(?:de|del|para|lo de|sobre)\s+(.{3,40})$", texto)
        if not match:
            return ""
        return _limpiar_payload(match.group(1))

    # --------------------------------------------------------------------- crear

    @staticmethod
    def _es_orden_temporizador(texto: str, duracion: Tuple[int, str]) -> bool:
        """«En diez minutos» a secas es una orden; «te lo digo en diez» no.

        Sin esta guarda, cualquier frase con una duración («en cinco minutos te
        llamo») pondría un temporizador.
        """
        if re.search(_VERBO_AVISO, texto) or re.search(r"\btemporizador\b", texto):
            return True
        if re.search(r"\b(?:pon|ponme|poner|programa|hazme)\b", texto):
            return True
        resto = texto.replace(duracion[1], " ", 1)
        resto = re.sub(r"\b(?:en|dentro de|de|para|parker|oye|por favor|vale|venga)\b",
                       " ", resto)
        return not resto.strip()

    def _crear(self, texto: str, ahora: datetime) -> Optional[str]:
        repetir = bool(re.search(_MARCA_REPETIR, texto))
        # 1) Temporizador: una duración («en 10 minutos», «temporizador de 10 min»).
        duracion = _duracion(texto)
        if duracion is not None and self._es_orden_temporizador(texto, duracion):
            segundos, trozo = duracion
            momento = ahora + timedelta(seconds=segundos)
            materia = _limpiar_payload(
                texto, [re.escape(trozo), r"\btemporizador\b",
                        r"\brecuerdame\b", r"\bavisame\b", r"\bacuérdate\b",
                        r"\bacuerdate\b"])
            self._anadir(TEMPORIZADOR, momento, materia,
                         duracion_seg=segundos, ahora=ahora)
            return (f"Temporizador de {_duracion_hablada(segundos)}. Te aviso a "
                    f"{_hora_hablada(momento)}.")

        hora = self._hora_del_texto(texto)
        fecha = self._fecha_del_texto(texto, ahora)
        es_alarma = re.search(_VERBO_ALARMA, texto) is not None
        es_apunte = re.search(_VERBO_APUNTE, texto) is not None
        es_aviso = re.search(_VERBO_AVISO, texto) is not None

        # 2) Cita con fecha (con o sin hora): «apunta que el viernes ...».
        if fecha is not None and (es_apunte or es_aviso) and not es_alarma:
            dia = fecha[0]
            quitar = [re.escape(fecha[1])]
            if hora is not None:
                h, m, pm, trozo = hora
                momento = self._momento_cita(h, m, dia, pm)
                quitar.append(re.escape(trozo))
            else:
                momento = datetime.combine(
                    dia, hora_del_dia(*self.hora_citas))
            materia = _limpiar_payload(texto, quitar)
            # En el calendario se guarda un TÍTULO corto, no la frase que se dijo
            # («cita dentista», no «tengo cita con el dentista el viernes a las
            # nueve»): es lo que se lee al preguntar y lo que suena en el aviso.
            titulo = _titulo(materia)
            self._anadir(CITA, momento, titulo, ahora=ahora, dicho=materia)
            return (f"Apuntado: {self._cuando_hablado(momento, ahora)}"
                    f"{': ' + titulo if titulo else ''}.")

        # 3) Alarma a una hora («pon una alarma a las 7:30», «despiértame a las 8»).
        if hora is not None and (es_alarma or es_aviso or es_apunte):
            h, m, pm, trozo = hora
            dia = fecha[0] if fecha is not None else None
            if dia is None:
                momento = self._momento_alarma(h, m, ahora, pm)
            else:
                momento = self._momento_cita(h, m, dia, pm)
            quitar = [re.escape(trozo),
                      r"\b(?:alarma|alarmas|despertador|recordatorio)\b"]
            if fecha is not None:
                quitar.append(re.escape(fecha[1]))
            materia = _limpiar_payload(texto, quitar)
            self._anadir(ALARMA, momento, materia, ahora=ahora)
            aviso_repetir = (" Solo lo pongo una vez; repetirlo cada día todavía "
                             "no sé hacerlo." if repetir else "")
            texto_materia = f": {materia}" if materia else ""
            return (f"Alarma puesta para {self._cuando_hablado(momento, ahora)}"
                    f"{texto_materia}.{aviso_repetir}")

        # 4) «Ponme una alarma para el viernes», sin hora: se pregunta cuál.
        if es_alarma and (fecha is not None or re.search(r"\balarma\b|\bdespertador\b",
                                                         texto)):
            return "¿A qué hora quieres la alarma?"
        return None

    # ----------------------------------------------------------- piezas de tiempo

    @staticmethod
    def _hora_del_texto(texto: str) -> Optional[Tuple[int, int, Optional[bool], str]]:
        """`(hora, minuto, es_tarde, trozo)`: es_tarde None si no lo dijo.

        «a las 7:30», «a las siete y media», «a las 9 menos cuarto»,
        «a las 7 de la tarde», «a la una». El acarreo se resuelve solo: «las
        nueve menos veinte» son las 8:40 y «las siete y cincuenta» las 7:50.
        """
        match = re.search(
            r"\ba las?\s+(\d{1,2}|[a-z]+)(?:\s*:\s*(\d{2}))?", texto)
        if not match:
            return None
        hora_txt = match.group(1)
        h = int(hora_txt) if hora_txt.isdigit() else _numero(hora_txt)
        if h is None or not 0 <= h <= 23:
            return None
        m = int(match.group(2)) if match.group(2) else 0
        trozo = match.group(0)
        cola = texto[match.end():match.end() + 40]

        reloj = re.match(r"\s*(y|menos)\s+(media|cuarto|(\d{1,2}|[a-z]+))", cola)
        if reloj:
            palabra = reloj.group(2)
            if palabra == "media":
                valor = 30
            elif palabra == "cuarto":
                valor = 15
            else:
                valor = _numero(palabra)
                if valor is None:
                    return None
            m += valor if reloj.group(1) == "y" else -valor
            trozo += reloj.group(0)
        elif re.match(r"\s*en punto\b", cola):
            trozo += " en punto"
        while m < 0:
            m += 60
            h -= 1
        while m > 59:
            m -= 60
            h += 1
        h %= 24

        pm: Optional[bool] = None
        parte = re.search(r"\bde (?:la|el) (manana|tarde|noche|mediodia)\b", cola)
        if parte:
            pm = parte.group(1) != "manana"
            trozo += " " + parte.group(0)
        return (h, m, pm, trozo)

    @staticmethod
    def _momento_alarma(h: int, m: int, ahora: datetime,
                        pm: Optional[bool]) -> datetime:
        """La PRÓXIMA vez que sean esas horas (hoy si aún no han pasado)."""
        hora = h + 12 if (pm and h < 12) else h
        momento = ahora.replace(hour=hora, minute=m, second=0, microsecond=0)
        if momento <= ahora:
            momento += timedelta(days=1)
        return momento

    @staticmethod
    def _momento_cita(h: int, m: int, dia: date, pm: Optional[bool]) -> datetime:
        """Cita: una hora de 1 a 7 se entiende de la tarde, 8-11 de la mañana."""
        hora = h
        if pm is True and h < 12:
            hora = h + 12
        elif pm is None and 1 <= h <= 7:
            hora = h + 12
        return datetime.combine(dia, hora_del_dia(hora, m))

    @staticmethod
    def _fecha_del_texto(texto: str,
                         ahora: datetime) -> Optional[Tuple[date, str]]:
        """`(día, trozo)` de la fecha dicha, o None.

        «hoy», «mañana», «pasado mañana», «el viernes», «el próximo lunes»,
        «el 12 de noviembre», «el 3/12», «en 5 días».
        """
        hoy = ahora.date()
        for patron, dias in ((r"\bpasado manana\b", 2), (r"\banteayer\b", -2),
                             (r"\bayer\b", -1)):
            if re.search(patron, texto):
                return (hoy + timedelta(days=dias), re.search(patron, texto).group(0))
        # «mañana» = el día siguiente; pero «de la mañana» es la franja horaria.
        match = re.search(r"(?<!de la )(?<!por la )(?<!esta )\bmanana\b", texto)
        if match:
            return (hoy + timedelta(days=1), match.group(0))
        match = re.search(r"\bhoy\b", texto)
        if match:
            return (hoy, match.group(0))
        match = re.search(r"\ben (\d{1,2}|[a-z]+) (dias?|semanas?)\b", texto)
        if match:
            cantidad = _numero(match.group(1))
            if cantidad:
                dias = cantidad * (7 if match.group(2).startswith("semana") else 1)
                return (hoy + timedelta(days=dias), match.group(0))
        match = re.search(r"\b(?:el|para el|este|esta|la)?\s*"
                          r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
                          texto)
        if match:
            objetivo = _DIAS_SEMANA[match.group(1)]
            delta = (objetivo - hoy.weekday()) % 7 or 7
            trozo = match.group(0) + _siguiente_etiqueta(texto[match.end():])
            return (hoy + timedelta(days=delta), trozo)
        match = re.search(r"\bel (\d{1,2}) de ([a-z]+)(?: de (\d{4}))?\b", texto)
        if match:
            mes = _MESES.get(match.group(2))
            if mes:
                anio = int(match.group(3)) if match.group(3) else hoy.year
                try:
                    fecha = date(anio, mes, int(match.group(1)))
                except ValueError:
                    return None
                if fecha < hoy and not match.group(3):
                    fecha = fecha.replace(year=anio + 1)
                return (fecha, match.group(0))
        match = re.search(r"\bel (\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", texto)
        if match:
            dia, mes = int(match.group(1)), int(match.group(2))
            anio = int(match.group(3)) if match.group(3) else hoy.year
            if anio < 100:
                anio += 2000
            try:
                fecha = date(anio, mes, dia)
            except ValueError:
                return None
            if fecha < hoy and not match.group(3):
                fecha = fecha.replace(year=anio + 1)
            return (fecha, match.group(0))
        return None


def _siguiente_etiqueta(resto: str) -> str:
    """«… que viene», «… próximo»: el trozo que acompaña al día de la semana."""
    return (" que viene" if re.match(r"\s*que viene\b", resto)
            else " próximo" if re.match(r"\s*(?:proximo|siguiente)\b", resto)
            else "")


def _duracion_hablada(segundos: int) -> str:
    """«diez minutos», «una hora y media», «un minuto y medio»: en palabras."""
    segundos = int(segundos or 0)

    def _plural(cantidad: int, singular: str, plural: str,
                articulo: str = "un") -> str:
        return (f"{articulo} {singular}" if cantidad == 1
                else f"{_numero_a_palabras(cantidad)} {plural}")

    if segundos >= 3600:
        horas, resto = divmod(segundos, 3600)
        base = _plural(horas, "hora", "horas", articulo="una")
        if not resto:
            return base
        if resto % 60 == 0:
            return f"{base} y {_plural(resto // 60, 'minuto', 'minutos')}"
        return (f"{base} y {_plural(resto // 60, 'minuto', 'minutos')} con "
                f"{_plural(resto % 60, 'segundo', 'segundos')}")
    if segundos >= 60:
        minutos, resto = divmod(segundos, 60)
        base = _plural(minutos, "minuto", "minutos")
        if not resto:
            return base
        return f"{base} y {_plural(resto, 'segundo', 'segundos')}"
    return _plural(segundos, "segundo", "segundos")
