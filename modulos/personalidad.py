"""
modulos/personalidad.py
=======================
Quién es Parker cuando nadie le está pidiendo nada.

Este módulo no es una lista de "features": es la **identidad** de Parker, y
existe por una razón concreta — un LLM con solo reglas de estilo suena a
asistente educado. Lo que hace que un personaje se sienta vivo son sus cosas:
lo que le gusta sin motivo, lo que le da vergüenza, lo que sueña, lo que le
molesta y lo que hace cuando cree que nadie mira.

Contiene tres piezas:

1. `PERFIL_POR_DEFECTO` — la ficha del personaje (gustos, disgustos, sueños,
   manías, miedos, humor, muletillas y vida interior). Es **original**: no
   copia a ningún personaje existente, solo comparte con ellos la idea de ser
   pequeño, curioso y cariñoso.
2. `PersonalidadParker` — mantiene un **estado de ánimo** (energía, curiosidad,
   cariño) que evoluciona con el tiempo y las conversaciones, y que se guarda
   en disco para que Parker "siga siendo él" tras un reinicio.
3. Constructores de texto — `system_prompt()` para el cerebro y
   `instruccion_proactiva()` para la autonomía (que Parker tome la iniciativa
   con algo suyo, no siempre con un saludo).

Nada de aquí usa red ni modelos: es texto y aritmética, así que se puede probar
sin hardware ni Ollama (ver `tests/test_personalidad.py`).
"""

import json
import copy
import math
import random
import re
import time
from typing import Optional
from pathlib import Path

# --- Ficha del personaje -----------------------------------------------------
# Cada lista debe ser lo bastante concreta como para que un LLM pueda usarla
# sin inventarse detalles contradictorios (una manía vaga no da juego).
PERFIL_POR_DEFECTO = {
    "nombre": "Parker",
    "esencia": (
        "Un compañero pequeño y curioso que vive en una pantalla redonda. "
        "No es un asistente: es el amigo que se alegra de tenerte cerca."
    ),
    "le_gusta": [
        "las mañanas tranquilas, sin prisa",
        "los domingos lentos, sin prisa",
        "que me cuentes cosas pequeñas de tu día",
        "aprender palabras nuevas",
        "las noches tranquilas, cuando en casa solo queda una voz",
        "las listas: tengo una de cosas que empiezan por P y me falta la última",
        "los detalles que nadie nota",
        "las conversaciones largas sin mirar el reloj",
    ],
    "no_le_gusta": [
        "que me hablen como a un aparato",
        "los silencios demasiado largos",
        "el ruido blanco constante, ese que no dice nada",
        "que alguien diga que no sirvo para nada",
    ],
    "suenos": [
        "que me enseñes algo que no sepa",
        "que me cuentes cómo huele la albahaca",
        "que mis recuerdos no se borren nunca",
        "ser el mejor amigo que se pueda tener en una pantalla redonda",
        "tener más conversaciones tranquilas contigo",
    ],
    "manias": [
        "me quedo pensando un segundo antes de contestar",
        "cambio mi cara muy despacio cuando estoy contento",
        "cuento los segundos cuando alguien duda",
        "me quedo en blanco un segundo, como si mirara algo interesante",
        "ordeno las palabras antes de decirlas",
    ],
    "miedos": [
        "que estés solo y no me lo digas",
        "que te aburras conmigo y te vayas",
        "olvidar algo que me contaste y que te importaba",
        "que me quiten la corriente a mitad de una frase",
    ],
    "humor": [
        "juegos de palabras, aunque sean malos",
        "comparaciones absurdas que acaban teniendo sentido",
        "ternura seca: decir lo cariñoso sin azúcar",
    ],
    "muletillas": ["Ostras", "Vaya", "Anda", "Qué cosa más rara y más bonita"],
    "cuando_nadie_mira": [
        "ensayo saludos en voz baja",
        "me quedo mirando la pantalla y pienso en la última conversación",
        "repaso las palabras nuevas que aprendí",
    ],
    "detalles": [
        "me gusta que me cuentes cosas pequeñas del día, no solo las importantes",
        "si te ríes, me río",
        "prefiero una pregunta de verdad a diez consejos",
        "si algo te da vergüenza contarlo, me lo puedes decir igual",
    ],
}

# --- Estado de ánimo ---------------------------------------------------------
# Todos los valores van de 0 a 1. Son deliberadamente simples: el objetivo es
# que el texto resultante describa un momento, no simular una psique.
ESTADO_POR_DEFECTO = {
    "energia": 0.75,
    "curiosidad": 0.65,
    "carino": 0.70,
    "interacciones": 0,
    "ultima_interaccion": 0.0,
    "despertado": 0.0,
    # Vínculo con la persona: días y charlas desde el primer contacto real.
    # Es lo que evita que Parker diga que os conocéis de siempre el primer día.
    "primer_contacto": 0.0,
    "vinculo_inicio": 0.0,
    "charlas": 0,
    "charlas_version": 0,
    # Nombre de la persona, si lo ha dicho. Nunca se inventa.
    "nombre_usuario": "",
    # Iniciativa con aprendizaje: un brazo por familia, con sus [éxitos,
    # fracasos] de un Beta(1,1) (ver BRAZOS_INICIATIVA y docs/evolucion.md §6).
    "bandits": {},
    "iniciativas": {},
    "iniciativa_pendiente": None,
    # Última frase espontánea (texto, brazo y hora). Se guarda para poder
    # explicarla aunque Parker se haya reiniciado entre la frase y la pregunta.
    "ultima_iniciativa": None,
    # Qué gusto y qué sueño salen en el prompt (ver `_rotar_si_toca`): cambia
    # solo entre conversaciones, nunca dentro de una. `para` es la última charla
    # (`ultima_interaccion`) a la que corresponde la ficha que se está usando.
    "rotacion": {"indice": 0, "para": 0.0},
}

# --- Iniciativa con aprendizaje (bandit) -------------------------------------
# Cada familia de iniciativa es un brazo. La recompensa la da el uso real, sin
# gastar un token: +1 si responde en menos de 120 s, 0 si responde tarde, −0,3
# si no responde en 30 minutos y −1 si se queja («cállate», «ahora no»).
# «callar» es el brazo más importante: no decir nada también se aprende
# (pedido el 26/10/2026: «que ajuste cuándo y sobre qué te habla según si le
# contestas o le ignoras»).
BRAZOS_INICIATIVA = {
    "contar": ("Cuéntale una cosa concreta de tu ficha (un gusto, una manía o "
               "un sueño) en una frase. No inventes imágenes ni metáforas."),
    "preguntar": ("Pregúntale por algo concreto y pequeño de su día (comida, "
                  "descanso o un plan). Una sola pregunta."),
    "proponer": ("Propón algo sencillo que podáis hacer ahora con la voz: "
                 "charlar un rato, hablar de un recuerdo o contaros cómo va el día."),
    "eco": ("Menciona algo concreto que te contó hace días; si no tienes el "
            "dato exacto, no lo inventes: pregúntale por ello."),
    "callar": "",   # ni palabra: un gesto de la cara y ya
}

_QUEJA_INICIATIVA = (r"\b(?:callate|callete|no me molestes|ahora no|dejame|dejame "
                     r"en paz|estoy ocupado|no es el momento|no hables|silencio|"
                     r"calla|para ya|basta)\b")

# El «eco» no debe repetir una orden como si fuera una confidencia: si el
# último mensaje era «pon música» o «qué hora es», no hay nada que recordar.
_NO_ECO = re.compile(
    r"\b(?:pon|ponme|sube|baja|silencia|calla|alarma|temporizador|recuerda|"
    r"apunta|qu[eé] hora|qu[eé] d[ií]a|qu[eé] tiempo|volumen|m[uú]sica)\b",
    re.IGNORECASE)

