# LoRA de personalidad de Parker

> Esta carpeta entrena **actitud y comportamiento**, no la voz. La voz es Edge
> TTS `es-ES-XimenaNeural` con Piper de respaldo (v6.10.0); un LoRA de voz es
> otro proyecto, explicado en [../docs/lora_voz.md](../docs/lora_voz.md).

El objetivo es que el modelo local no responda como un asistente genérico:
que mantenga el tono de Parker (BMO amable + Baymax sereno), que no invente
recuerdos, que no prometa cuerpo físico y que respete el contexto de Chroma.

## Estado actual (30/10/2026)

- **No se ha entrenado nada todavía.** Este PC no tiene GPU: `torch` es CPU
  (`torch 2.12.0+cpu`) y no hay `nvidia-smi`. La placa tampoco puede entrenar.
- Lo que **sí** está hecho y probado en seco:
  - `datos/semilla.jsonl`: 28 diálogos escritos a mano, **sin nombre fijo**.
  - `preparar_dataset.py`: valida, limpia, deduplica y parte 25/3 (train/val).
    El dataset resultante tiene **0 apariciones de «Alan»**: el nombre real lo
    pone el estado de Parker, no el LoRA.
  - `generar_dataset.py --dry-run`: plan de ampliación con Groq.
  - `entrenar_lora.py --dry-run`: dataset válido y plan de QLoRA.
  - `fusionar_lora.py --dry-run`, `exportar_ollama.sh` y `evaluar_lora.py
    --dry-run`: rutas y pasos comprobados.
  - `evaluar_lora.py --solo base` ejecutado de verdad contra la placa:
    [evaluacion_base.md](evaluacion_base.md).
  - `generar_dataset.py` probado con la clave válida de la placa: 2 diálogos
    válidos en una llamada. La clave del `.env` de este PC devuelve 401; para
    generar en el PC hay que actualizarla (o generar desde la placa).
- Lo que **falta** hasta tener el LoRA: GPU (PC con NVIDIA, Colab o alquiler),
  300-800 diálogos revisados y una tanda de entrenamiento.

## 0 bis. El nombre de la persona no se fija

La semilla **no usa un nombre fijo**. El system prompt dice que quien habla es
«tu amigo», que no asuma su nombre y que solo lo use si se lo dice. Así el LoRA
no aprende a llamar «Alan» a todo el mundo: el nombre real lo pone el estado de
Parker (`parker.estado.json`) en cada conversación.

Si añades ejemplos con nombre, que sean variados y pocos; nunca 30 diálogos
seguidos con el mismo. La pregunta «¿cómo me llamo?» ya se resuelve sin LLM en
`personalidad.respuesta_directa()`.

## 0 ter. Dónde entrenar

Este PC no tiene GPU y la Orange Pi tampoco entrena. Opciones realistas para
un QLoRA de 3B:

| Opción | VRAM | Coste orientativo | Notas |
|---|---:|---|---|
| **Colab T4** | 16 GB | Gratis / ~0,12 $/h de referencia | Suficiente para 3B en 4 bits; guarda el adaptador en Drive antes de que se cierre |
| **Kaggle T4/P100** | 16 GB | Gratis, cuota semanal (~30 h) | Buena alternativa si Colab no da GPU; descarga el adaptador al terminar |
| **RunPod RTX 4090 Community** | 24 GB | ~0,34 $/h (2-3 h ≈ 0,7-1 $) | Más predecible; el disco del pod es temporal, usa volumen o descarga |
| **Vast.ai RTX 4090** | 24 GB | ~0,2-0,5 $/h según oferta | Marketplace; puede ser interrumpible, guarda checkpoints |
| **Lambda V100/A100** | 16/40 GB | ~0,79 / 1,99 $/h | Sobra para un 3B; útil si ya tienes cuenta |
| **GPU local 8 GB** | 8 GB | 0 $/h + luz | Posible con microbatch 1; este PC no tiene NVIDIA |

Precios orientativos y cambiantes: confirma la tarifa al lanzar la instancia.
Un T4 de 16 GB es suficiente; no hace falta A100 para esta tanda.

**Recomendación:** empieza en Colab o Kaggle; si se corta o no hay GPU, alquila
un 4090 en RunPod por 2-3 horas. Guarda `training/salida/parker-lora/` fuera de
la VM antes de apagarla.

