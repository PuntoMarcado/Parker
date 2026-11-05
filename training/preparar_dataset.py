#!/usr/bin/env python3
"""
training/preparar_dataset.py
============================
Prepara el dataset de personalidad de Parker para un LoRA de TEXTO.

Entrada:
  - training/datos/semilla.jsonl   (diálogos escritos a mano)
  - opcional: un log de Parker (`--log ~/parker.log`)

Salida (JSONL con el campo `messages`, listo para Unsloth/TRL):
  - training/datos/parker_train.jsonl
  - training/datos/parker_val.jsonl

Reglas:
  - El system prompt es SIEMPRE training/persona_sistema.txt.
  - Se valida que los turnos alternen user/assistant y empiecen por user.
  - Se eliminan duplicados exactos (mismo primer mensaje + misma respuesta).
  - El split es por DIÁLOGO, no por turno: una conversación no puede estar
    en train y en val a la vez.
  - Del log se descartan órdenes (volumen, alarmas, música...) y ruido de
    pruebas: el LoRA debe aprender actitud, no la capa de comandos.

Uso:
    python training/preparar_dataset.py
    python training/preparar_dataset.py --log ~/parker.log
    python training/preparar_dataset.py --solo-validar
    python training/preparar_dataset.py --exigir-minimo 300

No requiere GPU ni instalar nada: solo la biblioteca estándar.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SISTEMA_PATH = BASE / "training" / "persona_sistema.txt"
SEMILLA = BASE / "training" / "datos" / "semilla.jsonl"
SALIDA = BASE / "training" / "datos"

# Órdenes que ya resuelve `parker._responder_sin_llm()`: no son actitud.
_ORDEN = re.compile(
    r"\b(?:pon|ponme|poner|baja|bajar|sube|subir|silencia|silencio|"
    r"alarma|temporizador|temporizador|cita|agenda|apunta|apuntame|"
    r"para la m[uú]sica|pon m[uú]sica|c[aá]llate|ap[aá]gate|"
    r"modo local|modo nube|modo autom[aá]tico|qu[eé] cerebro)\b",
    re.IGNORECASE,
)

_RUIDO = re.compile(
    r"(?:Traceback|Error|Exception|\[Latencia\]|\[Escucha\]|\[Cerebro\]|"
    r"\[Voz\]|\[Agenda\]|\[Música\]|\[Parker -> Voz\]|\[Parker\]|"
    r"Reproduccion finalizada|Transcripci[oó]n|\(silba\)|"
    r"^\s*(?:>>>|\.\.\.|\$)\s*$)",
    re.IGNORECASE,
)

_PRUEBA = re.compile(
    r"\b(?:prueba|probando|test|uno dos|dos tres|hola hola)\b",
    re.IGNORECASE,
)

_ACCION_FISICA = re.compile(
    r"\b(?:abrazo|abrazar|acaricio|acariciar|toco|tocar|salgo|salir|"
    r"camino|caminar|corro|correr|huelo|oler|besar|beso|como|comer)\b",
    re.IGNORECASE,
)


def _sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _limpiar(texto: str) -> str:
    texto = (texto or "").replace("\x00", " ")
    texto = re.sub(r"[\r\n\t]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _normalizar_respuesta(texto: str) -> str:
    """Toda respuesta lleva su etiqueta de cara; si el log no la trae, neutral."""
    texto = _limpiar(texto)
    if texto and not re.match(r"\[\s*CARA\s*:", texto, re.IGNORECASE):
        texto = "[CARA:neutral] " + texto
    return texto


def _valido(dialogo: dict) -> tuple[bool, str]:
    turnos = dialogo.get("turnos")
    if not isinstance(turnos, list) or len(turnos) < 2:
        return False, "menos de 2 turnos"
    if len(turnos) % 2 != 0:
        return False, "número impar de turnos"
    for i, turno in enumerate(turnos):
        if not isinstance(turno, dict):
            return False, f"turno {i} no es objeto"
        rol = turno.get("role")
        contenido = turno.get("content")
        if rol not in ("user", "assistant"):
            return False, f"rol inválido en turno {i}: {rol!r}"
        if rol != ("user" if i % 2 == 0 else "assistant"):
            return False, f"los roles no alternan en turno {i}"
        if not isinstance(contenido, str) or not contenido.strip():
            return False, f"turno {i} vacío"
        if len(contenido) > 500:
            return False, f"turno {i} demasiado largo ({len(contenido)} chars)"
    return True, ""


def _clave(dialogo: dict) -> str:
    """Huella para deduplicar: todo el diálogo normalizado, no solo el inicio."""
    partes = []
    for turno in dialogo["turnos"]:
        partes.append(turno["role"] + ":" + _sin_tildes(_limpiar(turno["content"])))
    return "|".join(partes)


def cargar_semilla(ruta: Path) -> list[dict]:
    dialogos = []
    if not ruta.exists():
        print(f"[Dataset] AVISO: no existe {ruta}")
        return dialogos
    with ruta.open("r", encoding="utf-8") as f:
        for numero, linea in enumerate(f, 1):
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError as e:
                print(f"[Dataset] semilla línea {numero}: JSON inválido ({e}); se salta")
                continue
            if isinstance(datos, dict) and "turnos" in datos:
                dialogos.append(datos)
            else:
                print(f"[Dataset] semilla línea {numero}: falta 'turnos'; se salta")
    return dialogos


def pares_desde_log(ruta: Path, incluir_ordenes: bool = False) -> list[dict]:
    """Extrae pares Usuario/`[Parker -> Voz]` del log de la placa.

    Es deliberadamente conservador: si el log está cortado, mezcla pruebas o
    la respuesta es un comando, se descarta. Mejor 20 pares limpios que 300
    con ruido.
    """
    if not ruta.exists():
        print(f"[Dataset] AVISO: no existe el log {ruta}")
        return []
    pares = []
    pendiente = None
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        limpia = linea.strip()
        if limpia.startswith("Usuario:"):
            pendiente = _limpiar(limpia[len("Usuario:"):])
            continue
        if limpia.startswith("[Parker -> Voz]") and pendiente:
            respuesta = _limpiar(limpia[len("[Parker -> Voz]"):])
            usuario, pendiente = pendiente, None
            if not usuario or not respuesta:
                continue
            if _RUIDO.search(usuario) or _RUIDO.search(respuesta):
                continue
            if _PRUEBA.search(usuario) or _PRUEBA.search(respuesta):
                continue
            if not incluir_ordenes and (_ORDEN.search(usuario) or _ORDEN.search(respuesta)):
                continue
            if len(usuario) > 300 or len(respuesta) > 500:
                continue
            if _sin_tildes(usuario) in ("hola", "hola parker", "buenas"):
                # Saludos sueltos no aportan actitud; ya están en la semilla.
                continue
            pares.append({"turnos": [
                {"role": "user", "content": usuario},
                {"role": "assistant", "content": _normalizar_respuesta(respuesta)},
            ]})
    return pares


def preparar(dialogos: list[dict], sistema: str, salida: Path,
             val_ratio: float, semilla: int,
             escribir: bool = True) -> tuple[list[dict], list[dict]]:
    """Valida, deduplica y parte por diálogo."""
    vistos = set()
    limpios = []
    descartados = {}
    for dialogo in dialogos:
        ok, motivo = _valido(dialogo)
        if not ok:
            descartados[motivo] = descartados.get(motivo, 0) + 1
            continue
        normalizado = {"turnos": [
            {"role": t["role"],
             "content": (_limpiar(t["content"]) if t["role"] == "user"
                         else _normalizar_respuesta(t["content"]))}
            for t in dialogo["turnos"]
        ]}
        clave = _clave(normalizado)
        if clave in vistos:
            descartados["duplicado"] = descartados.get("duplicado", 0) + 1
            continue
        vistos.add(clave)
        limpios.append(normalizado)

    if not limpios:
        return [], []

    azar = random.Random(semilla)
    azar.shuffle(limpios)
    n_val = max(1, int(round(len(limpios) * val_ratio))) if len(limpios) >= 5 else 0
    val = limpios[:n_val]
    train = limpios[n_val:]

    def envolver(dialogo: dict) -> dict:
        return {"messages": [{"role": "system", "content": sistema}]
                + dialogo["turnos"]}

    if escribir:
        salida.mkdir(parents=True, exist_ok=True)
        for nombre, datos in (("parker_train.jsonl", train),
                              ("parker_val.jsonl", val)):
            ruta = salida / nombre
            with ruta.open("w", encoding="utf-8") as f:
                for dialogo in datos:
                    f.write(json.dumps(envolver(dialogo), ensure_ascii=False) + "\n")

    if descartados:
        print("[Dataset] descartados:", ", ".join(
            f"{k}: {v}" for k, v in sorted(descartados.items())))
    return train, val


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepara el dataset de personalidad de Parker")
    ap.add_argument("--semilla", type=Path, default=SEMILLA)
    ap.add_argument("--extra", type=Path, action="append", default=[],
                    help="otro JSONL de diálogos (p.ej. el sintético); repetible")
    ap.add_argument("--log", type=Path, default=None,
                    help="log de Parker del que extraer conversaciones reales")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--val-ratio", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=3407)
    ap.add_argument("--incluir-ordenes", action="store_true",
                    help="no descartar órdenes del log (no recomendado)")
    ap.add_argument("--solo-validar", action="store_true",
                    help="valida y muestra estadísticas sin escribir ficheros")
    ap.add_argument("--exigir-minimo", type=int, default=0,
                    help="código 1 si hay menos diálogos que este número")
    args = ap.parse_args()

    sistema = SISTEMA_PATH.read_text(encoding="utf-8").strip()
    if not sistema:
        print("[Dataset] ERROR: persona_sistema.txt está vacío")
        return 1

    dialogos = cargar_semilla(args.semilla)
    for extra in args.extra:
        if not extra.exists():
            print(f"[Dataset] ERROR: no existe el extra {extra}")
            return 1
        antes = len(dialogos)
        dialogos.extend(cargar_semilla(extra))
        print(f"[Dataset] {len(dialogos) - antes} diálogos extra de {extra}")
    if args.log:
        reales = pares_desde_log(args.log, args.incluir_ordenes)
        print(f"[Dataset] {len(reales)} pares limpios extraídos de {args.log}")
        dialogos.extend(reales)

    train, val = preparar(dialogos, sistema, args.salida,
                          max(0.0, min(0.5, args.val_ratio)), args.seed,
                          escribir=not args.solo_validar)
    turnos_train = sum(len(d["turnos"]) for d in train)
    turnos_val = sum(len(d["turnos"]) for d in val)
    print(f"[Dataset] diálogos: {len(train) + len(val)} "
          f"(train {len(train)} / val {len(val)})")
    print(f"[Dataset] turnos: {turnos_train + turnos_val} "
          f"(train {turnos_train} / val {turnos_val})")
    if train:
        chars = sum(len(t["content"]) for d in train for t in d["turnos"])
        print(f"[Dataset] media por turno: {chars / max(1, turnos_train):.0f} chars")
    if not args.solo_validar:
        print(f"[Dataset] escrito en {args.salida}")
    if len(train) + len(val) < 300:
        print("[Dataset] AVISO: para un LoRA estable se recomiendan 300-800 "
              "diálogos; esto es una base, no el dataset final.")
    if args.exigir_minimo and len(train) + len(val) < args.exigir_minimo:
        print(f"[Dataset] ERROR: menos de {args.exigir_minimo} diálogos")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
