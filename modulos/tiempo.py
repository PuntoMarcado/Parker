"""
modulos/tiempo.py
=================
El tiempo que hace y el sitio donde está Parker.

Datos de **Open-Meteo** (https://open-meteo.com): sin clave, sin cuenta y sin
tarjeta. Se llama con latitud/longitud y devuelve el tiempo de hoy y de mañana.
Es la única función de Parker que necesita internet para un dato, así que si no
hay red lo dice claro en vez de inventárselo.

La ciudad es una **variable**, no una constante: «estamos en Madrid» la cambia,
la guarda en `parker.tiempo.json` (que manda sobre `config.yaml`) y la confirma
por voz diciendo la zona. El nombre se resuelve con el geocodificador del mismo
servicio, así que vale cualquier ciudad o pueblo.

Como la fecha o la hora, esto es un dato que Parker **sabe**: lo dice él con las
cifras reales, sin pasar por el modelo (Sistema 1). El resumen es corto a
propósito: se escucha por el altavoz.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests

from modulos.agenda import _numero_a_palabras, _plano

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
METEO_URL = "https://api.open-meteo.com/v1/forecast"
CIUDAD_POR_DEFECTO = "Barcelona"

# Códigos WMO de Open-Meteo, en castellano y en una frase corta.
_CIELO = {
    0: "despejado", 1: "casi despejado", 2: "con algunas nubes", 3: "nublado",
    45: "con niebla", 48: "con niebla helada",
    51: "con llovizna débil", 53: "con llovizna", 55: "con llovizna fuerte",
    56: "con llovizna helada", 57: "con llovizna helada fuerte",
    61: "con lluvia débil", 63: "con lluvia", 65: "con lluvia fuerte",
    66: "con lluvia helada", 67: "con lluvia helada fuerte",
    71: "con nieve débil", 73: "con nieve", 75: "con nieve fuerte",
    77: "con aguanieve", 80: "con chubascos débiles", 81: "con chubascos",
    82: "con chubascos fuertes", 85: "con chubascos de nieve",
    86: "con chubascos de nieve fuertes", 95: "con tormenta",
    96: "con tormenta y granizo", 99: "con tormenta fuerte y granizo",
}

# Formas de preguntar por el tiempo (y solo esas: «hoy hace frío» es charla).
_PREGUNTAS = (
    r"\bque (?:tal )?(?:el )?(?:tiempo|clima)\b",
    r"\bcomo (?:esta|estara|va a estar|estan) (?:el )?(?:tiempo|clima|dia)\b",
    r"\b(?:me dices|dime|sabes) (?:el |que )?(?:tiempo|clima)\b",
    r"\bel tiempo (?:que (?:hace|hara|va a hacer)|de (?:hoy|manana))\b",
    r"\bva a (?:llover|nevar|hacer sol|hacer frio|hacer calor)\b",
    r"\b(?:puede|podria|crees que va a) (?:llover|nevar)\b",
    r"\b(?:llovera|nevara)\b",
    r"\b(?:que|cuantos) (?:grados|temperatura)\b",
    r"\bque (?:frio|calor) (?:hace|va a hacer|hara)\b",
    r"\b(?:esta|estara|estan) (?:lloviendo|nublado|despejado|nevando)\b",
    r"\b(?:me hace falta|necesito|cojo|hay que coger) (?:el |mi )?paraguas\b",
    r"\bparaguas (?:hoy|manana)\b",
)
_LLUVIA = (r"\b(?:llover|llov(?:er|era|ia)|lluvia|paraguas|chubascos?|tormenta|"
           r"mojar(?:me|nos)|nev(?:ar|ara|ada))\b")
_NO_ES_SITIO = ("el ", "la ", "los ", "las ", "mi ", "tu ", "un ", "una ", "casa",
                "salon", "cocina", "habitacion", "bano", "trabajo", "oficina",
                "cama", "sofa", "calle", "pueblo", "ciudad", "barrio")


class TiempoParker:
    """Tiempo de hoy y de mañana, y la ciudad guardada como variable."""

    def __init__(self, ciudad: Optional[str] = None, ruta_ciudad: Optional[str] = None,
                 latitud: Optional[float] = None, longitud: Optional[float] = None,
                 pais: str = "", timeout: float = 6.0, cache_seg: float = 600.0):
        self.ruta_ciudad = Path(ruta_ciudad) if ruta_ciudad else None
        self.timeout = float(timeout)
        self.cache_seg = float(cache_seg)
        self.ciudad = str(ciudad or CIUDAD_POR_DEFECTO)
        self.latitud = latitud
        self.longitud = longitud
        self.pais = pais
        self._cache: Optional[Dict] = None
        self._cache_ts = 0.0
        # Lo que se diga por voz manda sobre config.yaml: es la ciudad de ahora.
        self._cargar()

    # ------------------------------------------------------------------ ciudad

    def _cargar(self) -> None:
        if not self.ruta_ciudad or not self.ruta_ciudad.exists():
            return
        try:
            datos = json.loads(self.ruta_ciudad.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        if datos.get("ciudad"):
            self.ciudad = str(datos["ciudad"])
        self.latitud = datos.get("latitud", self.latitud)
        self.longitud = datos.get("longitud", self.longitud)
        self.pais = str(datos.get("pais") or self.pais)

    def _guardar(self) -> None:
        if not self.ruta_ciudad:
            return
        try:
            self.ruta_ciudad.write_text(json.dumps({
                "ciudad": self.ciudad, "pais": self.pais,
                "latitud": self.latitud, "longitud": self.longitud,
                "guardado": datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            print(f"[Tiempo] No pude guardar la ciudad: {e}")

    def cambiar_ciudad(self, nombre: str) -> Optional[str]:
        """Resuelve el nombre y lo guarda. Devuelve la ciudad o `None`."""
        try:
            res = requests.get(GEO_URL, params={"name": nombre, "count": 1,
                                                "language": "es", "format": "json"},
                               timeout=self.timeout)
            res.raise_for_status()
            resultados = res.json().get("results") or []
        except Exception as e:
            print(f"[Tiempo] No pude buscar «{nombre}»: {e}")
            return None
        if not resultados:
            print(f"[Tiempo] No encuentro el sitio «{nombre}»")
            return None
        sitio = resultados[0]
        self.ciudad = str(sitio.get("name") or nombre).strip()
        self.pais = str(sitio.get("country") or "")
        self.latitud = sitio.get("latitude")
        self.longitud = sitio.get("longitude")
        self._cache = None
        self._cache_ts = 0.0
        self._guardar()
        print(f"[Tiempo] Ciudad: {self.ciudad} ({self.pais}) "
              f"[{self.latitud}, {self.longitud}]")
        return self.ciudad

    def zona(self) -> str:
        """«Barcelona» o «Madrid (España)»: cómo lo dice Parker."""
        if self.pais and self.pais.lower() not in self.ciudad.lower():
            return f"{self.ciudad} ({self.pais})"
        return self.ciudad

    # ---------------------------------------------------------------- órdenes

    def procesar(self, mensaje: str) -> Optional[str]:
        """Contesta si era una pregunta del tiempo o un cambio de sitio."""
        texto = _plano(mensaje)
        if not texto:
            return None

        if re.search(r"\bdonde (?:estoy|estamos|estas|vivo|vivimos|vives)\b", texto):
            return f"Vivo contigo, en {self.zona()}. El tiempo lo miro de ahí."

        cambio = re.search(r"\b(?:estamos|nos hemos mudado|me he mudado|ahora vivo|"
                           r"vivimos|estoy viviendo|estoy|vivo) (?:en|a|a vivir en) "
                           r"([a-z][a-z ]{2,27})", texto)
        if cambio:
            sitio = re.sub(r"\b(?:ahora|ya|ahora mismo|de nuevo|otra vez|los dos|"
                           r"parker|por cierto|esta semana)\b", " ", cambio.group(1))
            sitio = re.sub(r"\s+", " ", sitio).strip()
            if len(sitio) >= 3 and not sitio.startswith(_NO_ES_SITIO):
                resuelto = self.cambiar_ciudad(sitio)
                if resuelto:
                    return f"Vale: desde ahora miro el tiempo de {self.zona()}."
                # No es un sitio real («estoy en el salón»): que siga el cerebro.
                return None

        if not any(re.search(patron, texto) for patron in _PREGUNTAS):
            return None
        return self.respuesta_clima(texto)

    # ------------------------------------------------------------------ datos

    def _datos(self) -> Optional[Dict]:
        if self._cache is not None and time.time() - self._cache_ts < self.cache_seg:
            return self._cache
        if self.latitud is None or self.longitud is None:
            if not self.cambiar_ciudad(self.ciudad):
                return None
        try:
            res = requests.get(METEO_URL, params={
                "latitude": self.latitud, "longitude": self.longitud,
                "current": "temperature_2m,weather_code",
                "daily": ("temperature_2m_max,temperature_2m_min,"
                          "precipitation_probability_max,weather_code"),
                "timezone": "auto", "forecast_days": 2,
            }, timeout=self.timeout)
            res.raise_for_status()
            datos = res.json()
        except Exception as e:
            print(f"[Tiempo] Sin datos: {e}")
            return None
        self._cache = datos
        self._cache_ts = time.time()
        return datos

    def respuesta_clima(self, texto: str) -> str:
        """La frase que dice Parker con las cifras reales."""
        dia = "manana" if re.search(r"\bmanana\b", texto) else "hoy"
        solo_lluvia = (bool(re.search(_LLUVIA, texto))
                       and not re.search(r"\b(?:grados|temperatura|frio|calor)\b", texto))
        datos = self._datos()
        if not datos:
            return "No he podido mirar el tiempo: ahora mismo no tengo internet."
        indice = 1 if dia == "manana" else 0
        cuando = "mañana" if dia == "manana" else "hoy"
        diario = datos.get("daily") or {}
        lluvia = _en(diario.get("precipitation_probability_max"), indice)
        maxima = _en(diario.get("temperature_2m_max"), indice)
        minima = _en(diario.get("temperature_2m_min"), indice)
        cielo = _CIELO.get(int(_en(diario.get("weather_code"), indice) or 0),
                           "con el cielo raro")

        if solo_lluvia:
            if lluvia is None:
                return f"No sé la probabilidad, pero {cuando} estará {cielo}."
            porcentaje = _porcentaje(lluvia)
            if lluvia >= 40:
                return (f"Sí: {cuando} hay un {porcentaje} % de probabilidad de "
                        f"lluvia. Coge paraguas.")
            if lluvia >= 15:
                return (f"Puede caer algo: {porcentaje} % de probabilidad {cuando}, "
                        "pero no es seguro.")
            return f"No se espera lluvia {cuando} ({porcentaje} % de probabilidad)."

        actual = datos.get("current") or {}
        partes = []
        if actual.get("temperature_2m") is not None:
            partes.append(f"ahora hay {_grados(actual['temperature_2m'])} y está "
                          f"{_CIELO.get(int(actual.get('weather_code') or 0), 'con el cielo raro')}")
        frase = f"En {self.ciudad}"
        if partes:
            frase += ", " + " y ".join(partes)
        detalles = []
        if maxima is not None and minima is not None:
            detalles.append(f"máxima {_grados(maxima)} y mínima {_grados(minima)}")
        if lluvia is not None:
            detalles.append(f"lluvia {_porcentaje(lluvia)} por ciento")
        if detalles:
            frase += f". {cuando.capitalize()}: " + ", ".join(detalles)
        return frase + "."


def _en(lista, indice: int):
    """Elemento `indice` de una lista de la API, o `None` si no viene."""
    if not isinstance(lista, (list, tuple)) or len(lista) <= indice:
        return None
    return lista[indice]


def _grados(valor) -> str:
    grados = int(round(float(valor)))
    if grados < 0:
        return f"menos {_numero_a_palabras(abs(grados))} grados"
    return f"{_numero_a_palabras(grados)} grados"


def _porcentaje(valor) -> str:
    return _numero_a_palabras(int(round(float(valor))))
