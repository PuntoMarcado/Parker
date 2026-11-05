# Instalación en la placa (Orange Pi 5 Pro)

Este documento reúne **todas las instrucciones** para montar Parker en la
Orange Pi 5 Pro: dependencias del sistema, modelos, paso de archivos desde el
PC de desarrollo y primeras pruebas. Como los demás documentos, se **actualiza
con el progreso**: la §9 (registro) y el checklist de §8 se van rellenando a
medida que se valida en la placa.

Hardware de referencia:

| Componente | Detalle |
|---|---|
| Placa | Orange Pi 5 Pro, 8 GB RAM, RK3588 (4×A76 + 4×A55, Mali-G610, NPU 6 TOPS) |
| Pantalla | GC9A01 240×240 por SPI0 (`/dev/spidev0.0`), DC = gpiochip1 línea 8, RST = gpiochip4 línea 11 |
| Audio | Micrófono + altavoz (PortAudio) |
| PC de desarrollo | Windows (`D:\TREC\parker_v5`), Python 3.13 en `venv/` |

> Convención de rutas en la placa: proyecto en `~/parker`, entorno virtual en
> `~/env` (ya usados en `INS.txt`).

---

## 0. Receta completa (orden exacto)

Secuencia única desde `orangepi@orangepi5pro:~$`, con el proyecto ya en
`~/parker` y el venv en `~/env`. Cada bloque dice qué debe pasar; los
detalles y la solución de errores están en las secciones siguientes.

### 0.1 Sistema (apt)

```bash
sudo apt update
sudo apt install -y build-essential python3-dev python3-venv git \
  libportaudio2 libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
  libxcb-cursor0 libgpiod-dev gpiod alsa-utils
```

> Ojo: en jammy el paquete de herramientas GPIO es **`gpiod`**, no
> `libgpiod-tools` (que no existe). Si un paquete no localiza, **apt NO
> instala NADA de la lista entera** — reejecuta sin el que falte.

### 0.2 Permisos SPI/GPIO (esta imagen no tiene grupos `spi`/`gpio`)

```bash
sudo tee /etc/udev/rules.d/99-parker-hw.rules >/dev/null <<'EOF'
KERNEL=="spidev*", MODE="0666"
KERNEL=="gpiochip*", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -l /dev/spidev0.0 /dev/gpiochip1 /dev/gpiochip4
```

Debe verse `crw-rw-rw-` en los tres. Si da `cannot access '/dev/spidev0.0'`:
SPI no está activado → `sudo orangepi-config` → Hardware → SPI → reboot (§1.5).

### 0.3 Archivos del proyecto

```bash
cd ~/parker
ls config.yaml requirements.txt assets/voz/es_ES-davefx-medium.onnx
```

Si **no aparecen los tres**, faltan archivos en la placa → copiar del PC (§5)
o, en el caso de `config.yaml`, recrearlo aquí:

```bash
test -f config.yaml || cat > config.yaml <<'YAML'
# Parker v5 - Configuración Global
llama:
  host: "http://localhost:11434"
  modelo: "qwen2.5:3b"
  max_tokens: 90
  temperature: 0.7
  num_ctx: 1024
  num_thread: 4
  keep_alive: "24h"
  precalentar: true
  historial_mensajes: 2
memoria:
  db_path: "./parker.db"
  coleccion: "recuerdos_parker"
  modelo_embeddings: "paraphrase-multilingual-MiniLM-L12-v2"
  top_k_recuerdos: 2
  umbral_relevancia: 0.5
  max_caracteres_recuerdo: 110
voz:
  modelo_piper: "./assets/voz/es_ES-davefx-medium.onnx"
  modelo_config: "./assets/voz/es_ES-davefx-medium.onnx.json"
  velocidad: 0.9
  volumen: 0.9
escucha:
  backend: "auto"
  modelo_whisper: "base"
  modelo_faster: "base"
  beam_size: 1
  vad_filter: True
  idioma: "es"
  duracion_maxima_grabacion: 20
  silencio_corte_seg: 0.6
  hotwords: "Parker"
  umbral_silencio: 0.02
  canales: 1
  dispositivo_entrada: null
autonomia:
  intervalo_comprobacion_seg: 300
  umbral_silencio_seg: 2700
  umbral_sedentario_seg: 3600
YAML
```

Y comprobar que `requirements.txt` trae `PySide6` (si no, copiarlo del PC):
`grep -c PySide6 requirements.txt` debe dar ≥ 1.

### 0.4 Verificar el venv

```bash
source ~/env/bin/activate
python -c "import PySide6, sounddevice, chromadb, piper, onnxruntime, spidev, gpiod; print('deps ok')"
```

Debe imprimir `deps ok`. Si falla algún import → §3.

