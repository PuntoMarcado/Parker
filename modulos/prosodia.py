"""
modulos/prosodia.py
===================
Señal DÉBIL de ánimo a partir de la voz: cada turno guarda tres features
prosódicas, y `tendencia()` compara los días recientes con la línea base de
ESA persona (no un umbral universal).

La literatura de prosodia y ánimo (scoping review de 14 estudios) apunta a
F0, duración y ratio habla-silencio como señales asociadas al ánimo bajo,
pero SOLO como tendencia agregada respect al baseline de la persona y nunca
como diagnóstico por frase. Por eso:

  - Se registran features RELATIVAS (dB, Hz, densidad), sin etiquetar emoción.
  - La tendencia dice «suena más baja que otros días», no «está triste».
  - Solo se usa para DECIDIR SI PREGUNTAR (check-in, estilo Baymax), nunca
    para tomar decisiones automáticas sobre la respuesta.

Coste: SQLite + numpy ya en uso, unas decenas de ms por turno; el F0 se
calcula con autocorrelación por FFT sobre frames con voz.
"""

import os
import sqlite3
import time
from datetime import datetime

import numpy as np


def _db(rms: float) -> float:
    return 20.0 * float(np.log10(max(float(rms), 1e-9)))


def _f0_marco(marco: np.ndarray, sr: int,
              min_f0: float = 70.0, max_f0: float = 350.0) -> float | None:
    """F0 de un frame 30 ms por autocorrelación (FFT). None si no hay pico."""
    n = len(marco)
    if n < 240:
        return None
    tam = 1 << (2 * n - 1).bit_length()
    espec = np.abs(np.fft.rfft(marco - marco.mean(), n=tam)) ** 2
    autocorr = np.fft.irfft(espec)[:n]
    rius_zero = autocorr[0]
    if rius_zero <= 1e-12:
        return None
    autocorr = autocorr / rius_zero
    ini = int(sr / max_f0)
    fin = min(n // 2, int(sr / min_f0))
    if fin <= ini + 1:
        return None
    trozo = autocorr[ini:fin]
    pico = int(np.argmax(trozo))
    # El pico tiene que ser un máximo real de la curva, no un ascenso relleno.
    if pico == 0 or pico == len(trozo) - 1:
        return None
    valor = trozo[pico]
    if valor < 0.35:  # poca periodicidad: no es voz sonora
        return None
    return sr / float(ini + pico)


class ProsodiaParker:
    """Registro prosódico por turno + tendencia de últimos días."""

    def __init__(self, ruta: str = "./parker.prosodia.db",
                 dias_recientes: int = 3, dias_base: int = 14):
        base = os.path.dirname(os.path.abspath(ruta))
        if base:
            os.makedirs(base, exist_ok=True)
        self.ruta = ruta
        self.dias_recientes = int(dias_recientes)
        self.dias_base = int(dias_base)
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS muestras (
                 ts REAL PRIMARY KEY,
                 rms_db REAL NOT NULL,
                 f0_hz REAL,
                 densidad REAL,
                 duracion REAL NOT NULL
               )""")
        self._con.commit()

    # ------------------------------------------------------------ registrar -
    def registrar(self, audio: np.ndarray, sr: int = 16000) -> dict:
        """Anota el turno en la tabla y devuelve las medidas.

        Cuidado: pasar el audio SIN normalizar por pico; si se normaliza, la
        altura (RMS en dB) pierde el sentido entre turnos (paso en parker.py
        ANTES de la normalización del STT).
        """
        audio = np.asarray(audio, dtype=np.float32).ravel()
        duracion = len(audio) / float(sr or 16000)
        if len(audio) < int(0.25 * (sr or 16000)) or duracion <= 0.0:
            return {}
        rms_total = float(np.sqrt(np.mean(audio ** 2)))
        marco = int(0.030 * sr)
        salto = marco  # sin solape, val para densidad y F0
        if marco <= 0 or len(audio) < 3 * marco:
            f0 = None
            densidad = None
        else:
            trozos = [audio[i:i + marco]
                      for i in range(0, len(audio) - marco + 1, salto)]
            rms_marco = np.array(
                [float(np.sqrt(np.mean(t ** 2))) for t in trozos])
            umbral_voz = 0.30 * float(rms_marco.max())
            voces = np.where(rms_marco >= umbral_voz)[0]
            densidad = (float(len(voces)) / len(rms_marco)
                        if len(rms_marco) else None)
            f0s = [_f0_marco(trozos[i], sr) for i in voces.tolist()]
            f0s = [f for f in f0s if f is not None]
            f0 = float(np.median(f0s)) if len(f0s) >= 2 else None
        fila = {"duracion": duracion, "rms_db": _db(rms_total),
                "f0_hz": f0, "densidad": densidad}
        self._con.execute(
            "INSERT OR REPLACE INTO muestras (ts, rms_db, f0_hz, densidad, "
            "duracion) VALUES (?, ?, ?, ?, ?)",
            (time.time(), fila["rms_db"], fila["f0_hz"], fila["densidad"],
             fila["duracion"]))
        self._con.commit()
        return fila

    # ------------------------------------------------------------ tendencia -
    def tendencia(self, dias_recientes: int | None = None,
                  dias_base: int | None = None) -> dict | None:
        """¿Suena la voz de estos días diferente a la de su baseline?

        Devuelve None con pocas muestras (sin datos no se dice nada). El
        nivel «bajo»/«alto» se decide sobre el RMS en dB del turno entero,
        solo con >= 2.5 dB de diferencia: menos que eso es ruido de sala.
        """
        rec = int(dias_recientes if dias_recientes is not None
                  else self.dias_recientes)
        base = int(dias_base if dias_base is not None else self.dias_base)
        ahora = time.time()
        rec_desde = ahora - max(1, rec) * 86400.0
        base_desde = rec_desde - max(1, base) * 86400.0
        recientes = self._con.execute(
            "SELECT rms_db, f0_hz, densidad FROM muestras WHERE ts >= ?",
            (rec_desde,)).fetchall()
        previos = self._con.execute(
            "SELECT rms_db, f0_hz, densidad FROM muestras WHERE ts >= ? AND "
            "ts < ? ", (base_desde, rec_desde)).fetchall()
        if len(recientes) < 3 or len(previos) < 3:
            return None
        rms_rec = float(np.mean([f[0] for f in recientes]))
        rms_base = float(np.mean([f[0] for f in previos]))
        delta_rms = rms_rec - rms_base
        f0_rec = [f[1] for f in recientes if f[1] is not None]
        f0_base = [f[1] for f in previos if f[1] is not None]
        delta_f0_pct = None
        if len(f0_rec) >= 2 and len(f0_base) >= 2:
            media_base = float(np.mean(f0_base))
            if media_base > 0:
                delta_f0_pct = 100.0 * (float(np.mean(f0_rec)) - media_base) / media_base
        nivel = "normal"
        if delta_rms <= -2.5:
            nivel = "bajo"
        elif delta_rms >= 2.5:
            nivel = "alto"
        return {
            "muestras": len(recientes),
            "baseline": len(previos),
            "delta_rms_db": round(delta_rms, 2),
            "delta_f0_pct": (round(delta_f0_pct, 1)
                             if delta_f0_pct is not None else None),
            "nivel": nivel,
            "desde": datetime.fromtimestamp(rec_desde).strftime("%Y-%m-%d"),
        }

    def cerrar(self) -> None:
        """Cierra la base (los tests la sueltan para poder borrar el tmp)."""
        try:
            self._con.close()
        except Exception:
            pass

    # ------------------------------------------------------------- borrar ---
    def borrar_todos(self) -> int:
        n = int(self._con.execute("SELECT COUNT(*) FROM muestras").fetchone()[0])
        self._con.execute("DELETE FROM muestras")
        self._con.commit()
        return n


if __name__ == "__main__":
    sr = 16000
    t = np.arange(int(2.0 * sr), dtype=np.float32) / sr
    voz = (0.25 * np.sin(2 * np.pi * 150.0 * t)
           .astype(np.float32))  # tono limpio 150 Hz
    pros = ProsodiaParker("./prueba_prosodia.db")
    print(pros.registrar(voz, sr))
    print(pros.tendencia())
