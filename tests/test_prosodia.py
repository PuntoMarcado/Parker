"""
tests/test_prosodia.py
======================
Tests del registro prosódico y de la tendencia, con señales sintéticas
(sin micrófono ni hardware).

Ejecutar:  python -m pytest tests/test_prosodia.py -q
"""

import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.prosodia import ProsodiaParker, _f0_marco


def _tono(frecuencia=150.0, amplitud=0.2, duracion=2.0, sr=16000):
    t = np.arange(int(duracion * sr), dtype=np.float32) / sr
    onda = amplitude_ref(amplitud) * np.sin(2 * np.pi * frecuencia * t)
    return onda.astype(np.float32)


def amplitude_ref(amplitud):
    return amplitud


def test_f0_del_tono_limpio():
    sr = 16000
    señal = _tono(200.0, 0.3)
    marco = señal[: int(0.03 * sr)]
    f0 = _f0_marco(marco, sr)
    assert f0 is not None
    assert abs(f0 - 200.0) < 12.0, f0
    print("[OK] F0 de un tono limpio de 200 Hz se mide bien")


def test_rms_y_densidad_de_un_turno():
    with tempfile.TemporaryDirectory() as tmp:
        pros = ProsodiaParker(str(Path(tmp) / "p.db"))
        medidas = pros.registrar(_tono(150.0, 0.25, 2.0), 16000)
        assert medidas
        # 0.25 de amplitud en seno puro: rms = 0.25/sqrt(2) ≈ 0.177 -> ≈ -15 dB
        assert -20.0 <= medidas["rms_db"] <= -10.0, medidas["rms_db"]
        assert medidas["f0_hz"] is not None and abs(medidas["f0_hz"] - 150.0) < 8.0
        assert 0.0 < medidas["densidad"] <= 1.0
        pros.cerrar()
        print(f"[OK] rms={medidas['rms_db']:.1f}dB f0={medidas['f0_hz']:.0f}Hz "
              f"densidad={medidas['densidad']:.2f}")


def test_silencio_no_se_registra():
    with tempfile.TemporaryDirectory() as tmp:
        pros = ProsodiaParker(str(Path(tmp) / "p.db"))
        assert pros.registrar(np.zeros(400, dtype=np.float32), 16000) == {}
        pros.cerrar()
        print("[OK] audio demasiado corto no se registra")


def test_tendencia_baja_con_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        pros = ProsodiaParker(str(Path(tmp) / "p.db"))
        ahora = time.time()
        con = pros._con
        filas = []
        # Baseline: 6 turnos a -14 dB hace 10 días
        for i in range(6):
            filas.append((ahora - 10 * 86400 - i * 600, -14.0, 150.0, 0.6, 4.0))
        # Recientes: 4 turnos a -18.5 dB (4,5 dB por debajo)
        for i in range(4):
            filas.append((ahora - i * 600, -18.5, 130.0, 0.45, 4.0))
        con.executemany(
            "INSERT OR REPLACE INTO muestras (ts, rms_db, f0_hz, densidad, "
            "duracion) VALUES (?,?,?,?,?)", filas)
        con.commit()
        senal = pros.tendencia()
        pros.cerrar()
        assert senal is not None, "con 4+4 muestras sí hay tendencia"
        assert senal["nivel"] == "bajo", senal
        assert senal["delta_rms_db"] <= -2.5
        assert senal["delta_f0_pct"] is not None and senal["delta_f0_pct"] < 0
        print(f"[OK] tendencia 'bajo' detectada: {senal['delta_rms_db']:+.1f}dB, "
              f"f0 {senal['delta_f0_pct']:+.1f}%")


def test_tendencia_normal_si_no_cambia():
    with tempfile.TemporaryDirectory() as tmp:
        pros = ProsodiaParker(str(Path(tmp) / "p.db"))
        ahora = time.time()
        filas = []
        for i in range(6):
            filas.append((ahora - 10 * 86400 - i * 600, -15.0, 150.0, 0.6, 4.0))
        for i in range(4):
            filas.append((ahora - i * 600, -15.3, 152.0, 0.58, 4.0))
        pros._con.executemany(
            "INSERT OR REPLACE INTO muestras (ts, rms_db, f0_hz, densidad, "
            "duracion) VALUES (?,?,?,?,?)", filas)
        pros._con.commit()
        senal = pros.tendencia()
        pros.cerrar()
        assert senal is not None and senal["nivel"] == "normal", senal
        print("[OK] sin cambio de voz, tendencia 'normal' (no molesta)")


def test_pocas_muestras_devuelve_nada():
    with tempfile.TemporaryDirectory() as tmp:
        pros = ProsodiaParker(str(Path(tmp) / "p.db"))
        assert pros.tendencia() is None
        pros.cerrar()
        print("[OK] sin datos suficientes no se inventa ninguna tendencia")


def test_borrar_todos():
    with tempfile.TemporaryDirectory() as tmp:
        prosod = ProsodiaParker(str(Path(tmp) / "p.db"))
        prosod.registrar(_tono(), 16000)
        n = prosod.borrar_todos()
        assert n == 1
        assert prosod.tendencia() is None
        prosod.cerrar()
        print("[OK] borrado completo de medidas")


if __name__ == "__main__":
    test_f0_del_tono_limpio()
    test_rms_y_densidad_de_un_turno()
    test_silencio_no_se_registra()
    test_tendencia_baja_con_baseline()
    test_tendencia_normal_si_no_cambia()
    test_pocas_muestras_devuelve_nada()
    test_borrar_todos()
    print("[OK] prosodia: 7/7")
