"""
modulos/display_spidev.py
=========================
Driver de la pantalla circular **GC9A01** (Waveshare 1.28inch LCD Module) por
SPI + GPIO. Hardware objetivo: Orange Pi 5 Pro (RK3588S), header de 40 pines.

Los pines NO están cableados aquí: se declaran por **nombre de GPIO** en
`config.yaml` (sección `pantalla`), así que se puede recablear sin tocar código.
Además se **autodetecta el `/dev/gpiochipN`** correcto preguntándole a libgpiod
el label de cada nodo (`gpio1`, `gpio4`…) — lo mismo que muestra `gpiodetect`.
No se usa `/sys/class/gpio`: en el kernel de Orange Pi (6.1.43-rk3588) esos
directorios son symlinks, el nombre usa la base global (`gpiochip32` = `gpio1`)
y no tienen atributo `dev`.

Cableado de referencia (módulo → Orange Pi 5 Pro):

    módulo  señal              pin físico   GPIO
    ------  -----------------  ----------   ---------
    VCC     3.3 V                  1 (o 17)   —
    GND     GND                    6          —
    DIN     SPI0_MOSI_M2          19          GPIO1_B2
    CLK     SPI0_CLK_M2           23          GPIO1_B3
    CS      SPI0_CS0_M2           24          GPIO1_B4
    DC      comando/datos         22          GPIO1_B0
    RST     reset                 13          GPIO4_B3
    BL      3.3 V (brillo fijo)   17          —

Uso normal: Parker lo instancia y llama a `attach_scene(self.scene)`.

Diagnóstico sin arrancar Parker (chips GPIO, spidev y pinta rojo/verde) y barrido
de hipótesis (7 colores, uno por combinación de velocidad/modo/polaridad):

    QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py
    QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --barrido
    QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --parpadeo
    QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --colores
    QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --loopback
"""

import glob
import os
import queue
import threading
import time
from pathlib import Path

import gpiod
import spidev
from gpiod.line import Direction, Value
from PySide6.QtCore import QTimer, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

# Valores de fábrica = cableado de referencia de la Orange Pi 5 Pro (docs/placa.md §7)
CONFIG_POR_DEFECTO = {
    # 24 MHz = 38 ms por fotograma completo (240x240x2 B = 115 KB): el techo
    # real del bus es ~26 fps. A 25 fps no quedaba margen y la cola de envíos
    # crecía (cara congelada y fotogramas a medias, visto 25/10). 15 fps sobran
    # para una cara que respira.
    "fps": 15,
    "spi_bus": 0,
    "spi_dispositivo": 0,
    "velocidad_hz": 24_000_000,
    "dc_gpio": "GPIO1_B0",   # pin físico 22
    "rst_gpio": "GPIO4_B3",  # pin físico 13
    "modo_spi": 0,            # GC9A01 acepta modo 0 (por defecto) y 3
    "rst_activo_alto": True,  # el módulo reinicia con RST a nivel bajo
    "init_minima": False,     # True = secuencia corta (SWRESET/SLPOUT/COLMOD)
    "velocidad_init_hz": 1_000_000,  # el init va despacio: 1-2 bytes por escritura
    "madctl": 0x98,           # MADCTL oficial del módulo (orden/orientación de color)
    "inversion": True,        # INVON (0x21): sin él la imagen sale pálida y con tinte
}

GRUPOS = {"A": 0, "B": 1, "C": 2, "D": 3}
CHIP_AUTOMATICO = (None, "", "auto")


def numero_de_linea(nombre_gpio: str) -> tuple[int, int]:
    """`'GPIO1_B0'` → `(banco=1, línea=8)`.

    La línea dentro del banco es `grupo * 8 + número` (A=0, B=1, C=2, D=3),
    notación de Rockchip (GPIO1_B0 → 1*8+0 = 8; GPIO4_B3 → 1*8+3 = 11)."""
    limpio = nombre_gpio.strip().upper()
    if limpio.startswith("GPIO"):
        limpio = limpio[4:]
    try:
        banco, resto = limpio.split("_")
        return int(banco), GRUPOS[resto[0]] * 8 + int(resto[1:])
    except (ValueError, IndexError, KeyError) as e:
        raise ValueError(
            f"Nombre de GPIO invalido: {nombre_gpio!r} (formato esperado 'GPIO1_B0')"
        ) from e


def _orden_nodo(ruta: str) -> int:
    cola = ruta[len("/dev/gpiochip"):]
    return int(cola) if cola.isdigit() else 10 ** 9