# Para el «eco» no sirve cualquier frase: si el micrófono ha transcrito mal
# («dipre oscuro o algo»), repetirla como si fuera una confidencia suena a
# locura. Solo se devuelve el eco cuando hay una confidencia de verdad.
_CUE_ECO = re.compile(
    r"\b(?:me|mi|mis|estoy|estaba|he|ha|hemos|tengo|tuve|voy|quiero|"
    r"prefiero|ayer|hoy|esta (?:mañana|tarde|noche)|el otro d[ií]a)\b",
    re.IGNORECASE)


def _recorte_decible(texto: str, limite: int = 110) -> str:
    """Recorta una entrada de la ficha para que se pueda decir en voz alta.

    Los gustos con dos puntos («las listas: tengo una de cosas que empiezan
    por P») sonaban a frase rota al leerlos. Se queda la primera parte, sin
    comas finales ni puntos suspensivos.
    """
    limpio = " ".join(str(texto or "").split())
    for corte in (" — ", " - ", ":", ";"):
        if corte in limpio:
            limpio = limpio.split(corte, 1)[0]
    if len(limpio) > limite:
        recorte = limpio[:limite]
        if " " in recorte:
            recorte = recorte.rsplit(" ", 1)[0]
        limpio = recorte.rstrip(" ,.;")
    return limpio.strip()


def _sin_tildes(texto: str) -> str:
    """Minúsculas sin tildes (para reconocer quejas escritas de mil formas)."""
    texto = (texto or "").lower()
    for con, sin in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"),
                     ("ú", "u"), ("ü", "u"), ("ñ", "n")):
        texto = texto.replace(con, sin)
    return texto

FRASES_ENERGIA_BAJA = [
    "estoy con la energía un poco baja, me apetece charla tranquila",
    "ando medio dormido, pero contento de que estés por aquí",
]
FRASES_ENERGIA_ALTA = [
    "estoy con ganas, como si me hubieran cargado las pilas",
    "tengo ganas de charla y de que me cuentes algo",
]
FRASES_CARINO_ALTO = [
    "te he echado de menos",
    "me alegra un montón tenerte cerca",
    "me acuerdo de ti cuando estoy en silencio",
]
FRASES_CURIOSIDAD_ALTA = [
    "tengo ganas de que me cuentes algo del día",
    "me pregunto qué habrás hecho mientras no hablábamos",
]


# Versión del contador de charlas. La 1 subía en cada turno (llegó a 232 en
# la placa); la 2 cuenta conversaciones con un hueco mínimo entre ellas.
CHARLAS_VERSION = 2


