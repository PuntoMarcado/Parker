"""
modulos/hechos.py
=================
Memoria de datos EXACTOS dichos por la persona ("el hecho, no la transcripción").

Por qué existe (03/11/2026): en la evaluación de la memoria vectorial, 4 de 8
preguntas cortas de hechos («¿cómo se llama mi dentista?») no se recuperaban.
No es culpa de ChromaDB: es el límite de un embedding de 384 dims con frases
de conversación. Un nombre propio o un dato ("soy alérgico a la penicilina")
no se encuentra por similitud semántica con fiabilidad.

Aquí se guardan como SLOTS: (dentista -> "Dra. Puig"), (alergia ->
"penicilina"), (mascota -> "Rocky"). Son tan pocos (decenas) que NO necesi­tan
búsqueda: van SIEMPRE en el bloque estable del prompt (system), donde además
pagan cero prefill por turno (caché de prefijo).

Reglas del diseño:
  - El valor es el DATO, no la frase entera de la persona.
  - Cambiar un dato no borra el viejo: lo invalida (`hasta`), por si vuelve.
  - Solo SQLite y regex: cero dependencias y ~0 ms por turno.
  - Nunca se guardan órdenes, preguntas ni datos de Parker (solo de la persona).
"""

import os
import re
import sqlite3
from datetime import datetime

# ¿Qué regex "convierte en hecho"? Cada tupla es (slot, patrón). Los valores
# se recortan a lo dicho antes de un signo de puntuación para no arrastrar
# media frase («mi dentista es la Dra. Puig y va el jueves» -> "la Dra. Puig").
#
# Alergia va FIRST: «mi dentista soy...» no existe, pero «soy alérgico a X del
# dentista» sí; por orden no hay colisiones reales, se prioriza por legibilidad.
#
# Familia/mascota SOLO con "se llama": «mi madre es Germana» es rareza y «mi
# madre es muy simpática» no es un hecho; el patrón llama/sellama lo evita.
_PATRONES = (
    ("edad",
     r"\btengo\s+(?P<v>\d{1,3})\s+a[ñn]os\b"),
    ("alergia",
     r"\b(?:soy\s+al[eé]rgic[oa]|tengo\s+alergi[oa])\s+(?:a\s+)?"
     r"(?P<v>[^\n.!?;]{2,60})"),
    ("dentista",
     r"\bmi\s+dentista\s+(?:se\s+)?(?:llama|es)\s+(?P<v>[^\n.!?;]{2,50})"),
    ("medico",
     r"\bmi\s+m[eé]dico(?:\s+de\s+)?(?:cabecera)?\s+(?:se\s+)?(?:llama|es)\s+"
     r"(?P<v>[^\n.!?;]{2,50})"),
    ("profesor",
     r"\bmi\s+(?:profesor[áa]?|profesora|profe|tutor[áa]?)\s+(?:se\s+)?(?:llama|es)\s+"
     r"(?P<v>[^\n.!?;]{2,50})"),
    ("familia",
     r"\bmi\s+(?:madre|mam[aá]|padre|pap[aá]|herman[oa]|abuel[oa]|t[íi]o|t[íi]a|"
     r"primo|prim[áa]?|prima|madrasta|padrastro)\s+(?:se\s+)?llama\s+"
     r"(?P<v>[A-Za-zÁÉÍÓÚÜÑáéíóúñü][^\n.!?;]{0,40})"),
    ("mascota",
     r"\bmi\s+(?:perro|gato|perr[oa]|gat[oa]|mascota|conejo|p[áa]jaro|pájaro)\s+"
     r"(?:se\s+)?(?:llama|es)\s+(?P<v>[A-Za-zÁÉÍÓÚÜÑáéíóúñü][^\n.!?;]{0,40})"),
    ("vive",
     r"\bvivo\s+en\s+(?P<v>[^\n.!?;]{2,50})"),
    ("direccion",
     r"\bmi\s+(?:direcci[óo]n|calle|piso)\s+(?:es|est[aá]|queda)\s+(?P<v>[^\n.!?;]{2,60})"),
    ("trabajo",
     r"\btrabajo\s+(?:en|como|de)\s+(?P<v>[^\n.!?;]{2,60})"),
    ("estudios",
     r"\b(?:estudio|sigo\s+estudiando)\s+(?P<v>[^\n.!?;]{2,60})"),
    ("cumple",
     r"\bmi\s+cumplea[ñn]os\s+(?:es(?:\s+(?:el|a))?|es)\s+(?P<v>[^\n.!?;]{2,40})"),
    ("favorito",
     r"\bmi\s+(?:comida|color|desayuno|pel[íi]cula|peli|serie|canci[óo]n|grupo|"
     r"deporte|equipo)\s+favorit[oa]\s+(?:es|son)\s+(?P<v>[^\n.!?;]{2,60})"),
)