def chips_disponibles() -> list[tuple[str, str, str]]:
    """`[(dispositivo, label, líneas)]` de los `/dev/gpiochipN`, leído con libgpiod.

    Aquí **no** sirve leer `/sys/class/gpio`: comprobado en la Orange Pi 5 Pro
    (kernel 6.1.43-rk3588), esos directorios son *symlinks* a la ruta del device
    tree, **el nombre usa la base global** (`gpiochip32` = `gpio1`) y **no tienen
    atributo `dev`** para emparejar por `major:minor`. libgpiod abre cada nodo y
    devuelve su label, que es exactamente lo que imprime `gpiodetect`."""
    chips = []
    for ruta in sorted(glob.glob("/dev/gpiochip*"), key=_orden_nodo):
        etiqueta, lineas = "", ""
        try:
            chip = gpiod.Chip(ruta)
            try:
                info = chip.get_info()
                etiqueta = getattr(info, "label", "") or ""
                lineas = str(getattr(info, "num_lines", "") or "")
            finally:
                chip.close()
        except Exception:
            pass                      # un chip raro no debe romper la enumeración
        chips.append((ruta, etiqueta, lineas))
    return chips


def resolver_chip(banco: int, forzado: str | None = None) -> str:
    """Devuelve el `/dev/gpiochipN` cuyo label sea `gpio<banco>` (p. ej. `gpio1`)."""
    if forzado not in CHIP_AUTOMATICO:
        return forzado
    buscado = f"gpio{banco}"
    chips = chips_disponibles()
    for dispositivo, etiqueta, _ in chips:
        if etiqueta == buscado:
            return dispositivo
    # Sin labels del kernel (sysfs no legible) hay que confiar en la numeración
    # directa; pero si SÍ leímos labels y ninguno es el banco, es más seguro
    # fallar que conmutar el pin equivocado en silencio.
    if chips and not any(etiqueta for _, etiqueta, _ in chips):
        heredado = f"/dev/gpiochip{banco}"
        if os.path.exists(heredado):
            return heredado
    visibles = ", ".join(f"{d}({e or 'sin label'})" for d, e, _ in chips) or "ninguno"
    raise RuntimeError(
        f"No encuentro el banco {buscado} en {visibles}. "
        "Fija pantalla.dc_chip / pantalla.rst_chip en config.yaml con la ruta correcta."
    )


