"""
modulos/apuntes.py
==================
Notas, listas y contadores: lo que Parker apunta **sin hora**, sin tocar el modelo.

La agenda ([modulos/agenda.py](agenda.py)) es para lo que tiene FECHA: alarmas,
temporizadores y citas. Aquí vive lo demás:

* **Notas**: «apunta que compre leche», «recuérdame llamar al fontanero»; luego
  «¿qué tenía apuntado?» o «léeme las notas», y «borra la nota de la leche».
* **Contadores** (pedido con este ejemplo: «quiero que me cuentes los litros de
  agua que voy bebiendo al día, te los voy diciendo y me los apuntas»):
  «apunta un litro de agua» suma al día; «hoy he bebido dos litros de agua» fija
  el total del día; «¿cuánta agua llevo hoy?» lo dice con el dato real.

Cada contador guarda sus días, así que sirve para agua, café, pastillas,
kilómetros o lo que se le pida sin que nadie toque el código. **Es dato, no
comportamiento**: Parker puede crear y borrar sus propias variables (contadores,
notas) por voz, pero no se reescribe el programa — eso rompería la huella de
versión y podría dejarlo sin arrancar (decidido con el dueño el 26/10/2026).

Todo se guarda en `parker.apuntes.json`. Los días de contador de más de 60 días
se olvidan; las notas duran hasta que se borran.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modulos.agenda import (_limpiar_payload, _numero, _numero_a_palabras,  # noqa
                            _plano)

# Verbos con los que se pide apuntar algo (los mismos que usa la agenda).
_VERBO_APUNTE = (r"(?:apunta|apuntame|apuntalo|anota|anotame|anotalo|guarda|"
                 r"guardame|recuerdame|no me olvides|apunta ahi)")
_VERBO_BORRAR = (r"(?:borra|borrar|borrala|borralo|quita|quitar|quitala|quitalo|"
                 r"elimina|eliminar|olvida|olvidar|desapunta)")
_MARCA_CONSULTA = (r"\b(?:que|cuales) (?:tengo|tenia|hay) apuntad|\bque tengo en "
                   r"(?:los apuntes|la lista)|\bleeme (?:los|las) (?:notas|apuntes)|"
                   r"\bque apuntes hay|\bque hay apuntado|\bmis (?:notas|apuntes)\b|"
                   r"\btengo algo apuntado\b|\bque tenia apuntado\b|"
                   r"\bque llevo apuntado\b|\bque hay en la lista\b")
_MARCA_CUANTO = (r"\b(?:cuanto|cuanta|cuantos|cuantas)\b|\bcomo llevo\b|"
                 r"\bque llevo\b|\bllevo (?:hoy|esta semana)\b")
# Palabras que no pueden ser el nombre de un contador en «¿cuánto X llevo?».
_NO_SON_CONTADOR = {"llevo", "llevas", "tengo", "hay", "apuntado", "apuntados",
                    "anotado", "hoy", "esta", "semana", "dia", "dias", "de",
                    "me", "te", "vas", "he", "y"}

# «un litro y medio», «1,5 litros», «dos vasos de agua»
_CANTIDAD = (r"(\d+(?:[.,]\d+)?|un|una|uno|medio|media|dos|tres|cuatro|cinco|"
             r"seis|siete|ocho|nueve|diez|once|doce|quince|veinte|"
             r"[a-z]+(?: y (?:medio|media))?)")
_MEDIDA = (r"(litros?|l|vasos?|tazas?|caf[eé]s?|cafes?|kil[oó]metros?|km|pasos?|"
           r"pastillas?|minutos?|horas?|euros?|veces|veces al dia|unidades?|"
           r"gramos?|kilos?|puntos?)")

# Verbos que fijan el total del día en vez de sumar.
_VERBO_FIJAR = (r"\b(?:he bebido|he tomado|he comido|he hecho|ya llevo|llevo hoy|"
                r"hoy llevo|he gastado|he andado|he caminado)\b")
# Verbos que suman a lo de hoy.
_VERBO_SUMAR = (r"\b(?:suma|sumale|anade|añade|apunta|apuntame|anota|anotame|"
                r"otro|otra|uno mas|una mas|mas)\b")

_DIAS_CONSERVAR = 60


def _cantidad_de_texto(token: str, texto: str) -> Optional[float]:
    """«otro litro» = 1; «medio» = 0,5; «dos» = 2; «1,5» = 1,5."""
    token = (token or "").strip()
    if token in ("otro", "otra"):
        return 1.0
    if token in ("medio", "media"):
        return 0.5
    if token.endswith(" y medio") or token.endswith(" y media"):
        base = _numero(token.rsplit(" y ", 1)[0])
        return None if base is None else base + 0.5
    if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        return float(token.replace(",", "."))
    valor = _numero(token)
    return None if valor is None else float(valor)


def _unidad_hablada(valor: float, unidad: str) -> str:
    """«un litro», «dos litros», «medio litro», «un litro y medio»."""
    singular = unidad[:-1] if unidad.endswith("s") and len(unidad) > 3 else unidad
    if abs(valor - 0.5) < 1e-6:
        return f"medio {singular}"
    plural = unidad
    if valor >= 2 and not unidad.endswith("s") and len(unidad) > 2:
        plural = unidad + "s"      # «cafe» -> «cafes»
    entero = int(valor)
    resto = valor - entero
    if entero == 0:
        return f"{resto:.2f} {unidad}".replace(".", ",")
    nombre = singular if valor < 2 else plural
    base = "un" if entero == 1 else _numero_a_palabras(entero)
    texto = f"{base} {nombre}"
    if abs(resto - 0.5) < 1e-6:
        texto += " y medio"
    return texto


class ApuntesParker:
    """Notas, listas y contadores diarios guardados en local (sin LLM)."""

    def __init__(self, ruta_apuntes: Optional[str] = None,
                 dias_conservar: int = _DIAS_CONSERVAR):
        self.ruta_apuntes = Path(ruta_apuntes) if ruta_apuntes else None
        self.dias_conservar = int(dias_conservar)
        self.notas: List[Dict] = []
        self.contadores: Dict[str, Dict] = {}
        self._cargar()

    # ------------------------------------------------------------------ estado

    def _cargar(self) -> None:
        if not self.ruta_apuntes or not self.ruta_apuntes.exists():
            return
        try:
            datos = json.loads(self.ruta_apuntes.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            print("[Apuntes] No pude leer los apuntes guardados; empiezo vacío.")
            return
        self.notas = [n for n in (datos.get("notas") or []) if isinstance(n, dict)]
        self.contadores = {k: v for k, v in (datos.get("contadores") or {}).items()
                           if isinstance(v, dict)}
        self._purgar()

    def _guardar(self) -> None:
        if not self.ruta_apuntes:
            return
        try:
            self.ruta_apuntes.write_text(json.dumps(
                {"version": 1, "notas": self.notas, "contadores": self.contadores},
                ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            print(f"[Apuntes] No se pudo guardar: {e}")

    def _purgar(self, ahora: Optional[datetime] = None) -> None:
        """Olvida los días de contador de hace más de `dias_conservar` días."""
        hoy = (ahora or datetime.now()).date()
        for contador in self.contadores.values():
            dias = contador.get("dias") or {}
            for fecha in list(dias):
                try:
                    antiguedad = (hoy - datetime.fromisoformat(fecha).date()).days
                except ValueError:
                    del dias[fecha]
                    continue
                if antiguedad > self.dias_conservar:
                    del dias[fecha]

    @staticmethod
    def _clave(nombre: str) -> str:
        """«aguas» y «agua» son el mismo contador (y «litros» ≠ «agua»)."""
        nombre = _plano(nombre)
        if nombre.endswith("s") and len(nombre) > 3:
            nombre = nombre[:-1]
        return nombre

    # ---------------------------------------------------------------- órdenes

    def parece_contador(self, mensaje: str) -> bool:
        """¿Trae cantidad y unidad? («un litro de agua», «tres cafés»).

        Lo usa `parker.py` para darle prioridad a los contadores sobre la
        agenda: «apunta un litro de agua a las dos de la tarde» es un contador,
        no una alarma (visto en la placa el 26/10).
        """
        return self._leer_cantidad(_plano(mensaje)) is not None

    def procesar(self, mensaje: str,
                 ahora: Optional[datetime] = None) -> Optional[str]:
        """Contesta si era una orden de apuntes, o `None` si no lo era."""
        texto = _plano(mensaje)
        if not texto:
            return None
        ahora = ahora or datetime.now()

        # 1) ¿Cuánto llevo? («¿cuánta agua llevo hoy?»). La pregunta no dice
        #    ninguna cantidad: el nombre del contador se saca aparte.
        if re.search(_MARCA_CUANTO, texto):
            nombre = self._nombre_consulta(texto)
            if nombre:
                return self._responder_cuanto(nombre, ahora)

        # 2) Sumar o fijar el total del día («apunta un litro de agua», «hoy he
        #    bebido dos litros de agua»).
        cantidad = self._leer_cantidad(texto)
        if cantidad is not None and (re.search(_VERBO_SUMAR, texto)
                                     or re.search(_VERBO_FIJAR, texto)):
            valor, unidad, nombre = cantidad
            return self._anotar_cantidad(valor, unidad, nombre, texto, ahora)

        # 3) Preguntar por las notas.
        if re.search(_MARCA_CONSULTA, texto):
            return self._listar_notas()

        # 4) Borrar notas (o un contador entero).
        if re.search(_VERBO_BORRAR, texto):
            respuesta = self._borrar(texto)
            if respuesta is not None:
                return respuesta

        # 5) Apuntar una nota sin hora.
        if re.search(_VERBO_APUNTE, texto):
            return self._anotar_nota(texto, ahora)
        return None

    @staticmethod
    def _leer_cantidad(texto: str):
        """`(valor, unidad, nombre)` de «un litro de agua», o `None`."""
        match = re.search(rf"\b{_CANTIDAD}\s*{_MEDIDA}\b(?:\s+de\s+([a-z]+))?",
                          texto)
        if not match:
            return None
        valor = _cantidad_de_texto(match.group(1), texto)
        if valor is None or valor <= 0 or valor > 100000:
            return None
        unidad = match.group(2)
        # Abreviaturas: «1,5 l» y «5 km» se dicen enteros.
        unidad = {"l": "litros", "km": "kilometros"}.get(unidad, unidad)
        nombre = match.group(3) or unidad
        if unidad in ("litro", "litros") and nombre in ("agua", "aguas"):
            nombre = "agua"
        # «dos litros y medio de agua»: el medio va después de la unidad y el
        # nombre, después. Por eso se miran los dos trozos a mano.
        fin = match.end()
        medio = re.match(r"\s*y\s+medi[oa]\b", texto[fin:fin + 12])
        if medio:
            valor += 0.5
            fin += len(medio.group(0))
        tras = re.match(r"\s+de\s+([a-z]+)\b", texto[fin:fin + 20])
        if tras and not match.group(3):
            nombre = tras.group(1)
            if unidad in ("litro", "litros") and nombre in ("agua", "aguas"):
                nombre = "agua"
        return (valor, unidad, nombre)

    @staticmethod
    def _nombre_consulta(texto: str) -> str:
        """Contador por el que se pregunta: «cuántos litros DE agua» -> agua."""
        match = re.search(r"\bde\s+([a-z]+)\b", texto)
        if match and match.group(1) not in _NO_SON_CONTADOR:
            return match.group(1)
        match = re.search(rf"\b(?:cuanto|cuanta|cuantos|cuantas|como|que)\s+"
                          rf"(?:es\s+)?(?:el|la|los|las|mi|tu)?\s*"
                          rf"({_MEDIDA}|[a-z]+)\b", texto)
        if match and match.group(1) not in _NO_SON_CONTADOR:
            return match.group(1)
        return ""

    def _anotar_cantidad(self, valor: float, unidad: str, nombre: str,
                         texto: str, ahora: datetime) -> str:
        clave = self._clave(nombre)
        fijar = bool(re.search(_VERBO_FIJAR, texto))
        contador = self.contadores.get(clave)
        if contador is None:
            contador = {"nombre": clave, "unidad": unidad, "dias": {}}
            self.contadores[clave] = contador
        if contador.get("unidad") != unidad:
            # Misma cosa con otra unidad («vasos» tras «litros»): manda la nueva,
            # pero se avisa para que no parezca que se pierden datos.
            if contador.get("unidad") and contador["unidad"] != unidad:
                print(f"[Apuntes] {clave}: cambio de unidad "
                      f"{contador['unidad']} -> {unidad}")
            contador["unidad"] = unidad
        dias = contador["dias"]
        fecha = ahora.date().isoformat()
        anterior = float(dias.get(fecha, 0.0))
        total = valor if fijar else anterior + valor
        dias[fecha] = round(total, 3)
        self._guardar()
        sufijo = "" if self._clave(unidad) == clave else f" de {clave}"
        if fijar:
            print(f"[Apuntes] {clave} {fecha} fijado en {total}")
            return f"Apuntado: hoy llevas {_unidad_hablada(total, unidad)}{sufijo}."
        print(f"[Apuntes] {clave} {fecha}: +{valor} = {total}")
        return (f"Anotado: {_unidad_hablada(valor, unidad)}{sufijo}. Hoy llevas "
                f"{_unidad_hablada(total, unidad)}{sufijo}.")

    def _responder_cuanto(self, nombre: str, ahora: datetime) -> str:
        clave = self._clave(nombre)
        contador = self.contadores.get(clave)
        if contador is None:
            return f"Todavía no llevo nada apuntado de {clave}."
        unidad = contador.get("unidad") or "unidades"
        dias = contador.get("dias") or {}
        hoy = float(dias.get(ahora.date().isoformat(), 0.0))
        if hoy <= 0:
            return f"Hoy todavía no has apuntado nada de {clave}."
        sufijo = "" if self._clave(unidad) == clave else f" de {clave}"
        resumen = f"Hoy llevas {_unidad_hablada(hoy, unidad)}{sufijo}."
        if len(dias) > 1:
            resumen += f" Llevas {_numero_a_palabras(len(dias))} días apuntados."
        return resumen

    def _anotar_nota(self, texto: str, ahora: datetime) -> str:
        # Quita verbos y conectores con la misma limpieza que usa la agenda con
        # las citas: «Parker, apunta que compre leche» -> «compre leche».
        limpio = _limpiar_payload(texto, [rf"\b{_VERBO_APUNTE}\b"])
        if len(limpio) < 3:
            return "Dime qué quieres que apunte."
        self.notas.append({"id": f"{int(time.time() * 1000) % 10 ** 9}",
                           "texto": limpio, "creado": ahora.timestamp()})
        self._guardar()
        print(f"[Apuntes] Nota: {limpio}")
        return f"Apuntado: {limpio}."

    def _listar_notas(self) -> str:
        if not self.notas:
            return "No tienes nada apuntado."
        textos = [n.get("texto", "") for n in self.notas[-6:]]
        return f"Tienes {len(self.notas)} apuntes: " + "; ".join(textos) + "."

    def _borrar(self, texto: str) -> Optional[str]:
        if re.search(r"\b(?:contador|contadores)\b", texto):
            match = re.search(r"\b(?:de|del|para)\s+([a-z]+)", texto)
            clave = self._clave(match.group(1)) if match else ""
            if clave and clave in self.contadores:
                del self.contadores[clave]
                self._guardar()
                return f"Borrado el contador de {clave}."
            return None
        if not re.search(r"\b(?:apuntes?|notas?|lista|todo lo apuntado)\b", texto):
            return None
        if not self.notas:
            return "No hay nada apuntado que borrar."
        match = re.search(r"\b(?:de|del|sobre|lo de)\s+(.{3,40})$", texto)
        busca = _plano(match.group(1)) if match else ""
        # «de LA leche» busca «leche»: el artículo no está en la nota guardada.
        busca = re.sub(r"^(?:el|la|los|las|un|una|unos|unas|mi|mis|del)\s+", "", busca)
        if re.search(r"\b(?:todo|todos|todas)\b", texto) and not busca:
            cuantas = len(self.notas)
            self.notas = []
            self._guardar()
            return f"He borrado {cuantas} apuntes."
        if busca:
            fuera = [n for n in self.notas if busca in n.get("texto", "")]
            if not fuera:
                return "No encuentro esa nota."
            for nota in fuera:
                self.notas.remove(nota)
            self._guardar()
            if len(fuera) == 1:
                return f"Borrado: {fuera[0].get('texto', '')}."
            return f"He borrado {len(fuera)} apuntes."
        if len(self.notas) == 1:
            unica = self.notas.pop()
            self._guardar()
            return f"Borrado: {unica.get('texto', '')}."
        return "¿Cuál de los apuntes quieres que borre?"
