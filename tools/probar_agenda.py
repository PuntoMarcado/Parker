"""
tools/probar_agenda.py
======================
Prueba de verdad la agenda: reconoce la orden como si se la dijeran por voz,
espera a que venza y hace sonar la campana **midiendo con el micrófono** que el
aviso se oye por el altavoz.

Sirve para lo que no se puede comprobar con tests: que el sonido sale del
altavoz de la placa y no solo del código.

Uso (en la placa, con Parker parado, para que el micrófono esté libre):

    python3 tools/probar_agenda.py            # campana + temporizador de 8 s
    python3 tools/probar_agenda.py --seg 5 --materia "la lavadora"

Devuelve 0 si todo va bien, 1 si la campana no se oye o el temporizador no
dispara a su hora. Imprime en cada paso el nivel medido (RMS del micro).
"""

import argparse
import os
import sys
import time
import wave
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import sounddevice as sd
import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.agenda import AgendaParker          # noqa: E402
from modulos.sonidos import despertador          # noqa: E402
from modulos.voz import VozParker                # noqa: E402

TASA_MIC = 16000


def _microfono(preferencia: str = "usb"):
    """Índice del micro USB (los índices de ALSA cambian al reiniciar)."""
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and preferencia in str(dev["name"]).lower():
                return i
    except Exception as e:
        print(f"[Prueba] No pude listar micrófonos: {e}")
    return None


def _rms(audio: np.ndarray) -> float:
    if audio is None or len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.asarray(audio, dtype=np.float64) ** 2)))


def _voz_de_config() -> VozParker:
    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = (yaml.safe_load(f) or {}).get("voz") or {}
    modelo = cfg.get("modelo_piper", "./assets/voz/es_ES-davefx-medium.onnx")
    modelo = str(BASE / modelo) if not os.path.isabs(modelo) else modelo
    conf = cfg.get("modelo_config") or (modelo + ".json")
    return VozParker(modelo_path=modelo, config_path=str(conf),
                     velocidad=float(cfg.get("velocidad", 0.85)),
                     volumen=float(cfg.get("volumen", 0.55)))


def _medir_campana(voz: VozParker, volumen: float, micro):
    """Suena el despertador grabando: devuelve el factor y la grabación."""
    print(f"[Prueba] Volumen de la campana: {volumen:.2f}")
    # Referencia: 1 s de silencio antes de sonar.
    fondo = sd.rec(int(TASA_MIC * 1.0), samplerate=TASA_MIC, channels=1,
                   device=micro, dtype="float32")
    sd.wait()
    rms_fondo = _rms(fondo)
    print(f"[Prueba] Silencio de fondo: RMS {rms_fondo:.5f}")

    dur = len(despertador(volumen)) / 22050.0
    grabacion = sd.rec(int(TASA_MIC * (dur + 0.6)), samplerate=TASA_MIC,
                       channels=1, device=micro, dtype="float32")
    time.sleep(0.15)
    t0 = time.time()
    voz.reproducir(despertador(volumen), bloquear=True, forzar=True)
    print(f"[Prueba] Campana reproducida en {time.time() - t0:.2f}s de audio real")
    sd.wait()
    rms_campana = _rms(grabacion)
    factor = rms_campana / rms_fondo if rms_fondo > 0 else float("inf")
    print(f"[Prueba] Durante la campana: RMS {rms_campana:.5f} "
          f"({factor:.1f}x el fondo)")
    return factor, grabacion


def _guardar_wav(audio: np.ndarray, ruta: Path) -> None:
    datos = np.clip(np.asarray(audio).reshape(-1), -1.0, 1.0)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TASA_MIC)
        w.writeframes((datos * 32767).astype(np.int16).tobytes())
    print(f"[Prueba] Muestra guardada en {ruta}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba real de la agenda")
    parser.add_argument("--seg", type=int, default=8,
                        help="segundos del temporizador de prueba (defecto 8)")
    parser.add_argument("--materia", default="la lavadora",
                        help="qué se apunta en el temporizador")
    args = parser.parse_args()

    from modulos.version import linea_arranque
    print(linea_arranque())

    micro = _microfono()
    print(f"[Prueba] Micrófono: {micro} "
          f"({sd.query_devices(micro)['name'] if micro is not None else 'por defecto'})")
    voz = _voz_de_config()
    agenda = AgendaParker(ruta_agenda=str(Path("/tmp") / "agenda_prueba.json"))

    # 1. La orden, tal y como la diría el dueño por voz.
    orden = f"Parker, pon un temporizador de {args.seg} segundos {args.materia}"
    respuesta = agenda.procesar(orden, datetime.now())
    print(f"[Prueba] «{orden}» -> {respuesta}")
    if not respuesta or not agenda.avisos:
        print("[Prueba] FALLO: la orden no creó ningún aviso")
        return 1
    aviso = agenda.avisos[-1]
    cuando = datetime.fromtimestamp(aviso["ts"])
    print(f"[Prueba] Aviso: {aviso['tipo']} de {aviso.get('duracion_seg')} s "
          f"para las {cuando.strftime('%H:%M:%S')} «{aviso['texto']}»")

    # 2. La campana se oye de verdad (medido con su propio micrófono).
    try:
        factor, grabacion = _medir_campana(voz, 0.55, micro)
        _guardar_wav(grabacion, Path("/tmp/agenda_prueba_campana.wav"))
    except Exception as e:
        print(f"[Prueba] FALLO al medir la campana: {e}")
        print("[Prueba] ¿Está Parker en marcha ocupando el micrófono?")
        return 1

    # 3. El temporizador dispara a su hora y dice lo suyo.
    print("[Prueba] Esperando a que venza el temporizador...")
    while not agenda.vencidos():
        time.sleep(0.2)
    aviso = agenda.vencidos()[0]
    retraso = time.time() - aviso["ts"]
    frase = agenda.frase_aviso(aviso)
    print(f"[Prueba] Venció con {retraso:+.2f}s de desfase -> {frase}")
    agenda.marcar_avisado(aviso)
    if agenda.vencidos():
        print("[Prueba] FALLO: volvería a sonar (no se marcó como avisado)")
        return 1
    voz.hablar(frase, bloquear=True)
    print("[Prueba] La frase del aviso se ha dicho por el altavoz")

    if factor < 3:
        print(f"[Prueba] FALLO: la campana apenas se distingue del silencio "
              f"({factor:.1f}x)")
        return 1
    if abs(retraso) > 1.5:
        print(f"[Prueba] FALLO: el aviso saltó {retraso:.1f}s tarde")
        return 1
    print("[Prueba] TODO BIEN: la campana se oye y el aviso salta a su hora.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
