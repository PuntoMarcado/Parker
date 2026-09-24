"""
Parker - Cara minimalista (vectores, PySide6)
--------------------------------------------------------
Estilo: fondo negro, ojos blancos tipo capsula, boca blanca curva.
Sin cejas ni piel salvo cuando hacen falta para aclarar una expresion
asimetrica (confundido, pensando).

FaceController es autonomo: en cuanto se crea, ya respira, parpadea
y "mira" un poco alrededor de vez en cuando por su cuenta (idle vivo,
inspirado en como Taby / heytaby.com mantiene su personaje siempre en
movimiento aunque no este reaccionando a nada). Quien lo usa (parker.py
o este mismo archivo como demo) solo tiene que llamar a
set_expression(nombre) cuando quiera cambiar de emocion.

Principios de animacion tomados como referencia de Taby, aplicados aqui
con parametros e interpolacion (QVariantAnimation), no con sprites:
  - Idle vivo: respiracion + parpadeo + micro-miradas laterales.
  - Anticipacion: en expresiones fuertes (feliz, sorpresa) hay un
    pequeno gesto "hacia atras" antes del cambio principal.
  - Overshoot/rebote: esas mismas expresiones se pasan un poco del
    valor final y rebotan de vuelta (QEasingCurve.OutBack).
  - Loops de personalidad por estado: "pensando" oscila la ceja muy
    sutilmente mientras dura, "carino" tiene un latido suave en la boca.

Requisitos:
    pip install PySide6
Ejecutar como demo aislada:
    python cara_parker.py
"""

import math
import random
import sys

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------
# Geometria base de la cara (en coordenadas de la escena)
# ---------------------------------------------------------------------
FACE_W, FACE_H = 400, 400
EYE_L_CENTER = QPointF(150, 170)
EYE_R_CENTER = QPointF(250, 170)
EYE_BASE_W, EYE_BASE_H = 38, 58
MOUTH_CENTER = QPointF(200, 260)
MOUTH_HALF_WIDTH = 46
EYEBROW_L_CENTER = QPointF(150, 142)
EYEBROW_R_CENTER = QPointF(250, 142)
EYEBROW_LEN = 30      # longitud del trazo de ceja
EYEBROW_ARC = 7        # profundidad de la curva (0 = recta)
EYEBROW_THICKNESS = 7   # grosor del trazo

WHITE = QColor("#FFFFFF")
BG_BLACK = QColor("#000000")

BREATH_AMPLITUDE_PX = 4.0
BREATH_PERIOD_MS = 4200.0


