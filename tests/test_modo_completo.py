"""Prueba de integración del modo completo, sin audio ni hardware.

Comprueba el fallo real del 02/11/2026: «modo local» y «modo online» se
reconocían como cambio de cerebro, pero la voz seguía en Edge y el oído en
auto. Aquí se aplica la orden sobre un Parker construido con `__new__` y
componentes falsos: si vuelve a quedarse a medias, el test falla.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parker as modulo  # noqa: E402
from modulos.acciones import interpretar_orden_modo_completo  # noqa: E402


class CerebroFalso:
    def __init__(self):
        self.modo = "auto"

    def cambiar_modo(self, modo):
        self.modo = modo
        return ""


class VozFalsa:
    def __init__(self):
        self.motor = "edge"
        self.edge_voz = "test"

    def cambiar_motor(self, motor):
        self.motor = "piper" if motor == "piper" else "edge"
        return self.motor

    def motor_actual(self):
        return self.motor


class EscuchaFalsa:
    def __init__(self):
        self.motor = "auto"

    def cambiar_motor(self, motor):
        self.motor = motor
        return motor

    def motor_actual(self):
        return self.motor


def _parker():
    p = modulo.Parker.__new__(modulo.Parker)
    p.cerebro = CerebroFalso()
    p.voz = VozFalsa()
    p.escucha = EscuchaFalsa()
    p._guardar_modo_completo = lambda: None
    p._descripcion_modo = lambda: "prueba"
    p._hablar = lambda *a, **k: None
    p._registrar_suceso = lambda *a, **k: None
    return p


def test_modo_local_cambia_los_tres():
    p = _parker()
    pedido = interpretar_orden_modo_completo("modo local")
    assert pedido == "local", pedido
    p._aplicar_orden_modo_completo(pedido)
    assert p.cerebro.modo == "local", p.cerebro.modo
    assert p.voz.motor == "piper", p.voz.motor
    assert p.escucha.motor == "local", p.escucha.motor
    print("[OK] «modo local» cambia cerebro, oído y voz")


def test_modo_online_cambia_los_tres():
    p = _parker()
    p.cerebro.modo = "local"
    p.voz.motor = "piper"
    p.escucha.motor = "local"
    pedido = interpretar_orden_modo_completo("modo online")
    assert pedido == "nube", pedido
    p._aplicar_orden_modo_completo(pedido)
    assert p.cerebro.modo == "nube", p.cerebro.modo
    assert p.voz.motor == "edge", p.voz.motor
    assert p.escucha.motor == "auto", p.escucha.motor
    print("[OK] «modo online» cambia cerebro, oído y voz")


def test_cerebro_local_es_parcial():
    # «cerebro local» no entra por el modo completo: es el cambio parcial.
    assert interpretar_orden_modo_completo("cerebro local") is None
    print("[OK] «cerebro local» sigue siendo el cambio parcial")


if __name__ == "__main__":
    test_modo_local_cambia_los_tres()
    test_modo_online_cambia_los_tres()
    test_cerebro_local_es_parcial()
    print("\nModo completo: 3/3 en verde.")
