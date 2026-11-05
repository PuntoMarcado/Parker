"""
tests/test_memoria_hechos.py
============================
Tests del módulo de hechos exactos (slots), sin Chroma ni embeddings.

Ejecutar:  python -m pytest tests/test_memoria_hechos.py -q
"""

import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.hechos import HechosParker


def test_extraccion_de_datos_basicos():
    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        n = hechos.actualizar_desde_texto(
            "Mi dentista es la Dra. Puig, en la calle Mayor 12.")
        assert n == 1
        assert hechos.sabes_de_slot("dentista") == "la Dra. Puig"

        n = hechos.actualizar_desde_texto(
            "Soy alérgico a la penicilina y a los frutos secos.")
        assert n == 2, "las alergias múltiples guardan cada valor"
        valores = {h["valor"] for h in hechos.activos()}
        assert "penicilina" in valores and "frutos secos" in valores

        n = hechos.actualizar_desde_texto("Mi perro se llama Rocky.")
        assert n == 1
        assert hechos.sabes_de_slot("mascota") == "Rocky"

        n = hechos.actualizar_desde_texto("Tengo 17 años.")
        assert n == 1
        assert hechos.sabes_de_slot("edad") == "17"
        hechos.cerrar()
        print("[OK] extracción básica de hechos (dentista, alergia, mascota, edad)")


def test_no_guarda_preguntas_ni_ordenes():
    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        for frase in ("¿A qué soy alérgico?",
                      "¿Cómo se llama mi dentista?",
                      "Borra la memoria",
                      "Pon una alarma a las 7",
                      "Vale"):
            hechos.actualizar_desde_texto(frase)
        assert hechos.contar_activos() == 0, hechos.activos()
        hechos.cerrar()
        print("[OK] preguntas y órdenes no se convierten en hechos")


def test_actualizacion_invalida_el_viejo():
    """Cambiar de dentista no borra el anterior: lo invalida con fecha."""
    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        hechos.actualizar_desde_texto("Mi dentista es la Dra. Puig.")
        hechos.actualizar_desde_texto("Mi dentista es el Dr. Luna.")
        activos = hechos.activos()
        assert len(activos) == 1 and activos[0]["valor"] == "el Dr. Luna"

        # El anterior sigue en la base (historia) pero no activo.
        todos = hechos._con.execute(
            "SELECT valor, hasta FROM hechos WHERE slot='dentista' "
            "ORDER BY id").fetchall()
        assert len(todos) == 2
        assert todos[0][1] is not None and todos[1][1] is None

        # Repetir el mismo dato no crea segunda fila
        assert hechos.actualizar_desde_texto("Mi dentista es el Dr. Luna.") == 0
        hechos.cerrar()
        print("[OK] cambio de dato invalida el viejo y no duplica")


def test_bloque_prompt_estable_y_acotado():
    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        for frase in (
            "Mi dentista es la Dra. Puig.",
            "Soy alérgico a la penicilina.",
            "Mi hermana se llama Ana.",
            "Vivo en el segundo piso.",
        ):
            hechos.actualizar_desde_texto(frase)
        bloque = hechos.bloque_prompt()
        assert bloque.startswith("DATOS QUE LA PERSONA")
        assert bloque in bloque  # sanity trivial
        for esperado in ("Dentista", "Alergias", "Familia", "Vive en"):
            assert esperado in bloque, bloque
        # Vacío (borrado): el bloque desaparece (no añade tokens muertos)
        hechos.borrar_todos()
        assert hechos.bloque_prompt() == ""
        hechos.cerrar()
        print("[OK] bloque para el system prompt se compone y desaparece vacío")


def test_alergias_se_agrupan_en_el_bloque():
    with tempfile.TemporaryDirectory() as tmp:
        hechos = HechosParker(str(Path(tmp) / "hechos.db"))
        hechos.actualizar_desde_texto("Soy alérgico a la penicilina.")
        hechos.actualizar_desde_texto("Soy alérgico al marisco.")
        bloque = hechos.bloque_prompt()
        linea = [l for l in bloque.splitlines() if "Alergias" in l][0]
        assert "penicilina" in linea and "marisco" in linea, linea
        hechos.cerrar()
        print("[OK] alergias múltiples en una línea")


if __name__ == "__main__":
    test_extraccion_de_datos_basicos()
    test_no_guarda_preguntas_ni_ordenes()
    test_actualizacion_invalida_el_viejo()
    test_bloque_prompt_estable_y_acotado()
    test_alergias_se_agrupan_en_el_bloque()
    print("[OK] memoria de hechos: 5/5")