# Se compilan una única vez al importar (eran cadenas crudas y finditer
# petaba con 'str' has no attribute 'finditer'; visto en la primera prueba
# mínima del 03/11).
_PATRONES = tuple((slot, re.compile(patron, re.IGNORECASE))
                  for slot, patron in _PATRONES)

# Palabras que acaban una lista de valores colgada («, y », « y al »): para
# alergias múltiples («penicilina, frutos secos y marisco») se ROMPE al
# guardar cada trozo como SU valor propio con el mismo slot.
_SEPARADORES_LISTA = re.compile(
    r"\s*(?:,\s*y\s+|\s+y\s+(?:al|la|a\s+las|a\s+l[oa]s)\s*|,\s*|\s*y\s+)",
    re.IGNORECASE)

# Palabras que delatan que el "hecho" es otra cosa (órdenes, charla).
_NO_HECHO = re.compile(
    r"\b(?:borra|apunta\s+que|pon\s+una?|dime|puedes|quiero\s+que|no\s+s[eé]|"
    r"promete|suena|ponlos?)\b", re.IGNORECASE)

_MAX_VALOR = 80
_MAX_BLOQUE = 16  # hechos máximo en el prompt (los más recientes)


# Abreviaturas con punto que cortarían el valor en el símbolo «.» de las
# clases de carácter: «Mi dentista es la Dra. Puig» daba como valor «Dra».
# Se marcan antes de extraer y se desmarcan al guardar.
_ABREVIATURAS = re.compile(r"\b(Dra|Dr|Sra|Sr|Srta|Ldo|Lda|Ing)\.")
_MARCA = "§P§"


def _marcar_abreviaturas(texto: str) -> str:
    return _ABREVIATURAS.sub(r"\1" + _MARCA, texto or "")


def _desmarcar_abreviaturas(valor: str) -> str:
    return (valor or "").replace(_MARCA, ".")


def _limpiar_valor(valor: str) -> str:
    valor = re.sub(r"\s+", " ", (valor or "")).strip()
    valor = valor.strip(",;: ").strip()
    if len(valor) > _MAX_VALOR:
        valor = valor[:_MAX_VALOR - 1].rstrip() + "…"
    return valor


def _clave_comparacion(valor: str) -> str:
    """Huella del valor, sin acentos ni mayúsculas: 'Alergico' == 'alérgico'."""
    plano = re.sub(r"[^a-z0-9\s]", "", (valor or "").lower())
    return re.sub(r"\s+", " ", plano).strip()


_ETIQUETAS = {
    "edad": "Edad",
    "alergia": "Alergias",
    "dentista": "Dentista",
    "medico": "Médico",
    "profesor": "Profesor",
    "familia": "Familia",
    "mascota": "Mascota",
    "vive": "Vive en",
    "direccion": "Vive en",
    "trabajo": "Trabajo",
    "estudios": "Estudia",
    "cumple": "Cumpleaños",
    "favorito": "Favorito",
}


