# Arrancar Parker

Guía práctica para la Orange Pi 5 Pro: encender, comprobar que está vivo y
dejarlo listo para que arranque solo. Los conceptos (STT, TTFB, NPU…) están en
[conceptos.md](conceptos.md); los números de latencia, en
[rendimiento.md](rendimiento.md).

---

## 1. Qué hace falta

| Pieza | Detalle |
|---|---|
| Placa | Orange Pi 5 Pro (RK3588), Debian/Armbian con el usuario `orangepi` |
| Alimentación | 5 V / 3 A por USB-C (si falta corriente, la pantalla parpadea o el audio cruje) |
| Pantalla | GC9A01 240×240 por SPI (pines en [placa.md](placa.md) §7) |
| Voz | Altavoz por la salida de audio y micrófono USB (el de la cámara también vale) |
| Red | WiFi o cable; solo hace falta para SSH y para descargar modelos la primera vez |

En la placa todo vive en dos sitios:

```
/home/orangepi/parker   → el proyecto (este repositorio)
/home/orangepi/env      → el entorno Python (venv) con las dependencias
```

## 2. Encender: lo que pasa solo

1. Arranca Linux y el servicio **`ollama`** (queda cargado en segundo plano).
2. **cron** ejecuta `@reboot` → `tools/arrancar.sh` (ver §5).
3. El script espera a que Ollama responda (hasta 60 s), comprueba que no haya
   otra instancia y lanza `parker.py` en modo `offscreen`.
4. Parker hace su intro de ~4,5 s en la pantalla redonda, dice unas frases de
   bienvenida y se queda escuchando. El modelo se precalienta en segundo plano:
   la primera pregunta no paga la carga.

No hace falta HDMI ni escritorio: la cara se dibuja en la pantalla SPI.

## 3. Comprobar que está vivo

```bash
ssh orangepi@192.168.1.130
pgrep -af parker.py          # debe aparecer .../env/bin/python3 .../parker.py
tail -n 30 ~/parker.log      # log de arranque y de cada turno
```

En el log, un arranque sano se ve así:

```
[arranque] 2026-10-17 15:20:01 inicio desde /home/orangepi/parker
[Display] Pantalla SPI GC9A01 vinculada correctamente.
[Escucha] faster-whisper cargado correctamente
[Cerebro] Conectado a Ollama Local (qwen2.5:3b en http://localhost:11434)
[Voz] Modelo cargado. Sample rate: 22050Hz
[Escucha] Bucle continuo activo. Esperando voz humana...
[Cerebro] Modelo precalentado en 0.2s (la primera respuesta ya no lo paga)
```

Y al hablarle, tres líneas por turno:

```
[Latencia] STT: 1.79s
[Latencia] Primer token del cerebro: 1.04s
[Latencia] Fin de frase lista para hablar: 1.38s
```

## 4. Arrancar, parar y reiniciar a mano

```bash
# arrancar (en segundo plano, con log)
~/parker/tools/arrancar.sh >> ~/parker.log 2>&1 &

# ver el proceso real y su padre (arrancar.sh)
ps -o pid,ppid,cmd -C python3 | grep parker.py

# parar SOLO ese PID (sustituye 12345 por el que hayas visto).
# No uses pkill -f: el patrón puede coincidir con otras órdenes y matar
# procesos que no son Parker. arrancar.sh lo relanza en 5 s.
kill 12345
```

Si trabajas por SSH y quieres ver los prints en directo, mejor en primer plano:

```bash
cd ~/parker && QT_QPA_PLATFORM=offscreen ~/env/bin/python3 parker.py
```

## 5. Arranque automático

### 5.1 Lo que hay ahora: cron (sin sudo)

El usuario `orangepi` tiene esta línea en `crontab -l`:

```cron
@reboot /home/orangepi/parker/tools/arrancar.sh >> /home/orangepi/parker.log 2>&1
```

Ventaja: no necesita contraseña de administrador. Es lo que hace que Parker
arranque al enchufar la placa. **Verificado el 17/10/2026**: tras reiniciar la
placa, cron lanzó el script y Parker quedó hablando en ~40 s (13 s de ellos
cargando modelos).

Comprobar / reinstalar:

```bash
crontab -l
( crontab -l | grep -v arrancar.sh; \
  echo '@reboot /home/orangepi/parker/tools/arrancar.sh >> /home/orangepi/parker.log 2>&1' ) | crontab -
```

### 5.2 Alternativa: systemd (necesita sudo)

Más robusto (reinicia si el proceso muere, arranca después de Ollama). El
fichero está en el repositorio: `tools/parker.service`.

```bash
sudo cp ~/parker/tools/parker.service /etc/systemd/system/parker.service
sudo systemctl daemon-reload
sudo systemctl enable --now parker.service
systemctl status parker.service
journalctl -u parker.service -f
```

