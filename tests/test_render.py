"""Smoke test offline de render (offscreen). Ejecutar: python tests/test_render.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

import parker as P


def main():
    app = QApplication(sys.argv)
    senales = P.SenalesCara()
    # activar_display=False: el test solo mide render en memoria; si abriera
    # la pantalla SPI secuestraría el GPIO/display que usa la cara REAL de
    # Parker (visto 24/10: tras el test, la cara de la placa quedó congelada y
    # borrosa).
    w = P.ParkerWindow(senales, activar_display=False)
    w.show()
    # Sin parpadeos ni miradas aleatorias: el render debe ser reproducible
    w.face._blink_timer.stop()
    w.face._glance_timer.stop()
    # La ventana lanza la INTRO al crearse (~4,5 s: se estira, mira, bosteza...).
    # El render se mide sobre una cara ya asentada y mirando al frente: si se
    # mide a mitad de un gesto (p. ej. el bostezo, con los ojos cerrados), el
    # número de píxeles depende de la coreografía y no del render.

    resultado = {}

    def render():
        try:
            img = QImage(240, 240, QImage.Format_RGB16)
            img.fill(0)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            w.scene.render(p, QRectF(0, 0, 240, 240), QRectF(0, 0, 400, 400))
            p.end()
            raw = bytes(img.bits())
            resultado["nz"] = sum(1 for b in raw if b != 0)
            resultado["total"] = len(raw)
            resultado["params"] = {k: round(v, 2) for k, v in w.face.params.items()}
            resultado["items"] = len(w.scene.items())
        except Exception as e:
            resultado["error"] = repr(e)
        finally:
            app.quit()

    QTimer.singleShot(6500, render)
    app.exec()

    # Cierre limpio: la cara para sus temporizadores antes de salir
    w.face.detener()
    w.close()
    print("RESULTADO:", resultado)
    assert "error" not in resultado, resultado
    assert resultado["nz"] > 1500, resultado
    print("RENDER_OK")


if __name__ == "__main__":
    main()