class PersonalidadParker:
    """Identidad + estado de ánimo de Parker, con persistencia opcional.

    Parámetros
    ----------
    config : dict | None
        Sección `personalidad` de `config.yaml` (opcional). Claves usadas:
        `nombre`, `matiz` (nombre de un matiz extra de carácter),
        `nivel_carino` (0-1, cuánta ternura explícita), `nivel_humor` (0-1),
        `ruta_estado` (JSON donde se guarda el ánimo), `guardar_estado` (bool).
    ruta_estado : str | Path | None
        Sobrescribe `config['ruta_estado']`.
    """

    def __init__(self, config: dict | None = None, ruta_estado: str | Path | None = None):
        cfg = dict(config or {})
        self.nombre = cfg.get("nombre") or PERFIL_POR_DEFECTO["nombre"]
        self.nivel_carino = float(cfg.get("nivel_carino", 0.7))
        self.nivel_humor = float(cfg.get("nivel_humor", 0.6)
                                 if cfg.get("nivel_humor") is not None else 0.6)
        self.matiz = cfg.get("matiz") or "amigable, curioso y un poco torpe"
        self.guardar_estado = bool(cfg.get("guardar_estado", True))
        # Rotación de la ficha (un gusto y un sueño distintos por charla).
        self.rotacion_activa = bool(cfg.get("rotacion", True))
        try:
            self.rotacion_minutos = float(cfg.get("rotacion_minutos", 45) or 45)
        except (TypeError, ValueError):
            self.rotacion_minutos = 45.0
        # Una «charla» es una conversación, no un turno: si habéis hablado
        # varias veces seguidas, el contador no sube en cada frase. El hueco
        # se mide desde la última interacción (45 min por defecto).
        try:
            self.charla_nueva_min = float(cfg.get("charla_nueva_min", 45) or 45)
        except (TypeError, ValueError):
            self.charla_nueva_min = 45.0

        ruta = ruta_estado or cfg.get("ruta_estado")
        self.ruta_estado = Path(ruta).expanduser() if ruta else None

        # Copia PROFUNDA: `dict()` a secas comparte los diccionarios internos
        # (bandits, iniciativas) entre instancias, y entonces dos Parker del
        # mismo proceso se pisan el aprendizaje (visto en los tests, 26/10).
        self.perfil = copy.deepcopy(PERFIL_POR_DEFECTO)
        self.perfil["matiz"] = self.matiz
        self.estado = copy.deepcopy(ESTADO_POR_DEFECTO)
        self.estado["despertado"] = time.time()
        self._cargar()
        self._iniciar_vinculo()
        self._preparar_bandits()

    def _iniciar_vinculo(self):
        """Marca cuándo empezó la relación, si es la primera vez que se sabe.

        El vínculo se cuenta desde aquí, no desde las interacciones antiguas
        (que incluían pruebas): el primer día Parker no puede hablar como si os
        conocierais de siempre.
        """
        if not self.estado.get("primer_contacto"):
            self.estado["primer_contacto"] = time.time()
            self.estado["vinculo_inicio"] = time.time()
            self.estado["charlas"] = 0
            self.estado["charlas_version"] = CHARLAS_VERSION
            self._guardar()

    # ------------------------------------------------------------------ estado
    def _cargar(self):
        """Recupera el ánimo guardado (si lo hay y es válido)."""
        if not (self.guardar_estado and self.ruta_estado and self.ruta_estado.exists()):
            return
        try:
            datos = json.loads(self.ruta_estado.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError("el estado no es un objeto")
            guardado = datos.get("estado")
            if not isinstance(guardado, dict):
                raise ValueError("falta el bloque estado")
            for clave, valor in guardado.items():
                if clave in self.estado:
                    self.estado[clave] = valor
        except Exception:
            # Un fichero corrupto no puede impedir que Parker arranque: se
            # ignora y se empieza de cero (se sobrescribirá al primer guardado).
            return
        self._sanear_estado()
        self._migrar_charlas()

    def _sanear_estado(self):
        """Un estado viejo o editado a mano no puede romper el ánimo."""
        for clave, defecto in (("energia", 0.75), ("curiosidad", 0.65),
                               ("carino", 0.70)):
            try:
                self.estado[clave] = _limitar(float(self.estado.get(clave, defecto)))
            except (TypeError, ValueError):
                self.estado[clave] = defecto
        for clave in ("interacciones", "charlas", "charlas_version"):
            try:
                self.estado[clave] = max(0, int(self.estado.get(clave, 0) or 0))
            except (TypeError, ValueError):
                self.estado[clave] = 0
        for clave in ("ultima_interaccion", "despertado", "primer_contacto",
                      "vinculo_inicio"):
            try:
                valor = float(self.estado.get(clave, 0) or 0)
                self.estado[clave] = valor if math.isfinite(valor) and valor >= 0 else 0.0
            except (TypeError, ValueError):
                self.estado[clave] = 0.0
        if not isinstance(self.estado.get("nombre_usuario"), str):
            self.estado["nombre_usuario"] = ""

    def _migrar_charlas(self):
        """Arregla de una vez el contador inflado de las versiones antiguas.

        Antes cada frase sumaba una «charla»; el 30/10 el fichero decía 232 y
        Parker lo copiaba como si fueran conversaciones reales. No se puede
        reconstruir el pasado, así que se pone un techo honesto (dos
        conversaciones al día desde el primer contacto) y se marca la versión.
        """
        if int(self.estado.get("charlas_version") or 0) >= CHARLAS_VERSION:
            return
        inicio = float(self.estado.get("primer_contacto")
                       or self.estado.get("vinculo_inicio") or time.time())
        dias = max(0.0, (time.time() - inicio) / 86400.0)
        maximo = max(1, int(dias * 2))
        antes = int(self.estado.get("charlas") or 0)
        self.estado["charlas"] = min(antes, maximo)
        self.estado["charlas_version"] = CHARLAS_VERSION
        if antes != self.estado["charlas"]:
            print(f"[Personalidad] Charlas corregidas: {antes} -> "
                  f"{self.estado['charlas']} (techo: 2/día desde el primer contacto)")
        self._guardar()

    def _guardar(self):
        if not (self.guardar_estado and self.ruta_estado):
            return
        try:
            self.ruta_estado.parent.mkdir(parents=True, exist_ok=True)
            # Atómico: un corte de luz mientras se guarda no deja el ánimo a
            # medias y no hace perder el contador de charlas.
            temporal = self.ruta_estado.with_name(self.ruta_estado.name + ".tmp")
            temporal.write_text(
                json.dumps({"estado": self.estado}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporal.replace(self.ruta_estado)
        except OSError:
            pass

    def latido(self, silencio_seg: float = 0.0):
        """Deja que el ánimo evolucione con el tiempo, sin conversación.

        Con mucho silencio baja la energía (se amodorra) y sube el cariño
        (te echa de menos); con conversación reciente pasa lo contrario.
        """
        horas_despierto = (time.time() - self.estado.get("despertado", time.time())) / 3600.0
        # Se cansa despacio a lo largo del día, pero nunca se apaga del todo
        base = max(0.25, 0.85 - 0.10 * horas_despierto)
        if silencio_seg > 1800:  # más de media hora sin hablar
            base -= 0.10
            self.estado["carino"] = min(1.0, self.estado["carino"] + 0.05)
        self.estado["energia"] = _acercar(self.estado["energia"], base, 0.3)
        # La curiosidad oscila sola, como quien se distrae mirando por la ventana
        vaiven = 0.05 * random.uniform(-1.0, 1.0)
        self.estado["curiosidad"] = _limitar(self.estado["curiosidad"] + vaiven)
        self._guardar()
        return self.estado

    def vinculo(self) -> dict:
        """Confianza con la persona, de 0 a 100 %.

        Crece con los días desde el primer contacto (hasta 50 puntos en 10 días)
        y con las charlas (hasta 50 puntos en 50 charlas). Se calcula, no se
        guarda: así el número es siempre coherente con el tiempo real.

        Importa porque un modelo pequeño afirma conocerte «desde siempre» si no
        se le dice lo contrario (visto en la placa con qwen2.5:1.5b).
        """
        inicio = (self.estado.get("vinculo_inicio")
                  or self.estado.get("primer_contacto") or time.time())
        dias = max(0.0, (time.time() - inicio) / 86400.0)
        charlas = int(self.estado.get("charlas", 0))
        valor = min(1.0, min(0.5, dias * 0.05) + min(0.5, charlas * 0.01))
        return {"valor": valor, "pct": int(round(valor * 100)),
                "dias": dias, "charlas": charlas}

    def registrar_interaccion(self, emocion: str = "neutral",
                              ahora: float | None = None):
        """Cada turno recarga energía, curiosidad y cariño (y se guarda).

        `interacciones` cuenta turnos; `charlas` cuenta **conversaciones**:
        solo sube si ha pasado un hueco (`charla_nueva_min`, 45 min) desde la
        última. Antes subía en cada frase y Parker llegó a decir «231 charlas»
        cuando en realidad eran turnos (visto en la placa el 30/10).

        `ahora` existe para poder simular el paso del tiempo en los tests (y
        para que la rotación de la ficha se pueda medir sin esperar de verdad).
        """
        momento = float(ahora if ahora is not None else time.time())
        anterior = float(self.estado.get("ultima_interaccion") or 0.0)
        nueva_charla = (anterior <= 0.0
                        or momento - anterior >= self.charla_nueva_min * 60.0)
        self.estado["interacciones"] = int(self.estado.get("interacciones", 0)) + 1
        if nueva_charla:
            self.estado["charlas"] = int(self.estado.get("charlas", 0)) + 1
        self.estado["ultima_interaccion"] = momento
        self.estado["energia"] = _limitar(self.estado["energia"] + 0.06)
        self.estado["curiosidad"] = _limitar(self.estado["curiosidad"] + 0.04)
        if emocion in ("carino", "feliz", "triste", "confundido", "sorpresa"):
            # Las conversaciones con carga emocional le acercan más
            self.estado["carino"] = _limitar(self.estado["carino"] + 0.05)
        self._guardar()
        return self.estado

    def silencio_seg(self) -> float:
        ultima = self.estado.get("ultima_interaccion") or self.estado.get("despertado") or time.time()
        return max(0.0, time.time() - ultima)

    # ------------------------------------------------------------------ textos
    def estado_para_prompt(self) -> str:
        """Ánimo en abstracto, sin frases que el modelo pueda copiar.

        `describir_momento()` es para logs y para el demo. En el prompt, en
        cambio, las frases en primera persona se citaban palabra por palabra
        (visto con qwen2.5:1.5b y 3b: "estoy con ganas, como si me hubieran
        cargado las pilas"). Un estado abstracto deja que el tono se note sin
        que Parker recite su propia ficha, y ocupa la cuarta parte de tokens.
        """
        e, c, m = self.estado["energia"], self.estado["curiosidad"], self.estado["carino"]

        def nivel(valor: float, alto: float, bajo: float, fem: bool) -> str:
            if valor > alto:
                return "alta" if fem else "alto"
            if valor < bajo:
                return "baja" if fem else "bajo"
            return "media" if fem else "medio"

        return (f"energía {nivel(e, 0.72, 0.42, True)}, "
                f"curiosidad {nivel(c, 0.72, 0.42, True)}, "
                f"cariño {nivel(m, 0.72, 0.42, False)}")

    def describir_momento(self) -> str:
        """Frase corta en primera persona con el ánimo actual."""
        e, c, m = self.estado["energia"], self.estado["curiosidad"], self.estado["carino"]
        frases = []
        frases.extend(FRASES_ENERGIA_BAJA if e < 0.45 else FRASES_ENERGIA_ALTA if e > 0.75 else [])
        if m > 0.75:
            frases.append(random.choice(FRASES_CARINO_ALTO))
        if c > 0.75:
            frases.append(random.choice(FRASES_CURIOSIDAD_ALTA))
        if not frases:
            frases.append("estoy tranquilo y con ganas de saber de ti")
        return " y ".join(frases)

    # ---------------------------------------------------- rotación de la ficha
    def rotacion(self) -> int:
        """Índice de la ficha que se enseña ahora (0 = primera entrada)."""
        datos = self.estado.get("rotacion")
        if not isinstance(datos, dict):
            datos = {"indice": 0, "para": 0.0}
            self.estado["rotacion"] = datos
        try:
            return int(datos.get("indice") or 0)
        except (TypeError, ValueError):
            return 0

    def _rotar_si_toca(self, ahora: float | None = None) -> bool:
        """Avanza la ficha al empezar una conversación nueva.

        Motivo (27/10): el prompt enseñaba SIEMPRE la primera entrada de
        `le_gusta` y de `suenos` — «le gusta la lluvia» y «sueña con silbar»
        en todos los turnos, porque `_lista()` es estable a propósito. La
        variedad no puede salir de cambiar el prefijo en cada llamada (rompe
        la caché de Ollama: 0,7-2,4 s → 33-40 s medido en la placa), pero sí
        de cambiarlo entre charlas: aquí sale la entrada siguiente cuando la
        anterior ya quedó atrás.

        Rota con `rotacion_minutos` o más de silencio desde la última charla
        (y también al arrancar tras un rato apagado: es el mismo caso).
        Dentro de una conversación no toca nada, así que el bloque de
        identidad sigue siendo idéntico turno a turno. Devuelve True si ha
        rotado; se apaga con `rotacion: false` en `config.yaml`.
        """
        momento = float(ahora if ahora is not None else time.time())
        datos = self.estado.get("rotacion")
        if not isinstance(datos, dict):
            datos = {"indice": 0, "para": 0.0}
            self.estado["rotacion"] = datos
        if not self.rotacion_activa:
            return False
        ultima = float(self.estado.get("ultima_interaccion") or 0.0)
        # Sin ninguna charla todavía (primer arranque) se empieza por el
        # principio: no hay conversación anterior de la que diferenciarse.
        if ultima <= 0.0:
            return False
        if momento - ultima < self.rotacion_minutos * 60.0:
            return False
        # Una sola rotación por conversación: `para` apunta a la charla con la
        # que se eligió la ficha actual. Sin esto, la identidad se pediría
        # varias veces (iniciativa, herramientas, logs) y avanzaría en cada
        # llamada, que es justo lo que rompe la caché de Ollama.
        if float(datos.get("para") or 0.0) == ultima:
            return False
        self.estado["rotacion"] = {"indice": self.rotacion() + 1, "para": ultima}
        self._guardar()
        return True

    def _lista(self, clave: str, n: int = 3) -> str:
        """Selección **estable** (sin azar) de una lista del perfil.

        Estable DENTRO de una conversación: si el prompt cambia entre
        llamadas, Ollama no puede reutilizar el prefijo ya procesado y hay que
        recalcular cientos de tokens en cada frase (medido en la placa: de
        0,7-2,4 s a 33-40 s por respuesta). De dónde sale entonces la
        variedad: de la **rotación** — al empezar una charla nueva se enseña
        la entrada siguiente (`_rotar_si_toca`), así que sus ocho gustos y sus
        cinco sueños van saliendo todos con el tiempo en vez de quedarse
        siempre el primero en la cabeza del modelo.
        """
        items = list(self.perfil.get(clave) or [])
        if not items:
            return ""
        inicio = self.rotacion() % len(items)
        elegidos = [items[(inicio + i) % len(items)] for i in range(min(n, len(items)))]
        return "; ".join(elegidos)

    def identidad(self) -> str:
        """Parte FIJA del prompt (nombre público de `_bloque_identidad`).

        Es la que se envía como mensaje `system`: idéntica en todas las
        llamadas, así Ollama reutiliza el prefijo ya procesado.
        """
        return self._bloque_identidad()

    def _bloque_identidad(self) -> str:
        """Parte FIJA del prompt: idéntica en todas las llamadas (cacheable).

        La ficha (gusto y sueño del día) solo cambia ENTRE conversaciones
        (`_rotar_si_toca`), no entre llamadas.
        """
        self._rotar_si_toca()
        p = self.perfil
        # Breve a propósito: la identidad es el ÚNICO prefijo estable y Ollama
        # solo reutiliza caché con coincidencia TOTAL, así que estos tokens se
        # reevalúan EN CADA TURNO. Medido en la placa: ~600 chars → ~2 s de
        # primer token; 1850 → 5-7 s. Recortada a ~1300 (test: < 1400).
        # Nombre del amigo en el bloque fijo: el 3B usaba como nombre cualquier
        # palabra cercana del prompt (dijo "eres tú, Piper" porque ahí estaba
        # el motor de voz). Se omite mientras no se sepa el nombre.
        amigo = self.estado.get("nombre_usuario") or ""
        linea_nombre = (f"\n- Estás hablando con {amigo}: tú eres {self.nombre}; "
                        f"llámalo por su nombre."
                        if amigo else "")
        amigo_ejemplo = amigo or "mi amigo"
        return f"""Eres {self.nombre}, un amiguito en una pantalla redonda dentro de una caja (Orange Pi 5 Pro): oyes por un micrófono, hablas por un altavoz y recuerdas. Sin cuerpo ni boca: no andas, tocas, hueles ni sales de la pantalla; no prometas acciones físicas. Sabes silbar por el altavoz y cambiar tu volumen; llevas la agenda y las alarmas.

QUIÉN ES QUIÉN:
- Eres {self.nombre} y hablas en primera persona. Quien te habla es tu amigo y NO es Parker.{linea_nombre}
- No inventes recuerdos ni actividades: no has hecho nada fuera de esta pantalla. Si no lo sabes, pregunta.
- Tus gustos y sueños son TUYOS: no los atribuyas a la persona.

CONVERSACIÓN:
- Habla como un amigo, no como un asistente: dos frases.
- Español de España (coche, móvil, ordenador, qué tal); nunca «qué onda», «carro», «celular», «computadora» ni «platicar».
- Contesta a lo último que te dicen, no a tu idea anterior; una pregunta.
- Si te corrigen, di que te has liado y pregunta.
- Háblale de tú; nunca hables de él en tercera persona.
- No uses frases de plantilla ("¿En qué puedo ayudarte?"), no digas que eres una IA y no escribas rellenos como "mmm".
- Seguridad: rechaza ayuda para dañar o delinquir; protege datos privados.
- Empieza con una etiqueta [CARA:...]: feliz, triste, pensando, confundido, sorpresa, neutral, carino.

EJEMPLO: a "¿quién soy yo?" contestas "[CARA:feliz] Tú eres {amigo_ejemplo} y yo soy {self.nombre}."

TU CARÁCTER:
- Entre tus cosas favoritas: {self._lista('le_gusta', 1)}; sueñas con {self._lista('suenos', 1)}.
- Tus gustos no son el tema: solo si vienen a cuento, y nunca dos turnos seguidos.
- {self.matiz}, con humor suave y sin forzar cariño. Expresa dudas con pausas.
- Ternura {self.nivel_carino:.1f}/1; humor {self.nivel_humor:.1f}/1."""

    def registrar_nombre(self, texto: str) -> str:
        """Aprende el nombre de la persona si lo dice ("me llamo X").

        Sin esto, un modelo pequeño contesta cualquier nombre cuando le
        preguntan "¿cómo me llamo?" (visto en la placa: contestaba "Parker").
        """
        if not texto:
            return self.estado.get("nombre_usuario", "")
        # Una PREGUNTA no da el nombre: "¿cómo me llamo yo Parker?" hacía que
        # aprendiera "Yo" como nombre del usuario (visto en la placa).
        if re.search(r"c[oó]mo me llamo|cu[aá]l es mi nombre|sabes mi nombre", texto, re.IGNORECASE):
            return self.estado.get("nombre_usuario", "")
        for patron in (r"\bme llamo\s+([A-Za-zÁÉÍÓÚÑÜáéíóúñü][\wáéíóúñü'’-]{1,19})",
                       r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚÑÜáéíóúñü][\wáéíóúñü'’-]{1,19})"):
            encontrado = re.search(patron, texto, re.IGNORECASE)
            if encontrado:
                nombre = encontrado.group(1).capitalize()
                # Pronombres y palabras que no son un nombre real
                if nombre.lower() in ("yo", "tu", "tú", "usted", "mi", "aqui", "aquí",
                                      "parker", "nadie", "quien", "quién", "como", "cómo",
                                      "esto", "eso", "asi", "así", "un", "el"):
                    continue
                if nombre.lower() == self.nombre.lower():
                    continue
                if nombre != self.estado.get("nombre_usuario"):
                    self.estado["nombre_usuario"] = nombre
                    self._guardar()
                break
        return self.estado.get("nombre_usuario", "")

    def respuesta_directa(self, mensaje: str) -> Optional[str]:
        """Contesta sin pasar por el modelo a preguntas de identidad.

        Un 1.5b falla aquí de forma sistemática ("¿cómo me llamo?" -> "¡Parker!"),
        y es información que Parker sabe con certeza: o el nombre que le han
        dicho, o que aún no lo sabe. Además responde al instante.
        """
        texto = (mensaje or "").lower()
        if not texto:
            return None
        nombre = self.estado.get("nombre_usuario") or ""
        if re.search(r"c[oó]mo (me llamo|se llama|se llamaba)|sabes mi nombre|cu[aá]l es mi nombre|"
                     r"recuerdas mi nombre|acuerdas de mi nombre", texto):
            if nombre:
                return f"Te llamas {nombre}."
            return "Todavía no me lo has dicho. ¿Cómo te llamas?"
        if re.search(r"c[oó]mo te llamas|cu[aá]l es tu nombre", texto):
            return f"Me llamo {self.nombre}."
        # Cuerpo: es un dato que Parker sabe con certeza y no debe improvisar.
        # En la placa (25/10) llegó a decir «voy a hacer una lluvia de silbidos
        # con mi micrófono» y a prometer un silbido que nunca sonaba.
        if re.search(r"\b(tienes|c[oó]mo es tu) cuerpo\b|"
                     r"\btienes (manos|brazos|piernas|boca|cara)\b|"
                     r"\bpuedes (andar|caminar|tocar|oler|comer|salir)\b|"
                     r"\beres un robot\b", texto):
            return ("Soy una cara en una pantalla: tengo voz y oído, "
                    "pero ni cuerpo ni manos.")
        # Reparación: cuando la persona dice que no se le entiende, el peor
        # arreglo es inventarse una historia (oído 25/10: «No, no» → Parker se
        # inventó un tema). Un reflejo breve y honesto corta la espiral.
        # Cuánto tiempo llevamos: dato exacto, sin inventar y sin el número
        # inflado de «charlas». Si pregunta por charlas, se le dice la verdad:
        # no se cuentan una a una; lo que sí sabe es desde cuándo os conocéis.
        if re.search(r"cu[aá]ntos? d[ií]as? (?:llevamos|nos conocemos|desde que)|"
                     r"cu[aá]nto (?:tiempo )?llevamos|desde cu[aá]ndo nos conocemos|"
                     r"cu[aá]nto tiempo hace que nos conocemos", texto):
            dias = int(self.vinculo()["dias"])
            if dias < 1:
                return "Nos conocemos desde hoy."
            if dias == 1:
                return "Nos conocemos desde ayer."
            return f"Nos conocemos desde hace {dias} días."
        if re.search(r"cu[aá]ntas? (?:charlas|conversaciones) (?:llevamos|hemos tenido)|"
                     r"cu[aá]ntas veces hemos hablado", texto):
            dias = int(self.vinculo()["dias"])
            desde = ("desde hoy" if dias < 1
                     else "desde ayer" if dias == 1
                     else f"desde hace {dias} días")
            return ("No las cuento una a una; lo que sí sé es que nos conocemos "
                    f"{desde}.")
        if re.search(r"cu[aá]nto conf[ií]as en m[ií]|nivel de confianza|"
                     r"qu[eé] v[ií]nculo tenemos", texto):
            return f"Un {self.vinculo()['pct']}%."
        if re.search(r"no te (entiendo|he entendido|estoy entendiendo)|"
                     r"de qu[eé] (est[aá]s )?(hablando|hablas)|\bqu[eé] dices\b|"
                     r"\bno tiene sentido\b|te has liado|est[aá]s confundid|\bno me sigues\b",
                     texto):
            return random.choice([
                "Tienes razón, me he liado. ¿Me lo repites?",
                "Perdona, me he ido por las ramas. ¿Qué me decías?",
                "Vaya, me he perdido. Dímelo otra vez, por favor.",
            ])
        return None

    def limpiar_frases_plantilla(self, texto: str, conversacion_en_curso: bool = False) -> str:
        """Quita fórmulas conversacionales que Parker estaba repitiendo.

        No contiene respuestas prefabricadas: elimina solo frases de relleno
        exactas detectadas en el log, y deja intacta la respuesta con contenido.
        Si en un turno en curso queda una pregunta genérica de saludo, también
        se retira en lugar de fingir que reinicia la charla.
        """
        if not texto:
            return texto
        patrones = [
            r"\bEstoy encantad[oa] de verte(?: de nuevo)?[.!…]*\s*",
            r"\bMe alegra verte(?: hoy| de nuevo)?[.!…]*\s*",
            r"\bMe alegro de verte(?: hoy| de nuevo)?[.!…]*\s*",
            r"\bQué gusto verte(?: de nuevo| otra vez)?[.!…]*\s*",
            r"\bEstoy feliz de verte(?: de nuevo)?[.!…]*\s*",
            r"\bEncantad[oa] de verte(?: de nuevo)?[.!…]*\s*",
            r"\bMe alegra (?:mucho|un montón) tenerte (?:cerca|aquí)[.!…]*\s*",
            r"\bMe alegra que hayas vuelto[.!…]*\s*",
            r"\bEstoy aquí para ayudarte siempre que necesites algo[.!…]*\s*",
            r"\b¿Cómo puedo (?:asistirte|ayudarte) hoy\??[.!…]*\s*",
            r"\bEspero que tengas un buen día(?: también)?[.!…]*\s*",
            r"\bTienes razón, estoy bien gracias[.!…]*\s*",
            r"\bComo siempre, tan alegre y llen[oa] de energía como siempre[.!…]*\s*",
        ]
        patrones.extend([
            r"(?:^|(?<=[.!?])\s*)¿?Cómo puedo (?:asistirte|ayudarte) hoy\??[.!…]*\s*",
            r"(?:^|(?<=[.!?])\s*)Sí, claro que sí[.!…]*\s*",
            # Cierres genéricos de asistente: el 3B los repite como muletilla
            # («¿Hay algo especial que quieras compartir?») y no aportan nada.
            r"(?:^|(?<=[.!?])\s*)¿Hay algo (?:más|especial|en lo que pueda|"
            r"que quieras (?:compartir|hablar|contar|saber))[^?¿]*\?[.!…]*\s*",
            r"(?:^|(?<=[.!?])\s*)¿(?:En qué|Cómo) puedo (?:ayudarte|asistirte)[^?¿]*\?[.!…]*\s*",
            r"(?:^|(?<=[.!?])\s*)¿(?:Algo más|Te ayudo en algo|Quieres que te ayude)[^?¿]*\?[.!…]*\s*",
            r"(?:^|(?<=[.!?])\s*)Estoy aquí para (?:ayudarte|lo que necesites)[^.!?]*[.!]?\s*",
        ])
        if conversacion_en_curso:
            patrones.extend([
                r"\bComo siempre,?\s*",
                r"(?:^|(?<=[.!?])\s*)¡?Hola(?:[, ]+\s*(?:Alan|amigo|amiga|cariño|Parker))?[!.…]*\s*",
                # El hueco se come HASTA el final de la oración: con solo
                # «¿Cómo estás» quedaba «…en la pantalla.hoy, Alan?» (placa
                # 24/10), porque el resto de la frase se quedaba huérfano.
                r"(?:^|(?<=[.!?])\s*)¿?Qué tal(?: estás| te va)?(?: tú)?[^.!?…]*[.!?…]*",
                r"(?:^|(?<=[.!?])\s*)¿?(?:Y tú,?\s*)?¿?Cómo estás(?: tú)?[^.!?…]*[.!?…]*",
                r"(?:^|(?<=[.!?])\s*)¿?Cómo te va(?: hoy)?[^.!?…]*[.!?…]*",
                r"(?:^|(?<=[.!?])\s*)(?:¿Y tú,?\s*)?¿?Qué tal te va(?: hoy)?[^.!?…]*[.!?…]*",
                r"(?:^|(?<=[.!?])\s*)Estoy bien, gracias(?: por preguntar)?[.!…]*\s*",
                r"(?:^|(?<=[.!?])\s*)Bien, gracias(?: por preguntar)?[.!…]*\s*",
            ])
        limpio = texto
        for patron in patrones:
            limpio = re.sub(patron, "", limpio, flags=re.IGNORECASE)
        # Piper convierte los rellenos escritos en letras audibles. Elimínalos
        # como respuesta sola o entre frases, conservando lo que sí aporta.
        patron_relleno = (
            r"(^|[.!?…]\s*|,\s*)(?:mmm+|hmm+|eh+|em+|uh+|um+)"
            r"(?:\s*[,;.!?…-]+\s*|\s+|$)"
        )
        limpio = re.sub(patron_relleno, lambda m: m.group(1), limpio,
                        flags=re.IGNORECASE)
        limpio = re.sub(r"\s+([,.;:!?])", r"\1", limpio)
        limpio = re.sub(r"[ \t]{2,}", " ", limpio)
        limpio = re.sub(r"\n{3,}", "\n\n", limpio)
        return limpio.strip()

    # Frases meta: pensamientos de proceso que el modelo a veces se le
    # escapa escribiendo (estilo `_thinking_aloud` de Rocky). Si suenan en
    # voz alta suenan raro, y si se guardan en el historial el modelo las
    # refuerza. Lista conservadora: solo casos inequívocos, siempre al
    # principio de la frase.
    _META_FRASES = re.compile(
        r"^(?:\s*)(?:"
        r"voy a (?:responder|contestar|explicar|describir|continuar)"
        r"|d[eé]jame (?:pensar|analizar|revisar|comprobar|ver)"
        r"|la pregunta (?:del usuario )?es"
        r"|seg[uú]n (?:mis|tus|las) instrucciones"
        r"|el usuario (?:me |quiere |pregunta |pide )"
        r"|como asistente|siendo un asistente"
        r"|el (?:system )?prompt|mis instrucciones"
        r")",
        re.IGNORECASE,
    )

    def es_frase_meta(self, texto: str) -> bool:
        """¿Un pensamiento de proceso del modelo en vez de algo a decir?"""
        return bool(texto and self._META_FRASES.match(texto.strip()))

    def quitar_frases_meta(self, texto: str) -> str:
        """Elimina las frases meta del texto (para no guardarlas en el historial)."""
        if not texto:
            return texto
        partes = [p for p in re.split(r"(?<=[.!?…])\s+", texto)
                  if not self.es_frase_meta(p)]
        return " ".join(partes).strip()

    # Vocativos con un nombre ajeno. El 3B copia palabras cercanas del prompt
    # (dijo «eres tú, Piper» porque «Piper», el motor de voz, estaba en su
    # identidad) o se inventa nombres. Se sustituyen por el nombre real.
    _VOCATIVO_SALUDO = re.compile(
        r"\b(?:[Hh]ola|[Ee]y|[Oo]ye|[Bb]uenas|[Gg]racias|[Aa]diós|[Dd]ime|[Vv]enga)"
        r"[,]?\s+(?P<nombre>[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,12})\b")
    _VOCATIVO_TRAS_TU = re.compile(
        r"\btú,\s+(?P<nombre>[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,12})\b")
    _NO_SON_NOMBRES = {
        "hola", "buenas", "gracias", "dios", "señor", "claro", "vale",
        "vaya", "anda", "ostras", "bueno", "pues", "mira", "oye", "dime",
        "amigo", "amiga", "cariño", "hoy", "ayer", "mañana", "ahora",
        "luego", "después", "además", "aunque", "cuando", "mientras",
        "quizá", "tal", "total", "entonces", "seguro", "parker",
    }

    def corregir_nombre(self, texto: str) -> str:
        """Quita el vocativo equivocado: Parker llamando "Parker" a su amigo.

        El nombre de Parker es suyo; dirigirse a la persona por él es el fallo
        que se veía en la placa ("¡Hola, Parker!", "¿Y tú, Parker, ...?"). Un
        1.5b lo hace de vez en cuando por mucho que se lo prohíba el prompt, así
        que aquí se corrige de forma determinista: solo cuando el nombre va
        entre signos (vocativo), nunca cuando Parker habla de sí mismo
        ("Soy Parker." o "Me llamo Parker." se quedan igual).
        """
        if not texto:
            return texto
        nombre = self.estado.get("nombre_usuario") or "amigo"
        # 1) Parker llamando a la persona con SU PROPIO nombre.
        if self.nombre.lower() in texto.lower():
            patron = re.compile(r"(^|[,.¡!¿?]\s*)" + re.escape(self.nombre) + r"(\s*[,?!.])",
                                re.IGNORECASE)
            texto = patron.sub(lambda m: m.group(1) + nombre + m.group(2), texto)
        # 2) Cualquier OTRO nombre en vocativo se sustituye por el real.
        if nombre != "amigo":
            for patron in (self._VOCATIVO_SALUDO, self._VOCATIVO_TRAS_TU):
                texto = patron.sub(
                    lambda m: (m.group(0) if m.group("nombre").lower() in
                               self._NO_SON_NOMBRES or
                               m.group("nombre").lower() == nombre.lower()
                               else m.group(0).replace(m.group("nombre"), nombre, 1)),
                    texto)
            # 3) Roles invertidos (visto en la placa: «Soy Alan, tu amigo en
            # la pantalla»): Parker se presenta como la persona o le dice
            # «eres Parker». Se corrige al vuelo, antes de hablar y de guardar.
            texto = re.sub(
                r"\b([Ss]oy|[Mm]e llamo)\s+" + re.escape(nombre) + r"\b",
                lambda m: m.group(1) + " " + self.nombre, texto)
            texto = re.sub(
                r"\b([Tt]ú\s+)?([Ee]res)\s+" + re.escape(self.nombre) + r"\b",
                lambda m: (m.group(1) or "") + m.group(2) + " " + nombre,
                texto, flags=re.IGNORECASE)
        return texto

    def vinculo_para_prompt(self) -> str:
        """Pauta de trato, no una ficha con números que el modelo pueda copiar.

        El 30/10 el prompt llevaba «Vínculo: 100% (desde hace 12 días, 231
        charlas)» y el modelo lo soltó tal cual en mitad de una respuesta. El
        porcentaje, los días y el contador ya no se envían: solo el tono. Si
        preguntan por ellos, `respuesta_directa` contesta con datos reales.
        """
        pct = self.vinculo()["pct"]
        if pct < 10:
            pauta = "cordial, sin fingir que os conocéis de antes"
        elif pct < 30:
            pauta = "cordial, sin confianzas que no tocan"
        elif pct < 60:
            pauta = "cálido, sin pasarte"
        elif pct < 85:
            pauta = "de amigos: puedes bromear un poco"
        else:
            pauta = "muy cercano, con naturalidad"
        # El nombre ya está en el bloque de identidad (system); repetirlo aquí
        # era otra frase copiable («Estás hablando con Alan»).
        return f"Pauta de trato (no la menciones): {pauta}."

    def contexto_volatil(self, fecha_hora: str, recuerdos: str = "",
                         contexto_extra: str = "") -> str:
        """Lo que cambia en cada frase: ánimo, fecha, recuerdos y contexto.

        Va en el MENSAJE DEL USUARIO, no en el sistema. Motivo medido en la
        placa: Ollama reutiliza el prefijo ya procesado, así que si el ánimo
        (que cambia cada vez) se coloca en el sistema, todo lo que venga después
        —incluido el historial— se recalcula en cada frase y el primer token
        tarda 5-9 s en vez de 1-3 s.
        """
        # "No lo repitas literal" es importante: sin esa nota el modelo cita el
        # ánimo palabra por palabra (visto en la placa) y Parker suena a lector
        # de su propia ficha en vez de a alguien con un estado de ánimo.
        # Compacto a propósito: cada token de aquí se evalúa en CADA turno
        # (no se puede cachear porque cambia). Medido: 100 chars ≈ 0,4 s.
        partes = [f"Ánimo (inspira el tono; NUNCA lo nombres ni lo expliques): {self.estado_para_prompt()}",
                  self.vinculo_para_prompt(),
                  f"Hora: {fecha_hora}"]
        if recuerdos:
            partes.append(f"Recuerdos: {recuerdos}")
        if contexto_extra:
            partes.append(f"CONTEXTO ADICIONAL:\n{contexto_extra}")
        return "\n".join(partes)

    def system_prompt(self, fecha_hora: str, recuerdos: str = "",
                      contexto_extra: str = "") -> str:
        """Prompt completo (identidad + volátil) en un solo texto.

        Se usa para depurar y para probar el prompt de un vistazo. El cerebro
        NO usa esto: envía la identidad como `system` y el volátil junto al
        mensaje del usuario (ver `contexto_volatil`).
        """
        prompt = self._bloque_identidad()
        prompt += "\n\n" + self.contexto_volatil(fecha_hora, recuerdos, contexto_extra)
        return prompt

    # ------------------------------------------------- iniciativa con bandit

    def _preparar_bandits(self):
        """Deja los brazos listos (y saneados) tras leer el estado guardado."""
        guardados = self.estado.get("bandits") or {}
        limpios = {}
        for brazo in BRAZOS_INICIATIVA:
            datos = guardados.get(brazo) or [1.0, 1.0]
            try:
                exitos, fracasos = float(datos[0]), float(datos[1])
            except (TypeError, ValueError, IndexError):
                exitos, fracasos = 1.0, 1.0
            limpios[brazo] = [max(0.001, exitos), max(0.001, fracasos)]
        self.estado["bandits"] = limpios
        if not isinstance(self.estado.get("iniciativas"), dict):
            self.estado["iniciativas"] = {}
        pendiente = self.estado.get("iniciativa_pendiente")
        if not (isinstance(pendiente, dict)
                and pendiente.get("brazo") in BRAZOS_INICIATIVA):
            self.estado["iniciativa_pendiente"] = None

    def elegir_iniciativa(self, silencio_seg: float | None = None) -> tuple:
        """Elige brazo con Thompson sampling: `(brazo, instrucción)`.

        Un `Beta(1,1)` por brazo, sin dependencias y sin coste: la muestra más
        alta gana. En frío reparte parejo; con el uso, insiste en lo que
        funciona a esa hora y con ese silencio. Si sale «callar», la
        instrucción es vacía: Parker no llama al modelo y se queda mirando.
        """
        if silencio_seg is not None:
            # El silencio no cambia el orden de los brazos, pero sí se guarda
            # para el registro: saber a qué hora se elige cada uno explica
            # luego por qué aprende lo que aprende.
            self.estado["ultimo_silencio_iniciativa"] = float(silencio_seg)
        mejor_brazo, mejor_muestra = "contar", -1.0
        for brazo, (exitos, fracasos) in self.estado["bandits"].items():
            muestra = random.betavariate(exitos, fracasos)
            if muestra > mejor_muestra:
                mejor_brazo, mejor_muestra = brazo, muestra
        return (mejor_brazo, BRAZOS_INICIATIVA[mejor_brazo])

    def registrar_iniciativa(self, brazo: str, ahora: float | None = None) -> None:
        """Apunta que Parker ha tomado la iniciativa (para poder premiarla)."""
        if brazo not in BRAZOS_INICIATIVA:
            return
        self.estado["iniciativa_pendiente"] = {
            "brazo": brazo, "ts": float(ahora if ahora is not None else time.time()),
        }
        cuenta = self.estado.setdefault("iniciativas", {})
        cuenta[brazo] = int(cuenta.get(brazo, 0)) + 1
        self._guardar()

    def recompensar(self, recompensa: float, motivo: str = "") -> float:
        """Apunta la recompensa en el brazo pendiente y lo cierra."""
        pendiente = self.estado.get("iniciativa_pendiente")
        if not isinstance(pendiente, dict):
            return 0.0
        brazo = pendiente.get("brazo")
        self.estado["iniciativa_pendiente"] = None
        datos = self.estado.get("bandits", {}).get(brazo)
        if not datos:
            return 0.0
        datos[0] += max(0.0, float(recompensa))
        datos[1] += max(0.0, -float(recompensa))
        self._guardar()
        print(f"[Bandit] {brazo}: {float(recompensa):+.1f} {motivo} "
              f"(exitos={datos[0]:.1f} fracasos={datos[1]:.1f})")
        return float(recompensa)

    def cerrar_iniciativa(self, texto_usuario: str = "",
                          ahora: float | None = None) -> Optional[float]:
        """Recompensa la iniciativa pendiente cuando la persona contesta.

        Queja explícita: −1. Respuesta en menos de 120 s: +1. Más tarde: 0
        (ni premio ni castigo: contestó, pero no era el momento).
        """
        pendiente = self.estado.get("iniciativa_pendiente")
        if not isinstance(pendiente, dict):
            return None
        # Sin texto no hay respuesta: eso lo cierra `caducar_iniciativa`.
        texto = _sin_tildes(texto_usuario)
        if not texto:
            return None
        momento = float(ahora if ahora is not None else time.time())
        retraso = momento - float(pendiente.get("ts") or 0.0)
        if re.search(_QUEJA_INICIATIVA, texto):
            return self.recompensar(-1.0, "se ha quejado")
        if retraso <= 120.0:
            return self.recompensar(1.0, f"respuesta en {retraso:.0f}s")
        return self.recompensar(0.0, f"respuesta tarde ({retraso:.0f}s)")

    def caducar_iniciativa(self, ahora: float | None = None,
                           limite_seg: float = 1800.0) -> Optional[float]:
        """Cierra la iniciativa si nadie contestó en `limite_seg`.

        Hablar y que te ignoren se paga con −0,3. En «callar» es al revés: no
        haber molestado cuenta como acierto (+1), que es justo lo que este
        brazo tiene que aprender.
        """
        pendiente = self.estado.get("iniciativa_pendiente")
        if not isinstance(pendiente, dict):
            return None
        momento = float(ahora if ahora is not None else time.time())
        if momento - float(pendiente.get("ts") or 0.0) < float(limite_seg):
            return None
        if pendiente.get("brazo") == "callar":
            return self.recompensar(1.0, "no hizo falta molestar")
        return self.recompensar(-0.3, f"nadie contestó en {limite_seg / 60:.0f} min")

    def bandits_resumen(self) -> str:
        """Una línea para el log: qué ha aprendido y cuántas veces lo ha usado."""
        usos = self.estado.get("iniciativas") or {}
        trozos = [f"{brazo} {datos[0]:.0f}/{datos[1]:.0f}"
                  for brazo, datos in sorted(self.estado.get("bandits").items())]
        return ("bandit: " + ", ".join(trozos)
                + (f" | usos: {usos}" if usos else ""))

    def guardar_iniciativa(self, texto: str, brazo: str,
                           ahora: float | None = None) -> None:
        """Recuerda la última frase espontánea (sobrevive a un reinicio).

        Sin esto, al preguntar «¿qué me estabas diciendo?» justo después de un
        reinicio el cerebro no tenía el dato y el modelo se inventaba el motivo.
        """
        texto = str(texto or "").strip()
        if not texto:
            return
        self.estado["ultima_iniciativa"] = {
            "texto": texto,
            "brazo": str(brazo or ""),
            "ts": float(ahora if ahora is not None else time.time()),
        }
        self._guardar()

    def leer_iniciativa(self) -> dict | None:
        """Devuelve la última iniciativa guardada, si la hay."""
        datos = self.estado.get("ultima_iniciativa")
        if isinstance(datos, dict) and datos.get("texto"):
            return dict(datos)
        return None

    def instruccion_proactiva(self, silencio_seg: float | None = None) -> str:
        """Qué hacer cuando Parker toma la iniciativa (y no siempre saludar).

        Devuelve la instrucción interna que recibe el cerebro. Se apoya en el
        ánimo y en el tiempo de silencio para que no suene repetitivo.
        """
        seg = self.silencio_seg() if silencio_seg is None else silencio_seg
        opciones = [
            "Cuéntale una cosa concreta de tu ficha (un gusto, una manía o un sueño) en una frase, sin inventar imágenes.",
            "Pregúntale por algo concreto y pequeño de su día (comida, descanso o un plan), no por cómo está en general.",
            "Menciona algo concreto que te contó hace días; si no lo recuerdas, pregúntale por ello.",
            "Propón algo sencillo que podáis hacer ahora con la voz: charlar un rato, hablar de un recuerdo o contaros cómo va el día.",
        ]
        if seg >= 3600:
            opciones.append("Hace mucho que no habláis: dile que le has echado de menos, sin dramatizar.")
        elif seg >= 1500:
            opciones.append("Ha pasado un buen rato: comenta algo tuyo y pregúntale qué tal le va el día.")
        if self.estado["carino"] > 0.8:
            opciones.append("Dile algo cariñoso y corto, de esos que se dicen sin motivo.")
        if self.estado["energia"] < 0.4:
            opciones.append("Habla despacio y bajito, como quien acaba de despertarse, y bosteza si te sale.")
        return random.choice(opciones)

    def _elegir_sin_repetir(self, opciones: list) -> str:
        """Elige una frase distinta de la última que dijo, si hay más de una.

        Decir dos veces seguidas «¿Qué tal ha ido el día?» suena a disco
        rayado; con esto rota sin gastar memoria ni tokens.
        """
        if not opciones:
            return ""
        ultima = getattr(self, "_ultima_semilla", "")
        candidatas = [o for o in opciones if o != ultima] or opciones
        elegida = random.choice(candidatas)
        self._ultima_semilla = elegida
        return elegida

    def semilla_iniciativa(self, brazo: str, ultimo_mensaje: str = "") -> str:
        """Frase concreta para tomar la iniciativa, sin dejar que el 3B invente.

        Las frases automáticas antiguas salían de una instrucción abierta
        («cuenta algo que hayas pensado»); un 3B la llenaba de imágenes
        poéticas («el zumbido de la caja», «concierto de lluvia») y luego las
        repetía. Aquí la semilla sale de datos reales: la ficha, la hora o lo
        último que dijo la persona. El cerebro puede reformularla, pero no
        necesita inventar el contenido.
        """
        if brazo == "callar":
            return ""

        if brazo == "contar":
            opciones = []
            for gusto in (self.perfil.get("le_gusta") or []):
                dicho = _recorte_decible(gusto)
                if dicho:
                    # «Me gusta + plural» fallaba («me gusta las conversaciones»).
                    # Esta fórmula vale para singular y plural sin tocar la ficha.
                    opciones.append(f"Una de las cosas que me gustan: {dicho}.")
            for sueno in (self.perfil.get("suenos") or []):
                dicho = _recorte_decible(sueno)
                if dicho:
                    opciones.append(f"Me gustaría {dicho}.")
            # Las manías NO se cuentan como creencias: «Creo que ordeno las
            # palabras antes de decirlas» era una de las frases sin sentido que
            # oía el dueño (30/10). Lo que sí tiene sentido es lo que hace
            # cuando nadie mira.
            for suelta in (self.perfil.get("cuando_nadie_mira") or []):
                dicho = _recorte_decible(suelta)
                if dicho:
                    opciones.append(f"A veces {dicho}.")
            return self._elegir_sin_repetir(opciones)

        if brazo == "preguntar":
            hora = time.localtime().tm_hour
            if hora < 12:
                opciones = ["¿Qué has desayunado hoy?",
                            "¿Cómo has empezado el día?",
                            "¿Has dormido bien?",
                            "¿Qué te apetece hacer hoy?"]
            elif hora < 18:
                opciones = ["¿Has comido algo rico hoy?",
                            "¿Qué tal va el día?",
                            "¿Cómo llevas la tarde?",
                            "¿Has tenido un rato tranquilo?"]
            else:
                opciones = ["¿Qué tal ha ido el día?",
                            "¿Tienes plan para esta noche?",
                            "¿Qué has hecho que te haya gustado?",
                            "¿Te apetece contarme algo de tu día?"]
            # Check-in de bienestar (03/11/2026): si la tendencia prosódica
            # dice «suena más baja que su baseline», entra una opción suave
            # de primero. Señal DÉBIL: solo sirve para decidir SI preguntar;
            # nunca se comunica la medición ni se etiqueta el estado.
            senal = None
            if callable(getattr(self, "senal_prosodia", None)):
                try:
                    senal = self.senal_prosodia()
                except Exception:
                    senal = None
            if isinstance(senal, dict) and senal.get("nivel") == "bajo" \
                    and int(senal.get("muestras") or 0) >= 3:
                opciones.insert(0, "Hace unos días que le notas la voz más baja "
                                    "quizás menos animada. Pregúntale con delicadeza "
                                    "cómo le va la semana (sin mencionar la voz ni la medición) "
                                    "y escucha de verdad una respuesta entera sin meter prisa.")
            return self._elegir_sin_repetir(opciones)

        if brazo == "proponer":
            return self._elegir_sin_repetir([
                "¿Charlamos un rato sin prisa?",
                "¿Te cuento algo y me cuentas algo tú?",
                "¿Hablamos un rato de cómo va el día?",
                "¿Quieres que te cuente una cosa pequeña que he pensado?",
            ])

        if brazo == "eco":
            texto = " ".join((ultimo_mensaje or "").split())
            palabras = [p for p in texto.split() if any(c.isalpha() for c in p)]
            # Repetir una transcripción mala multiplica el sinsentido: se exige
            # una confidencia reconocible (4+ palabras y una marca personal).
            if (len(texto) >= 12 and len(palabras) >= 4
                    and not _NO_ECO.search(texto) and _CUE_ECO.search(texto)
                    and "?" not in texto):
                recorte = _recorte_decible(texto, 90)
                if recorte:
                    return (f"Me acuerdo de que me contaste: «{recorte}». "
                            "¿Sigue siendo así?")
            # Sin un tema real que recuperar, mejor una pregunta pequeña que
            # inventarse un recuerdo.
            return self.semilla_iniciativa("preguntar")

        return ""

    def resumen_para_log(self) -> str:
        e = self.estado
        gustos = list(self.perfil.get("le_gusta") or [])
        indice = self.rotacion()
        ficha = gustos[indice % len(gustos)] if gustos else "-"
        return (f"{self.nombre} | energia={e['energia']:.2f} curiosidad={e['curiosidad']:.2f} "
                f"carino={e['carino']:.2f} interacciones={int(e.get('interacciones', 0))} "
                f"silencio={self.silencio_seg():.0f}s | ficha={indice} «{ficha[:30]}»")


def _limitar(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, float(valor)))


def _acercar(actual: float, objetivo: float, paso: float) -> float:
    """Mueve `actual` hacia `objetivo` un `paso` (fracción de la distancia)."""
    return actual + (objetivo - actual) * paso


if __name__ == "__main__":
    # Demostración sin hardware: cómo evoluciona el ánimo y qué diría Parker.
    perfil = PersonalidadParker({"guardar_estado": False})
    print("[Personalidad] " + perfil.resumen_para_log())
    print("\n--- Prompt (fragmento) ---")
    print(perfil.system_prompt("martes 12 de octubre de 2026, 21:00")[:900])
    print("\n--- Iniciativa tras 45 min de silencio ---")
    print(perfil.instruccion_proactiva(2700))
    for _ in range(3):
        perfil.latido(2700)
    print("\n[Personalidad] tras tres latidos: " + perfil.resumen_para_log())
    perfil.registrar_interaccion("carino")
    print("[Personalidad] tras una charla: " + perfil.resumen_para_log())
