"""
tests/test_cara.py
==================
Tests offscreen de la animación de la cara (sin pantalla física).

Ejecutar:  QT_QPA_PLATFORM=offscreen python tests/test_cara.py

Cubre:
  1. Acción superpuesta: los grupos del rostro NO se mueven a la vez
     (los ojos arrancan antes que las cejas)
  2. Las expresiones llegan a su preset
  3. El parpadeo cierra y vuelve a abrir

Los tests comparan el ORDEN de los movimientos en vez de tiempos absolutos,
para no fallar por el retardo de primer frame del event loop.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsScene

from modulos.cara_parker import FaceController


def _cara(app):
    scene = QGraphicsScene(0, 0, 400, 400)
    face = FaceController(scene)
    # Sin timers aleatorios: los tests necesitan determinismo
    face._blink_timer.stop()
    face._glance_timer.stop()
    face._gesto_timer.stop()
    return face


def _esperar(condicion, app, max_seg=2.0):
    """Procesa eventos hasta que se cumpla la condición o pase el tiempo."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_seg:
        if condicion():
            return True
        app.processEvents()
        time.sleep(0.005)
    return condicion()


def test_estagger(app):
    """Cejas llegan tarde; los ojos arrancan solos (overlapping action)."""
    face = _cara(app)
    claves = ("eye_l_open", "mouth_curve", "eyebrow_opacity")

    # Calentar el event loop ANTES de animar: sin esto los timers de Qt pueden
    # no disparar hasta ~0,2 s tras la primera llamada y toda la escalonación
    # (ojos → cejas) cae en la misma muestra de 4 ms — el solape parecía 0,013
    # en vez de 0,04 (flakiness medido offscreen en PC, 24/10).
    QTest.qWait(150)
    face.animate_to({"eye_l_open": 0.6, "mouth_curve": -1.0, "eyebrow_opacity": 1.0},
                    duration_ms=400)

    t0 = time.monotonic()
    inicio = {}
    prev = dict(face.params)
    while time.monotonic() - t0 < 1.2 and len(inicio) < len(claves):
        app.processEvents()
        for k in claves:
            if k not in inicio and abs(face.params[k] - prev[k]) > 1e-9:
                inicio[k] = time.monotonic() - t0
        prev = dict(face.params)
        time.sleep(0.004)

    assert "eye_l_open" in inicio, f"los ojos no llegaron a moverse: {inicio}"
    assert "eyebrow_opacity" in inicio, f"las cejas no llegaron a moverse: {inicio}"
    assert inicio["eye_l_open"] < inicio["eyebrow_opacity"], \
        f"los ojos deben empezar ANTES que las cejas: {inicio}"
    assert inicio["eyebrow_opacity"] - inicio["eye_l_open"] >= 0.03, \
        f"el solape debe ser apreciable: {inicio}"

    QTest.qWait(1500)
    assert abs(face.params["eye_l_open"] - 0.6) < 0.02, face.params["eye_l_open"]
    assert abs(face.params["mouth_curve"] - (-1.0)) < 0.02, face.params["mouth_curve"]
    assert abs(face.params["eyebrow_opacity"] - 1.0) < 0.02, face.params["eyebrow_opacity"]
    print("[OK] acción superpuesta: ojos antes que cejas y destino alcanzado")


def test_expresion(app):
    """Una expresión llega a su preset tras la anticipación y el snap."""
    face = _cara(app)

    face.set_expression("sorpresa")
    QTest.qWait(1400)

    p = face.params
    assert abs(p["mouth_open"] - 0.75) < 0.05, p["mouth_open"]
    # 25/10: el ojo ya no pasa de EYE_OPEN_MAX (1.0). Más apertura convertía
    # el ojo en una cápsula alargada («los ojos se hacen más largos»).
    assert abs(p["eye_l_open"] - 1.0) < 0.05, p["eye_l_open"]
    assert abs(p["scale_y"] - 1.16) < 0.04, p["scale_y"]
    assert face._current_expression == "sorpresa"
    print("[OK] expresión 'sorpresa' aplicada con anticipación + snap")


def test_ojos_nunca_se_alargan(app):
    """El ojo no puede pasar de 38x58 aunque un gesto pida más."""
    from modulos.cara_parker import EYE_BASE_H, EYE_OPEN_MAX
    face = _cara(app)

    face.animate_to({"eye_l_open": 2.5, "eye_r_open": 2.5}, duration_ms=120,
                    estagger=False)
    QTest.qWait(500)
    assert face.params["eye_l_open"] <= 2.5, face.params["eye_l_open"]
    alto = EYE_BASE_H * min(face.params["eye_l_open"], EYE_OPEN_MAX)
    assert alto <= EYE_BASE_H + 0.001, alto

    # Y la red de seguridad del latido devuelve el parámetro a su rango.
    face.params["eye_l_open"] = 3.4
    face._acotar_params()
    assert face.params["eye_l_open"] == EYE_OPEN_MAX, face.params["eye_l_open"]
    print("[OK] los ojos no se alargan: techo 1.0 y corrección periódica")


def test_parpadeo(app):
    """El parpadeo cierra los ojos y vuelve a abrirlos (base restaurada)."""
    face = _cara(app)
    face.set_expression("neutral")
    assert _esperar(lambda: abs(face.params["eye_l_open"] - 1.0) < 0.02, app, 1.5), \
        face.params["eye_l_open"]

    face.blink()
    assert _esperar(lambda: face.params["eye_l_open"] < 0.6, app, 0.4), \
        f"debería cerrar: {face.params['eye_l_open']}"
    assert _esperar(lambda: face.params["eye_l_open"] > 0.9, app, 1.0), \
        f"debería reabrir: {face.params['eye_l_open']}"
    print("[OK] parpadeo: cierre rápido y apertura elástica")


