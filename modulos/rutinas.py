"""
modulos/rutinas.py
==================
El día de Parker: dormir, despertar, el parte del día, callarse un rato y apagarse.

Pedido el 26/10/2026: modo dormir, parte del día y «cállate un rato», más una
forma de decirle «Parker, apágate» que lo deje todo cerrado para poder cortar la
corriente sin romper nada.

Son órdenes de **estado de sesión** (Sistema 1, sin LLM):

* **Buenas noches**: se calla, deja de tomar la iniciativa y la cara se acuesta
  (quien pone la cara es `parker.py`; este módulo solo decide).
* **Buenos días**: despierta y suelta el parte del día si hay algo apuntado.
* **Cállate un rato**: silencio temporal («cállate diez minutos»). «Silencio» a
  secas sigue siendo el apagado de voz de `modulos/acciones.py`; esto es distinto:
  vuelve solo y no toca el volumen.
* **Apágate**: cierre limpio. Parker se despide, guarda memoria y agenda, cierra
  pantalla y audio y deja de escuchar; `tools/arrancar.sh` **no** lo reinicia
  porque el proceso termina con código 0. La placa sigue encendida y ya se puede
  desconectar la corriente sin riesgo para la tarjeta.

El estado no se guarda en disco a propósito: si la placa se reinicia, Parker
está despierto otra vez, que es lo que quieres al enchufarla.

El parte del día **no** lo escribe el modelo: es una lista de datos que Parker
sabe con certeza (su agenda) y se dice tal cual, como las fechas.
"""

import re
from datetime import datetime, time
from typing import Optional, Tuple

from modulos.agenda import (_duracion, _duracion_hablada, _duracion_suelta,  # noqa
                            _plano)

ORDEN_DORMIR = "dormir"
ORDEN_DESPERTAR = "despertar"
ORDEN_APAGAR = "apagar"
# 01/11: mantenimiento por voz. El borrado pide confirmación en parker.py.
ORDEN_BORRAR_MEMORIA = "borrar_memoria"
ORDEN_REINICIAR = "reiniciar"

# Silencio temporal cuando no se dice cuánto.
SILENCIO_POR_DEFECTO_SEG = 10 * 60
# «no hables más» / «hasta que te diga»: silencio indefinido.
SILENCIO_INDEFINIDO_SEG = 365 * 24 * 3600


