"""
tools/probar_musica_escucha.py
==============================
Prueba de verdad, EN LA PLACA, de la escucha «por encima de la música» (v6.5.0).

Qué mide, con el altavoz y el micrófono de la placa (sin tocar a Parker):

1. **Cuánto se oye la canción en su propio micrófono** (el «piso») y cuánto baja
   cuando se aplica el «duck». Esa diferencia es lo que hace posible oír una voz
   por encima: si el micrófono apenas oye el altavoz, sobra margen.
2. **Si el discriminador se confunde con la canción sola** (`OyenteMusica`): sin
   nadie hablando debe decidir SIEMPRE «era la canción» (0 turnos abiertos).
3. **Si te oye a ti** (`--hablar N`): durante esos segundos imprime «¡VOZ!» para
   que hables encima de la música y cuenta los turnos que abriría Parker.

Uso (con Parker PARADO, para que el micrófono esté libre):

    python3 tools/probar_musica_escucha.py                    # 25 s, sin hablar
    python3 tools/probar_musica_escucha.py --seg 40 --hablar 10
    python3 tools/probar_musica_escucha.py --volumen 0.7 --duck 0.15

Devuelve 0 si la canción sola no abre ningún turno y (cuando se pide hablar) se
abre alguno mientras se habla. 1 si hay falsos positivos o no te oye.
"""

import argparse
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.musica import MusicaParker, OyenteMusica  # noqa: E402
from modulos.version import linea_arranque            # noqa: E402

TASA_MIC = 16000
CHUNK = 1024


class FiltroPasoAlto:
    """Copia del de `parker.FiltroPasoAlto` (para no cargar PySide6 aquí).

    Quita el DC y el ronquido por debajo de ~120 Hz del RMS: es el mismo número
    que mide Parker, y así lo medido en esta prueba es comparable.
    """

    def __init__(self, hz: float = 120.0, sample_rate: int = TASA_MIC):
        self.a = 1.0 / (1.0 + 2.0 * np.pi * hz / sample_rate) if hz > 0 else None
        self._x = 0.0
        self._y = 0.0

    def procesar(self, audio: np.ndarray) -> np.ndarray:
        if self.a is None:
            return audio
        salida = np.empty_like(audio)
        for i, x in enumerate(audio):
            self._y = self.a * (self._y + x - self._x)
            self._x = x
            salida[i] = self._y
        return salida


class CancionSonando:
    """La canción por el altavoz, con la ganancia que le pide el oyente."""

    def __init__(self, musica: MusicaParker, audio: np.ndarray, sr: int):
        self.musica = musica
        self.audio = audio
        self.sr = sr
        self.ganancia = musica.ganancia_objetivo()
        self.parar = threading.Event()
        self.lista = threading.Event()
        self.hilo = threading.Thread(target=self._sonar, daemon=True)

    def arrancar(self) -> None:
        self.hilo.start()
        self.lista.wait(timeout=3)

    def _sonar(self):
        bloque = max(256, int(self.sr * 0.25))
        try:
            with sd.OutputStream(samplerate=self.sr, channels=1,
                                 dtype="float32") as flujo:
                self.lista.set()
                for inicio in range(0, len(self.audio), bloque):
                    if self.parar.is_set():
                        break
                    self.ganancia += (self.musica.ganancia_objetivo()
                                      - self.ganancia) * 0.6
                    trozo = self.musica.ganancia(
                        self.audio[inicio:inicio + bloque], ganancia=self.ganancia)
                    if trozo.shape[0] < bloque:
                        trozo = np.pad(trozo, (0, bloque - trozo.shape[0]))
                    flujo.write(trozo.reshape(-1, 1))
        except Exception as e:
            print(f"[Prueba] Error de audio al sonar: {e}")
        finally:
            self.lista.set()


