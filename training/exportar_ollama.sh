#!/usr/bin/env bash
# training/exportar_ollama.sh
# ===========================
# Convierte el adaptador LoRA de Parker en un modelo de Ollama.
#
# Requisitos: llama.cpp clonado y compilado, Python con transformers/peft/torch,
# Ollama instalado. No se ejecuta en la Orange Pi.
#
# Uso:
#   bash training/exportar_ollama.sh
#   bash training/exportar_ollama.sh training/salida/parker-lora \
#       training/salida/parker-gguf parker-lora
#
# Variables:
#   BASE_MODEL=Qwen/Qwen2.5-3B-Instruct
#   LLAMA_CPP=$HOME/llama.cpp
#   PYTHON=python
#   DRY_RUN=1  (solo imprime los pasos)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ADAPTER=${1:-$ROOT/training/salida/parker-lora}
SALIDA=${2:-$ROOT/training/salida/parker-gguf}
NOMBRE=${3:-parker-lora}
BASE_MODEL=${BASE_MODEL:-Qwen/Qwen2.5-3B-Instruct}
LLAMA_CPP=${LLAMA_CPP:-$HOME/llama.cpp}
PYTHON=${PYTHON:-python}

CONVERT="$LLAMA_CPP/convert_hf_to_gguf.py"
QUANT=${LLAMA_QUANTIZE:-}
if [ -z "$QUANT" ]; then
    for candidato in "$LLAMA_CPP/build/bin/llama-quantize" "$LLAMA_CPP/llama-quantize"; do
        if [ -x "$candidato" ]; then QUANT="$candidato"; break; fi
    done
fi

echo "[Export] adaptador=$ADAPTER"
echo "[Export] salida=$SALIDA"
echo "[Export] nombre Ollama=$NOMBRE base=$BASE_MODEL"

if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "[Export] dry-run: fusionar -> convertir -> cuantizar q4_k_m -> ollama create"
    [ -n "$QUANT" ] && echo "[Export] cuantizador: $QUANT" || echo "[Export] AVISO: no encuentro llama-quantize"
    [ -f "$CONVERT" ] && echo "[Export] conversor: $CONVERT" || echo "[Export] AVISO: no encuentro convert_hf_to_gguf.py"
    exit 0
fi

if [ ! -d "$ADAPTER" ]; then
    echo "[Export] ERROR: no existe $ADAPTER. Entrena primero."
    exit 1
fi
if [ ! -f "$CONVERT" ]; then
    echo "[Export] ERROR: falta $CONVERT"
    echo "[Export] Clona y compila llama.cpp:"
    echo "  git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp"
    echo "  cmake -S ~/llama.cpp -B ~/llama.cpp/build -DGGML_CUDA=OFF"
    echo "  cmake --build ~/llama.cpp/build --config Release -j"
    exit 1
fi
if [ -z "$QUANT" ]; then
    echo "[Export] ERROR: no encuentro llama-quantize en $LLAMA_CPP/build/bin"
    exit 1
fi
if ! command -v ollama >/dev/null 2>&1; then
    echo "[Export] ERROR: ollama no está en PATH"
    exit 1
fi

mkdir -p "$SALIDA"
echo "[Export] 1/4 fusionando adaptador..."
"$PYTHON" "$ROOT/training/fusionar_lora.py" \
    --base "$BASE_MODEL" --adapter "$ADAPTER" --salida "$SALIDA/merged"

echo "[Export] 2/4 convirtiendo a GGUF f16..."
"$PYTHON" "$CONVERT" "$SALIDA/merged" \
    --outfile "$SALIDA/parker-f16.gguf" --outtype f16

echo "[Export] 3/4 cuantizando q4_k_m..."
"$QUANT" "$SALIDA/parker-f16.gguf" "$SALIDA/parker-q4_k_m.gguf" q4_k_m

echo "[Export] 4/4 registrando en Ollama..."
cat > "$SALIDA/Modelfile" <<EOF
FROM ./parker-q4_k_m.gguf
PARAMETER temperature 0.45
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 2048
PARAMETER stop "<|im_end|>"
EOF
(cd "$SALIDA" && ollama create "$NOMBRE" -f Modelfile)

echo "[Export] listo: ollama run $NOMBRE"
echo "[Export] Prueba: python training/evaluar_lora.py --base qwen2.5:3b --lora $NOMBRE"
echo "[Export] Para usarlo como respaldo local, en config.yaml: llama.modelo: $NOMBRE"