class FaceController:
    """
    Dueño de los items graficos de la cara y de sus parametros.
    Todo lo que la cara "es" en un instante dado vive en self.params.
    Ademas gestiona en solitario sus animaciones de fondo (respiracion,
    parpadeo, miradas) para que quien la usa no tenga que preocuparse
    de nada de eso.
    """

    DEFAULT_PARAMS = {
        "eye_l_open": 1.0,
        "eye_r_open": 1.0,
        "mouth_open": 0.0,
        "mouth_curve": 0.0,
        "eyebrow_l_raise": 0.0,
        "eyebrow_r_raise": 0.0,
        "eyebrow_l_angle": 0.0,
        "eyebrow_r_angle": 0.0,
        "eyebrow_opacity": 0.0,
    }

    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self.params = dict(self.DEFAULT_PARAMS)
        self._active_anims = []

        self.eye_l = QGraphicsPathItem()
        self.eye_r = QGraphicsPathItem()
        for eye in (self.eye_l, self.eye_r):
            eye.setBrush(QBrush(WHITE))
            eye.setPen(Qt.NoPen)
            scene.addItem(eye)

        brow_pen = QPen(WHITE, EYEBROW_THICKNESS, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.eyebrow_l = QGraphicsPathItem()
        self.eyebrow_r = QGraphicsPathItem()
        for brow in (self.eyebrow_l, self.eyebrow_r):
            brow.setPen(brow_pen)
            brow.setBrush(Qt.NoBrush)
            brow.setOpacity(0.0)
            scene.addItem(brow)

        self.mouth = QGraphicsPathItem()
        self.mouth.setBrush(QBrush(WHITE))
        self.mouth.setPen(Qt.NoPen)
        scene.addItem(self.mouth)

        self.group = scene.createItemGroup(
            [self.eye_l, self.eye_r, self.eyebrow_l, self.eyebrow_r, self.mouth]
        )

        self.redraw()

        # --- Estado interno para las animaciones de fondo ---
        self._current_expression = "neutral"
        self._breath_t = 0.0
        self._breath_y = 0.0
        self._look_x = 0.0
        self._loop_timer = None
        self._loop_t = 0

        self._breath_timer = QTimer()
        self._breath_timer.setInterval(30)
        self._breath_timer.timeout.connect(self._tick_respiracion)
        self._breath_timer.start()

        self._blink_timer = QTimer()
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._parpadeo_aleatorio)
        self._programar_parpadeo()

        self._glance_timer = QTimer()
        self._glance_timer.setSingleShot(True)
        self._glance_timer.timeout.connect(self._mirar_aleatorio)
        self._programar_mirada()

    # -----------------------------------------------------------------
    # Dibujo: reconstruye las formas a partir de self.params
    # -----------------------------------------------------------------
    def redraw(self):
        p = self.params

        def eye_path(center: QPointF, openness: float) -> QPainterPath:
            openness = max(0.04, openness)
            w = EYE_BASE_W
            h = EYE_BASE_H * openness
            rect = QRectF(center.x() - w / 2, center.y() - h / 2, w, h)
            path = QPainterPath()
            radius = min(w, h) / 2
            path.addRoundedRect(rect, radius, radius)
            return path

        self.eye_l.setPath(eye_path(EYE_L_CENTER, p["eye_l_open"]))
        self.eye_r.setPath(eye_path(EYE_R_CENTER, p["eye_r_open"]))

        def eyebrow_path(center: QPointF, raise_amount: float) -> QPainterPath:
            # Trazo curvo (como un arco muy sutil) en vez de una barra recta:
            # se lee como una ceja de verdad, no como una pastilla flotando.
            offset_y = -raise_amount * 14  # mas recorrido que antes (era *10)
            half = EYEBROW_LEN / 2
            cx, cy = center.x(), center.y() + offset_y
            path = QPainterPath(QPointF(cx - half, cy + EYEBROW_ARC / 2))
            path.quadTo(QPointF(cx, cy - EYEBROW_ARC / 2), QPointF(cx + half, cy + EYEBROW_ARC / 2))
            return path

        self.eyebrow_l.setPath(eyebrow_path(EYEBROW_L_CENTER, p["eyebrow_l_raise"]))
        self.eyebrow_l.setTransformOriginPoint(EYEBROW_L_CENTER)
        self.eyebrow_l.setRotation(p["eyebrow_l_angle"])
        self.eyebrow_l.setOpacity(p["eyebrow_opacity"])

        self.eyebrow_r.setPath(eyebrow_path(EYEBROW_R_CENTER, p["eyebrow_r_raise"]))
        self.eyebrow_r.setTransformOriginPoint(EYEBROW_R_CENTER)
        self.eyebrow_r.setRotation(p["eyebrow_r_angle"])
        self.eyebrow_r.setOpacity(p["eyebrow_opacity"])

        open_h = 6 + 40 * p["mouth_open"]
        curve = p["mouth_curve"]
        cx, cy = MOUTH_CENTER.x(), MOUTH_CENTER.y()
        corner_y = cy - curve * 14
        top_y = cy - open_h / 2
        bottom_y = cy + open_h / 2

        path = QPainterPath(QPointF(cx - MOUTH_HALF_WIDTH, corner_y))
        path.quadTo(QPointF(cx, top_y), QPointF(cx + MOUTH_HALF_WIDTH, corner_y))
        path.quadTo(QPointF(cx, bottom_y), QPointF(cx - MOUTH_HALF_WIDTH, corner_y))
        path.closeSubpath()
        self.mouth.setPath(path)

    # -----------------------------------------------------------------
    # Animacion generica: interpola self.params actuales -> target
    # -----------------------------------------------------------------
    def animate_to(self, target: dict, duration_ms: int = 350,
                    easing=QEasingCurve.InOutQuad):
        start = dict(self.params)
        merged_target = {**self.params, **target}

        anim = QVariantAnimation()
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(easing)

        def on_value_changed(t):
            for key, end_val in merged_target.items():
                start_val = start.get(key, end_val)
                self.params[key] = start_val + (end_val - start_val) * t
            self.redraw()

        anim.valueChanged.connect(on_value_changed)

        def on_finished():
            if anim in self._active_anims:
                self._active_anims.remove(anim)

        anim.finished.connect(on_finished)
        anim.start()
        self._active_anims.append(anim)

    def _tween_valor(self, get_fn, set_fn, valor_final, duration_ms=350,
                      easing=QEasingCurve.InOutQuad):
        """Interpola un valor suelto (no parametro de self.params), ej. el
        desplazamiento lateral de la mirada."""
        inicio = get_fn()
        anim = QVariantAnimation()
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(easing)
        anim.valueChanged.connect(lambda t: set_fn(inicio + (valor_final - inicio) * t))

        def on_finished():
            if anim in self._active_anims:
                self._active_anims.remove(anim)

        anim.finished.connect(on_finished)
        anim.start()
        self._active_anims.append(anim)

    # -----------------------------------------------------------------
    # Presets de expresion. Las claves coinciden con las etiquetas
    # [CARA:emocion] del SYSTEM_PROMPT (feliz, pensando, confundido,
    # sorpresa, neutral), mas "triste" y "carino" como extras.
    # -----------------------------------------------------------------
    _ANTICIPACION_EXPRESIONES = ("feliz", "sorpresa")
    _LOOP_EXPRESIONES = ("pensando", "carino")

    def _presets(self):
        return {
            "neutral": dict(eye_l_open=1.0, eye_r_open=1.0, mouth_curve=0.3, mouth_open=0.0,
                             eyebrow_opacity=0.0),
            "feliz": dict(eye_l_open=0.55, eye_r_open=0.55, mouth_curve=1.0, mouth_open=0.15,
                          eyebrow_opacity=0.0),
            "triste": dict(eye_l_open=0.7, eye_r_open=0.7, mouth_curve=-1.0, mouth_open=0.0,
                           eyebrow_opacity=0.0),
            "sorpresa": dict(eye_l_open=1.3, eye_r_open=1.3, mouth_curve=0.0, mouth_open=0.6,
                             eyebrow_opacity=0.0),
            "pensando": dict(eye_l_open=0.6, eye_r_open=0.9, mouth_curve=0.0, mouth_open=0.0,
                             eyebrow_l_raise=-0.2, eyebrow_r_raise=0.6,
                             eyebrow_l_angle=-8, eyebrow_r_angle=16,
                             eyebrow_opacity=1.0),
            "confundido": dict(eye_l_open=0.85, eye_r_open=0.45, mouth_curve=-0.2, mouth_open=0.05,
                               eyebrow_l_raise=0.55, eyebrow_r_raise=-0.4,
                               eyebrow_l_angle=14, eyebrow_r_angle=-16,
                               eyebrow_opacity=1.0),
            "carino": dict(eye_l_open=0.65, eye_r_open=0.65, mouth_curve=0.6, mouth_open=0.08,
                           eyebrow_opacity=0.0),
        }

    def _preset_anticipo(self, target: dict) -> dict:
        """Pequeno gesto 'hacia atras' antes de una expresion fuerte,
        para que el cambio principal se sienta con mas peso."""
        return {
            "mouth_open": max(0.0, self.params.get("mouth_open", 0.0) - 0.08),
            "eye_l_open": max(0.1, self.params.get("eye_l_open", 1.0) * 0.85),
            "eye_r_open": max(0.1, self.params.get("eye_r_open", 1.0) * 0.85),
        }

    def set_expression(self, name: str):
        presets = self._presets()
        target = presets.get(name, presets["neutral"])
        resolved_name = name if name in presets else "neutral"

        self._current_expression = resolved_name
        self._detener_loop_micro()

        if resolved_name in self._ANTICIPACION_EXPRESIONES:
            anticipo = self._preset_anticipo(target)
            self.animate_to(anticipo, duration_ms=70, easing=QEasingCurve.InQuad)
            QTimer.singleShot(70, lambda: self.animate_to(
                target, duration_ms=380, easing=QEasingCurve.OutBack))
        else:
            self.animate_to(target, duration_ms=400)

        if resolved_name in self._LOOP_EXPRESIONES:
            self._iniciar_loop_micro(resolved_name)

    # -----------------------------------------------------------------
    # Loops de personalidad: mientras se mantiene una expresion como
    # "pensando" o "carino", hay un movimiento sutil constante en vez
    # de una pose totalmente fija.
    # -----------------------------------------------------------------
    def _iniciar_loop_micro(self, expresion: str):
        self._loop_t = 0
        self._loop_timer = QTimer()

        if expresion == "pensando":
            self._loop_timer.setInterval(900)

            def tick():
                self._loop_t += 1
                variacion = 0.15 * math.sin(self._loop_t * 0.8)
                self.animate_to({"eyebrow_r_raise": 0.6 + variacion},
                                 duration_ms=850, easing=QEasingCurve.InOutSine)
        else:  # "carino": latido suave en la boca
            self._loop_timer.setInterval(700)

            def tick():
                self._loop_t += 1
                pulso = 0.05 + 0.05 * abs(math.sin(self._loop_t * 1.2))
                self.animate_to({"mouth_open": pulso},
                                 duration_ms=650, easing=QEasingCurve.InOutSine)

        self._loop_timer.timeout.connect(tick)
        self._loop_timer.start()
        tick()

    def _detener_loop_micro(self):
        if self._loop_timer is not None:
            self._loop_timer.stop()
            self._loop_timer = None

    # -----------------------------------------------------------------
    # Parpadeo automatico, con intervalo aleatorio cada vez (idle vivo)
    # -----------------------------------------------------------------
    def _programar_parpadeo(self):
        self._blink_timer.start(random.randint(2500, 6000))

    def _parpadeo_aleatorio(self):
        self.blink()
        self._programar_parpadeo()

    def blink(self):
        base_l = self.params["eye_l_open"]
        base_r = self.params["eye_r_open"]
        self.animate_to({"eye_l_open": 0.05, "eye_r_open": 0.05},
                         duration_ms=90, easing=QEasingCurve.OutQuad)
        QTimer.singleShot(110, lambda: self.animate_to(
            {"eye_l_open": base_l, "eye_r_open": base_r},
            duration_ms=140, easing=QEasingCurve.OutBack))

    # -----------------------------------------------------------------
    # Respiracion sutil + mirada lateral ocasional (idle vivo). Ambas
    # comparten la posicion del grupo, por eso se combinan en un mismo
    # punto (_look_x, _breath_y) en vez de pisarse entre si.
    # -----------------------------------------------------------------
    def _tick_respiracion(self):
        self._breath_t += self._breath_timer.interval()
        angle = (2 * math.pi) * (self._breath_t / BREATH_PERIOD_MS)
        self._breath_y = BREATH_AMPLITUDE_PX * math.sin(angle)
        self.group.setPos(self._look_x, self._breath_y)

    def _set_look_x(self, valor: float):
        self._look_x = valor
        self.group.setPos(self._look_x, self._breath_y)

    def _programar_mirada(self):
        self._glance_timer.start(random.randint(4000, 9000))

    def _mirar_aleatorio(self):
        objetivo = random.uniform(-6, 6)
        self._tween_valor(lambda: self._look_x, self._set_look_x, objetivo, duration_ms=400)
        QTimer.singleShot(900, lambda: self._tween_valor(
            lambda: self._look_x, self._set_look_x, 0.0, duration_ms=400))
        self._programar_mirada()

    # -----------------------------------------------------------------
    # Punto de enganche para el futuro lip-sync: llamar muchas veces
    # por segundo con el volumen (0..1) o con el visema actual.
    # -----------------------------------------------------------------
    def set_mouth_open(self, value: float, duration_ms: int = 80):
        self.animate_to({"mouth_open": max(0.0, min(1.0, value))},
                         duration_ms=duration_ms, easing=QEasingCurve.OutQuad)