def _microfono(preferencia: str = "usb"):
    """Índice del micro por nombre (los índices de ALSA cambian al reiniciar)."""
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and preferencia in str(dev["name"]).lower():
                return i
    except Exception as e:
        print(f"[Prueba] No pude listar micrófonos: {e}")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Escucha por encima de la música")
    parser.add_argument("--seg", type=float, default=25, help="segundos de canción")
    parser.add_argument("--hablar", type=float, default=0,
                        help="segundos (al final) en los que hablas encima")
    parser.add_argument("--volumen", type=float, default=0.7,
                        help="volumen de la música (el de config.yaml)")
    parser.add_argument("--duck", type=float, default=0.15,
                        help="cuánto se baja la música al comprobar (duck_factor)")
    parser.add_argument("--consulta", default="queen",
                        help="qué buscar para la prueba")
    args = parser.parse_args()

    print(linea_arranque())
    musica = MusicaParker(volumen=args.volumen, duck_factor=args.duck,
                          max_segundos=args.seg + 5)
    cancion = musica.buscar(args.consulta)
    if not cancion:
        print("[Prueba] FALLO: no pude buscar la canción (¿hay internet?)")
        return 1
    datos = musica.preparar(cancion)
    if not datos:
        print("[Prueba] FALLO: no pude preparar el audio (¿hay ffmpeg?)")
        return 1
    audio, sr = datos
    print(f"[Prueba] «{cancion['titulo']}» de {cancion['artista']}: "
          f"{len(audio) / sr:.1f}s a {sr} Hz, volumen {args.volumen:.2f}")

    micro = _microfono()
    print(f"[Prueba] Micrófono: {micro} "
          f"({sd.query_devices(micro)['name'] if micro is not None else 'por defecto'})")

    sonando = CancionSonando(musica, audio, sr)
    oyente = OyenteMusica(chunk_seg=CHUNK / TASA_MIC)
    hp = FiltroPasoAlto()
    avisos = {"probar": 0, "musica": 0, "voz": 0}
    niveles = {"cancion": [], "duck": [], "voz": []}
    turno_hasta = 0.0
    t0 = time.time()
    sonando.arrancar()
    print(f"[Prueba] Suena {args.seg:.0f}s. Escuchando con el micrófono…"
          + (f" (a partir de los {args.seg - args.hablar:.0f}s, HABLA encima)"
             if args.hablar else ""))

    try:
        with sd.InputStream(samplerate=TASA_MIC, channels=1, dtype="float32",
                            device=micro) as flujo:
            while time.time() - t0 < args.seg:
                crudo, _ = flujo.read(CHUNK)
                datos_mic = hp.procesar(crudo.ravel().astype(np.float32))
                rms = float(np.sqrt(np.mean(datos_mic ** 2)))
                clave = "duck" if musica.duck else "cancion"
                niveles[clave].append(rms)

                aviso = oyente.observar(rms)
                if aviso == "probar" and time.time() >= turno_hasta:
                    avisos["probar"] += 1
                    musica.duck = True
                    print(f"[Prueba] Algo sobresale de la canción "
                          f"(RMS {rms:.4f}): bajo la música para comprobar…")
                elif aviso == "musica":
                    avisos["musica"] += 1
                    musica.duck = False
                elif aviso == "voz":
                    avisos["voz"] += 1
                    niveles["voz"].append(rms)
                    turno_hasta = time.time() + 2.5   # turno en curso
                    print(f"[Prueba] ¡VOZ! (RMS {rms:.4f}) -> Parker abriría "
                          f"turno (nº {avisos['voz']})")
    except Exception as e:
        print(f"[Prueba] FALLO con el micrófono: {e}")
        print("[Prueba] ¿Está Parker en marcha ocupando el micro?")
        return 1
    finally:
        sonando.parar.set()
        sonando.hilo.join(timeout=5)

    def _mediana(valores):
        return float(np.median(valores)) if valores else 0.0

    cancion_rms = _mediana(niveles["cancion"])
    duck_rms = _mediana(niveles["duck"])
    print(f"\n[Prueba] Canción en el micrófono: RMS {cancion_rms:.5f} "
          f"({len(niveles['cancion'])} bloques)")
    print(f"[Prueba] Con la música bajada:   RMS {duck_rms:.5f} "
          f"({len(niveles['duck'])} bloques)")
    if duck_rms > 0:
        print(f"[Prueba] El «duck» deja la canción x{cancion_rms / duck_rms:.1f} "
              f"más baja en el micrófono")
    print(f"[Prueba] Decisiones: {avisos['probar']} comprobaciones, "
          f"{avisos['musica']} «era la canción», {avisos['voz']} «eres tú»")

    fallo = False
    if not args.hablar and avisos["voz"] > 0:
        print("[Prueba] FALLO: la canción sola abrió turnos (falsos positivos). "
              "Sube musica.factor_disparo en config.yaml.")
        fallo = True
    if args.hablar and avisos["voz"] == 0:
        print("[Prueba] FALLO: no te oyó con la música sonando. Habla más alto "
              "o baja musica.factor_disparo en config.yaml.")
        fallo = True
    if cancion_rms < 0.002:
        print("[Prueba] AVISO: el micrófono apenas oye la canción "
              f"({cancion_rms:.5f}): con este margen el discriminador no tiene "
              "de qué distinguir. ¿Micrófono lejos del altavoz?")
    if not fallo:
        print("[Prueba] TODO BIEN: la canción no abre turnos y la voz sí.")
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