class GC9A01Display:
    def __init__(self, fps: int | None = None, config: dict | None = None):
        cfg = dict(CONFIG_POR_DEFECTO)
        cfg.update({k: v for k, v in (config or {}).items() if v is not None})
        self.cfg = cfg

        self.ancho = self.alto = 240
        self.fps = int(fps or cfg.get("fps", 25))

        # 1. Resolver y reservar los GPIO de DC y RST (nombre de GPIO → chip + línea)
        banco_dc, linea_dc = numero_de_linea(cfg["dc_gpio"])
        banco_rst, linea_rst = numero_de_linea(cfg["rst_gpio"])
        self.dc_chip = resolver_chip(banco_dc, cfg.get("dc_chip"))
        self.rst_chip = resolver_chip(banco_rst, cfg.get("rst_chip"))
        self.dc_line = int(cfg.get("dc_line") or linea_dc)
        self.rst_line = int(cfg.get("rst_line") or linea_rst)

        try:
            self.dc_req = gpiod.request_lines(
                self.dc_chip,
                consumer="GC9A01_DC",
                config={self.dc_line: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.INACTIVE)},
            )
        except Exception as e:
            raise RuntimeError(
                f"No pude reservar DC ({cfg['dc_gpio']}) en {self.dc_chip} "
                f"linea {self.dc_line}: {e}"
            ) from e

        try:
            self.rst_req = gpiod.request_lines(
                self.rst_chip,
                consumer="GC9A01_RST",
                config={self.rst_line: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.ACTIVE)},
            )
        except Exception as e:
            self.dc_req.release()
            raise RuntimeError(
                f"No pude reservar RST ({cfg['rst_gpio']}) en {self.rst_chip} "
                f"linea {self.rst_line}: {e}"
            ) from e

        # 2. Timer de captura (antes de SPI/GPIO: así close() siempre tiene algo que parar)
        self.timer = QTimer()
        self.timer.setInterval(int(1000 / self.fps))
        # Cola de UN hueco para los fotogramas ya empaquetados, y su hilo de
        # envío: el SPI no puede correr en el hilo de la interfaz (ver attach_scene).
        self._cola_frames: queue.Queue = queue.Queue(maxsize=1)
        self._hilo_envio = None
        # El envío y una posible reinicialización del panel no pueden usar el
        # SPI a la vez. El vigilante de abajo comprueba que la cara no se quede
        # clavada en el último fotograma (visto en la placa el 31/10).
        self._lock_spi = threading.Lock()
        self._ultimo_envio = time.monotonic()
        self._frames_capturados = 0
        self._frames_enviados = 0
        self._ultimo_aviso_display = 0.0
        self._cerrado = False
        self._vigia = None

        # 3. Configurar SPI
        self.spi = spidev.SpiDev()
        self.spi.open(int(cfg.get("spi_bus", 0)), int(cfg.get("spi_dispositivo", 0)))
        self.spi.max_speed_hz = int(cfg.get("velocidad_hz", 24_000_000))
        self.spi.mode = int(cfg.get("modo_spi", 0)) & 0b11

        # 4. Inicializar pantalla (el pulso de RST reinicia el controlador)
        try:
            self.init_display()
            self.clear_screen()
        except Exception:
            self.close()      # no dejar GPIO/SPI reservados si falla el init
            raise

    def close(self):
        """Libera cada recurso por separado: un fallo (p. ej. el timer aún no
        existía) no puede dejar GPIO o SPI reservados para el siguiente intento."""
        def parar_hilo():
            self._cerrado = True
            # `put(None)` a secas se queda esperando si la cola está llena y el
            # hilo de envío está atascado; el cierre no puede colgarse por eso.
            try:
                self._cola_frames.put_nowait(None)
            except queue.Full:
                try:
                    self._cola_frames.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._cola_frames.put_nowait(None)
                except queue.Full:
                    pass
            if self._hilo_envio is not None:
                self._hilo_envio.join(timeout=1.0)
            if self._vigia is not None:
                self._vigia.join(timeout=0.2)

        for liberar in (parar_hilo,
                        lambda: self.timer.stop(),
                        lambda: self.spi.close(),
                        lambda: self.dc_req.release(),
                        lambda: self.rst_req.release()):
            try:
                liberar()
            except Exception:
                pass

    def set_dc(self, val):
        self.dc_req.set_value(self.dc_line, Value.ACTIVE if val else Value.INACTIVE)

    def set_rst(self, val):
        """`1` = RST liberado (nivel alto), `0` = reset activo (nivel bajo).

        `pantalla.rst_activo_alto: false` invierte la polaridad, por si el módulo
        reinicia al revés (descarta un cable invertido sin tocarlo)."""
        alto = bool(self.cfg.get("rst_activo_alto", True))
        activo = bool(val) if alto else not bool(val)
        self.rst_req.set_value(self.rst_line, Value.ACTIVE if activo else Value.INACTIVE)

    def send_cmd(self, cmd):
        self.set_dc(0)
        self.spi.writebytes([cmd])

    def send_data(self, data):
        self.set_dc(1)
        if isinstance(data, int):
            self.spi.writebytes([data])
        else:
            chunk_size = 4096
            for i in range(0, len(data), chunk_size):
                self.spi.writebytes2(data[i:i + chunk_size])

    def init_display(self):
        """Secuencia completa del GC9A01: la oficial del módulo Waveshare 1.28".

        Incluye las tres partes que le faltaban a la primera versión y que dejan
        la imagen **pálida y con tinte raro** (gris-violáceo, verdes raros) en vez
        de blanco/colores limpios: los registros extendidos `0x8A`/`0x8B` y
        `0xB6`, las **tablas de gamma** (`0xF0`-`0xF3`, `0xED`, `0xAE`, `0xCD`,
        `0x70`, `0xE8`, `0x62`-`0x67`, `0x74`, `0x98`) y la **inversión de
        pantalla** (`0x21`, `INVON`, que este panel necesita). De paso el
        `MADCTL` oficial es `0x98`, no `0x48`.
        """
        # El init va despacio a propósito: son escrituras de 1-2 bytes con el pin
        # DC cambiando en cada una, la parte más frágil del enlace con Dupont.
        # Los fotogramas (bloques grandes) sí van a la velocidad de config.yaml.
        velocidad_fotogramas = self.spi.max_speed_hz
        self.spi.max_speed_hz = int(self.cfg.get("velocidad_init_hz", 1_000_000))

        self.set_rst(1); time.sleep(0.01)
        self.set_rst(0); time.sleep(0.01)
        self.set_rst(1); time.sleep(0.05)

        if self.cfg.get("init_minima"):
            # Versión corta: solo para descartar que el fallo sea la secuencia larga
            self.send_cmd(0x01); time.sleep(0.12)      # SWRESET
            self.send_cmd(0x36); self.send_data(int(self.cfg.get("madctl", 0x98)))
            self.send_cmd(0x3A); self.send_data(0x05)  # COLMOD: RGB565
            self.send_cmd(0x21 if self.cfg.get("inversion", True) else 0x20)
            self.send_cmd(0x11); time.sleep(0.12)      # SLPOUT
            self.send_cmd(0x29); time.sleep(0.02)      # DISPON
            self.spi.max_speed_hz = velocidad_fotogramas
            return

        # Desbloqueo de los registros internos (hay que hacerlo dos veces)
        self.send_cmd(0xEF)
        self.send_cmd(0xEB); self.send_data(0x14)
        self.send_cmd(0xFE)
        self.send_cmd(0xEF)
        self.send_cmd(0xEB); self.send_data(0x14)

        self.send_cmd(0x84); self.send_data(0x40)
        self.send_cmd(0x85); self.send_data(0xFF)
        self.send_cmd(0x86); self.send_data(0xFF)
        self.send_cmd(0x87); self.send_data(0xFF)
        self.send_cmd(0x88); self.send_data(0x0A)
        self.send_cmd(0x89); self.send_data(0x21)
        self.send_cmd(0x8A); self.send_data(0x00)   # faltaba
        self.send_cmd(0x8B); self.send_data(0x80)   # faltaba
        self.send_cmd(0x8C); self.send_data(0x01)
        self.send_cmd(0x8D); self.send_data(0x01)
        self.send_cmd(0x8E); self.send_data(0xFF)
        self.send_cmd(0x8F); self.send_data(0xFF)
        self.send_cmd(0xB6); self.send_data([0x00, 0x20])
        self.send_cmd(0x36); self.send_data(int(self.cfg.get("madctl", 0x98)))
        self.send_cmd(0x3A); self.send_data(0x05)   # COLMOD: RGB565
        self.send_cmd(0x90); self.send_data([0x08, 0x08, 0x08, 0x08])
        self.send_cmd(0xBD); self.send_data(0x06)
        self.send_cmd(0xBC); self.send_data(0x00)
        self.send_cmd(0xFF); self.send_data([0x60, 0x01, 0x04])
        self.send_cmd(0xC3); self.send_data(0x13)
        self.send_cmd(0xC4); self.send_data(0x13)
        self.send_cmd(0xC9); self.send_data(0x22)
        self.send_cmd(0xBE); self.send_data(0x11)
        self.send_cmd(0xE1); self.send_data([0x10, 0x0E])
        self.send_cmd(0xDF); self.send_data([0x21, 0x0C, 0x02])

        # --- tablas de gamma: sin esto la imagen sale lavada y con mal tono ---
        self.send_cmd(0xF0); self.send_data([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A])
        self.send_cmd(0xF1); self.send_data([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F])
        self.send_cmd(0xF2); self.send_data([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A])
        self.send_cmd(0xF3); self.send_data([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F])
        self.send_cmd(0xED); self.send_data([0x1B, 0x0B])
        self.send_cmd(0xAE); self.send_data(0x77)
        self.send_cmd(0xCD); self.send_data(0x63)
        self.send_cmd(0x70); self.send_data([0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03])
        self.send_cmd(0xE8); self.send_data(0x34)
        self.send_cmd(0x62); self.send_data([0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70])
        self.send_cmd(0x63); self.send_data([0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70])
        self.send_cmd(0x64); self.send_data([0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07])
        self.send_cmd(0x66); self.send_data([0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00])
        self.send_cmd(0x67); self.send_data([0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98])
        self.send_cmd(0x74); self.send_data([0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00])
        self.send_cmd(0x98); self.send_data([0x3E, 0x07])

        self.send_cmd(0x35)                                    # TEON
        self.send_cmd(0x21 if self.cfg.get("inversion", True) else 0x20)
        self.send_cmd(0x11); time.sleep(0.12)                  # SLPOUT
        self.send_cmd(0x29); time.sleep(0.02)                  # DISPON

        self.spi.max_speed_hz = velocidad_fotogramas

    def _ventana_completa(self):
        """Direcciona toda la pantalla (CASET/RASET) y abre la escritura de RAM."""
        self.send_cmd(0x2A); self.send_data([0, 0, 0, self.ancho - 1])
        self.send_cmd(0x2B); self.send_data([0, 0, 0, self.alto - 1])
        self.send_cmd(0x2C)

    def pintar_color(self, rgb: tuple[int, int, int]):
        """Rellena la pantalla entera con un color RGB565 (diagnóstico de cableado)."""
        r, g, b = rgb
        color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        n = self.ancho * self.alto
        buf = bytearray(n * 2)
        buf[0::2] = bytes([color >> 8]) * n
        buf[1::2] = bytes([color & 0xFF]) * n
        self._ventana_completa()
        self.send_data(buf)

    def clear_screen(self):
        self.pintar_color((0, 0, 0))

    def attach_scene(self, scene):
        """Renderiza en el hilo de Qt y envía por SPI en OTRO hilo.

        Enviar un fotograma son 115 KB por SPI: ~38 ms a 24 MHz. Hacerlo en el
        hilo de la interfaz dejaba la cara congelada y, si la cola del kernel
        se llenaba, el panel mostraba fotogramas a medias (los ojos parecían
        estirarse al quedar restos del anterior). Ahora:
          - la interfaz solo rasteriza (rápido) y deja el fotograma listo;
          - una cola de UN hueco guarda solo el más reciente (si el panel va
            por detrás, se descarta el viejo en vez de acumular retraso);
          - un hilo propio hace las escrituras SPI y los comandos de ventana.
        """
        self.scene = scene

        def capture():
            self._frames_capturados += 1
            # Renderizar en memoria directamente en formato RGB16 nativo
            img = QImage(self.ancho, self.alto, QImage.Format_RGB16)
            img.fill(Qt.black)

            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)
            self.scene.render(painter, QRectF(0, 0, self.ancho, self.alto), QRectF(0, 0, 400, 400))
            painter.end()

            # Intercambiar bytes de Little-Endian a Big-Endian a nivel C++ (<1ms)
            raw = bytes(img.bits())
            buf = bytearray(len(raw))
            buf[0::2] = raw[1::2]
            buf[1::2] = raw[0::2]

            try:
                self._cola_frames.put_nowait(buf)
            except queue.Full:
                try:
                    self._cola_frames.get_nowait()      # descarta el viejo
                except queue.Empty:
                    pass
                try:
                    self._cola_frames.put_nowait(buf)
                except queue.Full:
                    pass

        if self._hilo_envio is None:
            self._hilo_envio = threading.Thread(target=self._bucle_envio, daemon=True)
            self._hilo_envio.start()
        if self._vigia is None:
            self._vigia = threading.Thread(target=self._vigilar_panel, daemon=True)
            self._vigia.start()

        self.timer.timeout.connect(capture)
        self.timer.start()
        capture()

    def _vigilar_panel(self):
        """Reinicia el GC9A01 si la cara deja de refrescarse.

        El 31/10 la cara se quedó congelada con el proceso vivo: el panel
        dejó de recibir fotogramas aunque el SPI no daba errores. Este hilo no
        depende del bucle de Qt, así que puede detectarlo incluso si la
        interfaz se atasca, y reenvía la secuencia de init para recuperar el
        controlador sin reiniciar a Parker.
        """
        while not self._cerrado:
            time.sleep(2.0)
            if self._cerrado:
                return
            silencio = time.monotonic() - self._ultimo_envio
            if silencio < 8.0 or self._frames_capturados == 0:
                continue
            ahora = time.monotonic()
            if ahora - self._ultimo_aviso_display >= 30.0:
                self._ultimo_aviso_display = ahora
                print(f"[Display] La cara lleva {silencio:.1f}s sin refrescar "
                      f"({self._frames_capturados} capturados, "
                      f"{self._frames_enviados} enviados); reinicio el panel.")
            if not self._lock_spi.acquire(timeout=1.5):
                if ahora - self._ultimo_aviso_display >= 30.0:
                    self._ultimo_aviso_display = ahora
                    print("[Display] El hilo de envío no suelta el SPI; "
                          "no puedo reiniciar el panel todavía.")
                continue
            try:
                self.init_display()
                self.clear_screen()
                self._ultimo_envio = time.monotonic()
                print("[Display] Panel reiniciado; la cara vuelve a refrescarse.")
            except Exception as e:
                print(f"[Display] No pude reiniciar el panel: {e}")
            finally:
                self._lock_spi.release()

    def _bucle_envio(self):
        """Hilo de envío: coge el último fotograma y lo manda por SPI."""
        while True:
            buf = self._cola_frames.get()
            if buf is None:          # señal de cierre desde close()
                return
            try:
                with self._lock_spi:
                    self._ventana_completa()
                    self.send_data(buf)
                self._ultimo_envio = time.monotonic()
                self._frames_enviados += 1
            except Exception as e:
                print(f"[Display] Error al enviar el fotograma: {e}")
                time.sleep(0.2)