class HechosParker:
    """Tabla de hechos exactos de la persona (SQLite)."""

    def __init__(self, ruta: str = "./parker.hechos.db"):
        base = os.path.dirname(os.path.abspath(ruta))
        if base:
            os.makedirs(base, exist_ok=True)
        self.ruta = ruta
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS hechos (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 slot TEXT NOT NULL,
                 valor TEXT NOT NULL,
                 desde TEXT NOT NULL,
                 hasta TEXT,
                 fuente TEXT,
                 confianza REAL NOT NULL DEFAULT 0.6
               )""")
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_hechos_slot ON hechos(slot, hasta)")
        self._con.commit()

    # ------------------------------------------------------------ guardar ---
    def poner(self, slot: str, valor: str, fuente: str = "turno",
              confianza: float = 0.6, agrupar: bool = False) -> bool:
        """Guarda (o actualiza) un hecho. True si hubo cambio nuevo.

        Un dato cambia de valor no borra el anterior: lo invalida con `hasta`.
        Así si la persona vuelve a un dentista anterior, el dato sigue aquí.
        Con `agrupar=True` (listas, p. ej. alergias) los valores conviven:
        «penicilina» y «frutos secos» son dos datos, no una corrección.
        """
        slot = str(slot or "").strip()
        valor = _limpiar_valor(valor)
        if not slot or not valor or len(valor) < 2:
            return False
        clave = _clave_comparacion(valor)
        if not clave:
            return False
        fila = self._con.execute(
            "SELECT id, valor FROM hechos WHERE slot = ? AND hasta IS NULL "
            "ORDER BY id DESC", (slot,)).fetchall()
        for _id, viejo in fila:
            if _clave_comparacion(viejo) == clave:
                return False  # mismo dato, nada que hacer
        ahora = datetime.now().isoformat(timespec="seconds")
        if fila and not agrupar:
            self._con.execute(
                "UPDATE hechos SET hasta = ? WHERE slot = ? AND hasta IS NULL",
                (ahora, slot))
        self._con.execute(
            "INSERT INTO hechos (slot, valor, desde, hasta, fuente, confianza) "
            "VALUES (?, ?, ?, NULL, ?, ?)",
            (slot, valor, ahora, fuente, max(0.05, min(1.0, float(confianza)))))
        self._con.commit()
        return True

    def actualizar_desde_texto(self, texto: str, fuente: str = "turno",
                               confianza: float = 0.6) -> int:
        """Extrae hechos de un mensaje de la persona y los guarda.

        Devuelve cuántos datos NUEVOS (o cambiados) se apuntaron. Barato a
        propósito: solo regex, ~0 ms, sin LLM. Los patrones son conservadores:
        si no encajan bien, mejor lo guarda la conversación que este módulo.
        """
        texto = (texto or "").strip()
        if not texto or len(texto) < 6 or _NO_HECHO.search(texto):
            return 0
        texto = _marcar_abreviaturas(texto)
        nuevos = 0
        for slot, patron in _PATRONES:
            for coincidencia in patron.finditer(texto):
                valor_marcado = _limpiar_valor(coincidencia.group("v") or "")
                if not valor_marcado:
                    continue
                # Listas («penicilina y frutos secos»): SOLO alergia se
                # trocea entero. En el resto, la coma suele venir después del
                # dato («la Dra. Puig, en la calle Mayor»): con el primer
                # trozo vale y «en la calle…» es otra cosa, no el dato.
                trozos = [t for t in _SEPARADORES_LISTA.split(valor_marcado)
                          if t and t.strip()]
                if slot != "alergia" and len(trozos) > 1:
                    trozos = trozos[:1]
                for trozo in trozos[:4]:
                    trozo = _limpiar_valor(trozo)
                    # Artículos suelto en cadena («a los frutos secos»):
                    # se quitan en bucle, salvo que detrás venga un título
                    # marcado (Dra§P§).
                    for _ in range(3):
                        trozo = re.sub(
                            r"^(?:el|la|los|las|lo|al|a)\s+"
                            r"(?!(?:Dra|Dr|Sra|Sr|Srta|Ldo|Lda|Ing)§P§)",
                            "", trozo, flags=re.IGNORECASE).strip()
                    trozo = _desmarcar_abreviaturas(trozo)
                    if not trozo or len(trozo) < 2:
                        continue
                    if self.poner(slot, trozo, fuente=fuente,
                                  confianza=confianza,
                                  agrupar=(slot == "alergia")):
                        nuevos += 1
        return nuevos

    # ------------------------------------------------------------- leer------
    def activos(self, max_items: int | None = None) -> list[dict]:
        """Hechos vigentes, el más reciente primero."""
        sql = ("SELECT slot, valor, desde FROM hechos WHERE hasta IS NULL "
               "ORDER BY id DESC")
        filas = self._con.execute(sql).fetchall()
        if max_items is not None:
            filas = filas[:max_items]
        return [{"slot": f[0], "valor": f[1], "desde": f[2]} for f in filas]

    def contar_activos(self) -> int:
        return int(self._con.execute(
            "SELECT COUNT(*) FROM hechos WHERE hasta IS NULL").fetchone()[0])

    def bloque_prompt(self, max_items: int = _MAX_BLOQUE) -> str:
        """Bloque ESTABLE para el System prompt.

        Se integra en la parte fija del prompt (caché de prefijo), no en el
        volátil: así añadir un hecho no reevalúa el prompt entero, y no añadir
        ninguno no cuesta nada.
        """
        hechos = self.activos(max_items=max_items)
        if not hechos:
            return ""
        lineas = []
        agrupados: list[tuple[str, str]] = []  # (slot, [valores])
        for hecho in hechos:
            if agrupados and agrupados[-1][0] == hecho["slot"]:
                agrupados[-1][1].append(hecho["valor"])
            else:
                agrupados.append((hecho["slot"], [hecho["valor"]]))
        for slot, valores in agrupados:
            etiqueta = _ETIQUETAS.get(slot, slot)
            # Solo agrupar listas (alergias); los otros hechos con varias
            # versiones nuevas y viejas conviene resolverlas al final.
            if len(valores) > 1 and slot == "alergia":
                texto_valores = "y ".join(reversed(valores))
            else:
                texto_valores = ", ".join(reversed(valores))
            lineas.append(f"- {etiqueta}: {texto_valores}.")

        return ("DATOS QUE LA PERSONA TE HA DICHO DE SÍ (exactos; si pregunta "
                "por uno, contesta exactamente este dato):\n"
                + "\n".join(lineas))

    def sabes_de_slot(self, slot: str) -> str:
        """Último valor activo de un slot (o ''), para respuestas directas."""
        fila = self._con.execute(
            "SELECT valor FROM hechos WHERE slot = ? AND hasta IS NULL "
            "ORDER BY id DESC LIMIT 1", (slot,)).fetchone()
        return fila[0] if fila else ""

    # ------------------------------------------------------------ borrar-----
    def borrar_todos(self) -> int:
        n = self.contar_activos()
        self._con.execute("DELETE FROM hechos")
        self._con.commit()
        return n

    def cerrar(self) -> None:
        """Cierra la base (los tests la sueltan para poder borrar el tmp)."""
        try:
            self._con.close()
        except Exception:
            pass

    def cerrar_todo(self) -> int:
        """Marca todos como no vigentes (sin borrar la historia)."""
        ahora = datetime.now().isoformat(timespec="seconds")
        cur = self._con.execute(
            "UPDATE hechos SET hasta = ? WHERE hasta IS NULL", (ahora,))
        self._con.commit()
        return cur.rowcount


if __name__ == "__main__":
    ejemplos = [
        "Mi dentista es la Dra. Puig, en la calle Mayor.",
        "Soy alérgico a la penicilina y a los frutos secos.",
        "Mi perro se llama Rocky y mi hermana se llama Ana.",
        "Tengo 17 años y vivo el segundo piso.",
        "Trabajo en una tienda y estudio 4º de la ESO.",
    ]
    hechos = HechosParker("./prueba_hechos.db")
    for frase in ejemplos:
        print(hechos.actualizar_desde_texto(frase), "<-", frase)
    print("\n[Bloque prompt]\n" + hechos.bloque_prompt())
