"""
Pruebas del tiempo (Open-Meteo) con la red simulada: no se llama a internet.

Se comprueba la frase que dice Parker (cifras reales, en palabras), la pregunta
de lluvia, el cambio de ciudad por voz y que una caída de red se cuenta en vez de
inventarse el tiempo.
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import modulos.tiempo as modulo              # noqa: E402
from modulos.tiempo import TiempoParker      # noqa: E402

AHORA = datetime(2026, 10, 26, 16, 0)

METEO = {
    "current": {"temperature_2m": 18.4, "weather_code": 1},
    "daily": {
        "temperature_2m_max": [22.1, 21.0],
        "temperature_2m_min": [14.2, 13.0],
        "precipitation_probability_max": [10, 70],
        "weather_code": [1, 61],
    },
}
def _geo(sitio: str) -> dict:
    """El geocodificador devuelve el sitio que se le pide (como el real)."""
    return {"results": [{"name": str(sitio).title(), "country": "España",
                        "latitude": 40.4168, "longitude": -3.7038}]}


class RespuestaFalsa:
    def __init__(self, datos):
        self._datos = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self._datos


def _con_red(tiempo: TiempoParker, fallo: bool = False):
    """Sustituye requests.get del módulo: geocodificador y tiempo."""
    llamadas = {"total": 0, "urls": []}

    def get_falso(url, params=None, timeout=None):
        llamadas["total"] += 1
        llamadas["urls"].append(url)
        if fallo:
            raise ConnectionError("sin internet")
        if "geocoding" in url:
            return RespuestaFalsa(_geo((params or {}).get("name", "Barcelona")))
        return RespuestaFalsa(METEO)

    original = modulo.requests.get
    modulo.requests.get = get_falso
    return llamadas, original


def test_tiempo_de_hoy():
    tiempo = TiempoParker(ciudad="Barcelona")
    llamadas, original = _con_red(tiempo)
    try:
        respuesta = tiempo.procesar("¿qué tiempo hace hoy?")
    finally:
        modulo.requests.get = original
    assert respuesta == ("En Barcelona, ahora hay dieciocho grados y está casi "
                         "despejado. Hoy: máxima veintidos grados y mínima "
                         "catorce grados, lluvia diez por ciento."), respuesta
    # Una llamada al tiempo (más, la primera vez, la del geocodificador).
    assert sum(1 for u in llamadas["urls"] if "forecast" in u) == 1, llamadas
    print("[OK] el tiempo de hoy se dice con las cifras reales, en palabras")


def test_lluvia_y_manana():
    tiempo = TiempoParker(ciudad="Barcelona")
    llamadas, original = _con_red(tiempo)
    try:
        respuesta = tiempo.procesar("¿va a llover mañana?")
        # La segunda consulta tira de la caché: no vuelve a llamar a la red.
        otra = tiempo.procesar("¿qué tiempo hará mañana?")
    finally:
        modulo.requests.get = original
    assert respuesta == ("Sí: mañana hay un setenta % de probabilidad de lluvia. "
                         "Coge paraguas."), respuesta
    assert "En Barcelona" in otra and "nublado" not in otra, otra
    # La segunda consulta sale de la caché: no vuelve a llamar al tiempo.
    assert sum(1 for u in llamadas["urls"] if "forecast" in u) == 1, llamadas
    print("[OK] «¿va a llover mañana?» se contesta con la probabilidad y con caché")


def test_cambio_de_ciudad_por_voz():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "parker.tiempo.json")
        tiempo = TiempoParker(ciudad="Barcelona", ruta_ciudad=ruta)
        llamadas, original = _con_red(tiempo)
        try:
            respuesta = tiempo.procesar("Parker, ahora estamos en Madrid")
        finally:
            modulo.requests.get = original
        assert respuesta == "Vale: desde ahora miro el tiempo de Madrid (España).", \
            respuesta
        assert Path(ruta).exists()

        # El dato queda guardado: un reinicio sigue en Madrid.
        otro = TiempoParker(ciudad="Barcelona", ruta_ciudad=ruta)
        assert otro.ciudad == "Madrid" and otro.latitud is not None

        # Y a partir de ahí el tiempo se dice de Madrid.
        llamadas, original = _con_red(otro)
        try:
            dicho = otro.procesar("¿qué tiempo hace?")
        finally:
            modulo.requests.get = original
        assert dicho.startswith("En Madrid,"), dicho

    # «¿dónde estás?» contesta la ciudad, no la cambia.
    tiempo2 = TiempoParker(ciudad="Barcelona")
    assert tiempo2.procesar("¿dónde estás?").startswith("Vivo contigo, en Barcelona")
    print("[OK] la ciudad es una variable: «estamos en Madrid» la cambia y la guarda")


def test_sin_internet_se_dice():
    tiempo = TiempoParker(ciudad="Barcelona")
    _, original = _con_red(tiempo, fallo=True)
    try:
        respuesta = tiempo.procesar("¿qué tiempo hace?")
    finally:
        modulo.requests.get = original
    assert respuesta == ("No he podido mirar el tiempo: ahora mismo no tengo "
                         "internet."), respuesta
    print("[OK] sin internet lo dice claro en vez de inventarse el tiempo")


def test_la_charla_no_es_una_consulta():
    tiempo = TiempoParker(ciudad="Barcelona")
    for frase in ("hoy hace frío", "me gusta la lluvia", "ayer llovió un montón",
                  "estoy en el salón", "¿qué hora es?", "qué tal estás"):
        assert tiempo.procesar(frase) is None, frase
    print("[OK] «hoy hace frío» o «estoy en el salón» siguen siendo charla")


if __name__ == "__main__":
    test_tiempo_de_hoy()
    test_lluvia_y_manana()
    test_cambio_de_ciudad_por_voz()
    test_sin_internet_se_dice()
    test_la_charla_no_es_una_consulta()
    print("\nTiempo: 5/5 en verde.")