# Colores bien distintos para que puedas decir cuál apareció. El blanco no vale:
# es justo el aspecto del panel alimentado y sin inicializar.
COLORES_BARRIDO = [
    ("ROJO", (255, 0, 0)),
    ("VERDE", (0, 255, 0)),
    ("AZUL", (0, 0, 255)),
    ("AMARILLO", (255, 255, 0)),
    ("CIAN", (0, 255, 255)),
    ("MAGENTA", (255, 0, 255)),
    ("NARANJA", (255, 128, 0)),
]


def combinaciones_barrido(cfg: dict) -> list[tuple[str, dict]]:
    """Hipótesis de software a probar, en orden de probabilidad.

    Devuelve `[(descripción, ajustes_de_config)]`, de lo más probable a lo más
    raro: primero la configuración buena conocida (docs/placa.md §7: 24 MHz,
    modo 0, DC 22 y RST 13, init completa con inversión) y después las variantes
    de color, de bus y de secuencia."""
    return [
        ("config tal cual (init completa, invirtiendo, 24 MHz)", {}),
        ("1 MHz", {"velocidad_hz": 1_000_000}),
        ("sin inversión (INVOFF, 0x20)", {"inversion": False}),
        ("MADCTL 0x48 en vez de 0x98", {"madctl": 0x48}),
        ("SPI en modo 3", {"velocidad_hz": 1_000_000, "modo_spi": 3}),
        ("secuencia de init mínima a 1 MHz",
         {"velocidad_hz": 1_000_000, "init_minima": True}),
        ("init a 100 kHz y fotogramas a 24 MHz", {"velocidad_init_hz": 100_000}),
    ]


