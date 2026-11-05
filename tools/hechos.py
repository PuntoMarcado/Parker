"""
tools/hechos.py
===============
Ver, modificar y probar la tabla de HECHOS EXACTOS (modulos/hechos.py) por
línea de comandos, sin hablar con Parker.

Uso (en la placa, desde ~/parker):
  python tools/hechos.py                    -> los datos activos
  python tools/hechos.py --todo             -> también losinvalidados
  python tools/hechos.py --probar "frase"   -> prueba de extracción (no guarda)
  python tools/hechos.py --borrar           -> borra TODOS (con confirmación)
"""

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def _ruta_de_la_config() -> str:
    try:
        import yaml
        cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))
        ruta = str((cfg.get("memoria") or {}).get("hechos", {}).get("ruta")
                   or "./parker.hechos.db")
    except Exception:
        ruta = "./parker.hechos.db"
    if not Path(ruta).is_absolute():
        ruta = str(BASE / ruta)
    return ruta


def main():
    parser = argparse.ArgumentParser(description="Tabla de hechos de Parker")
    parser.add_argument("--todo", action="store_true",
                        help="lista también los hechos invalidados")
    parser.add_argument("--borrar", action="store_true",
                        help="borra todos los hechos")
    parser.add_argument("--probar", metavar="FRASE",
                        help="prueba la extracción sobre una frase (no guarda)")
    args = parser.parse_args()

    from modulos.hechos import HechosParker

    if args.probar:
        print(f"Frase: {args.probar!r}")
        print("Coincidencias (vista previa, no se guarda):")
        from modulos.hechos import (_PATRONES, _SEPARADORES_LISTA,
                                    _limpiar_valor, _marcar_abreviaturas,
                                    _desmarcar_abreviaturas)
        texto = _marcar_abreviaturas(args.probar)
        encontrados = []
        for slot, patron in _PATRONES:
            for m in patron.finditer(texto):
                trozos = [t for t in _SEPARADORES_LISTA.split(
                    _limpiar_valor(m.group('v') or '')) if t]
                for trozo in trozos:
                    print(f"  slot={slot:<10} "
                          f"valor={_desmarcar_abreviaturas(trozo.strip())!r}")
                    encontrados.append(slot)
        if not encontrados:
            print("  (ninguna)")
        return 0

    hechos = HechosParker(ruta=_ruta_de_la_config())

    if args.borrar:
        n = hechos.contar_activos()
        if n == 0:
            print("La tabla ya está vacía.")
            return 0
        respuesta = input(f"Se van a borrar {n} hechos. ¿Seguro? [s/N] ")
        if respuesta.strip().lower() in ("s", "si", "sí", "y"):
            print(f"Borrados {hechos.borrar_todos()} hechos.")
            return 0
        print("No se ha borrado nada.")
        return 0

    filas = hechos._con.execute(
        "SELECT slot, valor, desde, hasta FROM hechos ORDER BY id").fetchall()
    activos = hechos.activos()
    print(f"Hechos activos: {len(activos)}\n")
    for fila in activos:
        print(f"  [{fila['slot']:<10}] {fila['valor']} (desde {fila['desde']})")
    if args.todo:
        viejos = [f for f in filas if f[3] is not None]
        print(f"\nInvalidados (historia): {len(viejos)}")
        for slot, valor, desde, hasta in viejos:
            print(f"  [{slot:<10}] {valor}  ({desde} -> {hasta})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
