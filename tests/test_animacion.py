"""
tests/test_animacion.py
=======================
Tests de los 12 principios de animación en la cara (offscreen, sin pantalla).

Ejecutar:  QT_QPA_PLATFORM=offscreen python tests/test_animacion.py

Cubre:
  1. El mapa PRINCIPIOS tiene exactamente los 12 y cada uno apunta a código real
  2. Squash & Stretch + anticipación: la pose pasa por una fase previa contraria
  3. Exageración: el parámetro escala la desviación respecto a la pose neutra
  4. Continuación (muelle): el dibujo se pasa del objetivo y luego se asienta
  5. Acción secundaria: al hablar no solo se mueve la boca
  6. Atractivo y asimetría: guiño con un solo ojo, bostezo completo
  7. La intro termina en una pose legible (mirando al frente)
  8. `detener()` cancela los gestos ya programados (cierre limpio de verdad)
"""

import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsScene

from modulos import cara_parker as CP

PRINCIPIOS_ESPERADOS = {
    "squash_stretch", "anticipacion", "puesta_en_escena", "pose_a_pose",
    "continuacion_superposicion", "entradas_salidas", "arcos",
    "accion_secundaria", "timing", "exageracion", "dibujo_solido", "atractivo",
}

# Cada principio debe tener código detrás, no solo una frase en el mapa.
CODIGO_DE_CADA_PRINCIPIO = {
    "squash_stretch": ["_tick_alive_engine", "set_expression", "reproducir_intro"],
    "anticipacion": ["set_expression", "asentir", "negar"],
    "puesta_en_escena": ["pose_de_escucha", "reproducir_intro"],
    "pose_a_pose": ["_presets", "_lanzar_tween"],
    "continuacion_superposicion": ["_integrar_muelle", "animate_to"],
    "entradas_salidas": ["_lanzar_tween"],
    "arcos": ["_mirar_aleatorio", "_tween_valor"],
    "accion_secundaria": ["blink", "_animar_fonemas_habla"],
    "timing": ["animate_to"],
    "exageracion": ["set_expression", "reaccion_rapida"],
    "dibujo_solido": ["redraw"],
    "atractivo": ["guino", "bostezo", "doble_toma", "gesto", "cabecear", "micro_ceja"],
}


def _cara(app, **kwargs):
    scene = QGraphicsScene(0, 0, 400, 400)
    face = CP.FaceController(scene)
    # Sin timers aleatorios: los tests necesitan determinismo
    face._blink_timer.stop()
    face._glance_timer.stop()
    face._gesto_timer.stop()
    for clave, valor in kwargs.items():
        if clave in face.params:
            face.params[clave] = valor
    return face