def barrido(segundos: float = 5.0):
    """Agota de una pasada todo lo que depende del software, con un color por prueba.

    Para el caso "panel con retroiluminación que no pinta nada": en ~40 s prueba
    velocidad, modo SPI, polaridad de RST, DC/RST cruzados e init mínima. Si
    aparece alguno de los 7 colores, esa combinación es la que funciona y se deja
    fija en `config.yaml`. Si no aparece ninguno, el fallo está entre el header y
    el módulo (cable, conector o módulo): docs/placa.md §7."""
    cfg = _config_pantalla()
    pruebas = combinaciones_barrido(cfg)

    print("=== Barrido de hipótesis GC9A01 (Orange Pi 5 Pro) ===")
    print("Cada prueba pinta la pantalla ENTERA de un color distinto:")
    for i, (nombre, _) in enumerate(pruebas):
        print(f"  {i + 1}. {COLORES_BARRIDO[i][0]:<9} -> {nombre}")
    print(f"\nTotal ~{len(pruebas) * (segundos + 1.5):.0f} s. Mira la pantalla.\n", flush=True)

    for i, (nombre, ajustes) in enumerate(pruebas):
        etiqueta, color = COLORES_BARRIDO[i]
        combinada = dict(cfg)
        combinada.update(ajustes)
        print(f"[{i + 1}/{len(pruebas)}] {etiqueta} durante {segundos:.0f} s -> {nombre}", flush=True)
        try:
            pantalla = GC9A01Display(config=combinada)
        except Exception as e:
            print(f"      no pude prepararla: {e}", flush=True)
            continue
        try:
            pantalla.pintar_color(color)
            time.sleep(segundos)
        except Exception as e:
            print(f"      no pude pintar: {e}", flush=True)
        finally:
            pantalla.close()

    print("\nFin. Si has visto algún color, dime cuál: es la combinación que funciona.")
    print("Si no apareció ninguno, el fallo está entre el header y el módulo "
          "(cable, conector o módulo): docs/placa.md §7.")


