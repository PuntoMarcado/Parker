"""
Parker - Cara vectorial dinámica (PySide6) - Edición Animación Disney
===================================================================
Incorpora el "Alive Motion Engine" (motor de vida orgánica continua),
Principios de Animación Disney (Squash & Stretch, Anticipación, Rebotado,
Micro-acciones secundarias y animación de habla/lip-sync).

Los 12 principios de la animación (Thomas y Johnston) están aplicados uno a uno
y mapeados en el diccionario `PRINCIPIOS` de este módulo — ese diccionario es la
lista de comprobación: `tests/test_animacion.py` verifica que los 12 siguen ahí
y que cada uno tiene código detrás.

  1. Squash y Stretch ..... respiración, anticipación y estiramiento al despertar
  2. Anticipación ......... gesto previo contrario antes de cada cambio
  3. Puesta en escena ..... la cara siempre legible: frontal, centrada, un foco
  4. Pose a pose .......... llegar a la pose clave y luego romperla (no solo
                            interpolación lineal continua)
  5. Continuación y superposición ... muelle de inercia + grupos desfasados
  6. Entradas y salidas suaves ..... QEasingCurve distinto por fase
  7. Arcos ................ la mirada viaja en arco (x rápido, y lento)
  8. Acción secundaria .... cejas y cabeza acompañan parpadeo y habla
  9. Timing ............... duraciones con jitter: nada se repite igual
 10. Exageración .......... parámetro `exageracion` que escala la desviación
                            respecto a la pose neutra
 11. Dibujo sólido ........ geometría por curvas y radios coherentes
 12. Atractivo ............ asimetría, muletillas gestuales propias (guiño,
                            bostezo, doble toma) y poses que apetece mirar
"""

import math
import random
import sys

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QPainterPath, QTransform
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

# Mapa de los 12 principios → dónde vive cada uno en este módulo. Es la tabla
# que usa `tests/test_animacion.py` para que no se pierda ninguno por el camino.
PRINCIPIOS = {
    "squash_stretch": "respiración (_tick_alive_engine) + anticipación y estiramiento en set_expression/reproducir_intro",
    "anticipacion": "set_expression (fase 1) y gestos (asentir, negar, doble_toma)",
    "puesta_en_escena": "pose neutra frontal, un solo foco (ojos), pose_de_escucha",
    "pose_a_pose": "_presets() como poses clave + _lanzar_tween como interpolación",
    "continuacion_superposicion": "muelle de inercia (_integrar_muelle) y GRUPOS_ANIMACION",
    "entradas_salidas": "QEasingCurve por fase (InQuad, OutBack, OutExpo, InOutSine)",
    "arcos": "_mirar_aleatorio: sacada horizontal rápida con recorrido vertical lento",
    "accion_secundaria": "cejas en el parpadeo y micro-inclinación de cabeza al hablar",
    "timing": "random.randint/uniform en duraciones y retardos (jitter)",
    "exageracion": "parámetro `exageracion` de set_expression y de reaccion_rapida",
    "dibujo_solido": "eye_path/eyebrow_path con rectángulos redondeados y radios coherentes",
    "atractivo": "asimetría en las poses, muletillas propias (guiño, bostezo, doble toma, cabezada) y el director de gestos en reposo",
}

FACE_W, FACE_H = 400, 400
EYE_L_CENTER = QPointF(150, 170)
EYE_R_CENTER = QPointF(250, 170)
EYE_BASE_W, EYE_BASE_H = 38, 58
# Techo de apertura del ojo: 1.0 = 38x58 exactos. Por encima, el dibujo se
# convierte en una cápsula más alta que ancha y el ojo parece «alargarse»
# (visto en la placa 25/10: ojos cada vez más largos). La sorpresa se expresa
# con cejas, boca y la escala del grupo, no estirando el ojo.
EYE_OPEN_MAX = 1.0

# Red de seguridad de kiosco: la cara vive semanas encendida. Cada parámetro
# tiene su rango; si un gesto lo deja fuera (o se acumula por un tween a medias)
# se corrige en el latido y queda anotado en el log.
LIMITES_PARAMS = {
    "eye_l_open": (0.04, EYE_OPEN_MAX),
    "eye_r_open": (0.04, EYE_OPEN_MAX),
    "mouth_open": (0.0, 1.0),
    "mouth_curve": (-1.0, 1.0),
    "eyebrow_l_raise": (-0.6, 1.2),
    "eyebrow_r_raise": (-0.6, 1.2),
    "eyebrow_l_angle": (-30.0, 30.0),
    "eyebrow_r_angle": (-30.0, 30.0),
    "eyebrow_opacity": (0.0, 1.0),
    "head_tilt": (-18.0, 18.0),
    "scale_x": (0.80, 1.25),
    "scale_y": (0.75, 1.25),
}
MOUTH_CENTER = QPointF(200, 260)
MOUTH_HALF_WIDTH = 46
EYEBROW_L_CENTER = QPointF(150, 128)
EYEBROW_R_CENTER = QPointF(250, 128)
EYEBROW_W, EYEBROW_H = 34, 8

# --- Director de gestos en reposo (v6.8.0, 27/10/2026) ---------------------
# Pedido: «que la cara tenga más dinamismo cuando está callado y no escucha
# nada». Hasta aquí el reposo era flotar + parpadear + mirar de vez en cuando,
# y eso se lee como una foto que respira: falta que PASE algo. El director
# elige un gesto cada pocos segundos y la FAMILIA cambia con el tiempo que
# lleves sin hablarle: recién hablado mira alrededor, a los minutos se pone a
# pensar y con mucho silencio se le nota el aburrimiento y el sueño (bostezos
# y cabezadas), que es lo que hace que mirarlo cuente algo.
# Los números son pesos relativos dentro de cada familia: para quitar un gesto
# se borra su entrada, y para hacerlo más raro se le baja el peso.
FAMILIAS_GESTOS = {
    "despierto": {"micro_ceja": 3, "curiosear": 3, "doble_toma": 2,
                  "asentir": 2, "negar": 1},
    "solo":      {"mirar_arriba": 4, "curiosear": 3, "micro_ceja": 2,
                  "cabecear": 2, "asentir": 1, "guino": 1, "bostezo": 1},
    "aburrido":  {"bostezo": 4, "cabecear": 4, "suspirar": 3, "estiron": 2,
                  "mirar_arriba": 2, "guino": 1},
}
# Silencio (segundos) que separa una familia de la siguiente.
GESTOS_SOLO_SEG = 90.0        # 1,5 min sin hablarle: deja de mirar «a ti»
GESTOS_ABURRIDO_SEG = 480.0   # 8 min: se le nota el sueño
# Cuánto se espera entre gesto y gesto, por familia (mínimo, máximo) en segundos.
PAUSA_GESTOS_SEG = {"despierto": (6.0, 13.0), "solo": (5.0, 11.0),
                    "aburrido": (4.0, 9.0)}

# --- Modo demo (02/11/2026) -------------------------------------------------
# «Parker, modo demo»: recorre UNA vez la intro, todas las expresiones y todos
# los gestos del catálogo, y vuelve solo a neutral. La lista de gestos se
# deriva de FAMILIAS_GESTOS para que un gesto nuevo entre en la demo sin tener
# que copiarlo en dos sitios. No cambia cerebro, oído ni voz: es solo la cara.
EXPRESIONES_DEMO = ("neutral", "feliz", "triste", "sorpresa", "pensando",
                    "confundido", "escuchando", "carino")
GESTOS_DEMO = tuple(dict.fromkeys(
    gesto for familia in FAMILIAS_GESTOS.values() for gesto in familia))
DURACION_EXPRESION_DEMO_MS = 1900
DURACION_GESTOS_DEMO_MS = {
    "micro_ceja": 1000, "curiosear": 2400, "doble_toma": 1400,
    "asentir": 1100, "negar": 1200, "mirar_arriba": 2400,
    "cabecear": 1600, "guino": 900, "bostezo": 1800,
    "suspirar": 1700, "estiron": 1700,
}

WHITE = QColor("#FFFFFF")
BG_BLACK = QColor("#000000")

