"""
tests/test_memoria_hibrida.py
=============================
Test END-TO-END de la búsqueda híbrida: Chroma real + FTS5 real sobre una
base TEMPORAL. Necesita el modelo de embeddings (está en la placa); en un
entorno sin él se salta con `skip`, no falla.

Ejecutar (placa):  env/bin/python -m pytest tests/test_memoria_hibrida.py -q
"""

import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

try:
    from modulos.memoria import MemoriaParker
except Exception as _e:  # sin chroma/sentence-transformers instalados
    print(f"[SKIP] memoria vectorial no disponible ({_e})")
    sys.exit(0)


def _crea_memoria(tmp: str) -> MemoriaParker:
    return MemoriaParker(
        db_path=str(Path(tmp) / "parker.db"),
        coleccion="test_hibrida",
        modelo_embeddings="paraphrase-multilingual-MiniLM-L12-v2",
        ruta_fts=str(Path(tmp) / "fts.sqlite"),
        hibrida=True,
    )


def test_hibrida_tiene_fts():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        memoria = _crea_memoria(tmp)
        assert memoria.hibrida is True, "FTS5 tiene que estar disponible"
        print("[OK] índice léxico FTS5 activo")


def test_hibrida_devuelve_el_hecho_aunque_semantica_fai():
    """El caso real de la evaluación: pregunta corta de hecho exacto.

    '¿Cómo se llama mi dentista?' fallaba 4/8 por similitud coseno; el
    ranking léxico pilla 'dentista' (palabra literal en el recuerdo).
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        memoria = _crea_memoria(tmp)
        memoria.guardar_recuerdo(
            "Usuario: Mi dentista es la Dra. Puig y está en la calle Mayor 12.",
            texto_embedding="Mi dentista es la Dra. Puig y está en la calle Mayor 12.")
        memoria.guardar_recuerdo(
            "Usuario: Hoy he comido pasta en el trabajo.",
            texto_embedding="Hoy he comido pasta en el trabajo.")
        memoria.guardar_recuerdo(
            "Usuario: Mi vecino ensaya la trompeta por las tardes.",
            texto_embedding="Mi vecino ensaya la trompeta por las tardes.")

        resultados = memoria.recuperar_recuerdos(
            "¿Cómo se llama mi dentista?", top_k=3, umbral=0.0)
        assert resultados, "sin resultados no hay nada que puntuar"
        textos = [r["texto"] for r in resultados]
        assert any("dentista" in t.lower() for t in textos), textos
        # La pasta y la trompeta no deberían ganarle al dentista
        assert "pasta" not in textos[0].lower(), textos
        print(f"[OK] 'dentista' en top {min(3, len(textos))}: "
              f"{[t[:40] for t in textos]}")


def test_hibrida_ignora_capas_luego_borrado_sincroniza():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        memoria = _crea_memoria(tmp)
        doc = memoria.guardar_recuerdo(
            "Usuario: La receta secreta es pimienta.",
            texto_embedding="La receta secreta es pimienta.")
        assert memoria.coleccion.count() == 1
        n_fts = memoria._fts.execute(
            "SELECT COUNT(*) FROM recuerdos").fetchone()[0]
        assert n_fts == 1, "el texto ha de estar en las DOS puntas"
        memoria.eliminar_recuerdo(doc)
        n_fts = memoria._fts.execute(
            "SELECT COUNT(*) FROM recuerdos").fetchone()[0]
        assert memoria.coleccion.count() == 0 and n_fts == 0
        assert memoria.borrar_todos() == 0
        print("[OK] guardado y borrado sincronizados entre Chroma y FTS5")


def test_reshibrida_hasta_borra_no_levanta_excepciones():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        memoria = _crea_memoria(tmp)
        memoria.guardar_recuerdo("Usuario: hola", texto_embedding="hola")
        memoria.borrar_todos()
        assert memoria.recuperar_recuerdos("dentista") == []
        print("[OK] consultas con colecciones vacías no explotan")


if __name__ == "__main__":
    test_hibrida_tiene_fts()
    test_hibrida_devuelve_el_hecho_aunque_semantica_fai()
    test_hibrida_ignora_capas_luego_borrado_sincroniza()
    test_reshibrida_hasta_borra_no_levanta_excepciones()
    print("[OK] memoria híbrida: 4/4")