def parpadeo(segundos: float = 20.0):
    """Alterna negro y blanco 1 vez por segundo, a la velocidad de `config.yaml` y a 1 MHz.

    Un parpadeo no se puede confundir con el blanco estático de un panel sin
    inicializar: si lo ves, los píxeles SÍ están bajo el software y el problema
    es de init/color, no de cableado. Cada cambio se imprime con su segundo, así
    que se puede comparar lo que se ve con lo que sale en pantalla (el ciclo
    dura 1 s: cuenta los parpadeos)."""
    cfg = _config_pantalla()
    fases = [
        ("velocidad de config.yaml", {}),
        ("1 MHz", {"velocidad_hz": 1_000_000}),
    ]
    print("=== Parpadeo negro/blanco (1 ciclo por segundo) ===")
    for nombre, ajustes in fases:
        combinada = dict(cfg)
        combinada.update(ajustes)
        try:
            pantalla = GC9A01Display(config=combinada)
        except Exception as e:
            print(f"  no pude prepararla ({nombre}): {e}", flush=True)
            continue
        print(f"\n  Fase: {nombre} -- {segundos:.0f} s", flush=True)
        try:
            for i in range(max(1, int(segundos))):
                blanco = (i % 2 == 0)
                print(f"    t={i:>3}s  {'BLANCO' if blanco else 'NEGRO'}", flush=True)
                pantalla.pintar_color((255, 255, 255) if blanco else (0, 0, 0))
                time.sleep(1)
        except Exception as e:
            print(f"    fallo al pintar: {e}", flush=True)
        finally:
            pantalla.close()
    print("\nFin. Si has visto la pantalla cambiar de claro a oscuro, los píxeles "
          "están bajo control del software y el fallo no es de cableado.")


COLORES_PARPADEO = [
    ("ROJO", (255, 0, 0)),
    ("VERDE", (0, 255, 0)),
    ("AZUL", (0, 0, 255)),
    ("BLANCO", (255, 255, 255)),
    ("AMARILLO", (255, 255, 0)),
    ("CIAN", (0, 255, 255)),
    ("MAGENTA", (255, 0, 255)),
]


