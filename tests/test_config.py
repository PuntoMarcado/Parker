"""
tests/test_config.py
====================
Guarda contra un `config.yaml` roto o incompleto.

Motivo (25/10): una línea de comentario sin `#` rompió el YAML; `_cargar_config`
se tragaba el error y Parker arrancaba con valores por defecto (sin cerebro, sin
pantalla) pareciendo «que no coge el contexto». Este test hace que el fallo
aparezca al pasar las pruebas, no en la cara del usuario.

Uso:
    python tests/test_config.py
"""

import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def test_yaml_valido():
    ruta = BASE / "config.yaml"
    try:
        cfg = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise AssertionError(f"config.yaml no es YAML válido: {e}")
    assert isinstance(cfg, dict), "config.yaml no devuelve un diccionario"

    from parker import SECCIONES_OBLIGATORIAS
    faltan = [c for c in SECCIONES_OBLIGATORIAS if c not in cfg]
    assert not faltan, f"faltan secciones en config.yaml: {faltan}"
    print("[OK] config.yaml es válido y tiene todas las secciones")


def test_cerebro_y_escucha_coherentes():
    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))

    online = cfg["online"]
    llama = cfg["llama"]
    escucha = cfg["escucha"]

    # Motor online: o está apagado a propósito, o tiene modelo y URL.
    if online.get("activo"):
        assert online.get("modelo"), "online.activo sin modelo"
        assert str(online.get("base_url", "")).startswith("http"), online.get("base_url")
        assert float(online.get("timeout_conexion", 0)) > 0, "timeout_conexion debe ser > 0"

    # El local es el respaldo: siempre tiene que estar definido.
    assert llama.get("modelo"), "falta llama.modelo (respaldo local)"
    assert int(llama.get("historial_mensajes", 0)) in (2, 4, 6, 8), \
        "historial_mensajes fuera de lo razonable"

    # STT: el motor tiene que ser uno de los tres válidos.
    assert escucha.get("motor", "auto") in ("auto", "nube", "local"), escucha.get("motor")
    if escucha.get("motor") != "local":
        assert escucha.get("modelo_nube"), "motor de nube sin modelo_nube"
        assert escucha.get("api_key_env"), "motor de nube sin api_key_env"
    print("[OK] cerebro (nube+local), STT e historial son coherentes")


def main():
    test_yaml_valido()
    test_cerebro_y_escucha_coherentes()
    print("\nConfiguración: 2/2 en verde.")


if __name__ == "__main__":
    main()
