"""
tools/probar_dia.py
===================
Prueba EN LA PLACA lo que no se puede probar en el PC: red de verdad (Open-Meteo
y Deezer), decodificación con `ffmpeg`, sonido por el altavoz y permiso de
apagado. No usa micrófono ni voz sintetizada para decidir: encadena los módulos
reales y va imprimiendo el resultado.

Uso (en la placa, con Parker parado):

    ~/env/bin/python3 ~/parker/tools/probar_dia.py
    PARKER_APAGADO_SECO=1 ~/env/bin/python3 ~/parker/tools/probar_dia.py --apagado

Devuelve 0 si todo va bien y 1 si algo falla. Nunca apaga la placa de verdad:
el paso del apagado comprueba el permiso con `pkcheck` y, si se pide
`--apagado`, lanza el comando en seco.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

TMP = Path(tempfile.gettempdir())

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.apuntes import ApuntesParker          # noqa: E402
from modulos.agenda import AgendaParker            # noqa: E402
from modulos.musica import MusicaParker            # noqa: E402
from modulos.rutinas import ORDEN_APAGAR, RutinasParker  # noqa: E402
from modulos.tiempo import TiempoParker            # noqa: E402
from modulos.version import linea_arranque         # noqa: E402


def _probar_rutinas() -> bool:
    rutinas = RutinasParker(hora_parte="08:30")
    ok = True
    for frase, esperado in (("Parker, buenas noches", "dormir"),
                            ("Parker, cállate diez minutos", None),
                            ("Parker, cállate diez minutos", None),
                            ("Parker, apágate", ORDEN_APAGAR)):
        respuesta, accion = rutinas.procesar(frase, datetime.now()) or (None, None)
        print(f"[Prueba] «{frase}» -> {respuesta!r} ({accion})")
        if esperado and accion != esperado:
            print(f"[Prueba] FALLO: esperaba la acción {esperado}")
            ok = False
    if not rutinas.dormido:
        print("[Prueba] FALLO: «buenas noches» no lo durmió")
        ok = False
    if not rutinas.debe_callarse():
        print("[Prueba] FALLO: el «cállate» no puso el silencio temporal")
        ok = False
    # El parte del día. Los avisos se ponen con la API del módulo y para HOY
    # (no por voz: la voz ya se prueba arriba y con «mañana» caería fuera del
    # día que toca, que es justo lo que el parte no debe leer).
    from modulos.agenda import ALARMA, CITA
    agenda = AgendaParker(ruta_agenda=str(TMP / "dia_agenda.json"))
    hoy = datetime.now().date()
    respuesta = agenda.procesar("apunta que mañana a las 9 tengo cita con el dentista",
                                datetime.now())
    print(f"[Prueba] «apunta que mañana a las 9 tengo cita con el dentista» -> {respuesta}")
    agenda._anadir(CITA, datetime.combine(hoy, datetime.now().time().replace(
        hour=23, minute=55, second=0, microsecond=0)), "cita dentista")
    agenda._anadir(ALARMA, datetime.combine(hoy, datetime.now().time().replace(
        hour=23, minute=56, second=0, microsecond=0)), "") 
    rutinas.despertar()
    parte = rutinas.parte_del_dia(agenda, nombre="Alan")
    print(f"[Prueba] Parte del día -> {parte}")
    if not parte or "dentista" not in parte or not parte.startswith("Buenos días"):
        print("[Prueba] FALLO: el parte del día no incluye la cita de hoy")
        ok = False
    return ok


def _probar_apuntes() -> bool:
    ruta = TMP / "dia_apuntes.json"
    if ruta.exists():
        ruta.unlink()
    apuntes = ApuntesParker(ruta_apuntes=str(ruta))
    ok = True
    secuencia = ["Parker, apunta un litro de agua",
                 "Parker, apunta medio litro de agua",
                 "Parker, apunta que compre leche",
                 "Parker, ¿cuánta agua llevo hoy?",
                 "Parker, ¿qué tengo apuntado?",
                 "Parker, borra la nota de la leche"]
    for frase in secuencia:
        respuesta = apuntes.procesar(frase, datetime.now())
        print(f"[Prueba] «{frase}» -> {respuesta}")
        if not respuesta:
            print("[Prueba] FALLO: no reconoció la orden de apuntes")
            ok = False
    agua = apuntes.contadores.get("agua") or {}
    total = (agua.get("dias") or {}).get(datetime.now().date().isoformat())
    print(f"[Prueba] Contador de agua de hoy: {total}")
    if abs(float(total or 0) - 1.5) > 1e-6:
        print("[Prueba] FALLO: el contador no sumó 1,5 litros")
        ok = False
    if apuntes.notas:
        print("[Prueba] FALLO: la nota borrada sigue ahí")
        ok = False
    return ok


def _probar_tiempo(ciudad: str) -> bool:
    tiempo = TiempoParker(ciudad=ciudad, ruta_ciudad=str(TMP / "dia_tiempo.json"))
    respuesta = tiempo.respuesta_clima("¿qué tiempo hace hoy?")
    print(f"[Prueba] Tiempo en {tiempo.zona()} -> {respuesta}")
    if "no tengo internet" in respuesta.lower():
        print("[Prueba] FALLO: sin internet no hay prueba del tiempo")
        return False
    cambio = tiempo.procesar("Parker, estamos en Madrid")
    print(f"[Prueba] Cambio de sitio -> {cambio}")
    if not cambio or "Madrid" not in cambio:
        print("[Prueba] FALLO: no cambió la ciudad por voz")
        return False
    tiempo.procesar("Parker, estamos en Barcelona")
    return True


def _probar_musica(tocar: bool) -> bool:
    musica = MusicaParker()
    frase, orden, cancion = musica.procesar("Parker, pon algo de Queen") or (None, None, None)
    print(f"[Prueba] «pon algo de Queen» -> {frase!r} ({orden})")
    if not cancion:
        print("[Prueba] FALLO: Deezer no devolvió nada (¿internet?)")
        return False
    print(f"[Prueba] Elegido: {cancion['titulo']} — {cancion['artista']}")
    datos = musica.preparar(cancion)
    if not datos:
        print("[Prueba] FALLO: no pude descargar/decodificar el adelanto")
        return False
    audio, sr = datos
    print(f"[Prueba] Audio listo: {len(audio)} muestras a {sr} Hz "
          f"({len(audio) / sr:.1f}s)")
    if len(audio) < sr:      # menos de un segundo = algo va mal
        print("[Prueba] FALLO: el audio decodificado es demasiado corto")
        return False
    if not tocar:
        print("[Prueba] (--sonar no pedido: no lo reproduzco por el altavoz)")
        return True
    return _sonar_y_medir(musica, audio, sr)


def _sonar_y_medir(musica, audio, sr, segundos: float = 8.0,
                   micro: str = "usb") -> bool:
    """Suena 8 s por el altavoz con el MISMO bucle que usa Parker y lo mide.

    Se graba con el micrófono a la vez: si el RMS durante la música no es muy
    superior al del silencio de fondo, es que no está saliendo por el altavoz.
    """
    import numpy as np
    import sounddevice as sd

    def microfono():
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0 and micro in str(dev["name"]).lower():
                    return i
        except Exception as e:
            print(f"[Prueba] No pude listar micrófonos: {e}")
        return None

    indice = microfono()
    print(f"[Prueba] Micrófono para medir: {indice}")
    fondo = sd.rec(int(16000 * 1.0), samplerate=16000, channels=1,
                   device=indice, dtype="float32")
    sd.wait()
    rms_fondo = float(np.sqrt(np.mean(np.asarray(fondo) ** 2)))
    print(f"[Prueba] Silencio de fondo: RMS {rms_fondo:.5f}")

    trozo = musica.ganancia(audio)[:int(sr * segundos)]
    grabacion = sd.rec(int(16000 * (len(trozo) / sr + 0.5)), samplerate=16000,
                       channels=1, device=indice, dtype="float32")
    time.sleep(0.15)
    print(f"[Prueba] Reproduciendo {len(trozo) / sr:.1f} s por el altavoz "
          "(mismo bucle que Parker: bloques de 0,25 s)...")
    bloque = max(256, int(sr * 0.25))
    with sd.OutputStream(samplerate=sr, channels=1, dtype="float32") as flujo:
        for inicio in range(0, len(trozo), bloque):
            parte = trozo[inicio:inicio + bloque]
            if parte.shape[0] < bloque:
                parte = np.pad(parte, (0, bloque - parte.shape[0]))
            flujo.write(parte.reshape(-1, 1))
    sd.wait()
    rms_musica = float(np.sqrt(np.mean(np.asarray(grabacion) ** 2)))
    factor = rms_musica / rms_fondo if rms_fondo > 0 else float("inf")
    print(f"[Prueba] Durante la música: RMS {rms_musica:.5f} "
          f"({factor:.1f}x el fondo)")
    if factor < 3:
        print("[Prueba] FALLO: la música no se oye (¿altavoz o volumen?)")
        return False
    print("[Prueba] La música suena de verdad por el altavoz.")
    return True


def _probar_apagado() -> bool:
    """Comprueba el permiso de apagado SIN apagar la placa."""
    try:
        permiso = subprocess.run(
            ["pkcheck", "--action-id", "org.freedesktop.login1.power-off",
             "--process", str(os.getppid())],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        print(f"[Prueba] pkcheck power-off -> exit={permiso.returncode} "
              f"{(permiso.stderr or b'').decode('utf-8', 'replace').strip()}")
        autorizado = permiso.returncode == 0
    except Exception as e:
        print(f"[Prueba] Sin pkcheck: {e}")
        autorizado = False
    seco = str(os.environ.get("PARKER_APAGADO_SECO", "")).lower() in ("1", "true", "si", "sí")
    for orden in (["systemctl", "poweroff"], ["loginctl", "poweroff"]):
        cual = subprocess.run(["which", orden[0]], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
        print(f"[Prueba] {orden[0]}: {'disponible' if cual else 'NO está'}")
    if seco:
        print("[Prueba] MODO SECO: haría «systemctl poweroff» (no lo hago)")
    if not autorizado and not seco:
        print("[Prueba] AVISO: polkit no autoriza el apagado para este proceso. "
              "Parker lo diría por voz y seguiría vivo (ver docs/dia.md §2).")
    return autorizado or seco


def _decir(frase: str) -> int:
    """Dice una frase por el altavoz con la voz de Parker (prueba de oído).

    Para comprobar de punta a punta con Parker EN MARCHA: se sintetiza la frase
    con Piper y se suelta por el altavoz, así que el micrófono la oye como si la
    dijera el dueño. Después se mira `~/parker.log` para ver qué hizo.
    """
    import sounddevice as sd
    from modulos.voz import VozParker
    import yaml

    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = (yaml.safe_load(f) or {}).get("voz") or {}
    modelo = cfg.get("modelo_piper", "./assets/voz/es_ES-davefx-medium.onnx")
    modelo = str(BASE / modelo) if not os.path.isabs(modelo) else modelo
    config = cfg.get("modelo_config") or (modelo + ".json")
    voz = VozParker(modelo_path=modelo, config_path=str(config),
                    velocidad=float(cfg.get("velocidad", 0.85)),
                    volumen=float(cfg.get("volumen", 0.55)))
    voz.silenciado = False
    print(f"[Prueba] Digo por el altavoz: «{frase}»")
    # A tope: el micrófono de la placa tiene que oírla para que el turno sea
    # realista (a volumen bajo el STT se inventa la frase, medido el 26/10).
    audio = voz.sintetizar(frase, volumen=1.0)
    if audio is None or len(audio) == 0:
        print("[Prueba] FALLO: no pude sintetizar la frase")
        return 1
    sd.play(audio, voz.sample_rate)
    sd.wait()
    print("[Prueba] Frase dicha. Mira el log de Parker para ver qué hizo:")
    print("          tail -n 40 ~/parker.log")
    return 0


def _probar_apagar_de_verdad() -> bool:
    """Ejecuta `Parker._apagar()` en la placa, en modo seco.

    Sin voz ni cara (eso ya lo prueba la propia placa al decírselo), pero con
    el MISMO método que corre en producción: despedida (aquí sin audio),
    animación (no hay ventana), `_orden_apagado()` y el subproceso. En seco,
    así que solo lo apunta. Es la forma de comprobar en la placa que el
    apagado llega hasta el final sin apagarla.
    """
    import queue
    import threading
    import parker as P

    p = P.Parker.__new__(P.Parker)
    p.config = {"rutinas": {"apagado_seco": True, "despedida_seg": 0.5}}
    p.corriendo = True
    p.ocupado = False
    p.musica_sonando = False
    p._cola_voz = queue.Queue()
    p._cola_audio = queue.Queue()
    p._parar_musica = threading.Event()
    p.hablado = []
    p.emitido = []
    p._hablar = lambda texto, emocion="neutral", motor=True: p.hablado.append(texto)
    p._emitir = lambda nombre, valor: p.emitido.append((nombre, valor))
    print("[Prueba] Llamando a Parker._apagar() en modo seco...")
    p._apagar()
    print(f"[Prueba] Lo dicho: {p.hablado}")
    print(f"[Prueba] Señales a la cara: {p.emitido}")
    nombres = [e[0] for e in p.emitido]
    bien = (any("Hasta luego" in t for t in p.hablado)
            and ("despedida", "derecha") in p.emitido
            and "reaparecer" in nombres)
    if not bien:
        print("[Prueba] FALLO: el apagado no completó su ceremonia")
    return bien


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba real del día de Parker")
    parser.add_argument("--ciudad", default=None, help="ciudad para el tiempo")
    parser.add_argument("--sonar", action="store_true",
                        help="reproduce 8 s de música por el altavoz")
    parser.add_argument("--apagado", action="store_true",
                        help="incluye la prueba del apagado (usa PARKER_APAGADO_SECO=1)")
    parser.add_argument("--decir", default=None,
                        help="dice esta frase por el altavoz (con Parker en marcha)")
    parser.add_argument("--apagar-seco", action="store_true",
                        help="ejecuta Parker._apagar() en modo seco (no apaga nada)")
    args = parser.parse_args()

    print(linea_arranque())
    if args.decir:
        return _decir(args.decir)
    if args.apagar_seco:
        return 0 if _probar_apagar_de_verdad() else 1
    resultados = {}
    resultados["rutinas"] = _probar_rutinas()
    resultados["apuntes"] = _probar_apuntes()
    resultados["tiempo"] = _probar_tiempo(args.ciudad or "Barcelona")
    resultados["música"] = _probar_musica(args.sonar)
    if args.apagado:
        resultados["apagado"] = _probar_apagado()

    print("\n[Prueba] Resumen:")
    for nombre, bien in resultados.items():
        print(f"[Prueba]   {nombre}: {'OK' if bien else 'FALLO'}")
    fallos = [n for n, b in resultados.items() if not b]
    if fallos:
        print(f"[Prueba] FALLOS: {', '.join(fallos)}")
        return 1
    print("[Prueba] TODO BIEN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