def parpadeo_colores(segundos: float = 8.0):
    """Alterna cada color con negro 1 vez por segundo, uno detrás de otro.

    Es la forma más fácil de ver si el panel distingue **colores** o solo brillo:
    si el parpadeo blanco/negro se ve (lo normal: el panel responde) pero aquí
    todo parpadea igual, el problema es el formato de color (COLMOD/orden de
    bytes), no el cableado."""
    cfg = _config_pantalla()
    print("=== Parpadeo de colores (cada color contra negro, 1 ciclo por segundo) ===")
    try:
        pantalla = GC9A01Display(config=cfg)
    except Exception as e:
        print(f"  no pude prepararla: {e}")
        return
    try:
        ciclos = max(2, int(segundos))
        for nombre, color in COLORES_PARPADEO:
            print(f"\n  {nombre} durante {ciclos} s:", flush=True)
            for i in range(ciclos):
                encendido = (i % 2 == 0)
                print(f"    t={i:>3}s  {nombre if encendido else 'NEGRO'}", flush=True)
                pantalla.pintar_color(color if encendido else (0, 0, 0))
                time.sleep(1)
    finally:
        pantalla.close()
    print("\nFin. Dime qué colores has reconocido y en qué orden.")


# Velocidades a probar en el loopback: la de `config.yaml` primero y después
# varias más para saber dónde empieza a fallar el bus (cables Dupont).
VELOCIDADES_LOOPBACK = (1_000_000, 8_000_000, 24_000_000, 32_000_000, 48_000_000)


def _patron(n: int) -> bytes:
    """Patrón determinista y variado (cubre los 256 valores, con 0x00 y 0xFF
    explícitos al principio): si el bus pierde bytes o mueve bits, se ve en la
    comparación y siempre con el mismo resultado entre ejecuciones."""
    return bytes([0x00, 0xFF, 0xAA, 0x55]) + bytes(((i * 31) ^ (i >> 3)) & 0xFF for i in range(n - 4))


def _intercambiar(spi, datos: bytes, bloque: int = 4096) -> bytes:
    """Intercambio full-duplex por trozos: `spidev.xfer2` está limitado a
    4096 B por llamada (`Argument list size exceeds 4096 bytes`), así que los
    fotogramas completos van en 29 trozos, igual que en el driver real."""
    recibido = bytearray()
    for i in range(0, len(datos), bloque):
        recibido.extend(spi.xfer2(list(datos[i:i + bloque])))
    return bytes(recibido)


def loopback(tamano_max: int = 115_200):
    """Autotest del bus SPI **sin depender de lo que se ve en el panel**.

    Con un puente físico entre MOSI (pin 19) y MISO (pin 21), todo lo que se
    escribe por SPI se lee de vuelta. Compara patrón enviado y recibido en
    varios tamaños (16 B a un fotograma completo de 115200 B) y velocidades
    (1 a 48 MHz): así se sabe si el bus pierde bytes, si el techo real de
    velocidad está en el cableado y cuál es el máximo de fps de la pantalla.

    Sin el puente, MISO queda al aire y la lectura es `0xFF`: el fallo es
    entonces del puente/cable, no del código (los bloques grandes se trocean en
    4096 B por el límite de `spidev.xfer2`, como hace el driver real).

    No reserva DC/RST ni inicializa el panel: solo toca `/dev/spidev0.0`.
    """
    cfg = _config_pantalla()
    bus = int(cfg.get("spi_bus", 0))
    dispositivo = int(cfg.get("spi_dispositivo", 0))
    modo = int(cfg.get("modo_spi", 0)) & 0b11

    print("=== Loopback SPI (MOSI pin 19 <-> MISO pin 21) ===")
    print(f"Dispositivo /dev/spidev{bus}.{dispositivo} · modo {modo} · 8 bits\n")

    spi = spidev.SpiDev()
    try:
        spi.open(bus, dispositivo)
    except Exception as e:
        print(f"No pude abrir el SPI: {e}")
        raise SystemExit(1)

    spi.mode = modo
    spi.bits_per_word = 8
    spi.cshigh = False

    tamagnos = [16, 4096, 32_768, tamano_max]
    fallos = 0
    try:
        for velocidad in VELOCIDADES_LOOPBACK:
            spi.max_speed_hz = velocidad
            print(f"  {velocidad / 1e6:.0f} MHz:", flush=True)
            for n in tamagnos:
                envio = _patron(n)
                t0 = time.perf_counter()
                try:
                    recibido = _intercambiar(spi, envio)
                except Exception as e:
                    print(f"    {n:>6} B  ERROR: {e}", flush=True)
                    fallos += 1
                    continue
                dt = time.perf_counter() - t0
                mb_s = (len(envio) / dt / 1e6) if dt > 0 else 0.0
                extra = f", {1.0 / dt:5.0f} fotogramas/s de 240x240 teoricos" if n == tamano_max and dt > 0 else ""
                distintos = [(i, a, b) for i, (a, b) in enumerate(zip(envio, recibido)) if a != b]
                if len(recibido) != len(envio):
                    fallos += 1
                    print(f"    {n:>6} B  FALLO: envie {len(envio)} B y recibi {len(recibido)} B", flush=True)
                elif distintos:
                    fallos += 1
                    i, a, b = distintos[0]
                    print(f"    {n:>6} B  FALLO: {len(distintos)}/{len(envio)} bytes distintos "
                          f"(primero en {i}: envie 0x{a:02X}, recibi 0x{b:02X})", flush=True)
                else:
                    print(f"    {n:>6} B  OK    ({mb_s:5.1f} MB/s{extra})", flush=True)
    finally:
        spi.close()

    print()
    if fallos:
        print(f"Resultado: {fallos} prueba(s) con error. El puente esta bien puesto? "
              "Sin puente 19<->21 MISO lee 0xFF y todo falla (es lo esperado).")
        raise SystemExit(1)
    print("Resultado: bus SPI integro en todos los tamanos y velocidades probados.")
    print("Siguiente paso: si 24 MHz da OK, la cara puede ir mas rapido subiendo "
          "pantalla.velocidad_hz (el limite de fps esta entonces en el render, no en el cable).")


