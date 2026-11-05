#!/bin/bash
# tools/compara_cerebros.sh — SmolLM3-3B (HF GGUF) vs qwen2.5:3b, con
# ENFRIAMIENTO entre bloques, igual que bakeoff.sh.
#
# Medido 24/10: la RK3588 sube a 84 °C con inferencia sostenida y el prefill
# cae de ~150-200 t/s (frío) a 63-90 t/s (caliente). Si un modelo se mide
# caliente y otro frío, la termal decide el resultado, no el modelo.
#
# Cada bloque espera a que bigcore0 (thermal_zone1) baje de 58 °C.
# Ejecutar CON PARKER PARADO: si corre, compite por CPU y contamina.
#
# Uso:  nohup ~/parker/tools/compara_cerebros.sh > /dev/null 2>&1 &
# Log:  ~/compara_cerebros.log        (al final: "COMPARA TERMINADO")

cd "$(dirname "$0")/.." || exit 1
PY="$HOME/env/bin/python3"
SALIDA="$HOME/compara_cerebros.log"
CANDIDATO="${1:-hf.co/ggml-org/SmolLM3-3B-GGUF:Q4_K_M}"

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
    echo "########## COMPARA INICIO $(date +%H:%M:%S) temp_big=$(temp_big)"
    echo "########## candidato: $CANDIDATO"

    esperar_frio
    echo "########## $CANDIDATO latencia $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo "$CANDIDATO" --solo-latencia --turnos 6

    esperar_frio
    echo "########## $CANDIDATO contextos $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo "$CANDIDATO" --solo-contextos

    esperar_frio
    echo "########## qwen2.5:3b (referencia) latencia $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo qwen2.5:3b --solo-latencia --turnos 6

    esperar_frio
    echo "########## qwen2.5:3b (referencia) contextos $(date +%H:%M:%S) temp=$(temp_big)"
    $PY tools/eval_cerebro.py --modelo qwen2.5:3b --solo-contextos

    echo "########## COMPARA TERMINADO $(date +%H:%M:%S)"
} >> "$SALIDA" 2>&1
