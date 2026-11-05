"""
tests/test_voz.py
=================
Tests del TTS (Piper) sin altavoces: se sintetiza y se mide la señal.

Ejecutar:  python tests/test_voz.py

Cubre el fallo corregido el 17/10/2026: la velocidad se aplicaba remuestreando
la señal, lo que **bajaba el tono** de la voz (Parker sonaba más grave de lo que
le corresponde) y el volumen multiplicaba una señal ya normalizada, así que
sonaba a grito. Ahora el ritmo se pide con `length_scale` (dentro de Piper) y el
volumen es una ganancia controlada.
"""

import sys
from pathlib import Path
import numpy as np
import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.voz import VozParker

FRASE = "Hola, soy Parker. Hoy he visto la lluvia por la ventana y me he alegrado de verte."


def _f0(audio: np.ndarray, sr: int) -> float:
    """Frecuencia fundamental aproximada (Hz) por autocorrelación."""
    ventana = int(0.04 * sr)
    if len(audio) < ventana * 2:
        return 0.0
    mejores = []
    for inicio in range(0, len(audio) - ventana, ventana):
        trozo = audio[inicio:inicio + ventana]
        if np.max(np.abs(trozo)) < 0.1:
            continue
        trozo = trozo - np.mean(trozo)
        corr = np.correlate(trozo, trozo, mode="full")[ventana - 1:]
        if corr[0] <= 0:
            continue
        min_lag, max_lag = int(sr / 400), int(sr / 70)  # 70-400 Hz
        pico = min_lag + int(np.argmax(corr[min_lag:max_lag]))
        mejores.append(sr / pico)
    return float(np.median(mejores)) if mejores else 0.0


def main():
    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    vcfg = cfg["voz"]
    modelo = BASE / vcfg["modelo_piper"]
    config = BASE / vcfg["modelo_config"]
    if not modelo.exists():
        print(f"[SKIP] no está el modelo de voz ({modelo.name}); test de voz omitido")
        return

    voz = VozParker(str(modelo), str(config),
                    velocidad=vcfg["velocidad"], volumen=vcfg["volumen"])

    normal = voz.sintetizar(FRASE, velocidad=1.0, volumen=vcfg["volumen"])
    calmo = voz.sintetizar(FRASE, velocidad=vcfg["velocidad"], volumen=vcfg["volumen"])
    fuerte = voz.sintetizar(FRASE, velocidad=1.0, volumen=1.0)

    # 1. Habla más despacio: dura ~1/velocidad (el audio lleva menos prisa)
    ratio = len(calmo) / len(normal)
    esperado = 1.0 / vcfg["velocidad"]
    assert abs(ratio - esperado) / esperado < 0.15, (
        f"la duración no acompaña a la velocidad: {ratio:.2f} vs {esperado:.2f}")

    # 2. Pero el TONO no cambia: es la misma voz, solo más calmada
    f0_normal, f0_calmo = _f0(normal, voz.sample_rate), _f0(calmo, voz.sample_rate)
    assert f0_normal > 60, f"no se pudo medir el tono: {f0_normal:.1f} Hz"
    desvio = abs(f0_calmo - f0_normal) / f0_normal
    assert desvio < 0.05, (
        f"el ritmo cambia el tono ({f0_normal:.1f} -> {f0_calmo:.1f} Hz): "
        "se está remuestreando la señal en vez de usar length_scale")

    # 3. El volumen pedido es el que suena, sin saturar
    pico = float(np.max(np.abs(normal)))
    pico_fuerte = float(np.max(np.abs(fuerte)))
    assert abs(pico - vcfg["volumen"]) < 0.08, f"pico {pico:.2f} != volumen {vcfg['volumen']}"
    assert abs(pico_fuerte - 1.0) < 0.08, f"pico a volumen 1.0: {pico_fuerte:.2f}"
    assert vcfg["volumen"] <= 0.7, "un volumen así suena a grito en el altavoz de la placa"

    print(f"[OK] voz: {len(calmo)/voz.sample_rate:.2f}s calmada vs {len(normal)/voz.sample_rate:.2f}s normal, "
          f"tono {f0_calmo:.0f} Hz (= {f0_normal:.0f} Hz), pico {pico:.2f}")
    print("\nTodos los tests de voz han pasado.")


if __name__ == "__main__":
    main()