# --- Acción superpuesta (overlapping action) ---
# Cada grupo del rostro se mueve con su propio retardo y duración para que la
# cara nunca se mueva "en bloque" (aspecto mecánico). {grupo: (parámetros,
# retardo_ms, factor_duración)}
GRUPOS_ANIMACION = {
    "ojos":   (["eye_l_open", "eye_r_open"], 0, 1.0),
    "cabeza": (["head_tilt", "scale_x", "scale_y"], 40, 1.25),
    "boca":   (["mouth_open", "mouth_curve"], 65, 1.10),
    "cejas":  (["eyebrow_l_raise", "eyebrow_r_raise", "eyebrow_l_angle",
                "eyebrow_r_angle", "eyebrow_opacity"], 90, 1.15),
}


class FaceController:
    """
    Controlador autónomo de la cara de Parker estilo Disney.
    Mantiene a Parker constantemente vivo mediante micro-movimientos orgánicos,
    reacciones elásticas y sincronización de habla.
    """

    DEFAULT_PARAMS = {
        "eye_l_open": 1.0,
        "eye_r_open": 1.0,
        "mouth_open": 0.0,
        "mouth_curve": 0.3,
        "eyebrow_l_raise": 0.0,
        "eyebrow_r_raise": 0.0,
        "eyebrow_l_angle": 0.0,
        "eyebrow_r_angle": 0.0,
        "eyebrow_opacity": 0.0,
        "head_tilt": 0.0,       # Inclinación objetivo en grados
        "scale_x": 1.0,         # Deformación objetivo X
        "scale_y": 1.0,         # Deformación objetivo Y
    }

    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self.scene.setBackgroundBrush(QBrush(BG_BLACK))

        self.params = dict(self.DEFAULT_PARAMS)
        self._active_anims = []

        # Elementos gráficos
        self.eye_l = QGraphicsPathItem()
        self.eye_r = QGraphicsPathItem()
        for eye in (self.eye_l, self.eye_r):
            eye.setBrush(QBrush(WHITE))
            eye.setPen(Qt.NoPen)
            scene.addItem(eye)

        self.eyebrow_l = QGraphicsPathItem()
        self.eyebrow_r = QGraphicsPathItem()
        for brow in (self.eyebrow_l, self.eyebrow_r):
            brow.setBrush(QBrush(WHITE))
            brow.setPen(Qt.NoPen)
            brow.setOpacity(0.0)
            scene.addItem(brow)

        self.mouth = QGraphicsPathItem()
        self.mouth.setBrush(QBrush(WHITE))
        self.mouth.setPen(Qt.NoPen)
        scene.addItem(self.mouth)

        self.group = scene.createItemGroup(
            [self.eye_l, self.eye_r, self.eyebrow_l, self.eyebrow_r, self.mouth]
        )

        self._current_expression = "neutral"
        self._look_x = 0.0
        self._look_y = 0.0   # desplazamiento vertical: crea el arco de mirada
        # Cuánto lleva la persona sin hablarle (lo manda parker.py) y qué
        # familia de gestos se anunció ya en el log. Se define antes que los
        # timers porque el parpadeo ya consulta la familia al programarse.
        self._silencio_seg = 0.0
        self._familia_avisada = ""
        self._esta_hablando = False

        # Mientras el programa vive, los gestos programados con _programar()
        # siguen su curso; tras detener() se ignoran (cierre limpio de verdad).
        self._activo = True
        # Modo demo: identifica la tanda para que una demo nueva o detenida
        # invalide los pasos que ya estaban programados.
        self._demo_id = 0
        self._demo_activo = False

        # Muelle de inercia (Principio 5): el dibujo sigue al objetivo con
        # retardo y sobreimpulso. No toca `params`, así que la lógica y los
        # tests siguen viendo los valores exactos.
        self._muelle = {"tilt": 0.0, "vt": 0.0, "sx": 1.0, "vsx": 0.0, "sy": 1.0, "vsy": 0.0}

        # Variables del "Alive Motion Engine" (Ruido continuo)
        self._idle_t = random.uniform(0, 1000)
        self._idle_x = 0.0
        self._idle_y = 0.0
        self._idle_tilt = 0.0
        self._idle_scale_x = 1.0
        self._idle_scale_y = 1.0

        self._loop_timer = None
        self._loop_t = 0

        # Contador de latidos para la comprobación periódica de rangos.
        self._ticks = 0
        self._avisado_limites = False

        self.redraw()

        # Timer principal de movimiento orgánico (30 fps / ~33ms)
        self._idle_timer = QTimer()
        self._idle_timer.setInterval(33)
        self._idle_timer.timeout.connect(self._tick_alive_engine)
        self._idle_timer.start()

        # Timers viscerales/autónomos
        self._blink_timer = QTimer()
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._parpadeo_aleatorio)
        self._programar_parpadeo()

        self._glance_timer = QTimer()
        self._glance_timer.setSingleShot(True)
        self._glance_timer.timeout.connect(self._mirar_aleatorio)

        # Director de gestos en reposo: un gesto cada pocos segundos, de la
        # familia que toque según el silencio (lo manda parker.py).
        self._gesto_timer = QTimer()
        self._gesto_timer.setSingleShot(True)
        self._gesto_timer.timeout.connect(self._gesto_aleatorio)
        self._programar_gesto()
        self._programar_mirada()

        # Timer de animación de habla (Lip-Sync)
        self._talk_timer = QTimer()
        self._talk_timer.setInterval(110)
        self._talk_timer.timeout.connect(self._animar_fonemas_habla)

    def _tick_alive_engine(self):
        """Calcula variaciones orgánicas continuas (frecuencias superpuestas)"""
        self._idle_t += 33
        t = self._idle_t

        # 1. Flotación vertical y horizontal compuesta
        self._idle_y = math.sin(t * 0.0016) * 4.6 + math.sin(t * 0.0031) * 1.6
        self._idle_x = math.cos(t * 0.0011) * 3.2 + math.cos(t * 0.0007) * 1.0

        # 2. Micro-balanceo de cabeza involuntario
        self._idle_tilt = math.sin(t * 0.001) * 2.4 + math.cos(t * 0.0024) * 1.0

        # 3. Micro-respiración orgánica (Squash & Stretch sutil)
        self._idle_scale_y = 1.0 + 0.017 * math.sin(t * 0.0016)
        self._idle_scale_x = 1.0 - 0.012 * math.sin(t * 0.0016)

        # 4. Muelle de inercia (follow-through): la inclinación y la escala del
        #    dibujo persiguen su objetivo con retardo elástico, así que cuando
        #    la cara cambia de pose, se pasa un poco y vuelve (rebote natural).
        self._integrar_muelle(
            objetivo_tilt=self.params["head_tilt"] + self._idle_tilt,
            objetivo_sx=self.params["scale_x"] * self._idle_scale_x,
            objetivo_sy=self.params["scale_y"] * self._idle_scale_y,
            dt=0.033,
        )

        # Cada ~2 s (60 latidos a 30 fps): ningún parámetro puede quedarse
        # fuera de rango. Es lo que impide que los ojos «crezcan» tras horas.
        self._ticks += 1
        if self._ticks % 60 == 0:
            self._acotar_params()

        self.redraw()

    def _acotar_params(self):
        """Devuelve los parámetros a su rango si alguno se ha salido."""
        corregidos = []
        for clave, (minimo, maximo) in LIMITES_PARAMS.items():
            valor = self.params.get(clave)
            if valor is None or minimo <= valor <= maximo:
                continue
            self.params[clave] = min(max(valor, minimo), maximo)
            corregidos.append(f"{clave} {valor:.2f}->{self.params[clave]:.2f}")
        if corregidos and not self._avisado_limites:
            self._avisado_limites = True
            print("[Cara] Parámetros fuera de rango corregidos: " + ", ".join(corregidos))

    def _integrar_muelle(self, objetivo_tilt: float, objetivo_sx: float,
                         objetivo_sy: float, dt: float = 0.033,
                         rigidez: float = 90.0, amortiguacion: float = 12.0):
        """Integra un muelle amortiguado (segundo orden) para el dibujo.

        Rigidez alta + amortiguación moderada = llega rápido, se pasa un poco y
        se asienta: exactamente lo que hace una cabeza con masa. Este es el
        Principio 5 (continuación y superposición) y es lo que evita que la cara
        parezca pegada con silicona a la pose objetivo.
        """
        m = self._muelle
        for clave, v_clave, objetivo in (("tilt", "vt", objetivo_tilt),
                                         ("sx", "vsx", objetivo_sx),
                                         ("sy", "vsy", objetivo_sy)):
            aceleracion = rigidez * (objetivo - m[clave]) - amortiguacion * m[v_clave]
            m[v_clave] += aceleracion * dt
            m[clave] += m[v_clave] * dt

    def _programar(self, ms: int, fn):
        """`QTimer.singleShot` con guarda: después de `detener()` no corre nada."""
        def seguro():
            if self._activo:
                fn()
        QTimer.singleShot(ms, seguro)

    def redraw(self):
        p = self.params

        # Matriz de transformación global combinando postura + idle flotante
        transform = QTransform()
        center_x, center_y = FACE_W / 2.0, FACE_H / 2.0

        pos_x = self._look_x + self._idle_x
        pos_y = self._look_y + self._idle_y
        # Los valores "con inercia" del muelle son los que se dibujan, no los
        # instantáneos: de ahí sale el rebote de la cabeza al cambiar de pose.
        tilt_total = self._muelle["tilt"]
        sx_total = self._muelle["sx"]
        sy_total = self._muelle["sy"]

        transform.translate(pos_x, pos_y)
        transform.translate(center_x, center_y)
        transform.rotate(tilt_total)
        transform.scale(sx_total, sy_total)
        transform.translate(-center_x, -center_y)

        self.group.setTransform(transform)

        # Ojos
        def eye_path(center: QPointF, openness: float) -> QPainterPath:
            # El techo se aplica AL DIBUJAR: aunque algún preset o tween pida
            # más, el ojo nunca pasa de 38x58 y no puede verse «alargado».
            openness = min(max(0.04, openness), EYE_OPEN_MAX)
            w = EYE_BASE_W
            h = EYE_BASE_H * openness
            rect = QRectF(center.x() - w / 2, center.y() - h / 2, w, h)
            path = QPainterPath()
            radius = min(w, h) / 2
            path.addRoundedRect(rect, radius, radius)
            return path

        self.eye_l.setPath(eye_path(EYE_L_CENTER, p["eye_l_open"]))
        self.eye_r.setPath(eye_path(EYE_R_CENTER, p["eye_r_open"]))

        # Cejas
        def eyebrow_path(center: QPointF, raise_amount: float) -> QPainterPath:
            offset_y = -raise_amount * 10
            rect = QRectF(
                center.x() - EYEBROW_W / 2,
                center.y() + offset_y - EYEBROW_H / 2,
                EYEBROW_W, EYEBROW_H
            )
            path = QPainterPath()
            path.addRoundedRect(rect, EYEBROW_H / 2, EYEBROW_H / 2)
            return path

        self.eyebrow_l.setPath(eyebrow_path(EYEBROW_L_CENTER, p["eyebrow_l_raise"]))
        self.eyebrow_l.setTransformOriginPoint(EYEBROW_L_CENTER)
        self.eyebrow_l.setRotation(p["eyebrow_l_angle"])
        self.eyebrow_l.setOpacity(p["eyebrow_opacity"])

        self.eyebrow_r.setPath(eyebrow_path(EYEBROW_R_CENTER, p["eyebrow_r_raise"]))
        self.eyebrow_r.setTransformOriginPoint(EYEBROW_R_CENTER)
        self.eyebrow_r.setRotation(p["eyebrow_r_angle"])
        self.eyebrow_r.setOpacity(p["eyebrow_opacity"])

        # Boca
        open_h = 6 + 42 * p["mouth_open"]
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

    def animate_to(self, target: dict, duration_ms: int = 350,
                   easing=QEasingCurve.InOutQuad, estagger: bool = True):
        """
        Anima los parámetros indicados hacia `target`.

        Con `estagger=True` (por defecto) aplica ACCIÓN SUPERPUESTA: cada grupo
        del rostro (ojos, cabeza, boca, cejas) arranca con su propio retardo y
        duración en vez de moverse todo a la vez. Si el objetivo solo toca un
        grupo, o estagger=False, se anima todo junto (útil para lip-sync).
        """
        objetivo = {k: v for k, v in target.items()}

        grupos = []
        for _nombre, (claves, retardo, factor) in GRUPOS_ANIMACION.items():
            afectadas = [k for k in claves if k in objetivo]
            if afectadas:
                grupos.append((afectadas, retardo, factor))

        if not estagger or len(grupos) <= 1:
            self._lanzar_tween(objetivo, duration_ms, easing)
            return

        for claves, retardo, factor in grupos:
            sub = {k: objetivo[k] for k in claves}
            # Jitter: dos movimientos nunca duran exactamente lo mismo
            dur = max(60, int(duration_ms * factor * random.uniform(0.92, 1.08)))
            if retardo <= 0:
                self._lanzar_tween(sub, dur, easing)
            else:
                # El retardo captura los valores de partida al ejecutarse,
                # para no saltar desde una instantánea obsoleta.
                QTimer.singleShot(retardo,
                                  lambda s=sub, d=dur, e=easing: self._lanzar_tween(s, d, e))

    def _lanzar_tween(self, target: dict, duration_ms: int, easing):
        """Tween real: solo escribe las claves que anima, para no pisar a otros."""
        start = {k: self.params.get(k, v) for k, v in target.items()}

        anim = QVariantAnimation()
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(easing)

        def on_value_changed(t):
            for key, end_val in target.items():
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

    def _tween_valor(self, get_fn, set_fn, valor_final, duration_ms=350, easing=QEasingCurve.InOutQuad):
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

    def _presets(self):
        return {
            "neutral": dict(
                eye_l_open=1.0, eye_r_open=1.0, mouth_curve=0.3, mouth_open=0.0,
                eyebrow_opacity=0.0, head_tilt=0.0, scale_x=1.0, scale_y=1.0
            ),
            "feliz": dict(
                eye_l_open=0.55, eye_r_open=0.55, mouth_curve=1.0, mouth_open=0.18,
                eyebrow_opacity=0.0, head_tilt=-3.5, scale_x=1.06, scale_y=0.94
            ),
            "triste": dict(
                eye_l_open=0.65, eye_r_open=0.65, mouth_curve=-1.0, mouth_open=0.0,
                eyebrow_opacity=0.0, head_tilt=-4.0, scale_x=0.95, scale_y=1.03
            ),
            "sorpresa": dict(
                # Ojos a 1.0 (el máximo que existe): la sorpresa la cuentan la
                # boca abierta, el estirón vertical y las cejas.
                eye_l_open=1.0, eye_r_open=1.0, mouth_curve=0.0, mouth_open=0.75,
                eyebrow_opacity=0.0, head_tilt=0.0, scale_x=0.88, scale_y=1.16
            ),
            "pensando": dict(
                eye_l_open=0.6, eye_r_open=0.9, mouth_curve=0.0, mouth_open=0.0,
                eyebrow_l_raise=-0.1, eyebrow_r_raise=0.4,
                eyebrow_l_angle=-5, eyebrow_r_angle=12,
                eyebrow_opacity=1.0, head_tilt=-8.0, scale_x=0.98, scale_y=1.02
            ),
            "confundido": dict(
                eye_l_open=0.9, eye_r_open=0.45, mouth_curve=-0.2, mouth_open=0.05,
                eyebrow_l_raise=0.35, eyebrow_r_raise=-0.2,
                eyebrow_l_angle=10, eyebrow_r_angle=-12,
                eyebrow_opacity=1.0, head_tilt=9.0, scale_x=1.02, scale_y=0.98
            ),
            "escuchando": dict(
                eye_l_open=1.0, eye_r_open=1.0, mouth_curve=0.4, mouth_open=0.02,
                eyebrow_opacity=0.0, head_tilt=5.0, scale_x=1.03, scale_y=1.03
            ),
            "carino": dict(
                eye_l_open=0.65, eye_r_open=0.65, mouth_curve=0.7, mouth_open=0.08,
                eyebrow_opacity=0.0, head_tilt=-5.0, scale_x=1.04, scale_y=0.96
            ),
        }

    def set_expression(self, name: str, exageracion: float = 1.0,
                       con_anticipacion: bool = True):
        """Aplica una expresión (pose a pose) con anticipación y rebote.

        `exageracion` (Principio 10) escala la desviación respecto a la pose
        neutra: 1.0 la deja tal cual, 1.3 la exagera y 0.7 la suaviza. Sirve
        para reaccionar más o menos según el contexto (una broma frente a una
        mala noticia).
        `con_anticipacion=False` salta la fase previa: útil para respuestas que
        deben ser instantáneas (un susto).
        """
        presets = self._presets()
        neutral = presets["neutral"]
        crudo = presets.get(name, presets["neutral"])
        target = {}
        for clave, valor in crudo.items():
            referencia = neutral.get(clave, self.DEFAULT_PARAMS.get(clave, valor))
            target[clave] = referencia + (valor - referencia) * exageracion
        resolved_name = name if name in presets else "neutral"

        self._current_expression = resolved_name
        self._detener_loop_micro()

        # FASE 1: Anticipación (Squash previo antes del cambio expansivo)
        #         El gesto previo va en DIRECCIÓN CONTRARIA al cambio final, que es
        #         lo que hace que el movimiento se lea venir. Duración con jitter.
        dur_anticipacion = 0
        if con_anticipacion:
            dur_anticipacion = random.randint(55, 95)
            anticipacion = {
                "scale_x": 1.08,
                "scale_y": 0.90,
                "head_tilt": self.params.get("head_tilt", 0.0)
                             + (3.0 if target["head_tilt"] < 0 else -3.0)
            }
            self.animate_to(anticipacion, duration_ms=dur_anticipacion,
                            easing=QEasingCurve.InQuad)

        # FASE 2: Snap elástico a la expresión final (OutBack = rebote con
        #         sobreimpulso) con acción superpuesta entre grupos.
        dur_snap = random.randint(340, 440)
        self._programar(dur_anticipacion + random.randint(5, 25),
                        lambda: self.animate_to(
                            target, duration_ms=dur_snap,
                            easing=QEasingCurve.OutBack))

        if resolved_name in ("pensando", "carino"):
            self._iniciar_loop_micro(resolved_name)

    def _iniciar_loop_micro(self, expresion: str):
        self._loop_t = 0
        self._loop_timer = QTimer()

        if expresion == "pensando":
            self._loop_timer.setInterval(750)
            def tick():
                self._loop_t += 1
                var_tilt = -8.0 + 3.0 * math.sin(self._loop_t * 0.7)
                self.animate_to({"head_tilt": var_tilt}, duration_ms=700, easing=QEasingCurve.InOutSine)
        else:
            self._loop_timer.setInterval(600)
            def tick():
                self._loop_t += 1
                pulso = 0.04 + 0.05 * abs(math.sin(self._loop_t * 1.2))
                self.animate_to({"mouth_open": pulso}, duration_ms=550, easing=QEasingCurve.InOutSine)

        self._loop_timer.timeout.connect(tick)
        self._loop_timer.start()

    def _detener_loop_micro(self):
        if self._loop_timer is not None:
            self._loop_timer.stop()
            self._loop_timer = None

    def detener(self):
        """Para todos los temporizadores: cierre limpio del programa.

        `_activo = False` además invalida los gestos ya programados con
        `_programar()` (guiño, bostezo, intro...), para que ninguno intente
        animar una escena que ya se está cerrando.
        """
        self._activo = False
        self._demo_activo = False
        self._demo_id += 1
        for timer in (self._idle_timer, self._blink_timer,
                      self._glance_timer, self._talk_timer,
                      self._gesto_timer):
            timer.stop()
        self._detener_loop_micro()

    # --- MODO DEMO: todas las expresiones y gestos, una vez -----------------
    def _programar_demo(self, demo_id: int, ms: int, fn) -> None:
        """Programa un paso de la demo solo si sigue siendo la demo actual."""
        def paso():
            if self._activo and self._demo_id == demo_id:
                fn()
        QTimer.singleShot(ms, paso)

    def modo_demo(self, al_terminar=None) -> int:
        """Muestra la intro, las 8 expresiones y los 11 gestos del catálogo.

        Devuelve la duración total en ms. Si ya hay una demo en marcha no
        arranca otra: se evita que dos secuencias se pisen. Al terminar vuelve
        a neutral y devuelve el control al director de gestos en reposo.
        """
        if not self._activo or self._demo_activo:
            return 0
        self._demo_activo = True
        self._demo_id += 1
        demo_id = self._demo_id
        self._gesto_timer.stop()
        self._glance_timer.stop()
        self._detener_loop_micro()
        print(f"[Cara] Modo demo: intro + {len(EXPRESIONES_DEMO)} expresiones + "
              f"{len(GESTOS_DEMO)} gestos.")

        t = 0
        self._programar_demo(demo_id, t, self.reproducir_intro)
        t += 4500                     # la intro dura ~4,5 s
        for nombre in EXPRESIONES_DEMO:
            self._programar_demo(demo_id, t,
                                 lambda n=nombre: self._demo_expresion(n))
            t += DURACION_EXPRESION_DEMO_MS
        for nombre in GESTOS_DEMO:
            self._programar_demo(demo_id, t,
                                 lambda n=nombre: self._demo_gesto(n))
            t += DURACION_GESTOS_DEMO_MS.get(nombre, 1700)
        t += 1200                     # aire para que el último gesto cierre
        self._programar_demo(demo_id, t,
                             lambda: self._demo_fin(demo_id, al_terminar))
        return t

    def _demo_expresion(self, nombre: str) -> None:
        print(f"[Cara] Demo: expresión {nombre}")
        self.set_expression(nombre)

    def _demo_gesto(self, nombre: str) -> None:
        print(f"[Cara] Demo: gesto {nombre}")
        if not self.gesto(nombre):
            print(f"[Cara] Demo: el gesto {nombre} no se pudo ejecutar")

    def _demo_fin(self, demo_id: int, al_terminar=None) -> None:
        if not self._activo or demo_id != self._demo_id:
            return
        self._demo_activo = False
        self._demo_id += 1
        self.set_expression("neutral")
        self._programar_gesto()
        self._programar_mirada()
        print("[Cara] Modo demo terminado; vuelvo a la cara normal.")
        if al_terminar is not None:
            try:
                al_terminar()
            except Exception as e:
                print(f"[Cara] Error al cerrar el modo demo: {e}")

    def detener_demo(self) -> None:
        """Corta la demo y devuelve la cara a neutral (si sigue viva)."""
        if not self._demo_activo:
            return
        self._demo_activo = False
        self._demo_id += 1
        self._detener_loop_micro()
        if not self._activo:
            return
        self.set_expression("neutral", con_anticipacion=False)
        self._programar_gesto()
        self._programar_mirada()
        print("[Cara] Modo demo detenido; vuelvo a la cara normal.")

    # --- PARPADEO CON ACCIÓN SECUNDARIA ---
    def _programar_parpadeo(self):
        # Cuanto más rato lleva solo, más se le espacian los parpadeos (y más
        # pesados): es el mismo lenguaje que usa el director de gestos.
        if self.familia_gestos() == "aburrido":
            self._blink_timer.start(random.randint(3800, 8500))
        elif self.familia_gestos() == "solo":
            self._blink_timer.start(random.randint(2600, 6200))
        else:
            self._blink_timer.start(random.randint(2000, 5000))

    def _parpadeo_aleatorio(self):
        self.blink()
        if random.random() < 0.28:  # Probabilidad de doble parpadeo Disney
            QTimer.singleShot(260, self.blink)
        elif self.familia_gestos() == "aburrido" and random.random() < 0.35:
            # Solo y con sueño: un parpadeo largo en vez del doble parpadeo.
            QTimer.singleShot(220, lambda: self.blink(lento=True))
        self._programar_parpadeo()

    def blink(self, lento: bool = False):
        """
        Parpadeo orgánico (Timing): cierre rápido, apertura más lenta con
        sobreimpulso y las cejas acompañando como acción secundaria.
        Jitter en las duraciones para que no se repita idéntico.
        Con `lento=True` (sueño) todo va al doble de despacio: es el parpadeo
        pesado de quien lleva mucho rato sin hacer nada.
        """
        base_l = self.params["eye_l_open"]
        base_r = self.params["eye_r_open"]
        base_brow_l = self.params["eyebrow_l_raise"]
        base_brow_r = self.params["eyebrow_r_raise"]

        dur_cierre = random.randint(120, 175) if lento else random.randint(65, 90)
        dur_apertura = random.randint(240, 330) if lento else random.randint(130, 185)
        espera_apertura = dur_cierre + random.randint(8, 35)

        # Cierre rápido con bajada sutil de cejas (coreografiado a mano:
        # aquí NO queremos el retardo del estagger)
        self.animate_to({
            "eye_l_open": 0.04,
            "eye_r_open": 0.04,
            "eyebrow_l_raise": base_brow_l - 0.15,
            "eyebrow_r_raise": base_brow_r - 0.15
        }, duration_ms=dur_cierre, easing=QEasingCurve.OutQuad, estagger=False)

        # Apertura elástica con sobreimpulso
        QTimer.singleShot(espera_apertura, lambda: self.animate_to({
            "eye_l_open": base_l,
            "eye_r_open": base_r,
            "eyebrow_l_raise": base_brow_l,
            "eyebrow_r_raise": base_brow_r
        }, duration_ms=dur_apertura, easing=QEasingCurve.OutBack, estagger=False))

    # --- MIRADA Y SACCADES ---
    def _set_look_x(self, valor: float):
        self._look_x = valor
        self.redraw()

    def _programar_mirada(self):
        self._glance_timer.start(random.randint(3000, 7500))

    def _set_look_y(self, valor: float):
        self._look_y = valor
        self.redraw()

    def _mirar_aleatorio(self):
        """
        Mirada aleatoria con SACADAS + ARCO:
          - los ojos se mueven muy rápido (sacada, 140 ms con OutExpo),
          - el eje vertical va más lento → el recorrido dibuja un ARCO,
          - la cabeza los sigue con retardo (acción superpuesta).
        """
        objetivo_x = random.uniform(-12, 12)
        objetivo_y = random.uniform(-3.5, 3.5)
        tilt_asociado = -objetivo_x * 0.25

        # 1. Sacada ocular: rápido y con pequeño arco
        self._tween_valor(lambda: self._look_x, self._set_look_x, objetivo_x,
                          duration_ms=random.randint(120, 170), easing=QEasingCurve.OutExpo)
        self._tween_valor(lambda: self._look_y, self._set_look_y, objetivo_y,
                          duration_ms=260, easing=QEasingCurve.InOutSine)

        # 2. La cabeza arranca después (overlapping action)
        QTimer.singleShot(random.randint(140, 220), lambda: self.animate_to(
            {"head_tilt": tilt_asociado}, duration_ms=430, easing=QEasingCurve.InOutSine
        ))

        # 3. Regreso a la frontalidad tras un breve vistazo, también en arco
        def regresar():
            self._tween_valor(lambda: self._look_x, self._set_look_x, 0.0,
                              duration_ms=200, easing=QEasingCurve.OutQuad)
            self._tween_valor(lambda: self._look_y, self._set_look_y, 0.0,
                              duration_ms=380, easing=QEasingCurve.InOutSine)
            self.animate_to(
                {"head_tilt": self._presets().get(self._current_expression, {}).get("head_tilt", 0.0)},
                duration_ms=450, easing=QEasingCurve.InOutSine
            )

        QTimer.singleShot(random.randint(1000, 1600), regresar)
        self._programar_mirada()

    # --- CONTROL DE HABLA Y LIP-SYNC ---
    def iniciar_habla(self):
        """Activa la modulación dinámica de la boca mientras Piper TTS habla"""
        if not self._esta_hablando:
            self._esta_hablando = True
            self._talk_timer.start()

    def detener_habla(self):
        """Detiene la articulación y regresa a la boca base de la emoción actual"""
        self._esta_hablando = False
        self._talk_timer.stop()
        preset_actual = self._presets().get(self._current_expression, self._presets()["neutral"])
        self.animate_to({"mouth_open": preset_actual["mouth_open"]}, duration_ms=150)

    def _animar_fonemas_habla(self):
        """Simula fonemas variables para una dicción natural.

        La boca es el foco, pero no lo único que se mueve: cada cierto tiempo la
        cabeza acompaña el ritmo de las palabras (Principio 8, acción
        secundaria). Sin ese acompañamiento, la boca parece un títere.
        """
        apertura = random.choice([0.15, 0.45, 0.2, 0.7, 0.35, 0.8, 0.1])
        self.animate_to({"mouth_open": apertura}, duration_ms=90,
                        easing=QEasingCurve.Linear, estagger=False)
        if random.random() < 0.3:
            self.animate_to({"head_tilt": random.uniform(-2.2, 2.2)}, duration_ms=180,
                            easing=QEasingCurve.InOutSine, estagger=False)

    def set_mouth_open(self, value: float, duration_ms: int = 80):
        self.animate_to({"mouth_open": max(0.0, min(1.0, value))}, duration_ms=duration_ms, easing=QEasingCurve.OutQuad)

    # --- GESTOS EXPRESIVOS (atractivo: los detalles que hacen que apetezca mirar)
    def guino(self, ojo_izquierdo: bool = True):
        """Guiño: un ojo cierra y vuelve, el otro aguanta (asimetría = atractivo)."""
        clave = "eye_l_open" if ojo_izquierdo else "eye_r_open"
        base = self.params[clave]
        self.animate_to({clave: 0.05}, duration_ms=70,
                        easing=QEasingCurve.OutQuad, estagger=False)
        self._programar(170, lambda: self.animate_to(
            {clave: base}, duration_ms=140,
            easing=QEasingCurve.OutBack, estagger=False))

    def asentir(self, veces: int = 2):
        """Asentir con la cabeza: cada "sí" es un pequeño arco con rebote."""
        base = self.params.get("head_tilt", 0.0)
        for i in range(max(1, veces)):
            self._programar(i * 260, lambda b=base: self.animate_to(
                {"head_tilt": b + 4.0}, duration_ms=120,
                easing=QEasingCurve.OutQuad, estagger=False))
            self._programar(i * 260 + 140, lambda b=base: self.animate_to(
                {"head_tilt": b - 1.0}, duration_ms=200,
                easing=QEasingCurve.OutBack, estagger=False))

    def negar(self, veces: int = 2):
        """Negar girando la cabeza a un lado y a otro (con arco, no lineal)."""
        signos = [1.0, -1.0] * max(1, veces)
        for i, signo in enumerate(signos):
            self._programar(i * 230, lambda s=signo: self.animate_to(
                {"head_tilt": 7.0 * s}, duration_ms=170,
                easing=QEasingCurve.InOutSine, estagger=False))
            self._programar(i * 230 + 170, lambda s=signo: self._tween_valor(
                lambda: self._look_x, self._set_look_x, 8.0 * s,
                duration_ms=150, easing=QEasingCurve.OutQuad))
        self._programar(230 * len(signos) + 40, lambda: self._tween_valor(
            lambda: self._look_x, self._set_look_x, 0.0,
            duration_ms=220, easing=QEasingCurve.OutQuad))
        self._programar(230 * len(signos) + 60, lambda: self.animate_to(
            {"head_tilt": 0.0}, duration_ms=260, easing=QEasingCurve.OutBack,
            estagger=False))

    def bostezo(self):
        """Bostezo completo: anticipación (squash), expansión exagerada, cierre.

        Es el gesto con más "atractivo" de la cara: le pasa hasta cuando está
        solo, y por eso se siente vivo.
        """
        self.animate_to({"scale_x": 1.06, "scale_y": 0.92,
                         "mouth_open": 0.1}, duration_ms=180,
                        easing=QEasingCurve.InQuad, estagger=False)
        self._programar(200, lambda: self.animate_to(
            {"eye_l_open": 0.08, "eye_r_open": 0.08,
             "mouth_open": 0.95, "scale_x": 0.92, "scale_y": 1.12,
             "head_tilt": -6.0}, duration_ms=520, easing=QEasingCurve.OutBack,
            estagger=False))
        self._programar(980, lambda: self.animate_to(
            {"eye_l_open": 0.5, "eye_r_open": 0.5, "mouth_open": 0.15,
             "scale_x": 1.0, "scale_y": 1.0, "head_tilt": 0.0},
            duration_ms=520, easing=QEasingCurve.OutQuad, estagger=False))
        self._programar(1400, lambda: self.blink())

    def doble_toma(self, hacia: str = "izquierda"):
        """Doble toma: mira de reojo, se gira del todo, se queda y vuelve.

        Es el gesto que más "vida" transmite cuando llega algo inesperado: la
        mirada se anticipa a la cabeza, que llega tarde (superposición).
        """
        signo = -1.0 if hacia == "izquierda" else 1.0
        self._tween_valor(lambda: self._look_x, self._set_look_x, 16.0 * signo,
                          duration_ms=110, easing=QEasingCurve.OutExpo)
        self._programar(90, lambda: self.animate_to(
            {"head_tilt": 9.0 * signo}, duration_ms=260,
            easing=QEasingCurve.OutBack, estagger=False))
        self._programar(420, lambda: self._tween_valor(
            lambda: self._look_x, self._set_look_x, -9.0 * signo,
            duration_ms=140, easing=QEasingCurve.OutExpo))
        self._programar(700, lambda: self._tween_valor(
            lambda: self._look_x, self._set_look_x, 0.0,
            duration_ms=220, easing=QEasingCurve.OutQuad))
        self._programar(720, lambda: self.animate_to(
            {"head_tilt": 0.0}, duration_ms=300,
            easing=QEasingCurve.InOutSine, estagger=False))

    def reaccion_rapida(self, emocion: str, exageracion: float = 1.35):
        """Reacción instantánea: sin anticipación y con la pose exagerada.

        Para cuando algo interrumpe (una tos, un ruido): reaccionar rápido y
        exagerado y luego asentarse se lee como sorpresa de verdad.
        """
        self.set_expression(emocion, exageracion=exageracion, con_anticipacion=False)
        self._programar(700, lambda: self.set_expression(emocion, exageracion=1.0))

    def pose_de_escucha(self):
        """Pose de escucha activa (puesta en escena): se inclina hacia ti."""
        self.animate_to({"head_tilt": 5.0, "eye_l_open": 1.0,
                         "eye_r_open": 1.0, "mouth_curve": 0.4},
                        duration_ms=320, easing=QEasingCurve.OutBack)

    # --- DIRECTOR DE GESTOS EN REPOSO (v6.8.0) -------------------------------
    def set_silencio(self, segundos: float) -> None:
        """Cuánto lleva la persona sin hablarle (lo manda parker.py cada ~30 s)."""
        try:
            valor = max(0.0, float(segundos))
        except (TypeError, ValueError):
            valor = 0.0
        self._silencio_seg = valor
        familia = self.familia_gestos()
        if familia != self._familia_avisada:
            # Solo se escribe en el log al CAMBIAR de familia: si se dijera en
            # cada gesto, esto serían cientos de líneas por hora en la placa.
            self._familia_avisada = familia
            print(f"[Cara] Gestos en reposo: familia {familia} (silencio {valor:.0f}s)")

    def familia_gestos(self) -> str:
        """Despierto / solo / aburrido según el tiempo que lleve sin hablarle."""
        if self._silencio_seg < GESTOS_SOLO_SEG:
            return "despierto"
        if self._silencio_seg < GESTOS_ABURRIDO_SEG:
            return "solo"
        return "aburrido"

    def gesto(self, nombre: str) -> bool:
        """Ejecuta un gesto del catálogo por su nombre (`False` si no existe)."""
        catalogo = {g for familia in FAMILIAS_GESTOS.values() for g in familia}
        nombre = str(nombre or "").strip()
        if not self._activo or nombre not in catalogo:
            return False
        metodo = getattr(self, nombre, None)
        if not callable(metodo):
            print(f"[Cara] AVISO: el gesto '{nombre}' está en el catálogo pero no existe")
            return False
        metodo()
        return True

    def _programar_gesto(self) -> None:
        """Programa el siguiente gesto de reposo (la pausa depende de la familia)."""
        minimo, maximo = PAUSA_GESTOS_SEG.get(self.familia_gestos(), (6.0, 13.0))
        self._gesto_timer.start(int(random.uniform(minimo, maximo) * 1000))

    def _gesto_aleatorio(self) -> str | None:
        """Gesto de reposo al azar para el silencio actual. Devuelve su nombre."""
        self._programar_gesto()          # se reagenda pase lo que pase
        if not self._activo or self._esta_hablando or self._loop_timer is not None:
            # Hablando manda el lip-sync; y una expresión con micro-loop
            # («pensando») ya se mueve sola, así que no se le pone nada encima.
            return None
        familia = FAMILIAS_GESTOS.get(self.familia_gestos()) or FAMILIAS_GESTOS["despierto"]
        nombre = random.choices(list(familia), weights=list(familia.values()), k=1)[0]
        return nombre if self.gesto(nombre) else None

    def _pose_base(self) -> dict:
        """La pose de la expresión actual: a donde tiene que volver cada gesto."""
        presets = self._presets()
        return presets.get(self._current_expression, presets["neutral"])

    def _volver_al_frente(self) -> None:
        """Devuelve la mirada y la cabeza a la frontalidad (fin de un vistazo)."""
        self._tween_valor(lambda: self._look_x, self._set_look_x, 0.0,
                          duration_ms=230, easing=QEasingCurve.OutQuad)
        self._tween_valor(lambda: self._look_y, self._set_look_y, 0.0,
                          duration_ms=380, easing=QEasingCurve.InOutSine)
        self.animate_to({"head_tilt": self._pose_base().get("head_tilt", 0.0)},
                        duration_ms=450, easing=QEasingCurve.InOutSine)

    # --- Gestos del catálogo (los usa el director y también la voz) -----------
    def micro_ceja(self):
        """«¿Eh?»: sube las cejas un instante y las deja caer.

        Es el gesto más pequeño del catálogo y el que más se nota cuando nadie
        le habla: parece que acaba de pensar algo por su cuenta.
        """
        ceja_l = self.params["eyebrow_l_raise"]
        ceja_r = self.params["eyebrow_r_raise"]
        opacidad = self.params["eyebrow_opacity"]
        base = self._pose_base()
        self.animate_to({"eyebrow_l_raise": ceja_l + 0.4, "eyebrow_r_raise": ceja_r + 0.4,
                         "eyebrow_opacity": max(opacidad, 0.8),
                         "head_tilt": base.get("head_tilt", 0.0) - 1.5},
                        duration_ms=130, easing=QEasingCurve.OutQuad, estagger=False)
        self._programar(240, lambda cl=ceja_l, cr=ceja_r, op=opacidad,
                        b=base.get("head_tilt", 0.0): self.animate_to(
            {"eyebrow_l_raise": cl, "eyebrow_r_raise": cr, "eyebrow_opacity": op,
             "head_tilt": b},
            duration_ms=430, easing=QEasingCurve.OutBack, estagger=False))

    def curiosear(self, hacia: str | None = None):
        """Mira a un lado, se queda un momento mirando y vuelve al frente."""
        self._detener_loop_micro()
        signo = (random.choice((-1.0, 1.0)) if hacia is None
                 else (-1.0 if str(hacia).lower().startswith("izq") else 1.0))
        self._tween_valor(lambda: self._look_x, self._set_look_x, 15.0 * signo,
                          duration_ms=240, easing=QEasingCurve.OutExpo)
        self._tween_valor(lambda: self._look_y, self._set_look_y, 2.0,
                          duration_ms=430, easing=QEasingCurve.InOutSine)
        self._programar(150, lambda s=signo: self.animate_to(
            {"head_tilt": -4.0 * s}, duration_ms=420,
            easing=QEasingCurve.InOutSine, estagger=False))
        self._programar(random.randint(900, 1800), self._volver_al_frente)

    def mirar_arriba(self):
        """Pensando: mira arriba y a un lado con las cejas y vuelve con parpadeo."""
        self._detener_loop_micro()
        signo = random.choice((-1.0, 1.0))
        ceja_l = self.params["eyebrow_l_raise"]
        ceja_r = self.params["eyebrow_r_raise"]
        opacidad = self.params["eyebrow_opacity"]
        self._tween_valor(lambda: self._look_x, self._set_look_x, 9.0 * signo,
                          duration_ms=260, easing=QEasingCurve.OutExpo)
        self._tween_valor(lambda: self._look_y, self._set_look_y, -5.0,
                          duration_ms=450, easing=QEasingCurve.InOutSine)
        self.animate_to({"eyebrow_l_raise": ceja_l + 0.25, "eyebrow_r_raise": ceja_r + 0.5,
                         "eyebrow_l_angle": 4.0 * signo, "eyebrow_r_angle": 9.0 * signo,
                         "eyebrow_opacity": max(opacidad, 0.75),
                         "head_tilt": -5.0 * signo},
                        duration_ms=420, easing=QEasingCurve.OutBack)
        self._programar(random.randint(1100, 2100),
                        lambda cl=ceja_l, cr=ceja_r, op=opacidad: self._volver_de_pensar(cl, cr, op))

    def _volver_de_pensar(self, ceja_l: float, ceja_r: float, opacidad: float) -> None:
        """Cierre del gesto de pensar: vuelve al frente y parpadea como al aterrizar."""
        base = self._pose_base()
        self._volver_al_frente()
        self.animate_to({"eyebrow_l_raise": ceja_l, "eyebrow_r_raise": ceja_r,
                         "eyebrow_l_angle": base.get("eyebrow_l_angle", 0.0),
                         "eyebrow_r_angle": base.get("eyebrow_r_angle", 0.0),
                         "eyebrow_opacity": opacidad},
                        duration_ms=380, easing=QEasingCurve.InOutSine, estagger=False)
        self._programar(420, self.blink)

    def cabecear(self, veces: int = 2):
        """Cabezada de sueño: la cabeza se vence, se endereza y los ojos se entornan."""
        base_tilt = self.params["head_tilt"]
        ojo_l, ojo_r = self.params["eye_l_open"], self.params["eye_r_open"]
        for i in range(max(1, veces)):
            self._programar(i * 620, lambda b=base_tilt, l=ojo_l, r=ojo_r: self.animate_to(
                {"head_tilt": b - 7.0, "eye_l_open": l * 0.35, "eye_r_open": r * 0.35},
                duration_ms=460, easing=QEasingCurve.InOutSine, estagger=False))
            self._programar(i * 620 + 470, lambda b=base_tilt, l=ojo_l, r=ojo_r: self.animate_to(
                {"head_tilt": b + 2.0, "eye_l_open": l, "eye_r_open": r},
                duration_ms=280, easing=QEasingCurve.OutBack, estagger=False))
        self._programar(max(1, veces) * 620, lambda b=base_tilt: self.animate_to(
            {"head_tilt": b}, duration_ms=300,
            easing=QEasingCurve.InOutSine, estagger=False))

    def estiron(self):
        """Se estira: ojos apretados, se alarga un poco y se destensa con parpadeo."""
        base = self._pose_base()
        self.animate_to({"eye_l_open": 0.05, "eye_r_open": 0.05,
                         "scale_x": base.get("scale_x", 1.0) * 0.95,
                         "scale_y": base.get("scale_y", 1.0) * 1.09,
                         "mouth_open": 0.35,
                         "head_tilt": base.get("head_tilt", 0.0) - 2.0},
                        duration_ms=420, easing=QEasingCurve.OutQuad, estagger=False)
        self._programar(520, lambda b=dict(base): self.animate_to(
            {"eye_l_open": b.get("eye_l_open", 1.0), "eye_r_open": b.get("eye_r_open", 1.0),
             "scale_x": b.get("scale_x", 1.0), "scale_y": b.get("scale_y", 1.0),
             "mouth_open": b.get("mouth_open", 0.0),
             "head_tilt": b.get("head_tilt", 0.0)},
            duration_ms=430, easing=QEasingCurve.OutBack, estagger=False))
        self._programar(1250, self.blink)

    def suspirar(self):
        """Suspiro: coge aire, lo suelta con los ojos entornados y se le pasa."""
        base = self._pose_base()
        self.animate_to({"mouth_open": 0.32, "scale_y": base.get("scale_y", 1.0) * 1.04,
                         "eye_l_open": min(0.85, base.get("eye_l_open", 1.0)),
                         "eye_r_open": min(0.85, base.get("eye_r_open", 1.0)),
                         "mouth_curve": base.get("mouth_curve", 0.3) - 0.15},
                        duration_ms=520, easing=QEasingCurve.InOutSine)
        self._programar(560, lambda b=dict(base): self.animate_to(
            {"mouth_open": b.get("mouth_open", 0.0),
             "scale_y": b.get("scale_y", 1.0) * 0.985,
             "eye_l_open": b.get("eye_l_open", 1.0) * 0.75,
             "eye_r_open": b.get("eye_r_open", 1.0) * 0.75,
             "mouth_curve": b.get("mouth_curve", 0.3)},
            duration_ms=780, easing=QEasingCurve.InOutSine, estagger=False))
        self._programar(1400, lambda b=dict(base): self.animate_to(
            {"eye_l_open": b.get("eye_l_open", 1.0),
             "eye_r_open": b.get("eye_r_open", 1.0),
             "scale_y": b.get("scale_y", 1.0)},
            duration_ms=520, easing=QEasingCurve.InOutSine, estagger=False))

    def dormirse(self):
        """Se queda dormido: bostezo, ojos que se cierran y cabeza vencida.

        No es «neutral con los ojos cerrados»: hay un bostezo y un cabeceo
        lento, que es lo que se lee como sueño y no como avería.
        """
        self._detener_loop_micro()
        self._blink_timer.stop()          # dormido no parpadea
        self._gesto_timer.stop()          # ni gestos: está dormido
        self.animate_to({"eye_l_open": 0.55, "eye_r_open": 0.55,
                         "mouth_open": 0.55, "head_tilt": -3.0},
                        duration_ms=430, easing=QEasingCurve.InOutSine)
        self._programar(430, lambda: self.animate_to(
            {"eye_l_open": 0.02, "eye_r_open": 0.02, "mouth_open": 0.0,
             "mouth_curve": 0.15, "head_tilt": -7.0},
            duration_ms=900, easing=QEasingCurve.InOutSine, estagger=False))

    def despertarse(self):
        """Vuelve de dormido: estirón corto, ojos abiertos y parpadeo normal."""
        self.animate_to({"eye_l_open": 0.25, "eye_r_open": 0.25,
                         "mouth_open": 0.35, "mouth_curve": 0.3,
                         "head_tilt": 1.0},
                        duration_ms=260, easing=QEasingCurve.OutQuad)
        self._programar(270, lambda: self.animate_to(
            {"eye_l_open": 1.0, "eye_r_open": 1.0, "mouth_open": 0.0,
             "mouth_curve": 0.35, "head_tilt": 0.0},
            duration_ms=420, easing=QEasingCurve.OutBack, estagger=False))
        self._programar(700, self._programar_parpadeo)
        self._programar_gesto()          # despierto: vuelve el director de gestos

    def reaparecer(self):
        """Vuelve a su sitio si una despedida no acabó en apagado (sin permiso)."""
        self.group.setPos(0.0, 0.0)
        self.group.setScale(1.0)
        self.group.setOpacity(1.0)
        self.set_expression("neutral", con_anticipacion=False)
        self._programar_gesto()
        self._programar_parpadeo()

    def despedida(self, hacia: str = "derecha", fn_final=None, ms: int = 1500):
        """Se despide y se marcha: cabeceo, se va de lado y se funde a negro.

        Pedido el 26/10/2026: «una animación de despedida, estilo animada, que
        desaparezca de un lado». Es lo último que se ve antes de apagar la
        placa, así que el orden importa: primero se despide (bostezo y ojos
        cerrándose), después se marcha (se desliza con un poco de caída y se
        funde) y **al final** `fn_final` cierra audio y pantalla.
        """
        if not self._activo:
            return
        self._detener_loop_micro()
        self._blink_timer.stop()
        signo = 1.0 if str(hacia).lower() != "izquierda" else -1.0

        # 1) Cabeceo de sueño: se le van cerrando los ojos en dos tiempos.
        self.animate_to({"eye_l_open": 0.5, "eye_r_open": 0.5,
                         "mouth_open": 0.35, "mouth_curve": 0.2,
                         "head_tilt": -3.0 * signo},
                        duration_ms=280, easing=QEasingCurve.InOutSine)
        self._programar(300, lambda: self.animate_to(
            {"eye_l_open": 0.10, "eye_r_open": 0.10, "mouth_open": 0.0,
             "mouth_curve": 0.3, "head_tilt": -6.0 * signo},
            duration_ms=380, easing=QEasingCurve.InOutSine, estagger=False))

        # 2) Se marcha: se desliza hacia un lado, se encoge un poco y se funde.
        def marcharse():
            partida = QVariantAnimation(self.scene)
            partida.setStartValue(0.0)
            partida.setEndValue(1.0)
            partida.setDuration(int(ms))
            partida.setEasingCurve(QEasingCurve.InCubic)
            ancho = float(FACE_W)

            def paso(t: float):
                t = float(t)
                self.group.setPos(ancho * 0.8 * signo * (t ** 2), -8.0 * t)
                self.group.setScale(max(0.05, 1.0 - 0.35 * t))
                self.group.setOpacity(max(0.0, 1.0 - t * 1.2))

            def fin():
                self.group.setOpacity(0.0)
                if fn_final is not None:
                    fn_final()

            partida.valueChanged.connect(paso)
            partida.finished.connect(fin)
            self._active_anims.append(partida)   # que no lo recoja el GC
            partida.start()

        self._programar(300, marcharse)

    def reproducir_intro(self):
        """Despertar teatral de ~4 s, construido con los 12 principios.

        Guion y principio que justifica cada segundo:

        | t (ms) | Qué pasa                                             | Principio |
        |---|---|---|
        | 0      | duerme achatado (squash) y ojos cerrados              | 1, 3      |
        | 200    | se hunde un poco más: coge carrerilla         | 2         |
        | 420    | se estira de golpe al despertar (stretch)     | 1, 9      |
        | 700    | parpadeo de encendido (dos tiempos)           | 8, 9      |
        | 1000   | arco de mirada a un lado; la cabeza llega tarde | 5, 7      |
        | 1450   | arco al otro lado                             | 7         |
        | 1950   | doble toma: reojo, giro, vuelta               | 4, 10, 12 |
        | 2550   | bostezo grande                                | 1, 8, 12  |
        | 3300   | sonríe y se asienta mirando de frente         | 3, 6, 11  |
        """
        # Pose inicial: dormido, achatado y descentrado (nada de un neutral plano)
        self.params["eye_l_open"] = 0.03
        self.params["eye_r_open"] = 0.03
        self.params["mouth_open"] = 0.0
        self.params["mouth_curve"] = 0.1
        self.params["scale_x"] = 0.90
        self.params["scale_y"] = 0.84
        self.params["head_tilt"] = -7.0
        self._look_x = -6.0
        self._muelle.update({"tilt": -7.0, "vt": 0.0, "sx": 0.90, "vsx": 0.0,
                             "sy": 0.84, "vsy": 0.0})
        self.redraw()

        def anticipar():
            # Carrerilla: se hunde un poco MÁS antes de estirarse
            self.animate_to({"scale_x": 0.95, "scale_y": 0.78, "head_tilt": -9.0},
                            duration_ms=220, easing=QEasingCurve.InQuad, estagger=False)

        def despertar():
            # Estirón al abrir los ojos, con sobreimpulso
            self.animate_to({
                "eye_l_open": 1.0, "eye_r_open": 1.0,
                "scale_x": 0.90, "scale_y": 1.16,
                "mouth_open": 0.42, "mouth_curve": -0.15, "head_tilt": 0.0,
            }, duration_ms=380, easing=QEasingCurve.OutBack, estagger=False)

        def parpadeo_encendido():
            self.animate_to({"eye_l_open": 0.35, "eye_r_open": 0.35},
                            duration_ms=90, estagger=False)
            self._programar(110, lambda: self.animate_to(
                {"eye_l_open": 0.05, "eye_r_open": 0.05}, duration_ms=70,
                estagger=False))
            self._programar(230, lambda: self.animate_to(
                {"eye_l_open": 1.0, "eye_r_open": 1.0}, duration_ms=170,
                easing=QEasingCurve.OutBack, estagger=False))

        def curiosear(signo: float, cuanto: float):
            # Arco: el ojo sale rápido (sacada) y la cabeza lo sigue tarde
            self._tween_valor(lambda: self._look_x, self._set_look_x,
                              cuanto * signo, duration_ms=150,
                              easing=QEasingCurve.OutExpo)
            self._programar(120, lambda s=signo: self.animate_to(
                {"head_tilt": -10.0 * s}, duration_ms=340,
                easing=QEasingCurve.InOutSine, estagger=False))

        def asentarse():
            self._tween_valor(lambda: self._look_x, self._set_look_x, 0.0,
                              duration_ms=260, easing=QEasingCurve.OutQuad)
            self.animate_to({"head_tilt": 0.0}, duration_ms=300,
                            easing=QEasingCurve.OutBack, estagger=False)
            # Termina mirando al frente, sonriendo: puesta en escena legible
            self.set_expression("feliz")
            self._programar(1100, lambda: self.set_expression("neutral"))

        self._programar(200, anticipar)
        self._programar(420, despertar)
        self._programar(840, parpadeo_encendido)
        self._programar(1150, lambda: curiosear(1.0, 15.0))
        self._programar(1600, lambda: curiosear(-1.0, 15.0))
        self._programar(2050, lambda: self.doble_toma("derecha"))
        self._programar(2650, self.bostezo)
        self._programar(3350, asentarse)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parker - Demo Animaciones Disney")
        self.setStyleSheet("background-color: black;")

        central = QWidget()
        layout = QVBoxLayout(central)

        self.scene = QGraphicsScene(0, 0, FACE_W, FACE_H)
        self.scene.setBackgroundBrush(QBrush(BG_BLACK))

        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("border: none; background-color: black;")
        self.view.setFixedSize(FACE_W + 4, FACE_H + 4)
        layout.addWidget(self.view)

        self.face = FaceController(self.scene)

        # Botones de prueba de emociones
        buttons_row = QHBoxLayout()
        for label, expr in [("Neutral", "neutral"), ("Feliz", "feliz"),
                            ("Triste", "triste"), ("Sorpresa", "sorpresa"),
                            ("Pensando", "pensando"), ("Confundido", "confundido"),
                            ("Escuchando", "escuchando"), ("Cariño", "carino")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, e=expr: self.face.set_expression(e))
            buttons_row.addWidget(btn)

        # Botones de control de estado (Habla / Intro)
        self.talk_btn = QPushButton("Simular Habla")
        self.talk_btn.setCheckable(True)
        self.talk_btn.toggled.connect(
            lambda checked: self.face.iniciar_habla() if checked else self.face.detener_habla()
        )
        buttons_row.addWidget(self.talk_btn)

        self.intro_btn = QPushButton("Replay Intro")
        self.intro_btn.clicked.connect(self.face.reproducir_intro)
        buttons_row.addWidget(self.intro_btn)

        layout.addLayout(buttons_row)
        self.setCentralWidget(central)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()