#!/bin/sh
# Arranque de Parker al encender la placa.
#
# Lo lanza cron con @reboot (ver docs/inicio.md). No necesita sudo: corre como
# el usuario orangepi, que ya está en los grupos audio/video/dialout.
#
# Hace cuatro cosas:
#   1. Rota el log si se ha hecho grande.
#   2. Espera a que Ollama responda (su servicio arranca en paralelo).
#   3. Evita dos instancias si ya hay una (lock).
#   4. Arranca parker.py y lo reinicia si se cae (cron no tiene Restart=always).
set -u

DIR=$(cd "$(dirname "$0")/.." && pwd)
PY="$DIR/../env/bin/python3"
LOG="$HOME/parker.log"
TAG="[arranque]"

echo "$TAG $(date '+%Y-%m-%d %H:%M:%S') inicio desde $DIR"

if [ ! -x "$PY" ]; then
    echo "$TAG ERROR: no existe el intérprete $PY"
    exit 1
fi

# 1. Rotación sencilla: si pasa de 2 MB, se guarda una copia y se empieza otro.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 2000000 ]; then
    mv -f "$LOG" "$LOG.1"
    echo "$TAG log rotado a $LOG.1"
fi

# 2. Ollama puede tardar en levantar tras el encendido.
intentos=0
while [ "$intentos" -lt 60 ]; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        break
    fi
    intentos=$((intentos + 1))
    sleep 1
done
if [ "$intentos" -ge 60 ]; then
    echo "$TAG AVISO: Ollama no respondió en 60 s; arranco igualmente."
fi

# 2-bis. Ganancia del micrófono USB al máximo. Venía a 408/496 (25,5 dB de
# 31) y hablando de lejos no llegaba al umbral de voz. Se busca la tarjeta por
# NOMBRE («Device»), no por índice: tras reiniciar, los índices cambian.
if command -v amixer >/dev/null 2>&1; then
    if amixer -c Device cset numid=8 496 >/dev/null 2>&1; then
        echo "$TAG micrófono USB: ganancia de captura al máximo (31 dB)"
    else
        echo "$TAG AVISO: no pude subir la ganancia del micrófono USB; sigo."
    fi
fi

# 3. Una sola instancia.
exec 9>"$HOME/.parker.lock"
if ! flock -n 9; then
    echo "$TAG ya hay una instancia de Parker; salgo."
    exit 0
fi

# 4. Parker en primer plano, con reinicio si muere de forma anormal.
cd "$DIR" || exit 1
while :; do
    env \
        QT_QPA_PLATFORM=offscreen \
        ORT_LOGGING_LEVEL=3 \
        PYTHONUNBUFFERED=1 \
        "$PY" parker.py
    codigo=$?
    if [ "$codigo" -eq 0 ]; then
        echo "$TAG parker.py terminó limpiamente (0); no reinicio."
        break
    fi
    echo "$TAG parker.py terminó con código $codigo; reinicio en 5 s."
    sleep 5
done
