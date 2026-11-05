"""El micro USB que aparece después del arranque (bug del 30/10/2026).

Al encender la placa, la cara sale en pantalla y Parker abre el audio antes de
que el USB termine de enumerar. PortAudio cachea su lista de dispositivos al
importar, así que el micro «no existía» para el proceso y Parker se quedaba
escuchando el códec interno en silencio absoluto. Aquí se simula esa secuencia
sin hardware: la lista no trae el USB hasta que se refresca PortAudio.
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parker as P  # noqa: E402


def _dev(nombre: str, canales: int):
    return {"name": nombre, "max_input_channels": canales}


class _SDTardio:
    """`query_devices` no ve el USB hasta el primer `_initialize`."""

    def __init__(self):
        self.devices = [_dev("rockchip,es8388: dailink-multicodecs ES8323", 0),
                        _dev("rockchip-hdmi0: i2s-hifi-0", 0)]
        self.refrescos = 0

    def query_devices(self):
        return self.devices

    def _terminate(self):
        self.refrescos += 1

    def _initialize(self):
        # El USB aparece cuando se vuelve a enumerar, como en un arranque real.
        self.devices = list(self.devices) + [
            _dev("USB PnP Audio Device: Audio (hw:3,0)", 2)]


def test_microfono_que_aparece_tarde():
    original = P.sd
    falso = _SDTardio()
    P.sd = falso
    try:
        obj = types.SimpleNamespace()
        indice = P.Parker._resolver_microfono(
            obj, {"dispositivo_entrada": "usb"}, esperar_seg=2.0)

        assert indice == 2, f"debía elegir el USB (índice 2), no {indice}"
        assert falso.refrescos >= 1, "no se refrescó PortAudio"
        assert obj._micro_elegido == "usb"
        print("[OK] el micro que aparece tarde se encuentra al refrescar PortAudio")
    finally:
        P.sd = original


def test_microfono_presente_no_espera():
    original = P.sd

    class _SDInmediato:
        def query_devices(self):
            return [_dev("USB PnP Audio Device: Audio (hw:3,0)", 2)]

        def _terminate(self):
            raise AssertionError("no hacía falta refrescar")

        def _initialize(self):
            raise AssertionError("no hacía falta refrescar")

    P.sd = _SDInmediato()
    try:
        obj = types.SimpleNamespace()
        indice = P.Parker._resolver_microfono(
            obj, {"dispositivo_entrada": "usb"}, esperar_seg=25.0)
        assert indice == 0, indice
        print("[OK] si el micro ya está, se elige al instante")
    finally:
        P.sd = original


if __name__ == "__main__":
    test_microfono_que_aparece_tarde()
    test_microfono_presente_no_espera()
    print("\nMicrófono: 2/2 en verde.")
