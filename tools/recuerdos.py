"""
tools/recuerdos.py
==================
Ver y vaciar la memoria de Parker sin abrir una consola de ChromaDB.

    python tools/recuerdos.py            # lista los recuerdos
    python tools/recuerdos.py --borrar   # borra TODOS (pide confirmación)
    python tools/recuerdos.py --borrar --si   # sin preguntar

Parker puede estar corriendo: ChromaDB avisa si otra instancia escribe a la vez
(usa `pkill -f parker.py` si prefieres vaciar la base con Parker parado).
"""

import argparse
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.chdir(BASE)

import yaml  # noqa: E402
from modulos.memoria import MemoriaParker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Recuerdos de Parker")
    parser.add_argument("--borrar", action="store_true", help="borrar todos")
    parser.add_argument("--si", action="store_true", help="no preguntar")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(BASE / "config.yaml", encoding="utf-8"))
    mem_cfg = cfg.get("memoria", {})
    memoria = MemoriaParker(db_path=mem_cfg.get("db_path", "./parker.db"),
                            coleccion=mem_cfg.get("coleccion", "recuerdos_parker"),
                            modelo_embeddings=mem_cfg.get("modelo_embeddings",
                                                          "paraphrase-multilingual-MiniLM-L12-v2"))
    total = memoria.coleccion.count()

    if args.borrar:
        if total == 0:
            print("No hay recuerdos que borrar.")
            return 0
        if not args.si:
            respuesta = input(f"¿Borrar los {total} recuerdos? [s/N] ").strip().lower()
            if respuesta not in ("s", "si", "sí", "y"):
                print("Cancelado.")
                return 1
        borrados = memoria.borrar_todos()
        print(f"Borrados {borrados} recuerdos. Quedan: {memoria.coleccion.count()}")
        return 0

    if total == 0:
        print("La memoria está vacía: Parker irá guardando aquí lo que le cuentes.")
        return 0
    datos = memoria.coleccion.get(include=["documents", "metadatas"])
    filas = sorted(zip(datos["ids"], datos["documents"], datos["metadatas"]),
                   key=lambda f: f[2].get("timestamp", ""))
    for i, (doc_id, texto, meta) in enumerate(filas, 1):
        print("%2d  %s  %s | %s" % (i, doc_id[:8], str(meta.get("timestamp", ""))[:19],
                                    texto.replace("\n", " / ")[:90]))
    print(f"\ntotal: {total} recuerdos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