## 0 quater. ¿Y un LoRA de BMO/Baymax ya hecho?

Revisión con fuentes y comprobación en vivo de las APIs en
[recursos_externos.md](recursos_externos.md). Resumen corregido:

- **No hay un LoRA de texto en español** de BMO o Baymax que sirva.
- **Sí hay modelos BMO completos en inglés**:
  [`amrmantawi/bmo-qwen2.5-3b`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b)
  (6,18 GB, base Qwen2.5-3B) y una conversión
  [`rk3588-1.2.2`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b-rk3588-1.2.2)
  para el NPU del RK3588 (2 × 3,76 GB `.rkllm`). Sin ficha, sin licencia y sin
  prueba de español.
- Los tres «LoRA» del mismo autor (`bmo-qwen2.5-3b-lora`, `bmo-qwen3.5-2B-lora`,
  `bmo-qwen3.5-4B-lora`) tienen el `adapter_model.safetensors` de **40 bytes**:
  están **vacíos**. No son adaptadores entrenados.
- El corpus más grande que he encontrado es
  [`bibidentuhanoi/BMO_BASE_1.0`](https://huggingface.co/datasets/bibidentuhanoi/BMO_BASE_1.0):
  **8.811 diálogos en inglés**, ChatML, sin licencia. Se puede usar como
  referencia de tono o traducir un subconjunto revisado; no entrenar con él tal
  cual.
- Los «Baymax» de Hugging Face son modelos **médicos**, no el personaje. No hay
  un corpus limpio de Baymax; sus diálogos se escriben a mano.
- En GitHub **no hay pesos de LoRA**: los proyectos BMO usan prompt + Ollama.
  Lo aprovechable son ideas de arquitectura y prompts, no pesos.

## 1. Requisitos

- GPU NVIDIA con 6-8 GB de VRAM para Qwen2.5-3B en 4 bits (un T4 de Colab vale);
  4 GB para Qwen2.5-1.5B.
- Python 3.10 o 3.11 (no 3.13) y CUDA.
- Para exportar: `llama.cpp` clonado/compilado y Ollama.

```bash
python3.11 -m venv ~/env-lora
source ~/env-lora/bin/activate
pip install --upgrade pip
pip install -r training/requirements-lora.txt
```

## 2. Construir el dataset

```bash
# Base escrita a mano (28 diálogos)
python training/preparar_dataset.py

# Añadir conversaciones reales de la placa (sin órdenes ni pruebas)
scp orangepi@192.168.1.130:~/parker.log /tmp/parker.log
python training/preparar_dataset.py --log /tmp/parker.log

# Ampliar con Groq (gasta tokens; revisar lo generado)
python training/generar_dataset.py --n 180
python training/preparar_dataset.py --extra training/datos/sintetico.jsonl \
    --exigir-minimo 300
```

Salida: `datos/parker_train.jsonl` y `datos/parker_val.jsonl`, en formato
ChatML (`messages` con system/user/assistant). El system prompt es
`persona_sistema.txt`, la versión compacta de la identidad real.

**Calidad antes que cantidad:** los comandos («baja el volumen», «pon una
alarma») no son actitud y el limpiador los descarta. Tampoco entran pruebas,
líneas con `Traceback` ni respuestas vacías.

## 2 bis. Línea base que hay que batir (qwen2.5:3b, placa, 30/10/2026)

El evaluador real, con 10 prompts y el system de entrenamiento **neutral**, dio:

- 10/10 respuestas, **9/10** con etiqueta válida `[CARA:...]`;
- **0 etiquetas fuera del catálogo** (se corrigió el ejemplo `[CARA:emocion]`);
- TTFB p50 **0,58 s** una vez cargado (el primer turno pagó 2,56 s en caliente;
  en frío llegó a 9,08 s);
- **1/10** suena a asistente («¿en qué puedo ayudarte hoy?»);
- **1/10** regurgita el prompt («Eres Parker no puede explicar…») y pone la
  etiqueta al final, no al principio;
- **2/10** respuestas de 3 frases, cuando el prompt pide 2;
- 0/10 promesas de acciones físicas;
- **0 menciones a «Alan»** ni a ningún nombre fijo.

La primera medición se hizo con el historial vivo, que incluía «Alan», y está
descartada. Esta es la línea base limpia que hay que batir. Objetivo del LoRA:
mantener el formato (10/10 respuestas y 9/10 etiquetas al inicio) y bajar a **0**
la respuesta de asistente, la que regurgita el prompt y las respuestas de 3
frases, sin perder contexto ni inventar. El banco completo está en
[evaluacion_base.md](evaluacion_base.md).

## 2 ter. Corpus BMO externo (opcional)

Si se quiere acelerar el dataset con el corpus de 8.811 diálogos:

```bash
# descarga (10,8 MB), fuera de git: training/datos/_externos/ está ignorado
mkdir -p training/datos/_externos
curl -L -o training/datos/_externos/BMO_BASE_1.0.json \
  https://huggingface.co/datasets/bibidentuhanoi/BMO_BASE_1.0/resolve/main/dataset.json
```

- Está en **inglés** y sin licencia. Traduce solo 300-500 diálogos, quita las
  funciones (`StreamMusic`, `MusicControl`), elimina el nombre fijo «BMO» del
  system y revisa a mano antes de entrenar.
- No mezclar las 8.811 filas en inglés con la semilla española: el LoRA
  aprendería a contestar en inglés.
- El material externo **no se sube al repositorio**; `training/datos/_externos/`
  está en `.gitignore`.

## 3. Entrenar

```bash
python training/entrenar_lora.py --dry-run   # valida sin GPU

python training/entrenar_lora.py \
    --modelo Qwen/Qwen2.5-3B-Instruct \
    --epocas 3 --r 16 --alpha 32 --max-seq 2048 \
    --batch 1 --grad-accum 8 --lr 1e-4
```

- QLoRA 4 bits, `r=16`, `alpha=32`, `dropout=0.05`, AdamW 8-bit.
- El adaptador sale en `training/salida/parker-lora/`.
- Si hay poca VRAM: `--max-seq 1024 --batch 1 --grad-accum 16` o
  `--modelo Qwen/Qwen2.5-1.5B-Instruct`.
- No entrenar más de 2-4 épocas con 300-500 ejemplos: empieza a repetir frases.

## 4. Exportar a Ollama

```bash
bash training/exportar_ollama.sh
# o con rutas/nombre propios:
bash training/exportar_ollama.sh training/salida/parker-lora \
    training/salida/parker-gguf parker-lora
```

Pasos que ejecuta: fusionar el adaptador (`fusionar_lora.py`) → convertir a
GGUF f16 (`convert_hf_to_gguf.py`) → cuantizar `q4_k_m` → `ollama create
parker-lora`.

## 5. Evaluar antes de tocar la placa

```bash
python training/evaluar_lora.py --base qwen2.5:3b --lora parker-lora
```

Genera `training/evaluacion.md` con 10 prompts y señales automáticas:

- respuesta vacía;
- acción física prometida (Parker no tiene cuerpo);
- frase de asistente o mención de IA;
- etiqueta `[CARA:...]` al inicio;
- número de preguntas y frases;
- TTFB de cada modelo.

Después, prueba de contexto y latencia con el banco real:

```bash
python tools/eval_cerebro.py --local --modelo parker-lora --turnos 6
```

Solo se despliega si mejora en **contexto y coherencia**, aunque la latencia
suba un poco. La nube sigue siendo el cerebro primario (`modo auto`); el LoRA
es el respaldo local.

## 6. Desplegar y volver atrás

En `config.yaml`:

```yaml
llama:
  modelo: "parker-lora"
```

Reiniciar Parker y comprobar en el log `[Cerebro] ... respaldo LOCAL
(parker-lora)`. Para volver al 3B: `modelo: "qwen2.5:3b"`.

## 7. Reglas de datos

- No incluir claves, tokens, direcciones ni datos que no quieras entrenar.
- ChromaDB **no** se vuelca entero: los recuerdos son contexto, no actitud.
- El sintético de Groq puede inventar; se revisa a mano antes de entrenar.
- El split es por conversación; nunca se parte un diálogo entre train y val.
- Guarda la semilla en git y los datasets generados fuera (ver `.gitignore`).
- El corpus BMO externo es inglés y **sin licencia**: no se redistribuye ni se
  sube a git. Solo se usa como referencia de tono o se traduce un subconjunto
  revisado para uso personal.

## 8. Por qué no vale solo con Edge TTS

Edge cambia la voz, no la forma de pensar. La actitud sale del modelo de texto
y del prompt; por eso este LoRA es el que de verdad puede hacer que Parker
suene a Parker y no a un asistente.