### 0.5 Cerebro (Ollama + qwen2.5:3b, ~2 GB)

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen2.5:3b
# opcional, más «cabeza» pero ~2 s más por respuesta:
# ollama pull qwen2.5:3b
curl -s http://localhost:11434/api/version
```

Debe responder JSON `{"version": ...}` (§4.1).

### 0.6 Voz Piper (solo si el `ls` de §0.3 no encontraba el `.onnx`)

```bash
cd ~/parker/assets/voz
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium
curl -LO $BASE/es_ES-davefx-medium.onnx
curl -LO $BASE/es_ES-davefx-medium.onnx.json
```

Embeddings y faster-whisper ya se descargaron en el primer arranque (si no,
se bajan solos al arrancar, §4.3–§4.4).

### 0.7 Escritorio X (para ver la cara)

```bash
ls /tmp/.X11-unix/ 2>/dev/null      # ¿existe X0?
systemctl is-active display-manager # lightdm/gdm3/sddm
```

- Hay `X0` → desde SSH: `export DISPLAY=:0` (mejor: lanzar desde una
  terminal **del escritorio físico**, evita problemas de `XAUTHORITY`).
- No hay `X0` → arrancar el escritorio: `sudo systemctl enable --now lightdm`
  y reboot. Sin escritorio **no hay ventana** aunque el proceso siga (§6).

> **Montaje definitivo (sin HDMI)**: la placa se controla por SSH y la salida
> visual es solo la pantalla circular. En ese caso **no hace falta escritorio**: 
> lanzar siempre con `QT_QPA_PLATFORM=offscreen python parker.py` — la cara se 
> renderiza sin ventana y la muestra el driver SPI a 25 fps.

### 0.8 Arranque

```bash
cd ~/parker && source ~/env/bin/activate
python parker.py
# con log: python parker.py 2>&1 | tee -a ~/parker.log
```

Debe verse, en orden (además de la cara en pantalla y el saludo hablado):

```
[Display] Pantalla SPI GC9A01 vinculada correctamente.
[Memoria] Colección 'recuerdos_parker' lista. Documentos: 0
[Escucha] faster-whisper cargado correctamente
[Cerebro] Conectado a Ollama Local (qwen2.5:3b en http://localhost:11434)
[Voz] Modelo cargado. Sample rate: 22050Hz
```

Habla → imprime `[Latencia] STT / Primer token / Fin de frase` (rendimiento §1).
**ESC** sale limpio. Cualquier otro mensaje → tabla §7.

---

## 1. Preparar la placa (una sola vez)

1. **Imagen**: flashear la imagen oficial (Orange Pi OS / Debian) o Armbian en
   la eMMC/microSD con Rufus/balenaEtcher.
2. **SSH**: localizar la IP (`ip neigh` desde el PC o ver la pantalla conectada)
   y entrar: `ssh <usuario>@<IP>`. Credenciales por defecto según imagen
   (Orange Pi OS suele ser `orangepi`/`orangepi`; Armbian pide cambiar `root`
   en el primer arranque).
3. **Actualizar sistema**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **Permisos de hardware**. Ojo: en la imagen oficial de Orange Pi (Ubuntu
   jammy) **no existen los grupos `spi`/`gpio`** (son de Armbian) —
   `usermod -aG spi,gpio` falla con `group 'spi' does not exist`. Primero
   mira a quién pertenece el dispositivo:
   ```bash
   ls -l /dev/spidev0.0 /dev/gpiochip1 /dev/gpiochip4
   ```
   - Si el grupo que aparece existe (p. ej. `dialout`), únete a él:
     `sudo usermod -aG <grupo> $USER` y reloguea.
   - **Si es `root:root` con permisos de lectura (lo habitual aquí), regla
     udev** — funciona sin reloguear:
     ```bash
     sudo tee /etc/udev/rules.d/99-parker-hw.rules <<'EOF'
     KERNEL=="spidev*", MODE="0666"
     KERNEL=="gpiochip*", MODE="0666"
     EOF
     sudo udevadm control --reload-rules && sudo udevadm trigger
     ls -l /dev/spidev0.0   # debe verse crw-rw-rw-
     ```
     (`0666` es permisivo pero práctico en una placa de proyecto; para
     endurecer, usa `GROUP="plugdev", MODE="0660"` y únete a `plugdev`.)
   - Alternativa sin tocar nada: lanzar Parker con `sudo` como en `INS.txt`.
5. **Activar SPI** para ver `/dev/spidev0.0`:
   ```bash
   ls /dev/spidev*          # debe aparecer spidev0.0
   # si no existe:
   sudo orangepi-config      # → System → Hardware → activar SPI → reboot
   # (en Armbian: sudo armbian-config → System → Hardware)
   sudo reboot
   ```
6. **Verificar GPIO** (API libgpiod v2, la que usa el driver):
   ```bash
   gpioinfo | head           # viene del paquete `gpiod` (ver §2)
   ls /dev/gpiochip*         # debe haber gpiochip1 y gpiochip4
   ```

## 2. Paquetes del sistema (apt)

```bash
sudo apt install -y \
  build-essential python3-dev python3-venv git \
  libportaudio2 \
  libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
  libxcb-cursor0 \
  libgpiod-dev gpiod \
  alsa-utils
```

Qué es cada cosa:

| Paquete | Para qué |
|---|---|
| `build-essential`, `python3-dev` | compilar `spidev` (viene como sdist) |
| `libportaudio2` | `sounddevice` (entrada de voz y reproducción) en Linux usa PortAudio del sistema |
| `libgl1`, `libegl1`, `libxkbcommon0`, `libfontconfig1`, `libdbus-1-3` | runtime gráfico de Qt/PySide6 |
| `libxcb-cursor0` | **obligatorio desde Qt 6.5** para el plugin `xcb`; sin él: `Could not load the Qt platform plugin "xcb"` |
| `libgpiod-dev`, `gpiod` | libgpiod **v2** (requisito del paquete pip `gpiod`); `gpiod` trae `gpioinfo` — *ojo: `libgpiod-tools` no existe en jammy* |
| `alsa-utils` | `aplay -l` / `arecord -l` para diagnosticar audio |

Comprobación de audio:

```bash
arecord -l        # lista micrófonos
aplay -l          # lista salidas
```

## 3. Entorno virtual + dependencias Python

```bash
mkdir -p ~/parker && cd ~/parker
python3 -m venv ~/env
source ~/env/bin/activate
pip install --upgrade pip
```

Instalación principal (igual que el README):

```bash
pip install -r requirements.txt
```

`requirements.txt` trae PySide6, whisper, chromadb, sentence-transformers,
piper-tts, onnxruntime, sounddevice… **En la placa además** (solo Linux/SBC):

```bash
pip install spidev gpiod      # driver de la pantalla GC9A01 (§ display)
```

- `spidev` compila un módulo C (por eso `build-essential`/`python3-dev`).
- `gpiod` (v2) enlaza con libgpiod 2.x del sistema (`libgpiod-dev`). Si el
  import falla, tu imagen trae libgpiod 1.x: compilar libgpiod ≥ 2.0 desde
  fuente o usar una imagen más reciente.

Verificación rápida (sin arrancar Parker):

```bash
python -c "import PySide6, sounddevice, chromadb, piper, onnxruntime; print('ok')"
python -c "import spidev, gpiod; print('hw ok')"
```

> `faster-whisper` está en `requirements.txt`; si en tu plataforma falla la
> rueda, se instala aparte: `pip install faster-whisper` (el backend `auto`
> cae a `openai-whisper` si no está).

## 4. Modelos (descarga o copia)

Se descargan **solos en el primer arranque**, pero conviene hacerlo antes y
con cable de red. Todos se pueden precargar con estos comandos:

### 4.1 Cerebro — Ollama + qwen2.5:3b (~2 GB)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
curl http://localhost:11434/api/version    # debe responder JSON
```

> `qwen2.5:3b` sigue disponible como opción (mejor redacción, ~2 s más por
> respuesta). Medido en la placa el 17/10/2026: 1.5b primer token 2-3,4 s y
> 17-19 tok/s; 3b 6,5-7,8 s y 9,5 tok/s. Detalle en
> [rendimiento.md](rendimiento.md).

`config.yaml` apunta a `http://localhost:11434` con `keep_alive: 24h`, así que
una vez cargado no se descarga cada 5 minutos. Si Ollama no arranca en
autostart: `sudo systemctl enable --now ollama`.

### 4.2 Voz — Piper (`es_ES-davefx-medium`, ~61 MB)

Los `.onnx` **no están en git** (`.gitignore`), así que o se descargan en la
placa o se copian desde el PC (§5):

```bash
mkdir -p ~/parker/assets/voz && cd ~/parker/assets/voz
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium
curl -LO $BASE/es_ES-davefx-medium.onnx
curl -LO $BASE/es_ES-davefx-medium.onnx.json
```

### 4.3 Memoria — embeddings multilingües (~500 MB, HuggingFace)

```bash
python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'); print('ok')"
```

### 4.4 Escucha — Whisper

```bash
# faster-whisper base int8 (~145 MB) → ~/.cache/huggingface
python -c "from faster_whisper import WhisperModel; \
WhisperModel('base', device='cpu', compute_type='int8'); print('ok')"

# (small también vale: transcribe algo mejor, pero tarda ~3 s más)

# openai-whisper base (fallback) → ~/.cache/whisper
python -c "import whisper; whisper.load_model('base'); print('ok')"
```

### 4.5 Instalación sin internet (copia de cachés desde el PC)

Si la placa no tiene red, copiar los directorios de caché del PC (§5) y
declararlos:

```bash
export HF_HOME=~/.cache/huggingface     # embeddings + faster-whisper
export XDG_CACHE_HOME=~/.cache          # whisper: ~/.cache/whisper
```

## 5. Paso de archivos desde el PC

El estado actual del repo (cambios sin commitear) **no llega por git**, así
que el canal principal es `scp`/`rsync`. Las rutas de la placa son
`~/parker` (código) y `~/env` (venv, no se copia nunca).

### 5.1 Desde Windows (PowerShell, `scp` viene incluido)

```powershell
cd D:\TREC\parker_v5
scp parker.py config.yaml requirements.txt user@IP:~/parker/
scp -r modulos tests docs assets user@IP:~/parker/
```

### 5.2 Desde Git Bash / WSL (rsync, recomendado por rapidez y reintentos)

```bash
cd /d/TREC/parker_v5
rsync -av --partial \
  --exclude venv/ --exclude .git/ --exclude __pycache__/ \
  --exclude '*.pyc' --exclude parker.db/ --exclude .freebuff/ \
  ./ user@IP:~/parker/
```

Notas:

- `rsync`/`scp -r` **sí** copian `assets/voz/*.onnx` aunque git los ignora
  (si no, §4.2 los descarga en la placa).
- No copiar `venv/` (los wheels de Windows no sirven en ARM Linux) ni
  `parker.db` (la memoria se regenera; o se copia a propósito si se quiere
  trasladar recuerdos).
- Desarrollo en paralelo: repetir el `rsync` tras cada sesión de cambios; es
  idempotente.

### 5.3 Alternativa con git

Si se quiere el flujo git, hay que commitear en el PC primero (solo si se
pide) y clonar en la placa. Ojo: `assets/voz/*.onnx` seguiría fuera; para
esos dos archivos, `scp`.

### 5.4 Ejecutar en la placa desde el PC (SSH sin contraseña)

Para no copiar/pegar a mano en cada prueba (y para que el agente pueda lanzar
los tests directamente), autorizar una clave del PC en la placa **una sola vez**:

```bash
# en el PC (Git Bash):
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "parker-pc"
cat ~/.ssh/id_ed25519.pub          # copia esta línea
```

En la sesión SSH de la placa, pegar la línea anterior dentro del heredoc:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'ssh-ed25519 AAAA... parker-pc' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

(Alternativa desde el PC: `ssh-copy-id orangepi@IP` y teclear la contraseña una
vez.) A partir de ahí, todo se lanza de un tirón desde el PC:

```bash
ssh orangepi@IP "cd ~/parker && QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py"
ssh orangepi@IP "sudo cat /sys/kernel/debug/gpio | grep -E '^gpiochip|[0-9]+\\(GC9A01'"
```

> **Trampa de `scp` (sufrida)**: `scp modulos/display_spidev.py config.yaml parker.py
> user@IP:~/parker/modulos/../` copia los **tres** ficheros en `~/parker/` (el
> `..` deshace el `modulos/`) y deja el driver desactualizado en
> `~/parker/modulos/`. Copiar siempre en dos órdenes separadas:
> `scp config.yaml parker.py user@IP:~/parker/` y
> `scp modulos/display_spidev.py user@IP:~/parker/modulos/`.

### 5.5 Copia por USB (exFAT)

La imagen de la Orange Pi **no monta exFAT con `-t exfat`** (falta el módulo
del kernel); usar FUSE:

```bash
sudo apt install exfat-fuse exfatprogs
sudo mkdir -p /mnt/usb
sudo mount -t exfat-fuse /dev/sda1 /mnt/usb   # imprime "FUSE exfat 1.3.0"
cp -r /mnt/usb/* ~/parker/
sudo umount /mnt/usb
```

Ojo: copiar también los archivos sueltos de la raíz (**`config.yaml`** y
**`requirements.txt`**) — son fáciles de olvidar y sin ellos Parker no arranca
con la configuración correcta. Basura de Windows que se puede borrar:

```bash
rm -rf ~/parker/'System Volume Information' ~/parker/tests/__pycache__
```

## 6. Arranque en la placa

```bash
cd ~/parker
source ~/env/bin/activate
python parker.py
```

o el comando único de `INS.txt` (silencia logs de Qt/ORT):

```bash
sudo ORT_LOGGING_LEVEL=3 QT_LOGGING_RULES="qt.qpa.*=false;*.warning=false" \
  ~/env/bin/python3 ~/parker/parker.py
```

Qué se debe ver al arrancar (orden típico):

```
[Display] Pantalla SPI GC9A01 vinculada correctamente.   (o error controlado)
[Memoria] Cargando modelo de embeddings...
[Escucha] Cargando faster-whisper 'base' (int8, CPU)...
[Voz] Modelo cargado. Sample rate: 22050Hz
[Latencia] STT: ...                                       (al primer diálogo)
```

- **ESC** sale limpio (para timers de la cara y el display).
- **Qt necesita un escritorio X/Wayland activo.** Diagnosticar:
  ```bash
  ls /tmp/.X11-unix/           # ¿existe X0? → hay X corriendo
  systemctl is-active lightdm  # o gdm3/sddm: ¿gestor de pantallas activo?
  ```
  - Ejecutando por SSH con X activo: `export DISPLAY=:0` y lanzar (o mejor,
    lanzar desde una **terminal del escritorio** físico, evita problemas de
    `XAUTHORITY`).
  - Si la imagen arranca en consola (sin `X0`): arrancar el escritorio
    (`sudo systemctl start lightdm` o reiniciar y comprobar que entra en
    modo gráfico) o crear la entrada de autostart de §6 desde otro sitio.
  - Sin escritorio no hay ventana: Qt puede cargar otro plugin y el proceso
    sigue, pero **la cara no se ve en ningún sitio**.
- Autostart opcional: entrada en
  `~/.config/autostart/parker.desktop` con
  `Exec=bash -c "cd ~/parker && source ~/env/bin/activate && python parker.py"`.

### Pruebas en la placa

```bash
cd ~/parker && source ~/env/bin/activate
QT_QPA_PLATFORM=offscreen python tests/test_pipeline.py   # sin Ollama/audio
QT_QPA_PLATFORM=offscreen python tests/test_cara.py       # animación
QT_QPA_PLATFORM=offscreen python tests/test_render.py     # render Qt
```

## 7. Diagnóstico rápido de fallos

| Síntoma | Causa probable | Solución |
|---|---|---|
| `[Display] Módulo SPI no disponible` | falta `spidev`/`gpiod` o SPI desactivado | §3, §1.5 |
| `open /dev/spidev0.0 failed (Permission denied)` | permisos | regla udev de §1.4 o `sudo` |
| `usermod: group 'spi' does not exist` | imagen Orange Pi (no Armbian): no hay grupos `spi`/`gpio` | no hace falta: udev en §1.4 |
| `[Error Display] ... gpiochip` | libgpiod 1.x, banco equivocado o chip desplazado por el PMIC | `gpiodetect` + `pantalla.dc_chip`/`rst_chip` (§7) |
| Pantalla **blanca** con datos saliendo (25 fps) | el panel no interpreta nada: DC/RST/CS, overlay de SPI0 o velocidad | escalera de §7 (autotest + `debugfs`) |
| `PortAudio` al abrir el micro | falta `libportaudio2` o no hay dispositivo | §2, `arecord -l` |
| Qt: `could not connect to display :0` | sin escritorio X o ejecutado por SSH | diagnosticar `X0`/display manager, §6 |
| `Could not load the Qt platform plugin "xcb"` + `xcb-cursor0` | falta `libxcb-cursor0` (Qt ≥ 6.5) | `sudo apt install libxcb-cursor0` (§2) — *ya comprobado: instalado* |
| Ollama: `Connection refused` | servicio caído | `sudo systemctl start ollama` (§4.1) |
| Respuestas lentas del LLM | modelo recargado | verificar `keep_alive: "24h"` en `config.yaml` |
| `pip install` falla en `spidev` | falta toolchain | `build-essential python3-dev` (§2) |
| `E: Unable to locate package libgpiod-tools` | no existe en jammy (se llama `gpiod`) | reejecutar la lista sin él — **apt aborta entero la lista** |
| Aviso `onnxruntime ... GPU device discovery failed` | onnxruntime busca GPU y no la encuentra | **inofensivo**: corre en CPU, se ignora |

### Cableado de la pantalla (Waveshare 1.28" → Orange Pi 5 Pro)

Módulo **Waveshare 1.28inch LCD Module** (GC9A01, conector de 8 pines:
`VCC GND DIN CLK CS DC RST BL`). Los pines de SPI0 los confirma el manual
oficial §3.18.3 (`SPI0_M2`: MOSI 19 · MISO 21 · CLK 23 · CS0 24) y los de
DC/RST la tabla de pines del mismo manual (§3.18.1: pin 7 = `GPIO1_B7` y
§3.18.2: pin 11 = `GPIO4_B2`; el banco GPIO1 en orden → **pin 22 =
`GPIO1_B0`**, y tras `GPIO4_B2` (pin 11) → **pin 13 = `GPIO4_B3`**).

| Módulo | Señal | Pin físico | GPIO | gpiochip / línea |
|---|---|---|---|---|
| VCC | alimentación 3.3 V | **1** (o 17) | — | — |
| GND | tierra | **6** | — | vale cualquier GND: 6, 9, 14, 20, 25, 30, 34, 39 |
| DIN | datos SPI | **19** | GPIO1_B2 | `SPI0_MOSI_M2` |
| CLK | reloj SPI | **23** | GPIO1_B3 | `SPI0_CLK_M2` |
| CS | chip select | **24** | GPIO1_B4 | `SPI0_CS0_M2` |
| DC | comando/datos | **22** | GPIO1_B0 | `gpiochip1` línea 8 |
| RST | reset | **13** | GPIO4_B3 | `gpiochip4` línea 11 |
| BL | retroiluminación | **17** | — | 3.3 V = brillo máximo |

- **Localizar el pin 1**: pin de 3.3 V del extremo del header, junto a la
  serigrafía; los impares van por un lado (1, 3, 5…) y los pares por el otro
  (2, 4, 6…). Nunca VCC y BL en el mismo pin 17: uno al 1 y el otro al 17.
- **SPI**: activar `spi0-m2-cs0-spidev` con `sudo orangepi-config` → Hardware
  (§0.5) y comprobar el overlay activo con
  `grep -i overlay /boot/orangepiEnv.txt` (Armbian: `/boot/armbianEnv.txt`).
  **Un overlay de SPI0 que no sea el M2 manda los datos a otros pines y deja la
  pantalla en blanco.**
- El driver **no cablea los números**: `config.yaml` → `pantalla.dc_gpio` y
  `pantalla.rst_gpio` (por nombre) y él resuelve el chip
  (`GPIO1_B0` → línea `1*8+0 = 8` del banco 1). Así se recablea sin tocar código.
- Manual: <https://orangepi.net/wp-content/uploads/2024/05/OrangePi_5_Pro_RK3588S_User-Manual_v1.1.pdf>

### Pantalla en blanco: escalera de comprobación

De lo más barato a lo más caro (blanco **con retroiluminación** = BL alimentado;
si BL no recibe 3.3 V la pantalla se ve **negra**, no blanca):

1. **¿Qué chip GPIO es cuál?** (descarta el desplazamiento de numeración que
   puede provocar el chip extra del PMIC rk806):
   ```bash
   gpiodetect        # label de cada /dev/gpiochipN: ESTO es lo que usa el driver
   ```
   > **Comprobado en la placa (2026-10-12, kernel 6.1.43-rk3588)**: los
   > directorios `/sys/class/gpio/gpiochipN` son **symlinks** a la ruta del device
   > tree, el nombre usa la **base global** (`gpiochip0, 32, 64, 96, 128, 509`) y
   > **no tienen atributo `dev`**, así que no se pueden emparejar con `/dev` por
   > `major:minor`. El driver pide el label a **libgpiod**, lo mismo que
   > `gpiodetect`, y el autotest imprime:
   >
   > ```
   > /dev/gpiochip0 label='gpio0'   /dev/gpiochip1 label='gpio1'
   > /dev/gpiochip2 label='gpio2'   /dev/gpiochip3 label='gpio3'
   > /dev/gpiochip4 label='gpio4'   /dev/gpiochip5 label='rk806-gpio' (3)
   > ```
   >
   > En este kernel se cumple la numeración directa (`/dev/gpiochip1` = banco
   > `gpio1`, `/dev/gpiochip4` = `gpio4`), pero el driver **no lo asume**: lo
   > comprueba por label en cada arranque.
2. **Overlay y nodo SPI** (paso anterior) + `ls -l /dev/spidev0.0`.
3. **Autotest del driver**: imprime chips, nodos spidev y pines resueltos, pinta
   **rojo** a la velocidad de `config.yaml` y **verde** a 1 MHz tras re-init.
   ```bash
   cd ~/parker && source ~/env/bin/activate
   QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py
   ```
   - **Rojo y verde** → hardware y driver OK (el fallo era la velocidad): deja
     `pantalla.velocidad_hz: 8000000`.
   - **Solo verde** → el panel no aguanta 24 MHz con cables Dupont: baja
     `pantalla.velocidad_hz` a `8000000`.
   - **Blanco en los dos** → cableado. Paso 4.
3b. **Barrido de hipótesis** (7 pruebas, ~46 s): agota de una pasada todo lo que
depende del software **antes** de tocar cables — velocidad, modo SPI,
polaridad de RST, DC/RST cruzados e init mínima — pintando la pantalla entera
de un color distinto en cada prueba:
   ```bash
   cd ~/parker && source ~/env/bin/activate
   QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --barrido
   ```
   | Color | Combinación que se está probando |
   |---|---|
   | ROJO | `config.yaml` tal cual (24 MHz, modo 0) |
   | VERDE | 1 MHz |
   | AZUL | 100 kHz |
   | AMARILLO | DC y RST **cruzados** (pines 22 y 13 al revés) |
   | CIAN | RST con polaridad invertida |
   | MAGENTA | SPI en **modo 3** |
   | NARANJA | secuencia de **init mínima** a 1 MHz |
   - Aparece **algún** color → esa combinación es la que funciona: se deja fija
     en `config.yaml` (`velocidad_hz`, `modo_spi`, `rst_activo_alto`) y no hay
     que mover un solo cable.
   - **Ningún** color → el software queda descartado entero (las 7 combinaciones
     se ejecutan sin error) y el fallo está entre el header y el módulo: paso 4.
3c. **Parpadeo** (los dos instrumentos que resuelven "¿píxeles o cableado?"):
   con el panel **con** retroiluminación pero sin pintar nada, no se puede
   distinguir a ojo "no llegan datos" de "los datos no valen". Un parpadeo sí:
   ```bash
   cd ~/parker && source ~/env/bin/activate
   # blanco <-> negro, 1 ciclo por segundo, a 24 MHz y a 1 MHz
   QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --parpadeo
   # cada color contra negro, 1 ciclo por segundo: ¿distingue COLORES o solo brillo?
   QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --colores
   ```
   - **Parpadea** → DIN, CLK, CS, DC, RST e init están bien: el problema es de
     **color o de init incompleta** (ver más abajo, «Pantalla "en blanco": causa
     raíz encontrada»), no de cableado. Mover cables a partir de aquí solo empeora.
   - **No parpadea nada** → no hay retroiluminación o no llegan datos: paso 4.

3d. **Loopback del bus SPI** (necesita un puente físico entre los pines 19 y 21,
es decir MOSI con MISO): es el único diagnóstico que **no depende de la vista**.
El driver escribe patrones conocidos y los lee de vuelta por MISO.
   ```bash
   cd ~/parker && source ~/env/bin/activate
   QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --loopback
   ```
   | Lo que sale | Qué significa |
   |---|---|
   | `OK` en 16 B a 115200 B, de 1 a 48 MHz | Bus íntegro: si la cara va lenta, el cuello de botella es el render, no el cable |
   | Fallos con `recibi 0xFF` | MISO al aire: el puente no toca el pin 21 (o el 19) |
   | Fallos con `recibi 0x00` | MISO atado a un nivel bajo (pin 21 en un GND, o el cable en el pin de al lado) |
   | `OK` hasta 8-24 MHz y fallos a 48 MHz | El límite real está en la velocidad, no en el cableado |

   **Trampa comprobada en la placa (2026-10-12)**: leer los pines 19/21 como
   GPIO **no sirve** para esto. Con el SPI abierto, el pin 19 (MOSI) se lee
   `ACTIVE` aunque se le acabe de enviar `0x00`: el mux deja el camino de
   entrada del GPIO desconectado del pad. La única lectura fiable de MISO es la
   del propio controlador (el eco).

   **El puente es un cable APARTE**: el cable del **DIN del módulo se queda en
   el 19** y el puente va *encima* (19 → 21, dos conectores en el pin 19). Si se
   *mueve* el DIN del 19 al 21 en lugar de puentear, el panel se queda **negro**
   (pin 21 es la **entrada** MISO del SoC: no puede gobernar al módulo) y el eco
   pasa a leerse constante en vez de seguir a MOSI. Comprobado: el usuario movió
   el DIN del 19 al 21 y la pantalla dejó de pintar.

**Lección aprendida (2026-10-12)**: 3b y 3c se adelantaron a propósito antes de
mover cables, y fue lo que resolvió el caso — la pantalla "en blanco" era la
**init incompleta**, no el cableado (detalle más abajo).

4. **DC y RST en el pin físico** — `gpio readall` (wiringOP) **funciona sin
   `sudo`** y da la tabla del header con modo y valor de cada pin. Se puede
   verificar en un solo pegado, forzando valores distintos y releyendo:
   ```bash
   cd ~/parker && source ~/env/bin/activate
   python - <<'PY' &
   import time, gpiod
   from gpiod.line import Direction, Value
   gpiod.request_lines('/dev/gpiochip1', consumer='HOLD_DC',
       config={8: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)})
   gpiod.request_lines('/dev/gpiochip4', consumer='HOLD_RST',
       config={11: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)})
   time.sleep(50)
   PY
   sleep 2 && gpio readall | sed -n '8,15p' && wait
   ```
   **Comprobado en la placa (2026-10-12)** con DC=1 y RST=0:

   ```
   |  139 |   7 |  CAN1_TX |    OUT | 0 | 13 || 14 |   |        | GND      |     |      |
   |   42 |  11 | SPI0_TXD |   ALT8 | 1 | 19 || 20 |   |        | GND      |     |      |
   |   41 |  12 | SPI0_RXD |   ALT8 | 1 | 21 || 22 | 1 | OUT    | GPIO1_B0 | 13  | 40   |
   |   43 |  14 | SPI0_CLK |   ALT8 | 0 | 23 || 24 | 1 | ALT8   | SPI0_CS0 | 15  | 44   |
   ```

   Es decir: pin **13** = GPIO global **139** = `GPIO4_B3` (RST) y pin **22** =
   global **40** = `GPIO1_B0` (DC), ambos en modo `OUT` con el valor forzado, y
   **19/21/23/24 ya muxados como `SPI0_TXD/RXD/CLK/CS0`** (`ALT8`).
   `gpiodetect` confirma además `/dev/gpiochip0…4` = `gpio0…gpio4`.

   Si esto sale como arriba, **el lado del SoC está bien** y el fallo vive
   **entre el header y el módulo**: continuidad de los 8 hilos, conector/ribbon
   bien encajado, y sobre todo que **VCC esté en 3.3 V (pin 1 o 17) y nunca en
   los 5 V (pines 2 o 4)** — un VCC en 5 V deja el panel con retroiluminación,
   blanco y sin responder a nada.
   **Prueba de 30 s**: intercambia los cables de **DC y RST** (pines 22 y 13) y
   repite el paso 3 — si aparece rojo y verde, estaban cruzados en el conector
   del módulo (que `gpio readall` no puede ver).
   Alternativa con `debugfs` (requiere `sudo`): `sudo cat /sys/kernel/debug/gpio`
   debe listar `gpio-40 (GC9A01_DC)` bajo el chip `gpio1` y `gpio-139
   (GC9A01_RST)` bajo `gpio4`.
   *Si los labels no cuadran*: fija `pantalla.dc_chip` / `pantalla.rst_chip` con
   lo que imprima `gpiodetect`.

### Pantalla "en blanco": causa raíz encontrada (2026-10-12)

El síntoma (retroiluminación encendida, panel claro/lavado y sordo a todo) **no
era ni un cable ni el pinout**: era la **secuencia de inicialización incompleta**.
A la primera versión del driver le faltaban cuatro bloques del GC9A01:

| Faltaba | Comando | Efecto de omitirlo |
|---|---|---|
| Registros extendidos | `0x8A`/`0x8B`, `0xB6 = 00 20` | El panel no sale de su estado por defecto |
| **Tablas de gamma** | `0xF0`-`0xF3`, `0xED`, `0xAE`, `0xCD`, `0x70`, `0xE8`, `0x62`-`0x67`, `0x74`, `0x98` | Imagen **pálida, sin contraste**, con tinte verdoso/violáceo |
| **Inversión de pantalla** | `0x21` (INVON) | Este panel muestra lo contrario de lo que se le manda |
| MADCTL correcto | `0x36 = 0x98` (no `0x48`) | Orientación/orden de color equivocados |

Con la secuencia completa (la oficial del módulo Waveshare 1.28") el panel
pinta la cara de Parker y responde a los colores. Detalles de la corrección:

- La **secuencia de init va a 1 MHz** (`pantalla.velocidad_init_hz`): son
  escrituras de 1-2 bytes con el pin DC cambiando en cada una, la parte más
  frágil del enlace. Los **fotogramas** (bloques de 115 KB) sí van a 24 MHz.
- `0x21`/`0x20` y el valor de MADCTL son **configurables** (`pantalla.inversion`,
  `pantalla.madctl`), para probar variantes sin editar el driver.
- Si vuelve a verse lavado o con tonos cambiados (otra tirada de módulo),
  la vía rápida es el parpadeo de colores: `--colores` (ver §7 paso 3c).

**Lección para el diagnóstico**: un panel *con* retroiluminación que no pinta
no distingue por sí solo entre "no llegan datos" y "los datos no valen". Los
dos instrumentos que lo separaron en un minuto fueron `--parpadeo` (blanco↔negro:
¿píxeles bajo control?) y `--colores` (¿distingue colores o solo brillo?).

Causas restantes de pantalla blanca si el panel *no* parpadea: DC sin conectar
o en otro pin · overlay de SPI0 distinto del M2 · RST mal · CS fuera del pin 24 ·
velocidad SPI excesiva para cables Dupont.

### Pines de DC/RST configurables (sin tocar código)

`config.yaml` → sección `pantalla`:

```yaml
pantalla:
  fps: 25
  spi_bus: 0                 # → /dev/spidev0.0
  velocidad_hz: 24000000     # 8000000 si el panel no responde
  dc_gpio: "GPIO1_B0"        # pin físico 22
  rst_gpio: "GPIO4_B3"       # pin físico 13
  # solo si la autodetección falla:
  # dc_chip: "/dev/gpiochip1" ; dc_line: 8
  # rst_chip: "/dev/gpiochip4" ; rst_line: 11
```

Si mueves un cable, cambia solo el **nombre del GPIO** (p. ej.
`rst_gpio: "GPIO4_B2"` para el pin 11). `dc_chip`/`rst_chip` en `"auto"`
(por defecto) resuelven el `/dev/gpiochipN` por el label del banco.

### Audio: qué dispositivo es cuál (medido el 2026-10-12)

| Card | Nombre | Uso |
|---|---|---|
| 0 | `rockchip-hdmi0` | HDMI (sin montaje, no se usa) |
| 1 | `rockchip,dp0` | DisplayPort |
| 2 | `rockchip,es8388` | Jack de la placa: abre bien, pero capta 10x menos que el USB |
| 3 | **`USB PnP Audio Device`** | **Micro y altavoz de Parker** |

`/etc/asound.conf` apunta al card 3, así que Parker no necesita configurar
dispositivo: `sd.rec(device=None)` ya va al USB. Comprobaciones útiles:

```bash
arecord -l                 # tarjetas de captura
arecord -D hw:3,0 -f S16_LE -r 16000 -c 2 -d 5 /tmp/m.wav   # -c 1 FALLA en hw:
# la captura mono solo funciona por el dispositivo por defecto (PortAudio sí
# lo abre con channels=1, como hace parker.py)
```

## 8. Checklist de validación en la placa

Marcar a medida que se pruebe. Los tres números de latencia se imprimen solos
(`[Latencia] STT`, `Primer token`, `Fin de frase`) — ver
[rendimiento.md](rendimiento.md) §1.

- [x] Imagen instalada, SSH, permisos SPI/GPIO (udev §1.4 — la imagen no tiene grupos `spi`/`gpio`)
- [x] `/dev/spidev0.0` visible tras activar SPI
- [ ] `apt` — paquetes del sistema (§2) (`libgpiod-tools` no existe en jammy: usar `gpiod`)
- [x] `venv` + `pip install -r requirements.txt` + `spidev`/`gpiod` (§3)
- [x] Tests offscreen en la placa: pipeline, personalidad, rendimiento, cara, render (§6) — 5/5 OK
- [x] Ollama instalado y `qwen2.5:3b` descargado (§4.1)
- [x] Piper `es_ES-davefx-medium` en `assets/voz/` (§4.2)
- [x] Embeddings + faster-whisper precargados (§4.3, §4.4)
- [x] Archivos del PC pasados con scp/rsync (§5)
- [x] Arranque completo: cara + display SPI + audio + escucha (§7)
- [x] **Pantalla SPI pintando la cara** (init completa con gamma + `0x21`, §7)
- [x] Diálogo completo: STT → cerebro → TTS con latencias anotadas
- [ ] Autonomía: saludo proactivo tras 45 min de silencio
- [ ] Cierre limpio con ESC (sin colgares de Qt)

## 9. Registro de progreso

Actualizar con cada sesión de pruebas en la placa.

| Fecha | Paso realizado | Resultado / notas |
|---|---|---|
| 2026-10-04 | Copia inicial por USB a `~/parker` (§5.5) | Hecha; faltaron `config.yaml` y `requirements.txt`, y aún no hay venv (§3) |
| 2026-10-04 | Arreglo `requirements.txt`: **faltaba `PySide6`** | Sin él, `pip install -r requirements.txt` no instala Qt y el arranque falla |
| 2026-10-04 | venv `~/env` + `pip install -r requirements.txt` + `spidev`/`gpiod` (§3) | OK — `spidev 3.8`, `gpiod 2.5.0` (ruedas aarch64) |
| 2026-10-04 | Tests offscreen en la placa (§6) | **3/3 OK** (pipeline, cara, render). Aviso onnxruntime GPU inofensivo |
| 2026-10-04 | Display SPI en el test | `Permission denied` al abrir `/dev/spidev0.0` — faltan grupos `spi`/`gpio` o `sudo` (§1.4, §7) |
| 2026-10-04 | Primer `python parker.py` en la placa | Memoria OK (embeddings descargados de HF), faster-whisper cargando. **Fallo Qt**: sin escritorio X + falta `libxcb-cursor0`; SPI sigue con `Permission denied` |
| 2026-10-04 | `libxcb-cursor0` | **Ya estaba instalado** → el fallo Qt restante es solo `DISPLAY`/escritorio |
| 2026-10-04 | `usermod -aG spi,gpio` | **Falla**: la imagen no tiene esos grupos → regla udev en §1.4 |
| 2026-10-12 | Regla udev (§0.2) | **OK**: los tres nodos `crw-rw-rw-`; `[Display] Pantalla SPI GC9A01 vinculada correctamente` |
| 2026-10-12 | Ollama (§0.5) | **OK**: servicio activo, `qwen2.5:3b` bajado (1,9 GB), API `0.40.3` |
| 2026-10-12 | `apt` §0.1 | **Abortado entero**: `libgpiod-tools` no existe en jammy → usar `gpiod` y reejecutar |
| 2026-10-12 | Primer arranque completo | Saludo hablado OK, TTS OK, STT OK (`[Latencia] STT: 5,48s`), memoria OK. **Sin escritorio X** (imagen server): Qt cae a offscreen |
| 2026-10-12 | Pantalla | Usuario reporta **pantalla en blanco** — ¿cuál? HDMI (esperado sin X) o SPI (probar test rojo §7) |
| 2026-10-12 | `apt upgrade` + lista `gpiod` | OK (18 paquetes; `dnsmasq` no arranca por puerto 53 — irrelevante para Parker) |
| 2026-10-12 | **Diálogo completo por SSH** (offscreen) | STT 6,4 s · primer token 2,75 s · fin de frase 5,26 s · TTS OK · recuerdo guardado |
| 2026-10-12 | Montaje definitivo confirmado | **Sin HDMI**: solo SSH + pantalla circular → `offscreen` es el modo permanente |
| 2026-10-12 | Pantalla SPI | Sigue **blanca** con datos fluyendo (25 fps) → no interpreta lo que llega: cableado DC/RST/CS o init. Pendiente pinout + test a dos velocidades |
| 2026-10-12 | Foto del cableado + manual oficial | Pantalla = **Waveshare 1.28inch LCD Module**; pinout SPI0 = pines 19/23/24 (§7). Falta ubicar DC/RST con `gpio readall` |
| 2026-10-12 | Cableado contrastado con el manual oficial | Tabla definitiva en §7: VCC 1/17 · GND 6 · DIN 19 · CLK 23 · CS 24 · DC 22 (`GPIO1_B0`) · RST 13 (`GPIO4_B3`) · BL 17 |
| 2026-10-12 | Driver `display_spidev.py` | Pines por **nombre de GPIO** en `config.yaml` + autodetección del `gpiochip` por label (`gpio1`/`gpio4`) + `pintar_color()` |
| 2026-10-12 | Autotest nuevo | `python modulos/display_spidev.py`: imprime chips/spidev/pines resueltos y pinta rojo (24 MHz) → verde (1 MHz). Salida en ASCII puro (locale `C` no rompe) |
| 2026-10-12 | Autotest en la placa (§7) | Overlay `spi0-m2-cs0-spidev` **OK** y `/dev/spidev0.0` presente. **Bug del driver**: leer el label desde `/sys/class/gpio/gpiochipN` falla en este kernel (symlinks, nombre con base global `gpiochip32`, sin atributo `dev`) → `FileNotFoundError` al pedir DC. Corregido: label vía **libgpiod** |
| 2026-10-12 | Mapeo de bancos **verificado en la placa** | `gpiodetect`: `/dev/gpiochip0…4` = `gpio0…gpio4`, `/dev/gpiochip5` = `rk806-gpio` → **DC (`gpiochip1`:8) y RST (`gpiochip4`:11) siempre estuvieron en los bancos correctos**; descartado el chip equivocado |
| 2026-10-12 | **Mapeo físico verificado** (`gpio readall` sin `sudo` + forzado DC=1/RST=0) | pin 13 = global **139** = `GPIO4_B3` (OUT, 0) y pin 22 = global **40** = `GPIO1_B0` (OUT, 1); 19/21/23/24 en `ALT8` = `SPI0_TXD/RXD/CLK/CS0`. `spidev_test -D /dev/spidev0.0` sin `sudo` saca datos y `RX=FF…` (MISO al aire, esperado sin puente 19↔21) → **lado del SoC correcto**; el fallo queda entre el header y el módulo (cable, conector o módulo) |
| 2026-10-12 | Trampa de `scp` | `scp ... user@IP:~/parker/modulos/../` copia todo en `~/parker/` y deja `modulos/` sin actualizar (§5.4) |
| 2026-10-12 | Barrido de hipótesis en el driver (§7 paso 3b) | `--barrido`: 7 combinaciones (24 MHz / 1 MHz / 100 kHz, modo 0 y 3, DC-RST cruzados, RST invertido, init mínima) con un color distinto cada una. **Ejecutado en la placa 7/7 sin error** (reserva de GPIO y SPI OK en las siete) |
| 2026-10-12 | Prueba de humo del camino real de Parker | `GC9A01Display` + `attach_scene` en la placa: `DC gpiochip1:8`, `RST gpiochip4:11`, SPI 24 MHz modo 0, **54 fotogramas en 3,16 s = 17,1 fps** y cierre limpio (los 25 fps del timer no se alcanzan: cada fotograma son 115 KB por SPI) |
| 2026-10-12 | **FALLO: la placa tenía el driver viejo** | `md5sum` en la placa ≠ PC (556 vs 594 líneas): nunca llegó a ejecutarse la secuencia con gamma. Se despliega y se verifica **md5 `7a7ffc73…` idéntico** en ambos lados. Comprobar md5 **en la placa** (con comillas simples) antes de sacar conclusiones de una prueba visual |
| 2026-10-12 | `--parpadeo` y `--colores` en el panel real | Parpadeo blanco↔negro 1 Hz y cada color contra negro: el usuario **ve la cara de Parker y los 7 colores parpadeando**. Descartados cableado, pinout y MADCTL; el problema era la init |
| 2026-10-12 | **✅ CAUSA RAÍZ RESUELTA** | La secuencia de init estaba **incompleta**: faltaban `0x8A`/`0x8B`/`0xB6=00 20`, las **tablas de gamma**, la **inversión `0x21` (INVON)** y el MADCTL oficial `0x98`. Con la secuencia oficial del módulo + init a 1 MHz el panel queda **operativo**. Detalle en §7 |
| 2026-10-12 | Verificación del camino real con la init nueva | `GC9A01Display` + `FaceController` en la placa: **82 fotogramas en 5,00 s = 16,4 fps**, fotogramas de **115200 bytes** exactos, **1602 píxeles encendidos** con caja **centrada en (120,120)** (x 78-161, y 84-156) y reparto 1466 arriba (ojos) / 136 abajo (boca) → el panel recibe la cara, no basura |
| 2026-10-12 | Batería tras el cambio | `test_pipeline`, `test_cara`, `test_render`: **3/3 exit=0** con el driver nuevo |
| 2026-10-12 | Herramienta nueva `--loopback` (§7 paso 3d) | Escritura/lectura por SPI con **puente 19↔21**: compara patrón enviado y recibido en 16 B, 4096 B, 32768 B y 115200 B a 1/8/24/32/48 MHz. Descubierto de paso que `spidev.xfer2` **no acepta más de 4096 B** por llamada: los bloques grandes van troceados, como en el driver |
| 2026-10-12 | **El puente 19↔21 no está cerrado** | El usuario lo puso; el eco sale `0xFF` en las cuatro tallas y, en una ejecución posterior, `0x00` en las cuatro: **nunca sigue a MOSI** (con `0xFF` enviado y eco `0x00` queda descartado el puente). Pendiente saber si el cable fue a un GND o al pin de al lado |
| 2026-10-12 | Trampa descartada: leer pines muxados como GPIO | Con `/dev/spidev0.0` abierto, leer el pin 19 como GPIO da `ACTIVE` incluso después de enviar `0x00` por él → el mux desconecta la entrada del GPIO. **No vale** como método de diagnóstico; solo el eco del controlador |
| 2026-10-12 | **Pantalla negra al mover el cable equivocado** | El cable del **DIN del módulo** se movió del pin **19** al **21** para hacer el loopback → **pantalla negra** (el 21 es la **entrada** MISO del SoC, no puede llevar datos al módulo) y eco constante en vez de seguir a MOSI. Corregido devolviendo el DIN al 19; el puente era un **cable aparte**, no mover el del módulo |
| 2026-10-12 | Cable devuelto al 19 y prueba de pantalla | **Vuelve a pintar**: parpadeo blanco/negro y los 7 colores contra negro confirmados por el usuario. Sin tocar ningún otro cable |
| 2026-10-12 | Batería con el driver que incluye `--loopback` | `test_pipeline`, `test_cara`, `test_render`: **3/3 exit=0** |
| — | (pendiente) | Medir el bus con `--loopback`, que necesita un **cable de repuesto** entre 19 y 21 (el del módulo se queda en el 19). Con el resultado se decide si subir `velocidad_hz` a 32/48 MHz para acercarse a los 25 fps |
| 2026-10-12 | **Audio verificado** (§7, «Audio: qué dispositivo es cuál») | `card 3 = USB PnP Audio Device` es el dispositivo por defecto (`/etc/asound.conf`) y el que usa Parker: micro (`input channels=1` OK, voz rms 0,046 frente a 0,0011 de la sala) y altavoz (Piper 0,77 s de síntesis, 3,9 s de audio reproducido). La ES8388 de la placa también abre, pero capta 10x menos |
| 2026-10-12 | **Parker completo end-to-end** | Log real: memoria (5 documentos), faster-whisper, Ollama, Piper, saludo hablado en tres frases, bucle de escucha, transcripción del usuario, respuesta del cerebro y recuerdo guardado. Confirmado por el usuario: voz clara y cara animándose en la pantalla |
| 2026-10-12 | **Umbral de voz adaptativo** (§7, «Audio: qué dispositivo es cuál») | El umbral fijo de 0,02 hacía que Parker contestara a conversaciones ajenas. Ahora mide el ruido de fondo, exige 2 fragmentos seguidos (~130 ms) y 0,4 s de voz sostenida (`factor_ruido`, `duracion_minima_seg`, `chunks_voz_minimos`) |
| 2026-10-12 | **Personalidad propia** (`modulos/personalidad.py`) | Ficha de personaje original (gustos, sueños, manías, miedos, muletillas) + ánimo persistente (`parker.estado.json`) + iniciativa variada. Verificado con Qwen real: responde como amigo y cuenta cosas suyas |
| 2026-10-12 | **Lección de latencia del prompt** | El ánimo dentro del mensaje `system` hacía que Ollama reprocesara historial y recuerdos en cada frase: **33-40 s** por respuesta. Con el bloque de identidad estable en `system` (~246 tokens) y lo volátil en el mensaje del usuario: **2,3-5,7 s** al primer token |
| 2026-10-12 | **12 principios de animación** en la cara | Diccionario `PRINCIPIOS` con los 12 mapeados a código + muelle de inercia (follow-through), exageración parametrizable, guiño, bostezo, doble toma e intro nueva de ~4,5 s |
| 2026-10-12 | Batería final | `test_pipeline`, `test_personalidad`, `test_animacion`, `test_cara`, `test_render`: **5/5 exit=0** (22 comprobaciones `[OK]` + `RENDER_OK`) |
| — | (resuelto 2026-10-17) | ~~Latencia de voz: el primer token variaba entre 2 y 14 s según los recuerdos y el historial~~ → modelo `1.5b`, primera tanda con prompt más corto, STT `base` y silencio de 0,6 s. Medido en esa 1ª tanda: **6,5-6,8 s hasta que empieza a sonar** (antes 15-20 s); medidas posteriores en condiciones distintas dieron 4,2-4,7 s percibidos, no una garantía por turno. Ver [rendimiento.md](rendimiento.md) |
| 2026-10-17 | **Optimización de latencia (1ª tanda)** | STT `small`→`base` (4,8-5,3 s → 1,6-1,8 s), LLM `3b`→`1.5b`, prompt recortado, `hotwords: Parker` (arregla "parquear"), precalentado del modelo al arrancar y corte de silencio 1,3→0,6 s. Medido: **6,5-6,8 s hasta que empieza a sonar** |
| 2026-10-17 | **Caché de prefijo y precalentamiento seguro** | El historial guarda el mensaje exacto enviado; no se precalienta cada turno porque compite con Whisper (un ensayo llegó a 24 s de TTFB). La carga del modelo ocurre antes de abrir el micrófono. Medidas previas con módulos reales dieron 0,9-1,9 s de primer token y 4,2-4,7 s percibidos; no se atribuyen al modo concurrente ni se garantizan en cada turno. |
| 2026-10-12 | Batería offscreen en la placa con el driver nuevo | `test_pipeline`, `test_cara`, `test_render`: **3/3 exit=0** |
| 2026-10-17 | **Arranque automático real (enchufar y listo)** | La línea de cron `@reboot` apuntaba a `sudo ~/env/bin/python3 parker.py` y **fallaba siempre** (`sudo: a password is required`). Sustituida por `tools/arrancar.sh`: espera a Ollama, usa lock (una sola instancia), rota el log a 2 MB y reinicia a Parker si muere con código distinto de 0. **Verificado reiniciando la placa**: cron lo lanzó solo, Parker arrancó en modo `offscreen` y quedó escuchando (intro hablada). La unidad systemd (`tools/parker.service`, corregida con `QT_QPA_PLATFORM=offscreen`) queda como alternativa: instalarla necesita contraseña de administrador |
| 2026-10-17 | **Identidad, vínculo y voz** | Tres fallos vistos en vivo: (1) a "¿cómo me llamo yo Parker?" respondía *"Creíamos que nos conocíamos desde siempre... Eres realmente Parker"* → bloque «QUIÉN ES QUIÉN», aprendizaje del nombre que le digan, atajo sin LLM para las preguntas de nombre y corrección determinista del vocativo antes de sintetizar; (2) decía conoceros el primer día → **vínculo** 0-100 % (días + charlas) en el prompt, que arranca en 0 % y va por tramos; (3) la voz sonaba **más grave y a grito** → la velocidad se aplicaba remuestreando la señal (el tono caía de 119 a 110 Hz, medido) y el volumen multiplicaba una señal ya normalizada: ahora usa `length_scale` de Piper (mismo tono a 0,85× de ritmo) y volumen 0,55. Test nuevo `tests/test_voz.py` (duración, tono y pico) y `test_personalidad` ampliado. Batería en la placa: **6/6 exit=0** |
| 2026-10-17 | **Sin saludos de plantilla + diagnóstico térmico** | Se quita el saludo grabado al iniciar; el filtro de voz suprime "encantado de verte" y preguntas genéricas repetidas, conservando la reacción concreta. Se registran las zonas `thermal_zone*`, `type`, temperaturas y trips reales del kernel cada minuto; el aviso configurado a 70 °C es preventivo, no límite de seguridad. 60 °C aislados no prueban sobretemperatura ni throttling. Ollama CPU queda como baseline; se recomienda evaluar RKLLM en entorno separado antes de migrar (benchmark no comparable). |
| 2026-10-17 | **Runtime investigado** | En Orange Pi 5 Pro, RKLLM oficial es candidato real para probar la NPU del RK3588, con conversión y dependencias específicas de kernel/driver. Mantener Ollama activo por ahora: Qwen2.5-1.5B medido localmente a 17-19 tok/s; RKLLM publica 15,44 tok/s pero no es el mismo benchmark ni demuestra menor TTFT. Detalle y fuentes: [rendimiento.md](rendimiento.md) §4-5. |
| 2026-10-17 | **Validación in situ tras este ajuste** | Despliegue selectivo de `parker.py`, `config.yaml`, `modulos/cerebro.py` y `modulos/personalidad.py`, con respaldo remoto en `~/parker-backup-2026-10-17_180632/`. Hashes verificados y bytecode/config válidos. Parker vuelve a correr desde `arrancar.sh`, sin saludo de inicio; Ollama sigue con Qwen2.5-1.5B. Log: modelo calentado en 0,1 s, filtro activo en ruta de voz y siete zonas térmicas registradas. Lectura ~37 °C en reposo; trips reales soc-thermal passive 75/85 °C, critical 115 °C. No se altera la memoria ni se instala RKLLM. |
| 2026-10-17 | **Memoria e2e borrada** | La `parker.db` solo tenía recuerdos de pruebas (13 al empezar, incluidos los del usuario). Copiada a `backups/2026-10-17_1515_parker-db/` y recreada vacía. Para gestionarla: `python tools/recuerdos.py [--borrar]` |
| — | (pendiente) | Observar el barrido (¿ROJO/VERDE/AZUL/AMARILLO/CIAN/MAGENTA/NARANJA?) y comprobar que **VCC está en 3,3 V** (pines 1 o 17) y **no** en 5 V (pines 2 o 4): un VCC a 5 V deja el panel blanco, iluminado y sin responder a nada |
| 2026-10-26 | **Día completo, apuntes, tiempo, música y aprendizaje (v6.4.0)** | Desplegado y verificado en la placa: rutinas (dormir/despertar/cállate/apágate con despedida animada), apuntes y contadores por voz, el tiempo real con la ciudad variable, música por API (Deezer + `ffmpeg`, 10,6× el fondo medido con el micro) y el bandit de iniciativa. Guía: [dia.md](dia.md). Log del arranque en la placa: `[Parker] v6.4.0-dia-musica-bandit … código f5a33c9f`, las cuatro secciones nuevas y el bucle de escucha activo. Por voz (frase dicha por su propio altavoz): tiempo («quince grados»), apuntes («un litro de agua» → 2,5 L, sin crear alarma) y fecha («martes, 27 de octubre de 2026»). `pkcheck power-off` → autorizado; `Parker._apagar()` completo en modo seco. Batería: **25/25** en la placa (los mismos ficheros que en el PC) |
| 2026-10-26 | **Dos fallos que encontró la prueba por voz** | (1) «apunta un litro de agua a las 2 de la tarde» creaba una **alarma** en vez de un contador → ahora un contador (cantidad + unidad) manda sobre la agenda. (2) Las muletillas del STT acababan dentro del titular («porque apunta un litro de agua») y «apágate» llegó como «apajate» y no apagó nada → limpieza de muletillas, variantes de apagado y arreglo del apóstrofo («d'agua» → «de agua»). Los tres con test |
| 2026-10-27 | **La cara con vida propia (v6.8.0) y las dos instancias** | Director de gestos en reposo (tres familias según el silencio, cinco gestos nuevos), parpadeo que se espacia con el silencio, charla propia a los 15 min (antes 45) y la cara en `pensando` antes de hablar. En el log de la placa: `[Cara] Gestos en reposo: familia despierto (silencio 39s)` → `familia solo (silencio 99s)`, y tras hablarle `familia despierto (silencio 17s)`. Prueba por voz: micro USB elegido por nombre, `Ponte en local.` → `[Cerebro] Modo auto -> local (por voz)` en 8,25 s. **Aprendido**: matar `parker.py` a mano no deja la placa sin Parker — `tools/arrancar.sh` (cron `@reboot`) lo relanza en 5 s y, si además se levanta una instancia a mano, quedan **dos Parker peleándose por el micrófono y la pantalla SPI** (`Device or resource busy` en el DC y `[Error Stream Audio] Device unavailable` en bucle). No arrancar Parker a mano: matar el proceso y dejar que el lanzador lo levante |
| 2026-10-27 | **Música con orejas (v6.5.0)** | Reportado: con música no se podía cambiar el volumen y Parker dejaba de escuchar (también después). Eran dos cosas: un turno nacido de la propia canción se ignoraba **sin soltar `ocupado`** (sordo para siempre) y, mientras suena, las órdenes de volumen las cogía la voz. Ahora el turno se suelta siempre, las órdenes de música van primero («baja el volumen» con música es la música) y el modo música usa el truco del «duck» (`OyenteMusica`): se baja la música un momento y se mira si el nivel cae con ella (era la canción) o sigue alto (eres tú). **Medido en la placa con «Bohemian Rhapsody» a volumen 0,7** (`tools/probar_musica_escucha.py`, con Parker parado): canción 0,0115 de RMS en su propio micrófono, picos de 0,038; **2 comprobaciones en 24 s**, las dos «era la canción», **0 turnos abiertos** (antes de afinar el disparo: 6). Huella `5a6a82c4` idéntica en PC y placa, batería **22/22** en los dos. Para el otro lado de la prueba (que te oiga por encima) queda `--hablar 10`, que necesita una persona delante |

| 2026-10-30 | **El oído llega tarde (v6.8.1)** | Reportado: recién encendida, la cara sale pero no reacciona. El log lo delataba: `ningún micrófono contiene «usb»` y `Entrada de audio muerta (0.00009)`; `arecord -l` sí veía el USB (tarjeta 3). El USB apareció a los ~29 s del arranque (`dmesg`), después de que PortAudio cacheara su lista; el rearme no servía porque `query_devices()` seguía con la lista vieja. Ahora el primer intento espera hasta 25 s (`esperar_micro_seg`) y refresca PortAudio (`_terminate`/`_initialize`); al quedar listo suena un chime de dos notas (`micro_listo`), porque la cara aparece antes que el oído. Verificado en vivo: v6.8.1, huella `8473cad9` idéntica en PC y placa, micro `[3] USB PnP`, chime y `prueba_redonda.py` → «Hola, Parker, ¿me oyes?» → «Oye, Alan, te escucho sin problema» (turno 8,70 s, con la Piper de la prueba compitiendo por la CPU). Test nuevo `tests/test_microfono.py` 2/2; el arranque en frío real queda por confirmar con un ciclo de corriente |
| 2026-11-01 | **La cara se congela (v6.10.3)** | Reportado: hablando con Parker la cara se quedó congelada; al pasar al cerebro local volvió y luego se congeló otra vez. El SPI no tenía errores (`errors=0`, `timedout=0`) y el log mostró que «Parker, cambio el cerebro en local» **no se ejecutó**: el patrón solo aceptaba «cambia al cerebro local» y siguió en la nube (el modelo se inventó el cambio). La causa documentada que mejor encaja es la de siempre: dos instancias peleándose por el SPI y el micro, porque `arrancar.sh` tenía *lock* pero un `python parker.py` a mano no (no se pudo confirmar en el momento). Ahora Parker toma `~/.parker.runtime.lock`; la segunda instancia sale con aviso y sin tocar hardware. Además, un vigilante reinicia el GC9A01 si el panel lleva >8 s sin recibir fotogramas y un latido anota bloqueos del hilo gráfico. Verificado en la placa: v6.10.3, huella `079c39f8`, una sola instancia, segundo Parker rechazado, **15,4 fps en reposo y 14–15 fps durante un turno local** (TTFT 5,44 s), y cambio por voz local → automático. El congelado original no se reprodujo en la prueba |

## 10. Apagado ordenado por voz (v6.4.0, 26/10/2026)

«Parker, apágate» hace la ceremonia completa: se despide por el altavoz, la cara
se marcha con su animación lateral, la agenda/apuntes/ánimo ya están guardados al
vuelo y pide el apagado del sistema (`rutinas.orden_apagado`, por defecto
`systemctl poweroff`). Después **solo hay que desenchufar**: la placa se apagó
limpia (systemd sincroniza la tarjeta), así que no hay riesgo de corromper los
recuerdos; el LED rojo puede quedarse encendido porque es la fuente, no el SoC.

Comprobar el permiso **sin apagar nada**:

```bash
pkcheck --action-id org.freedesktop.login1.power-off --process $$   # exit 0 = autorizado
PARKER_APAGADO_SECO=1 ~/env/bin/python3 ~/parker/tools/probar_dia.py --apagado
```

Si algún día polkit dejara de autorizarlo (Parker lo diría por voz y seguiría
funcionando), hay dos salidas limpias, ambas con la contraseña del dueño y **una
sola vez**:

```bash
# a) permiso solo para apagar, a tu usuario (recomendado)
echo "orangepi ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff" | \
  <tu-orden-de-administrador> tee /etc/sudoers.d/parker-apagado
# y en config.yaml: rutinas.orden_apagado: "<tu-orden-de-administrador> -n systemctl poweroff"
# b) o arrancar Parker como administrador desde el cron de root (lo que hacía
#    INS.txt), pero entonces el log y los ficheros de estado pasan a ser de root:
#    no mezclar.
```