def _config_pantalla(config_path: str | None = None) -> dict:
    """Lee la sección `pantalla` de `config.yaml` (si existe y hay pyyaml)."""
    ruta = Path(config_path) if config_path else Path(__file__).resolve().parents[1] / "config.yaml"
    try:
        import yaml
        with open(ruta, "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("pantalla") or {}
    except Exception:
        return {}


def diagnostico():
    """Autotest: chips GPIO, nodos spidev, rojo a la velocidad de `config.yaml`
    y verde a 1 MHz tras reinicializar (descarta velocidad excesiva).

    La salida es ASCII puro a proposito: la placa puede estar en locale C y un
    print con acentos o flechas reventaria con UnicodeEncodeError."""
    cfg = _config_pantalla()
    print("=== Diagnostico pantalla GC9A01 (Orange Pi 5 Pro) ===")

    print("\nChips GPIO (/dev/gpiochip*, labels via libgpiod):")
    chips = chips_disponibles()
    if not chips:
        print("  (ninguno visible: prueba con sudo o revisa los permisos de 1.4)")
    for dispositivo, etiqueta, lineas in chips:
        print(f"  {dispositivo:<18} label={etiqueta!r:<16} lineas={lineas}")
    if chips and all(not e for _, e, _ in chips):
        print("  (labels vacios: empareja con /dev a mano via pantalla.dc_chip/rst_chip)")

    nodos_spi = glob.glob("/dev/spidev*")
    print("\nSPI:", ", ".join(nodos_spi) or "(ninguno: activa spi0-m2-cs0-spidev)")

    combinada = dict(CONFIG_POR_DEFECTO)
    combinada.update({k: v for k, v in cfg.items() if v is not None})
    for etiqueta in ("dc", "rst"):
        banco, linea = numero_de_linea(combinada[f"{etiqueta}_gpio"])
        linea = int(combinada.get(f"{etiqueta}_line") or linea)
        chip = resolver_chip(banco, combinada.get(f"{etiqueta}_chip"))
        print(f"{etiqueta.upper():<4}-> {combinada[f'{etiqueta}_gpio']} = {chip} linea {linea}")

    pantalla = GC9A01Display(config=cfg)
    print(f"\nROJO a {pantalla.spi.max_speed_hz / 1e6:.0f} MHz durante 4 s...  cambia la pantalla?")
    pantalla.pintar_color((255, 0, 0)); time.sleep(4)

    pantalla.spi.max_speed_hz = 1_000_000
    pantalla.init_display(); pantalla.clear_screen()
    print("VERDE a 1 MHz tras re-init durante 5 s...")
    pantalla.pintar_color((0, 255, 0)); time.sleep(5)

    pantalla.close()
    print("\nfin. Rojo y verde = hardware y driver OK. "
          "Blanco en ambos = cableado o pines (docs/placa.md 7).")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    segs = 5.0
    for arg in args:
        if arg.startswith("--segundos="):
            segs = float(arg.split("=", 1)[1])
    if "--barrido" in args:
        barrido(segs)
    elif "--parpadeo" in args:
        parpadeo(segs)
    elif "--colores" in args:
        parpadeo_colores(segs)
    elif "--loopback" in args:
        loopback()
    else:
        diagnostico()