def _esperar(condicion, app, max_seg=2.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_seg:
        if condicion():
            return True
        app.processEvents()
        time.sleep(0.005)
    return condicion()


def test_mapa_de_principios():
    assert set(CP.PRINCIPIOS) == PRINCIPIOS_ESPERADOS, (
        f"faltan: {PRINCIPIOS_ESPERADOS - set(CP.PRINCIPIOS)} | "
        f"sobran: {set(CP.PRINCIPIOS) - PRINCIPIOS_ESPERADOS}"
    )
    for principio, metodos in CODIGO_DE_CADA_PRINCIPIO.items():
        assert CP.PRINCIPIOS[principio].strip(), f"{principio} sin descripción"
        for nombre_metodo in metodos:
            assert hasattr(CP.FaceController, nombre_metodo), \
                f"el principio '{principio}' cita {nombre_metodo}, que no existe"
    print(f"[OK] los {len(CP.PRINCIPIOS)} principios están mapeados y con código detrás")


def test_anticipacion(app):
    """Antes de la pose final hay un gesto contrario (cuerpo que coge carrerilla)."""
    face = _cara(app)
    face.set_expression("neutral")
    QTest.qWait(900)

    face.set_expression("sorpresa")   # escala hacia 0.88 en X
    vistos = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < 1.3:
        vistos.append(face.params["scale_x"])
        app.processEvents()
        time.sleep(0.006)

    assert max(vistos) > 1.02, f"no hubo anticipación de estirar antes de encoger: {max(vistos):.3f}"
    assert vistos[-1] < 0.95, f"no llegó a la pose final: {vistos[-1]:.3f}"
    print(f"[OK] anticipación: pico {max(vistos):.2f} antes de asentarse en {vistos[-1]:.2f}")


def test_exageracion(app):
    """La misma expresión con más exageración se desvía más del neutral."""
    suave = _cara(app)
    suave.set_expression("sorpresa")
    QTest.qWait(1300)

    grande = _cara(app)
    grande.set_expression("sorpresa", exageracion=1.6)
    QTest.qWait(1300)

    neutral_y = suave._presets()["neutral"]["scale_y"]
    desvio_suave = abs(suave.params["scale_y"] - neutral_y)
    desvio_grande = abs(grande.params["scale_y"] - neutral_y)
    assert desvio_grande > desvio_suave + 0.03, (desvio_suave, desvio_grande)

    # Y también se puede suavizar por debajo del preset
    flojo = _cara(app)
    flojo.set_expression("sorpresa", exageracion=0.5)
    QTest.qWait(1300)
    assert abs(flojo.params["scale_y"] - neutral_y) < desvio_suave, flojo.params["scale_y"]
    print(f"[OK] exageración: desvío {desvio_suave:.3f} (1.0) vs {desvio_grande:.3f} (1.6)")


def test_muelle_con_sobreimpulso(app):
    """El dibujo persigue el objetivo con inercia: se pasa y luego se asienta."""
    face = _cara(app)
    face.params["head_tilt"] = 0.0
    face._muelle.update({"tilt": 0.0, "vt": 0.0})

    objetivo = 12.0
    valores = []
    for _ in range(120):
        face._integrar_muelle(objetivo, 1.0, 1.0, dt=0.033)
        valores.append(face._muelle["tilt"])

    sobreimpulso = max(valores) - objetivo
    assert sobreimpulso > 0.3, f"sin sobreimpulso no hay follow-through: {sobreimpulso:.3f}"
    assert abs(valores[-1] - objetivo) < 0.2, f"no se asienta: {valores[-1]:.3f}"
    print(f"[OK] muelle: sobreimpulso de {sobreimpulso:.2f} grados y se asienta en {valores[-1]:.2f}")


def test_accion_secundaria_al_hablar(app):
    """Al hablar, la cabeza acompaña a la boca (y la boca se mueve de verdad)."""
    face = _cara(app)
    face.set_expression("neutral")
    QTest.qWait(800)

    face.iniciar_habla()
    bocas, cabezas = set(), []
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2.5:
        bocas.add(round(face.params["mouth_open"], 2))
        cabezas.append(face.params["head_tilt"])
        app.processEvents()
        time.sleep(0.01)
    face.detener_habla()

    assert len(bocas) >= 3, f"la boca no articula: {bocas}"
    assert max(cabezas) - min(cabezas) > 0.5, f"la cabeza no acompaña el habla: {cabezas[:10]}"
    print(f"[OK] acción secundaria: {len(bocas)} aperturas de boca y cabeza de "
          f"{min(cabezas):.2f} a {max(cabezas):.2f} grados")


def test_gestos_propios(app):
    """Guiño asimétrico y bostezo completo: los detalles con 'atractivo'."""
    face = _cara(app)
    face.params["eye_l_open"] = 1.0
    face.params["eye_r_open"] = 1.0

    face.guino(ojo_izquierdo=True)
    assert _esperar(lambda: face.params["eye_l_open"] < 0.4, app, 0.5), \
        f"el ojo no se cerró: {face.params['eye_l_open']}"
    assert face.params["eye_r_open"] > 0.8, "el otro ojo debe aguantar abierto (asimetría)"
    assert _esperar(lambda: face.params["eye_l_open"] > 0.8, app, 1.2), \
        f"el ojo no volvió a abrirse: {face.params['eye_l_open']}"

    face.bostezo()
    abierto = _esperar(lambda: face.params["mouth_open"] > 0.7, app, 1.2)
    assert abierto, f"el bostezo no abrió la boca: {face.params['mouth_open']}"
    assert _esperar(lambda: face.params["mouth_open"] < 0.4, app, 2.0), \
        f"el bostezo no cerró: {face.params['mouth_open']}"
    print("[OK] gestos: guiño asimétrico y bostezo con retorno")


def test_intro_termina_legible(app):
    """La intro despierta, mira a los lados, bosteza y acaba mirando al frente."""
    face = _cara(app)
    face.reproducir_intro()

    assert _esperar(lambda: face.params["scale_y"] > 1.05, app, 1.2), \
        "no hubo estirón de despertar"
    assert _esperar(lambda: abs(face._look_x) > 8.0, app, 2.5), \
        f"no hubo arco de mirada: {face._look_x}"
    QTest.qWait(5200)

    p = face.params
    assert abs(p["scale_y"] - 1.0) < 0.12, f"no se asentó: {p['scale_y']:.3f}"
    assert abs(p["scale_x"] - 1.0) < 0.12, f"no se asentó: {p['scale_x']:.3f}"
    assert abs(face._look_x) < 6.0, f"no mira al frente al terminar: {face._look_x}"
    assert abs(p["eye_l_open"] - 1.0) < 0.25, f"ojos no legibles: {p['eye_l_open']:.2f}"
    print("[OK] intro: se estira, mira a los lados, bosteza y termina al frente")


def test_detener_cancela_gestos(app):
    """Tras detener() ningún gesto programado debe seguir tocando la cara."""
    face = _cara(app)
    face.params["mouth_open"] = 0.0
    face.bostezo()
    face.detener()

    QTest.qWait(1400)
    assert face.params["mouth_open"] < 0.2, \
        f"un gesto siguió actuando tras detener(): {face.params['mouth_open']:.2f}"
    assert face._activo is False
    print("[OK] detener(): los gestos programados quedan cancelados")


def test_gestos_solo_despierto(app):
    """El director de gestos se para al dormirse y vuelve al despertar."""
    face = _cara(app)
    # El helper apaga los timers aleatorios: aquí se enciende a propósito.
    face._programar_gesto()
    assert face._gesto_timer.isActive(), "el director debe quedar programado"

    face.dormirse()
    QTest.qWait(120)
    assert not face._gesto_timer.isActive(), "dormido no gesticula: solo respira"

    face.despertarse()
    QTest.qWait(900)
    assert face._gesto_timer.isActive(), "despierto vuelve a moverse por su cuenta"
    print("[OK] director de gestos: parado mientras duerme y activo al despertar")


def test_demo_cara_catalogo(app):
    """El modo demo cubre TODO el catálogo y sabe arrancar y detenerse."""
    face = _cara(app)
    assert set(CP.EXPRESIONES_DEMO) == set(face._presets()), \
        "la demo no cubre todas las expresiones"
    catalogo = {g for familia in CP.FAMILIAS_GESTOS.values() for g in familia}
    assert set(CP.GESTOS_DEMO) == catalogo, \
        (set(CP.GESTOS_DEMO) - catalogo, catalogo - set(CP.GESTOS_DEMO))
    for nombre in CP.GESTOS_DEMO:
        assert callable(getattr(face, nombre, None)), f"falta el gesto '{nombre}'"

    assert face.modo_demo() > 0, "la demo no programó nada"
    assert face._demo_activo, "la demo no quedó activa"
    assert not face._gesto_timer.isActive(), "el director no debe pisar la demo"
    face.detener_demo()
    assert not face._demo_activo, "detener_demo no cerró la secuencia"
    assert face._gesto_timer.isActive(), "al cerrar debe volver el director"
    face.detener()
    print(f"[OK] modo demo: {len(CP.EXPRESIONES_DEMO)} expresiones y "
          f"{len(CP.GESTOS_DEMO)} gestos, con arranque y corte")


def main():
    app = QApplication(sys.argv)
    test_mapa_de_principios()
    test_anticipacion(app)
    test_exageracion(app)
    test_muelle_con_sobreimpulso(app)
    test_accion_secundaria_al_hablar(app)
    test_gestos_propios(app)
    test_intro_termina_legible(app)
    test_detener_cancela_gestos(app)
    test_gestos_solo_despierto(app)
    test_demo_cara_catalogo(app)
    print("\nTodos los tests de animación han pasado.")


if __name__ == "__main__":
    main()