Si usas systemd, **quita la línea de cron** para no tener dos arranques:

```bash
crontab -l | grep -v arrancar.sh | crontab -
```

> La unidad antigua que había en la placa apuntaba a `DISPLAY=:0` y no tenía
> `QT_QPA_PLATFORM=offscreen`: en esta instalación sin escritorio fallaba. La
> versión del repositorio ya lo corrige.

## 6. Probar que todo sigue bien

```bash
cd ~/parker
for t in test_pipeline test_personalidad test_rendimiento test_cara test_render; do
    QT_QPA_PLATFORM=offscreen ~/env/bin/python3 tests/$t.py >/tmp/$t.log 2>&1
    echo "$t exit=$?"
done
```

Los cinco deben dar `exit=0`. `test_rendimiento` además vigila que no vuelvan
los valores lentos (modelo, STT, tamaño del prompt, caché del prefijo).

Medición de latencia punta a punta con los módulos reales (sin micrófono), y
gestión de la memoria:

```bash
cd ~/parker
QT_QPA_PLATFORM=offscreen ~/env/bin/python3 tools/medir_latencia.py   # 5 turnos
~/env/bin/python3 tools/recuerdos.py            # ver recuerdos guardados
~/env/bin/python3 tools/recuerdos.py --borrar   # vaciar la memoria
```

## 7. Problemas frecuentes

| Síntoma | Qué mirar |
|---|---|
| No arranca al encender | `crontab -l` (línea `@reboot`), `~/parker.log`, permisos de `tools/arrancar.sh` (`chmod +x`) |
| Arranca y muere | `tail ~/parker.log`; casi siempre falta `QT_QPA_PLATFORM=offscreen` o el venv no existe |
| Pantalla en blanco | Alimentación y cableado ([placa.md](placa.md) §7); `~/env/bin/python3 modulos/display_spidev.py --colores` |
| No oye | Micrófono: `arecord -l`; umbral en `config.yaml` → `escucha.umbral_silencio` |
| No habla | `aplay -l`, volumen `alsamixer`, y que `assets/voz/es_ES-davefx-medium.onnx` exista |
| Responde muy lento | Mira el log: si «Primer token» > 3 s, Ollama está frío o el modelo no es el de `config.yaml` |
| «Ollama no responde» | `systemctl status ollama`, `curl localhost:11434/api/tags` |

## 8. Datos y actualización

| Qué | Dónde | Se puede borrar |
|---|---|---|
| Recuerdos (ChromaDB) | `~/parker/parker.db/` | sí: se recrea vacío al arrancar |
| Ánimo persistente | `~/parker/parker.estado.json` | sí: vuelve al estado por defecto |
| Modelos de voz | `~/parker/assets/voz/` | no, hacen falta |
| Modelos de Ollama | `/usr/share/ollama/.ollama/models` | no |
| Log | `~/parker.log` (se añade en cada arranque) | sí |

Para vaciar la memoria sin tocar nada más (dos formas equivalentes):

```bash
rm -rf ~/parker/parker.db            # con Parker parado; se recrea vacío
~/env/bin/python3 tools/recuerdos.py --borrar   # con Parker parado o en marcha
```

La base actual se vació el 17/10/2026; hay copia en
`backups/2026-10-17_1515_parker-db/` dentro del repositorio (en el PC).

Actualizar el código desde el PC de desarrollo (sin tocar datos ni venv):

```bash
scp parker.py config.yaml orangepi@192.168.1.130:~/parker/
scp modulos/*.py orangepi@192.168.1.130:~/parker/modulos/
# Tras copiar: localiza el PID real y mátalo; arrancar.sh lo relanza solo.
ps -o pid,ppid,cmd -C python3 | grep parker.py
kill 12345   # sustituye 12345 por el PID visto arriba
```

## 9. Mapa rápido

| Fichero | Para qué |
|---|---|
| `parker.py` | ventana/escucha/orador, bucle de conversación |
| `modulos/cerebro.py` | prompt, caché del prefijo, llamada a Ollama |
| `modulos/escucha.py` | STT (faster-whisper) |
| `modulos/voz.py` | TTS (Piper) |
| `modulos/memoria.py` | recuerdos (ChromaDB + embeddings) |
| `modulos/personalidad.py` | quién es Parker y su ánimo |
| `modulos/cara_parker.py` | cara animada |
| `modulos/display_spidev.py` | pantalla SPI GC9A01 |
| `tools/arrancar.sh` | arranque sin sudo (cron/systemd) |
| `tools/medir_latencia.py` | mide STT/TTFB/TTS de 5 turnos sin micrófono |
| `tools/recuerdos.py` | ver y borrar los recuerdos guardados |
| `config.yaml` | todos los ajustes |