class RutinasParker:
    """Estado del día de Parker: dormido, callado, hora del parte y apagado."""

    def __init__(self, hora_parte: str = "08:30", parte_si_vacio: bool = False):
        self.hora_parte = self._leer_hora(hora_parte)
        self.parte_si_vacio = bool(parte_si_vacio)
        self.dormido = False
        self.calla_hasta = 0.0
        self.ultimo_parte = ""      # fecha ISO del último parte dicho
        self._silencio_avisado = True

    # ------------------------------------------------------------------ estado

    @staticmethod
    def _leer_hora(texto: str) -> Tuple[int, int]:
        match = re.match(r"\s*(\d{1,2})[:.](\d{2})", str(texto or ""))
        if not match:
            return (8, 30)
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return (h, m)
        return (8, 30)

    def dormir(self) -> None:
        self.dormido = True
        self.calla_hasta = 0.0
        self._silencio_avisado = True

    def despertar(self) -> None:
        self.dormido = False

    def callar(self, segundos: int, ahora: Optional[datetime] = None) -> None:
        base = (ahora or datetime.now()).timestamp()
        self.calla_hasta = base + max(0, int(segundos))
        self._silencio_avisado = False

    def debe_callarse(self, ahora: Optional[datetime] = None) -> bool:
        ahora = ahora or datetime.now()
        return self.dormido or ahora.timestamp() < self.calla_hasta

    def silencio_expirado(self, ahora: Optional[datetime] = None) -> bool:
        """True UNA vez cuando el «cállate un rato» acaba (para avisar)."""
        ahora = ahora or datetime.now()
        if self._silencio_avisado or self.calla_hasta == 0.0:
            return False
        if ahora.timestamp() >= self.calla_hasta:
            self._silencio_avisado = True
            return True
        return False

    def tema_silencio(self) -> str:
        """Cómo se cuenta el silencio en el log de autonomía."""
        if self.dormido:
            return "dormido"
        if self.calla_hasta > 0.0:
            return (f"callado {max(0, self.calla_hasta - datetime.now().timestamp()):.0f}s")
        return ""

    # ---------------------------------------------------------------- órdenes

    def procesar(self, mensaje: str,
                 ahora: Optional[datetime] = None) -> Optional[Tuple[str, Optional[str]]]:
        """`(frase, acción)` si era una orden del día, o `None` si no lo era.

        Acciones: `dormir`, `despertar`, `apagar`, `borrar_memoria` o
        `reiniciar` (las ejecuta `parker.py`).
        """
        texto = _plano(mensaje)
        if not texto:
            return None
        ahora = ahora or datetime.now()
        sin_muletillas = re.sub(r"^(?:oye |eh |parker |por favor |anda )+", "", texto)

        # Mantenimiento (01/11): borrar la memoria y reiniciar. Van antes que
        # dormir/callar para que funcionen también con Parker callado.
        if re.search(
                r"\b(?:borra|borrar|limpia|limpiar|olvida|olvidar|vacia|vaciar)\s+"
                r"(?:(?:toda\s+)?(?:tu|la)\s+)?memoria\b"
                r"(?!\s+(?:del|de la|de tu)\s+(?:movil|telefono|ordenador|pc|placa))|"
                r"\b(?:borra|borrar|limpia|limpiar|olvida|olvidar|vacia|vaciar)\s+"
                r"(?:todos\s+)?(?:tus\s+|los\s+)?recuerdos\b|"
                r"\bolvida\s+todo\b", texto):
            return ("", ORDEN_BORRAR_MEMORIA)
        if re.match(
                r"^(?:reinicia|reiniciate|reiniciar|reinicio|reinicia ya)"
                r"(?:\s+(?:parker|el sistema|todo|ahora|ya))?\s*$",
                sin_muletillas):
            return ("", ORDEN_REINICIAR)

        # Preguntar cómo está es conversación, no una orden: se contesta.
        if re.search(r"\b(?:estas|sigues|ya estas) (?:despiert[oa]|dormid[oa])\b", texto):
            if self.dormido:
                return ("Estoy dormido, pero te oigo.", None)
            return ("Despierto, sí.", None)

        pedido_silencio = self._pedido_silencio(texto)
        if pedido_silencio is not None:
            segundos, dicho = pedido_silencio
            self.callar(segundos, ahora)
            if segundos >= SILENCIO_INDEFINIDO_SEG:
                return ("Vale, me callo hasta que me digas.", None)
            rato = _duracion_hablada(segundos) if dicho else "un rato"
            return (f"Vale, me callo {rato}.", None)

        if re.search(r"\b(?:buenas noches|a dormir|me voy a dormir|me voy a la cama|"
                     r"voy a la cama|es hora de dormir|duermete|hasta manana)\b", texto):
            self.dormir()
            return ("Buenas noches. Descansa.", ORDEN_DORMIR)

        # «despiértate» sí; «despierta a tu hermana» no es una orden para él.
        pide_despertar = bool(re.match(
            r"^(?:despierta|despiertate|despierta ya|ya es de dia|arriba)\b",
            sin_muletillas))
        if pide_despertar and re.match(
                r"^(?:despierta|despierta ya)\s+(?:a|al|la|el|los|las|mi|tu|su|un|una)\b",
                sin_muletillas):
            pide_despertar = False
        if sin_muletillas.startswith("buenos dias") or pide_despertar:
            self.despertar()
            return ("Buenos días.", ORDEN_DESPERTAR)

        # Variantes del STT: «apágate» llega a veces como «apajate» o
        # «apagate» (medido en la placa el 26/10, y ese día no se apagó nada).
        if re.search(r"\bapag[ae]te\b(?=\s|$)|"          # apagate / apagete
                     r"\bapajate\b|"                        # apajate (STT)
                     r"\bapaga\s+(?:ya|todo|el sistema|la placa|el ordenador|"
                     r"parker|y para)\b",
                     texto):
            return ("Vale, me voy a dormir del todo. Hasta luego.", ORDEN_APAGAR)
        return None

    @staticmethod
    def _pedido_silencio(texto: str) -> Optional[Tuple[int, bool]]:
        """`(segundos, lo_dijo)` de «cállate un rato», o `None` si no lo pide."""
        if not re.search(r"\b(?:callate|callete|callarte|callaros|estate callado|"
                         r"no hables|no digas nada|guardate silencio|"
                         r"guardate las palabras)\b", texto):
            return None
        if re.search(r"\b(?:para siempre|hasta que te diga|no hables mas|"
                     r"deja de hablar)\b", texto):
            return (SILENCIO_INDEFINIDO_SEG, True)
        duracion = _duracion(texto) or _duracion_suelta(texto)
        if duracion is not None:
            return (max(30, int(duracion[0])), True)
        return (SILENCIO_POR_DEFECTO_SEG, False)

    # ------------------------------------------------------------ parte del día

    def toca_parte(self, ahora: Optional[datetime] = None) -> bool:
        """¿Es la hora del parte del día y no se ha dicho todavía?"""
        ahora = ahora or datetime.now()
        if self.dormido or self.debe_callarse(ahora):
            return False
        if self.ultimo_parte == ahora.date().isoformat():
            return False
        return ahora.time() >= time(*self.hora_parte)

    def marcar_parte(self, ahora: Optional[datetime] = None) -> None:
        self.ultimo_parte = (ahora or datetime.now()).date().isoformat()

    def parte_del_dia(self, agenda, ahora: Optional[datetime] = None,
                      nombre: str = "") -> Optional[str]:
        """«Buenos días, Alan. Hoy tienes: …». `None` si no hay nada que contar.

        Los datos salen de la agenda ya probada (`del_dia` y `_descripcion`):
        mismo formato de hora hablada que usa para las citas.
        """
        ahora = ahora or datetime.now()
        saludo = f"Buenos días{', ' + nombre if nombre else ''}."
        if agenda is None:
            return None
        # Citas del día y alarmas que aún no han sonado. Los temporizadores no
        # entran: son de la sesión (a las 8 de la mañana uno de ayer ya no dice
        # nada) y lo que ya sonó, tampoco.
        hoy = [a for a in agenda.del_dia(ahora.date(), ahora)
               if not a.get("avisado") and a.get("tipo") != "temporizador"]
        if not hoy:
            if not self.parte_si_vacio:
                return None
            return f"{saludo} No tienes nada apuntado para hoy."
        frases = [re.sub(r"^hoy a las", "a las", agenda._descripcion(a, ahora))
                  for a in hoy[:4]]
        resto = len(hoy) - len(frases)
        cola = f" y {resto} más" if resto else ""
        return f"{saludo} Hoy tienes: {agenda._unir(frases)}{cola}."