def test_dormirse_despertarse_y_despedida(app):
    """Dormir/despertar y la despedida de «apágate» (se va de lado y se funde)."""
    face = _cara(app)
    face.dormirse()
    QTest.qWait(1500)
    assert face.params["eye_l_open"] < 0.1, face.params["eye_l_open"]
    assert not face._blink_timer.isActive(), "dormido no debe parpadear"

    face.despertarse()
    QTest.qWait(1200)
    assert face.params["eye_l_open"] > 0.9, face.params["eye_l_open"]
    assert face._blink_timer.isActive(), "despierto vuelve a parpadear"

    llamado = []
    face.despedida("derecha", fn_final=lambda: llamado.append(True), ms=250)
    assert _esperar(lambda: bool(llamado), app, 2.5), "la despedida no terminó"
    # Se marcha de verdad: fuera de su sitio, encogida y transparente.
    assert face.group.pos().x() > 10, face.group.pos().x()
    assert face.group.opacity() < 0.1, face.group.opacity()

    # Y si al final no se pudo apagar, vuelve a su sitio.
    face.reaparecer()
    QTest.qWait(200)
    assert face.group.opacity() == 1.0, face.group.opacity()
    assert abs(face.group.pos().x()) < 0.001, face.group.pos().x()
    assert face.group.scale() == 1.0, face.group.scale()
    print("[OK] dormirse, despertarse y despedida (se marcha y puede reaparecer)")


def test_director_de_gestos(app):
    """El reposo se mueve: familia según el silencio, gestos que van y vuelven.

    Antes de la v6.8.0 la cara en reposo solo flotaba, parpadeaba y miraba de
    vez en cuando; este test fija lo que se pidió el 27/10: que en silencio
    PASE algo y que lo que pase cambie con el tiempo que lleve sin hablarle.
    """
    from modulos.cara_parker import (EYE_OPEN_MAX, FAMILIAS_GESTOS,
                                     GESTOS_ABURRIDO_SEG, GESTOS_SOLO_SEG)
    face = _cara(app)
    face.set_expression("neutral", con_anticipacion=False)
    QTest.qWait(900)

    # 1. La familia la decide el tiempo sin hablarle, no el azar.
    face.set_silencio(5)
    assert face.familia_gestos() == "despierto", face.familia_gestos()
    face.set_silencio(GESTOS_SOLO_SEG + 10)
    assert face.familia_gestos() == "solo", face.familia_gestos()
    face.set_silencio(GESTOS_ABURRIDO_SEG + 10)
    assert face.familia_gestos() == "aburrido", face.familia_gestos()

    # 2. Todo gesto del catálogo existe de verdad: un nombre mal escrito (o un
    #    método borrado) se quedaría ahí sin que nadie lo notara.
    for nombre in sorted({g for familia in FAMILIAS_GESTOS.values() for g in familia}):
        assert callable(getattr(face, nombre, None)), f"falta el gesto '{nombre}'"

    # 3. Un gesto mueve la cara de verdad y la deja como estaba.
    base_y = face.params["scale_y"]
    assert face.gesto("estiron"), "el gesto no se ejecutó"
    assert _esperar(lambda: face.params["scale_y"] > base_y + 0.03, app, 1.0), \
        f"el estirón no se notó: {face.params['scale_y']}"
    assert _esperar(lambda: abs(face.params["scale_y"] - base_y) < 0.03, app, 1.5), \
        f"el estirón no volvió: {face.params['scale_y']}"
    assert face.gesto("no_existe") is False

    # 4. El director elige de la familia que toca y no gesticula mientras habla.
    face.set_silencio(0)
    elegidos = {face._gesto_aleatorio() for _ in range(12)}
    elegidos.discard(None)
    assert elegidos <= set(FAMILIAS_GESTOS["despierto"]), elegidos
    face.iniciar_habla()
    QTest.qWait(60)
    assert face._gesto_aleatorio() is None, "hablando manda el lip-sync"
    face.detener_habla()
    face._gesto_timer.stop()   # de aquí en adelante, gestos a mano (determinismo)

    # 5. Regresión del 25/10: después de mucho gesto los ojos no se alargan.
    for nombre in ("bostezo", "estiron", "suspirar", "cabecear", "mirar_arriba",
                   "curiosear", "micro_ceja", "asentir", "negar", "guino"):
        face.gesto(nombre)
    QTest.qWait(2400)
    face._acotar_params()
    assert face.params["eye_l_open"] <= EYE_OPEN_MAX, face.params["eye_l_open"]
    assert face.params["eye_r_open"] <= EYE_OPEN_MAX, face.params["eye_r_open"]
    print("[OK] director de gestos: familias por silencio, gestos con vuelta y ojos "
          "sin alargarse")


def main():
    app = QApplication(sys.argv)
    test_estagger(app)
    test_expresion(app)
    test_ojos_nunca_se_alargan(app)
    test_parpadeo(app)
    test_dormirse_despertarse_y_despedida(app)
    test_director_de_gestos(app)
    print("\nTodos los tests de la cara han pasado.")


if __name__ == "__main__":
    main()
