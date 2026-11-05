#!/bin/bash
# tools/bakeoff.sh — Bake-off de cerebros con ENFRIAMIENTO entre bloques.
#
# Medido 24/10: los big cores de la RK3588 suben a 84 °C con inferencia
# sostenida y el prefill cae de ~150-200 t/s (frío) a 63-75 t/s (caliente).
# Por eso CADA bloque espera a que bigcore0 baje de 58 °C: así todos los
# modelos se miden en las mismas condiciones térmicas.
#
# Uso:  nohup ~/parker/tools/bakeoff.sh > /dev/null 2>&1 &
# Log:  ~/bakeoff.log        (al final: "BAKE-OFF TERMINADO")

cd "$(dirname "$0")/.." || exit 1
PY="$HOME/env/bin/python3"
SALIDA="$HOME/bakeoff.log"

esperar_frio() {
    local i t
    for i in $(seq 1 60); do        # hasta 10 min
        t=$(cat /sys/class/thermal/thermal_zone1/temp 2>/dev/null || echo 0)
        [ "$t" -lt 58000 ] && return 0
        sleep 10
    done
    return 0
}

temp_big() { cat /sys/class/thermal/thermal_zone1/temp 2>/dev/null; }

{
    echo "########## BAKE-OFF INICIO $(date +%H:%M:%S) temp_big=$(temp_big)"

    # 1) Referencia: el 3b actual (también valida la calidad de partida)
    esperar_frio
    echo "########## qwen2.5:3b latencia $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo qwen2.5:3b --solo-latencia --turnos 6
    esperar_frio
    echo "########## qwen2.5:3b contextos $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo qwen2.5:3b --solo-contextos

    # 2) Draft especulativo: mismos pesos, decode con verificación del 1.5b.
    #    Solo latencia: la calidad es la del 3b (mismos pesos).
    esperar_frio
    echo "########## qwen25-3b-spec latencia $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo qwen25-3b-spec --solo-latencia --turnos 6

    # 3) llama3.2:3b (control con español)
    esperar_frio
    echo "########## llama3.2:3b latencia $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo llama3.2:3b --solo-latencia --turnos 6
    esperar_frio
    echo "########## llama3.2:3b contextos $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo llama3.2:3b --solo-contextos

    # 4) gemma3n:e2b cuando termine su descarga (espera hasta 15 min)
    for i in $(seq 1 90); do
        ollama list 2>/dev/null | grep -q "gemma3n" && break
        grep -q "success" /home/orangepi/pull-e2b.log 2>/dev/null && break
        sleep 10
    done
    if ollama list 2>/dev/null | grep -q "gemma3n"; then
        esperar_frio
        echo "########## gemma3n:e2b latencia $(date +%H:%M:%S) temp=$(temp_big)"
        $PY tools/eval_cerebro.py --modelo gemma3n:e2b --solo-latencia --turnos 6
        esperar_frio
        echo "########## gemma3n:e2b contextos $(date +%H:%M:%S) temp=$(temp_big)"
        $PY tools/eval_cerebro.py --modelo gemma3n:e2b --solo-contextos
    else
        echo "########## gemma3n:e2b NO DESCARGADO, se omite"
    fi

    echo "########## BAKE-OFF TERMINADO $(date +%H:%M:%S)"
} >> "$SALIDA" 2>&1
