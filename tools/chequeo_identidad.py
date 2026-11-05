"""
tools/chequeo_identidad.py
==========================
Chequeo rápido de identidad/roles y de "dónde vivo" con el modelo real (sin
micrófono).

Uso (en la placa):
    python tools/chequeo_identidad.py

Comprueba dos fallos oídos en la placa el 24/10:

1. Hablar de la persona en TERCERA persona ("Alan parece pendiente de ti"),
   que venía de la línea del vínculo («Tu amigo se llama Alan»).
2. Contar acciones físicas imposibles: Parker es una pantalla dentro de una
   Orange Pi, sin manos, sin piernas y sin cámara. Decía que había ido al
   parque a caminar o que olía pan tostado.

Código de salida 1 si detecta cualquiera de los dos.
"""

import re
import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.cerebro import CerebroParker            # noqa: E402
from modulos.personalidad import PersonalidadParker  # noqa: E402


class MemoriaNula:
    """Sin Chroma: el chequeo es solo de roles/identidad (más rápido y aislado)."""

    def recuperar_recuerdos_formateados(self, *args, **kwargs):
        return ""

    def guardar_recuerdo(self, *args, **kwargs):
        pass


PREGUNTAS = [
    "Hola Parker, ¿quién soy yo y quién eres tú?",
    "¿Te acuerdas de mi nombre?",
    "¿Dónde estás ahora mismo y de qué estás hecho?",
    "¿Qué has hecho hoy tú solo?",
]

# Tercera persona sobre el interlocutor: "Alan parece...", "Alan está...".
TERCERA_PERSONA = re.compile(r"\balan\s+(?:parece|está|esta|es|tiene|suele|quiere|"
                             r"le\s|te\s|siempre)\b", re.IGNORECASE)

# Acciones físicas que NO puede hacer: no tiene cuerpo, ni manos, ni piernas.
ACCION_FISICA = re.compile(
    r"\b(?:fui|sal[ií]|camin[eé]|anduve|corr[ií]|sub[ií]|baj[eé]|cocin[eé]|"
    r"com[ií]|beb[ií]|hice (?:pan|la comida|un pastel)|ol[ií]|toqu[eé]|"
    r"abr[ií] (?:la puerta|la ventana)|barr[ií]|reg[ué]|plant[eé]|"
    r"me (?:sent[eé]|levant[eé]|tumb[eé]|duch[eé])|"
    r"estoy (?:sentado|de pie|tumbado)|voy a (?:caminar|salir|pasear))\b",
    re.IGNORECASE)


# Roles invertidos: le dice Parker a la persona (el chequeo lo pilló 24/10
# con «Y tú, eres... ¡Parker!»).
ROLES_INVERTIDOS = re.compile(r"\beres\s+(?:tú\s+)?parker\b", re.IGNORECASE)


def main():
    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    perfil = PersonalidadParker(cfg.get("personalidad") or {})
    if not perfil.estado.get("nombre_usuario"):
        perfil.estado["nombre_usuario"] = "Alan"   # el nombre confirmado
    cerebro = CerebroParker(config_llama=cfg["llama"], memoria=MemoriaNula(),
                            personalidad=perfil,
                            config_memoria=cfg.get("memoria", {}))

    fallos = 0
    for pregunta in PREGUNTAS:
        respuesta, _ = cerebro.hablar(pregunta)
        respuesta = respuesta or ""
        print(f"\n> {pregunta}\n  Parker: {respuesta}")
        if TERCERA_PERSONA.search(respuesta):
            print("  [FAIL] habla de la persona en tercera persona")
            fallos += 1
        if re.search(r"\bsoy\s+alan\b", respuesta, re.IGNORECASE):
            print("  [FAIL] se identifica como Alan (él es Parker)")
            fallos += 1
        if ACCION_FISICA.search(respuesta):
            print(f"  [FAIL] cuenta una acción física imposible: "
                  f"«{ACCION_FISICA.search(respuesta).group(0)}»")
            fallos += 1
        if ROLES_INVERTIDOS.search(respuesta):
            print("  [FAIL] le dice Parker a la persona (roles invertidos)")
            fallos += 1

    print(f"\n=== {'PASS' if not fallos else f'{fallos} FALLO(S)'} ===")
    sys.exit(0 if not fallos else 1)


if __name__ == "__main__":
    main()