class MainWindow(QMainWindow):
    """Ventana de demo aislada, con botones manuales para probar expresiones.
    La respiracion, el parpadeo y las miradas ya las gestiona FaceController
    solo, no hace falta nada mas aqui."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parker - demo de cara")
        self.setStyleSheet("background-color: black;")

        central = QWidget()
        central.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(central)

        self.scene = QGraphicsScene(0, 0, FACE_W, FACE_H)
        self.scene.setBackgroundBrush(QBrush(BG_BLACK))

        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("border: none; background-color: black;")
        self.view.setFixedSize(FACE_W + 4, FACE_H + 4)
        layout.addWidget(self.view)

        self.face = FaceController(self.scene)

        buttons_row = QHBoxLayout()
        for label, expr in [("Neutral", "neutral"), ("Feliz", "feliz"),
                            ("Triste", "triste"), ("Sorpresa", "sorpresa"),
                            ("Pensando", "pensando"), ("Confundido", "confundido"),
                            ("Cariño", "carino")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, e=expr: self.face.set_expression(e))
            buttons_row.addWidget(btn)

        self.blink_btn = QPushButton("Parpadear")
        self.blink_btn.clicked.connect(lambda: self.face.blink())
        buttons_row.addWidget(self.blink_btn)

        self.talk_btn = QPushButton("Simular hablar (on/off)")
        self.talk_btn.setCheckable(True)
        self.talk_btn.toggled.connect(self.toggle_talking)
        buttons_row.addWidget(self.talk_btn)

        layout.addLayout(buttons_row)
        self.setCentralWidget(central)

        self.talk_timer = QTimer(self)
        self.talk_timer.setInterval(90)
        self.talk_timer.timeout.connect(
            lambda: self.face.set_mouth_open(random.uniform(0.0, 0.9))
        )

    def toggle_talking(self, checked: bool):
        if checked:
            self.talk_timer.start()
        else:
            self.talk_timer.stop()
            self.face.set_mouth_open(0.0)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()