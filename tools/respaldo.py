"""
tools/respaldo.py
=================
Copia de seguridad completa del proyecto, con fecha, dentro de `backups/`.

Solo en el ORDENADOR PRINCIPAL. En la placa (Orange Pi) no se respalda: el
espacio de la placa es para los recuerdos de Chroma, no para copias de código
(el código vive en git y en este PC). El script se niega a ejecutarse allí.

Uso:
    python tools/respaldo.py                     # snapshot con la fecha actual
    python tools/respaldo.py "antes-de-voz"      # etiqueta opcional
    python tools/respaldo.py --con-recuerdos     # añade parker.db de la placa

Copia los ficheros COMPLETOS (no parches) de parker.py, config.yaml,
requirements.txt, README.md, INS.txt, modulos/, tests/, tools/, docs/ y
training/ (incluye la semilla y la tubería LoRA; los datasets generados van
en .gitignore pero se copian igual en el respaldo local).
No toca el entorno virtual ni las claves de .env (solo anota sus NOMBRES).

Cada snapshot lleva:
    LEEME.txt        qué es, de qué versión y cómo se restaura
    MANIFIESTO.txt   sha256 + tamaño de cada fichero (para saber si algo cambió)

Restaurar = copiar el contenido del snapshot encima del proyecto.
"""

import hashlib
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DESTINO_RAIZ = BASE / "backups"

FICHEROS = ["parker.py", "config.yaml", "requirements.txt", "README.md", "INS.txt"]
CARPETAS = ["modulos", "tests", "tools", "docs", "training"]
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def _es_la_placa() -> bool:
    """True si este proceso corre en la Orange Pi (allí NUNCA se respalda)."""
    try:
        modelo = Path("/proc/device-tree/model").read_text(errors="ignore")
    except OSError:
        return False
    # El device-tree real de la placa es «RK3588S OPi 5 Pro» — no contiene
    # "Orange Pi", así que se comprueba también «OPi» y «RK3588» (medido 24/10).
    return bool(re.search(r"orange\s*pi|\bOPi\b|rk3588", modelo, re.IGNORECASE))


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _nombres_env() -> list:
    """Solo los NOMBRES de las variables de .env, nunca sus valores."""
    ruta = BASE / ".env"
    if not ruta.exists():
        return []
    nombres = []
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", linea)
        if m:
            nombres.append(m.group(1))
    return nombres


def _version() -> str:
    try:
        sys.path.insert(0, str(BASE))
        from modulos.version import etiqueta
        return etiqueta()
    except Exception:
        return "(sin modulos/version.py)"


def _cerebro_config() -> str:
    try:
        import yaml
        cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8")) or {}
        online = (cfg.get("online") or {})
        local = (cfg.get("llama") or {})
        estado = "activo" if online.get("activo") else "apagado"
        return (f"online: {estado} ({online.get('modelo', '?')} @ "
                f"{online.get('base_url', '?')}) | local: {local.get('modelo', '?')}")
    except Exception as e:
        return f"(no se pudo leer config.yaml: {e})"


def main():
    if _es_la_placa():
        print("[Respaldo] Esto es la placa: los respaldos viven solo en el "
              "ordenador principal. Nada que hacer aquí.")
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    con_recuerdos = "--con-recuerdos" in sys.argv
    etiqueta = ("_" + args[0].strip().replace(" ", "-")) if args else ""
    destino = DESTINO_RAIZ / (datetime.now().strftime("%Y-%m-%d_%H%M") + etiqueta)
    if destino.exists():
        destino = destino.with_name(destino.name + "_2")

    destino.mkdir(parents=True)
    copiados = 0
    for nombre in FICHEROS:
        origen = BASE / nombre
        if origen.exists():
            shutil.copy2(origen, destino / nombre)
            copiados += 1
    for nombre in CARPETAS:
        origen = BASE / nombre
        if origen.is_dir():
            shutil.copytree(origen, destino / nombre, ignore=IGNORAR)
            copiados += sum(1 for _ in (destino / nombre).rglob("*") if _.is_file())

    # Recuerdos de la placa (opcional): la memoria de Parker no está en git.
    if con_recuerdos:
        placa = destino / "placa"
        placa.mkdir()
        # parker.db es un DIRECTORIO en la placa (Chroma persiste una carpeta),
        # así que se copia recursivo; el estado es un fichero suelto.
        for remoto in ("parker.db", "parker.estado.json"):
            subprocess.run(
                ["scp", "-q", "-r", "-o", "BatchMode=yes",
                 f"orangepi@192.168.1.130:~/parker/{remoto}", str(placa / "")],
                check=False,
            )
        copiados += sum(1 for _ in placa.rglob("*") if _.is_file())

    # Manifiesto: sha256 de todo, para comparar copias sin abrir ficheros.
    lineas = ["# MANIFIESTO de la copia", f"# {destino.name}", ""]
    for ruta in sorted(destino.rglob("*")):
        if ruta.is_file() and ruta.name not in ("MANIFIESTO.txt",):
            rel = ruta.relative_to(destino).as_posix()
            lineas.append(f"{_sha256(ruta)}  {ruta.stat().st_size:>8}  {rel}")
    (destino / "MANIFIESTO.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    nombres_env = _nombres_env()
    (destino / "LEEME.txt").write_text(
        f"Copia de seguridad completa de Parker\n"
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Versión: {_version()}\n"
        f"Cerebro: {_cerebro_config()}\n"
        f"Ficheros: {copiados} (completos, no parches)\n"
        f"Variables de .env necesarias (NOMBRES, los valores no se copian): "
        f"{', '.join(nombres_env) or '(ninguna)'}\n"
        f"Recuerdos de la placa: {'incluidos en placa/' if con_recuerdos else 'no incluidos'}\n"
        f"Restaurar: copiar el contenido de esta carpeta encima del proyecto.\n"
        f"Ver docs/respaldos.md para el índice de todas las copias.\n",
        encoding="utf-8",
    )
    print(f"[Respaldo] {copiados} ficheros -> {destino.relative_to(BASE)}")


if __name__ == "__main__":
    main()
