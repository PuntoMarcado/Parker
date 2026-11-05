"""
tests/test_bandit.py
====================
Idea 14: que Parker aprenda de lo que funciona (el bandit de docs/evolucion.md §6).

Lo que se comprueba, que es lo que se nota en casa con el tiempo:
  1. En frío reparte parejo y nunca se queda sin brazo válido.
  2. Con recompensas, insiste en el brazo que funciona (y deja el que molesta).
  3. Las recompensas se miden como están documentadas: +1 respuesta rápida,
     0 tarde, −0,3 sin respuesta en 30 min, −1 queja explícita.
  4. «Callar» también se aprende: no molestar cuenta como acierto.
  5. Los contadores sobreviven al reinicio (parker.estado.json).

Ejecutar:
    QT_QPA_PLATFORM=offscreen python tests/test_bandit.py
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.personalidad import (  # noqa: E402
    BRAZOS_INICIATIVA,
    PersonalidadParker,
)


def _perfil(ruta=None):
    cfg = {"guardar_estado": bool(ruta)}
    if ruta:
        cfg["ruta_estado"] = str(ruta)
    return PersonalidadParker(cfg)


def test_brazos_y_arranque_neutro():
    perfil = _perfil()
    assert set(BRAZOS_INICIATIVA) == {"contar", "preguntar", "proponer", "eco",
                                      "callar"}, list(BRAZOS_INICIATIVA)
    # En frío todos los brazos valen, y «callar» no trae instrucción (silencio).
    elegidos = set()
    for _ in range(400):
        brazo, instruccion = perfil.elegir_iniciativa(2700)
        elegidos.add(brazo)
        if brazo == "callar":
            assert instruccion == "", instruccion
        else:
            assert instruccion, brazo
    assert len(elegidos) >= 4, elegidos
    print(f"[OK] cinco brazos, en frío reparte: {sorted(elegidos)}")


def test_aprende_con_recompensas():
    perfil = _perfil()
    for _ in range(40):
        perfil.registrar_iniciativa("preguntar", ahora=time.time() - 10)
        perfil.cerrar_iniciativa("sí, mira, justo estaba con eso", ahora=time.time())
    for _ in range(40):
        perfil.registrar_iniciativa("contar", ahora=time.time() - 10)
        perfil.cerrar_iniciativa("cállate un rato", ahora=time.time())
    elecciones = [perfil.elegir_iniciativa(2700)[0] for _ in range(300)]
    assert elecciones.count("preguntar") > elecciones.count("contar") * 3, \
        (elecciones.count("preguntar"), elecciones.count("contar"))
    datos = perfil.estado["bandits"]
    assert datos["preguntar"][0] > datos["preguntar"][1], datos
    assert datos["contar"][1] > datos["contar"][0], datos
    print("[OK] tras premiar «preguntar» y castigar «contar», insiste en preguntar")


def test_recompensas_documentadas():
    perfil = _perfil()
    ahora = time.time()

    perfil.registrar_iniciativa("eco", ahora=ahora)
    assert perfil.cerrar_iniciativa("ah, ¿sí?", ahora=ahora + 30) == 1.0

    perfil.registrar_iniciativa("eco", ahora=ahora)
    assert perfil.cerrar_iniciativa("bueno, pues nada", ahora=ahora + 600) == 0.0

    perfil.registrar_iniciativa("proponer", ahora=ahora)
    assert perfil.cerrar_iniciativa("", ahora=ahora + 1900) is None  # no caduca aquí
    assert perfil.caducar_iniciativa(ahora=ahora + 1900) == -0.3

    perfil.registrar_iniciativa("contar", ahora=ahora)
    assert perfil.cerrar_iniciativa("Parker, cállate y déjame", ahora=ahora + 5) == -1.0

    # Sin iniciativa pendiente no hay recompensa que dar (no inventa premios).
    assert perfil.cerrar_iniciativa("hola", ahora=ahora) is None
    print("[OK] +1 rápida, 0 tarde, -0.3 sin respuesta y -1 con queja")


def test_callar_se_aprende():
    perfil = _perfil()
    ahora = time.time()
    perfil.registrar_iniciativa("callar", ahora=ahora)
    assert perfil.caducar_iniciativa(ahora=ahora + 1900) == 1.0
    # Y una queja sigue siendo una queja, incluso callado.
    perfil.registrar_iniciativa("callar", ahora=ahora)
    assert perfil.cerrar_iniciativa("no me molestes", ahora=ahora + 10) == -1.0
    usos = perfil.estado["iniciativas"]
    assert usos.get("callar") == 2, usos
    print("[OK] «callar» aprende: no molestar suma, quejarse resta")


def test_persistencia_de_lo_aprendido():
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "parker.estado.json"
        perfil = _perfil(ruta)
        for _ in range(5):
            ahora = time.time()
            perfil.registrar_iniciativa("eco", ahora=ahora)
            perfil.cerrar_iniciativa("cuéntame", ahora=ahora + 5)
        perfil._guardar()
        guardado = json.loads(ruta.read_text(encoding="utf-8"))
        assert guardado["estado"]["bandits"]["eco"][0] > 1.0, guardado

        otro = _perfil(ruta)
        assert otro.estado["bandits"]["eco"] == perfil.estado["bandits"]["eco"]
        assert otro.estado["iniciativas"].get("eco") == 5, otro.estado["iniciativas"]
        # Y un fichero corrupto no impide arrancar con los brazos por defecto.
        ruta.write_text("{esto no es json", encoding="utf-8")
        tercero = _perfil(ruta)
        assert tercero.estado["bandits"]["eco"] == [1.0, 1.0], tercero.estado["bandits"]
    print("[OK] lo aprendido sobrevive al reinicio (y un JSON roto no lo tumba)")


if __name__ == "__main__":
    test_brazos_y_arranque_neutro()
    test_aprende_con_recompensas()
    test_recompensas_documentadas()
    test_callar_se_aprende()
    test_persistencia_de_lo_aprendido()
    print("\nBandit de iniciativa: 5/5 en verde.")
