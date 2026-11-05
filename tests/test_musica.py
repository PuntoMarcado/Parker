"""
tests/test_musica.py
====================
La música por orden de voz, sin salir a internet.

Se comprueba lo que no puede fallar en el salón:
  1. «pon música» pone ALGO (lista de éxitos) y lo dice con nombre y artista.
  2. «pon algo de Queen» busca por texto; «pon la mesa» NO es música.
  3. Parar, subir/bajar el volumen y «¿qué está sonando?».
  4. El audio se prepara en memoria: se sustituye `requests.get` y `ffmpeg`
     por dobles, y se verifica que sale mono 22050 Hz en float32 y con tope.
  5. Si no hay internet o no hay `ffmpeg`, se dice y no se rompe nada.
  6. Con música sonando, «baja el volumen» es la música («el volumen de tu
     voz» no, y sin música tampoco: esa frase es de `acciones.py`).
  7. El «duck» baja la música sin tocar el volumen que pidió el dueño.
  8. `OyenteMusica`: la canción sola no abre turnos y una persona por encima
     sí, con los niveles reales medidos en la placa (canción 0,0108 con picos
     de 0,037; voz ~0,05).

Ejecutar:
    QT_QPA_PLATFORM=offscreen python tests/test_musica.py
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from modulos import musica as M  # noqa: E402

_PISTAS = [
    {"id": 1, "title": "Bohemian Rhapsody", "duration": 355,
     "artist": {"name": "Queen"}, "preview": "https://cdn.example/bohemian.mp3"},
    {"id": 2, "title": "Don't Stop Me Now", "duration": 209,
     "artist": {"name": "Queen"}, "preview": "https://cdn.example/dont.mp3"},
    {"id": 3, "title": "Sin preview", "duration": 100, "artist": {"name": "X"}},
]


class RespuestaFalsa:
    def __init__(self, datos=None, error=None, content=b""):
        self._datos = datos or {}
        self._error = error
        self.content = content

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._datos


class _Dobles:
    """Sustituye `requests.get` y `subprocess.run` (ffmpeg) por dobles."""

    def __init__(self, pistas=None, error=None, sin_ffmpeg=False,
                 audio_bytes=b"\x10\x00" * 11025):
        self.pistas = _PISTAS if pistas is None else pistas
        self.error = error
        self.sin_ffmpeg = sin_ffmpeg
        self.audio_bytes = audio_bytes
        self.consultas = []
        self._get = M.requests.get
        self._run = M.subprocess.run
        self.ffmpeg_args = None

    def __enter__(self):
        def get(url, params=None, timeout=None):
            if self.error:
                raise self.error
            if url.endswith(".mp3"):        # descarga del adelanto
                return RespuestaFalsa(content=self.audio_bytes)
            if url == M.EXITOS_URL:
                self.consultas.append("")
                return RespuestaFalsa({"data": self.pistas})
            self.consultas.append((params or {}).get("q", ""))
            return RespuestaFalsa({"data": self.pistas})

        def run(args, **k):
            if self.sin_ffmpeg:
                raise FileNotFoundError("ffmpeg")
            self.ffmpeg_args = args
            return subprocess.CompletedProcess(args, 0, self.audio_bytes, b"")

        M.requests.get = get
        M.subprocess.run = run
        return self

    def __exit__(self, *exc):
        M.requests.get = self._get
        M.subprocess.run = self._run
        return False


def test_pon_musica_sin_nombre():
    musica = M.MusicaParker()
    with _Dobles():
        frase, orden, cancion = musica.procesar("pon música")
    assert orden == "poner" and cancion, (orden, cancion)
    assert cancion["titulo"] == "Bohemian Rhapsody", cancion
    assert "Queen" in frase and "Bohemian" in frase, frase
    print("[OK] «pon música» pone algo de verdad (lista de éxitos)")


def test_pone_por_nombre_y_no_confunde_la_charla():
    musica = M.MusicaParker()
    dobles = _Dobles()
    with dobles:
        frase, orden, cancion = musica.procesar("Parker, pon algo de Queen")
    assert orden == "poner" and cancion["artista"] == "Queen", cancion
    assert "queen" in dobles.consultas[-1], dobles.consultas

    musica = M.MusicaParker()
    with _Dobles():
        # «pon la mesa» o «pon el despertador» NO son música (y no deben gastar
        # una búsqueda): vuelven None para que los resuelva quien corresponda.
        for frase in ("pon la mesa", "pon el despertador a las 7",
                      "pon una alarma en 5 minutos", "recuérdame comprar pan",
                      "hoy hace un día precioso"):
            assert musica.procesar(frase) is None, frase
    print("[OK] busca por artista y no confunde «pon la mesa» con música")


def test_parar_volumen_y_preguntar():
    musica = M.MusicaParker(volumen=0.5)
    with _Dobles():
        musica.procesar("pon música")
    assert musica.ultima, "debería recordar lo que suena"

    frase, orden, _ = musica.procesar("Parker, para la música")
    assert orden == "parar", (frase, orden)

    inicio = musica.porcentaje()
    _, orden, _ = musica.procesar("sube la música")
    assert orden == "subir" and musica.porcentaje() > inicio
    _, orden, _ = musica.procesar("baja la música")
    assert orden == "bajar" and musica.porcentaje() == inicio

    _, orden, _ = musica.procesar("¿qué está sonando?")
    assert orden == "preguntar", orden
    assert "Bohemian" in musica.que_suena(), musica.que_suena()
    print("[OK] parar, subir/bajar el volumen y «¿qué está sonando?»")


def test_pregunta_generica_no_es_musica():
    """«¿De qué estás hablando?» no es «¿qué está sonando?».

    El 01/11 este cruce hacía que Parker contestara «la música está
    desactivada» a cualquier pregunta; el dueño lo oyó y no tenía sentido.
    """
    musica = M.MusicaParker()
    for frase in ("¿De qué estás hablando, Parker?", "¿Qué tal tu día?",
                  "Parker, ¿qué hora es?", "¿Qué has hecho hoy?"):
        assert musica.procesar(frase) is None, frase
    for frase in ("¿Qué está sonando?", "¿Qué canción es esta?",
                  "¿Qué es lo que suena?", "¿Quién canta?"):
        resultado = musica.procesar(frase)
        assert resultado and resultado[1] == "preguntar", (frase, resultado)
    print("[OK] una pregunta normal no se confunde con una orden de música")


def test_audio_en_memoria_mono_22050():
    musica = M.MusicaParker(max_segundos=0.5, sample_rate=22050)
    dobles = _Dobles()
    with dobles:
        cancion = musica.buscar("queen")
        audio, sr = musica.preparar(cancion)
    assert sr == 22050, sr
    # 22050 muestras/s * 2 bytes * 0,5 s = 22050 bytes de PCM16 = 11025 muestras
    assert audio.dtype == np.float32, audio.dtype
    assert audio.shape[0] == 11025, audio.shape
    assert dobles.ffmpeg_args[:3] == ["ffmpeg", "-v", "error"], dobles.ffmpeg_args
    assert "-ar" in dobles.ffmpeg_args and "22050" in dobles.ffmpeg_args
    assert "pipe:1" in dobles.ffmpeg_args, dobles.ffmpeg_args

    pico = float(np.max(np.abs(audio)))
    ganado = musica.ganancia(audio)
    assert abs(float(np.max(np.abs(ganado))) - pico * 0.7) < 1e-6, \
        (pico, float(np.max(np.abs(ganado))))
    musica.silenciar()
    assert float(np.max(np.abs(musica.ganancia(audio)))) == 0.0
    print("[OK] el adelanto se decodifica en memoria a mono 22 kHz (sin ficheros)")


def test_volumen_con_la_musica_sonando():
    musica = M.MusicaParker(volumen=0.7)
    # Con música puesta, «baja el volumen» a secas es la música: es lo que se
    # está oyendo (27/10).
    frase, orden, _ = musica.procesar("Parker, baja el volumen", sonando=True)
    assert orden == "bajar", (frase, orden)
    assert musica.porcentaje() == 55, musica.porcentaje()
    # Sin música puesta, esa frase es de la voz (la resuelve acciones.py).
    assert M.MusicaParker().procesar("baja el volumen") is None
    # Y «de tu voz» tampoco es la música.
    assert M.MusicaParker().procesar("baja el volumen de tu voz", sonando=True) is None
    # Con música sonando, lo de siempre sigue funcionando.
    musica = M.MusicaParker(volumen=0.5)
    _, orden, _ = musica.procesar("sube la música", sonando=True)
    assert orden == "subir" and musica.porcentaje() == 65, (orden, musica.porcentaje())
    print("[OK] con música sonando, «baja el volumen» es la música")


def test_duck_baja_la_musica_sin_tocar_el_volumen_pedido():
    musica = M.MusicaParker(volumen=0.8, duck_factor=0.2)
    audio = np.ones(64, dtype=np.float32)
    assert abs(float(musica.ganancia(audio)[0]) - 0.8) < 1e-6
    assert abs(musica.ganancia_objetivo() - 0.8) < 1e-6
    musica.duck = True
    assert abs(musica.ganancia_objetivo() - 0.16) < 1e-6
    assert abs(float(musica.ganancia(audio)[0]) - 0.16) < 1e-6
    # La rampa del hilo de música pasa la suya y no toca nada más.
    assert abs(float(musica.ganancia(audio, ganancia=0.4)[0]) - 0.4) < 1e-6
    musica.duck = False
    assert musica.porcentaje() == 80, musica.porcentaje()
    print("[OK] el «duck» baja la música sin cambiar el volumen pedido")


def _simular_cancion(oyente, musica, voz=None, chunks=1200, turno_seg=2.5):
    """Reproduce el bucle real: si el oyente dispara, se baja la música.

    Cuando confirma voz, el turno lo atiende Parker (y mientras tanto no se le
    sigue preguntando al oyente): por eso el turno salta `turno_seg` bloques.
    """
    ganancia, objetivo, voces = 1.0, 1.0, 0
    bloque = 0.064
    turno_hasta = -1
    for i in range(chunks):
        v = voz(i) if voz else 0.0
        if i >= turno_hasta:
            aviso = oyente.observar(float(np.hypot(musica(i) * ganancia, v)))
            if aviso == "probar":
                objetivo = 0.15
            elif aviso == "musica":
                objetivo = 1.0
            elif aviso == "voz":
                voces += 1
                objetivo = 1.0
                turno_hasta = i + int(turno_seg / bloque)
        ganancia += (objetivo - ganancia) * 0.2
    return voces


def test_oyente_distingue_voz_de_cancion():
    """Niveles reales de la placa (medidos el 27/10): la canción deja 0,0108 de
    mediana con picos de 0,037, y una voz normal ronda 0,05."""
    ruido = 0.005

    def cancion(i):
        fuerte = 0.037 if (i // 25) % 8 == 0 else 0.0108 * (1 + 0.3 * ((i // 10) % 3))
        return ruido + fuerte

    # La canción sola no abre ningún turno: lo que sube cae con el «duck».
    assert _simular_cancion(M.OyenteMusica(chunk_seg=0.064), cancion) == 0

    # Una voz por encima (0,05 de RMS, ~3,5× el nivel de la canción), sí:
    # turno en cada frase (10 de 10).
    voz = lambda i: 0.05 if (i // 60) % 2 == 0 else 0.0  # noqa: E731
    voces = _simular_cancion(M.OyenteMusica(chunk_seg=0.064), cancion, voz)
    assert voces >= 10, voces
    print(f"[OK] el oyente distingue la canción (0 turnos) de una persona ({voces} turnos)")


def test_sin_internet_y_sin_ffmpeg():
    musica = M.MusicaParker()
    with _Dobles(error=RuntimeError("sin internet")):
        frase, orden, cancion = musica.procesar("pon música")
    assert orden == "poner" and cancion is None, (frase, cancion)
    assert "no he podido" in frase.lower(), frase

    with _Dobles(error=RuntimeError("sin internet")):
        assert musica.buscar("queen") is None
        assert musica.pistas_de("queen") == []

    musica = M.MusicaParker()
    with _Dobles(sin_ffmpeg=True):
        cancion = musica.buscar("queen")
        assert musica.preparar(cancion) is None
    print("[OK] sin internet (y sin ffmpeg) lo dice claro y no se rompe nada")


if __name__ == "__main__":
    test_pon_musica_sin_nombre()
    test_pone_por_nombre_y_no_confunde_la_charla()
    test_parar_volumen_y_preguntar()
    test_pregunta_generica_no_es_musica()
    test_audio_en_memoria_mono_22050()
    test_volumen_con_la_musica_sonando()
    test_duck_baja_la_musica_sin_tocar_el_volumen_pedido()
    test_oyente_distingue_voz_de_cancion()
    test_sin_internet_y_sin_ffmpeg()
    print("\nMúsica: 9/9 en verde.")
