"""
tools/diagnostico_cara.py
=========================
Reproduce la vida de la cara SIN la placa ni la pantalla SPI y vigila si los
ojos se van deformando con el tiempo (síntoma visto en la placa 25/10: «los
ojos se hacen cada vez más largos»).

Hace lo mismo que parker.py: alterna expresiones (escuchando → pensando →
neutral) con parpadeos, guiños y bostezos, y cada 5 s imprime:
    apertura  ojo tal como lo ve el dibujo (alto = EYE_BASE_H × apertura)
    escala    escala efectiva del grupo (muelle de inercia)
    alto_px   altura real del ojo en pantalla

Uso:
    QT_QPA_PLATFORM=offscreen python tools/diagnostico_cara.py --segundos 60
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402

from modulos.cara_parker import EYE_BASE_H, FaceController  # noqa: E402

SECUENCIA = ["escuchando", "neutral", "pensando", "neutral", "escuchando",
             "neutral", "carino", "neutral"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=float, default=45.0)
    ap.add_argument("--cada", type=float, default=5.0)
    ap.add_argument("--png", default=None,
                    help="guarda un fotograma 240x240 (igual que el panel) al final")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    escena = QGraphicsScene(0, 0, 400, 400)
    face = FaceController(escena)
    face.reproducir_intro()

    paso = {"i": 0}

    def cambiar():
        face.set_expression(SECUENCIA[paso["i"] % len(SECUENCIA)])
        paso["i"] += 1
        # Gestos que parker.py lanza en la vida normal
        if paso["i"] % 3 == 0:
            face.guino()
        if paso["i"] % 5 == 0:
            face.bostezo()

    def medir():
        p = face.params
        alto = EYE_BASE_H * p["eye_l_open"] * face._muelle["sy"]
        print(f"t={paso['i']:>3}  apertura={p['eye_l_open']:.3f}  "
              f"scale_y={p['scale_y']:.3f}  muelle_sy={face._muelle['sy']:.3f}  "
              f"alto_px={alto:.1f}  anim_activas={len(face._active_anims)}")

    t_cambio = QTimer()
    t_cambio.timeout.connect(cambiar)
    t_cambio.start(3000)

    t_medir = QTimer()
    t_medir.timeout.connect(medir)
    t_medir.start(int(args.cada * 1000))

    def guardar():
        # Mismo tamaño y encuadre que el panel GC9A01 (240x240 desde 400x400).
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter
        img = QImage(240, 240, QImage.Format_RGB888)
        img.fill(0)
        pintor = QPainter(img)
        pintor.setRenderHint(QPainter.Antialiasing)
        escena.render(pintor, QRectF(0, 0, 240, 240), QRectF(0, 0, 400, 400))
        pintor.end()
        img.save(args.png)
        print(f"[PNG] guardado en {args.png}")

    if args.png:
        QTimer.singleShot(int(args.segundos * 1000) - 200, guardar)

    QTimer.singleShot(int(args.segundos * 1000), app.quit)
    app.exec()
    face.detener()


if __name__ == "__main__":
    main()
