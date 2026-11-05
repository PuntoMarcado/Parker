# BMO, Baymax y LoRAs: qué existe de verdad (30/10/2026)

> Búsqueda hecha en vivo contra la API de Hugging Face y la API de GitHub, no
> solo con resultados de buscador. Sirve para el LoRA de **actitud** de Parker.
> Un LoRA de imagen (Stable Diffusion/Civitai) **no** se puede cargar en
> Qwen/Llama para conversar: son cosas distintas.

## Corrección importante

La conclusión anterior («no existe ningún LoRA de texto de BMO») era demasiado
amplia. Lo correcto es:

- **No hay un LoRA de texto de BMO o Baymax en español** que podamos usar tal cual.
- **Sí hay modelos BMO completos en inglés**, incluido un Qwen2.5-3B y una
  conversión para el NPU RK3588.
- Los tres «LoRA» de BMO publicados por `amrmantawi` están **vacíos**: el
  `adapter_model.safetensors` pesa **40 bytes**. No son adaptadores entrenados;
  son repositorios con configuración y tokenizer. No sirven.
- En GitHub **no hay pesos de LoRA de BMO/Baymax**: los proyectos que existen
  usan un prompt de personalidad con Ollama, no un adaptador entrenado.

## Lo que sí existe (y qué se puede hacer con ello)

### 1. BMO 3B sobre Qwen2.5-3B, en inglés y sin ficha

| Recurso | Qué es | Tamaño | Estado |
|---|---|---|---|
| [`amrmantawi/bmo-qwen2.5-3b`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b) | Modelo completo, familia Qwen2.5-3B (`Qwen2ForCausalLM`) | 6,18 GB (safetensors) | Sin model card, sin licencia declarada, 6 descargas |
| [`amrmantawi/bmo-qwen2.5-3b-rk3588-1.2.2`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b-rk3588-1.2.2) | Conversión a **RKLLM w8a8** para NPU RK3588 | 2 × 3,76 GB `.rkllm` | Dice «compatible con RKLLM 1.2.2»; sin ficha de datos ni licencia |
| [`amrmantawi/bmo-qwen2.5-3b-lora`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b-lora) | Supuesto adaptador LoRA | **40 bytes** el safetensors | **Vacío. No usar** |
| [`amrmantawi/bmo-qwen3.5-2B`](https://huggingface.co/amrmantawi/bmo-qwen3.5-2B) | Modelo completo Qwen3.5 | 8,43 GB | La ficha no aclara idioma/licencia; el `adapter_config` de su variante dice base 4B, hay confusión de nombres |
| [`amrmantawi/bmo-qwen3.5-2B-rk3588-1.3.0`](https://huggingface.co/amrmantawi/bmo-qwen3.5-2B-rk3588-1.3.0) | Conversión RKLLM w8a8 | 2 × 2,94 GB `.rkllm` | Requiere RKLLM 1.3.0; el runtime de la placa está sin identificar |

**No está demostrado que hable español.** El corpus BMO que circula es inglés;
la ficha del modelo no declara idioma. Antes de usarlo como respaldo local hay
que probarlo con preguntas en castellano y catalán. Tampoco tiene licencia: para
un proyecto personal se puede estudiar, pero no es material para redistribuir.

### 2. BMO 7B/8B en inglés, con algo más de documentación

| Modelo | Base | Licencia | Tamaño | ¿Sirve en la placa? |
|---|---|---|---|---|
| [`bibidentuhanoi/BMO-8B-Instruct-Llama3`](https://huggingface.co/bibidentuhanoi/BMO-8B-Instruct-Llama3) | Dolphin 2.9 Llama3 8B | Apache-2.0 | 8B | No: 8B en 8 GB de RAM no cabe con holgura; además es inglés |
| [`bibidentuhanoi/BMO-7B-Instruct-Mistral`](https://huggingface.co/bibidentuhanoi/BMO-7B-Instruct-Mistral) | Mistral 7B | Sin licencia clara | 7B | No para la placa; inglés |
| [`s3nh/bibidentuhanoi-BMO-7B-Instruct-GGUF`](https://huggingface.co/s3nh/bibidentuhanoi-BMO-7B-Instruct-GGUF) | Copia GGUF Q4_K_M | `openrail`, `zh/en` | ~4,37 GB | Podría caber, pero no hay prueba de español ni de calidad |

Son proyectos de aficionado, con fichas incompletas. No los pondría como
cerebro de Parker sin un banco de pruebas en español.

### 3. El corpus BMO más grande que he encontrado: 8.811 diálogos

[`bibidentuhanoi/BMO_BASE_1.0`](https://huggingface.co/datasets/bibidentuhanoi/BMO_BASE_1.0)
es un JSON de **10,8 MB con 8.811 filas**. Cada fila es una conversación en
formato ChatML:

```
<|im_start|>system
Your name is BMO. You are a friendly and truthful robot pal...
<|im_end|>
<|im_start|>user
Hey there, BMO! How are you today?
<|im_end|>
<|im_start|>assistant
Hi, buddy! I'm doing great. Just here, ready to chat with you...
<|im_end|>
```

- **Idioma: inglés.** En las primeras 300 filas: `hello` 2, `the ` 1.644,
  `hola` 0, `qué ` 0. No es material directo para Parker.
- Incluye instrucciones de funciones (`StreamMusic`, `MusicControl`) y al
  personaje llamándose BMO; no está pensado para un usuario con nombre variable.
- **No tiene licencia.** Es material de fans/experimento; úsalo como referencia
  de tono, no como corpus que se redistribuya.
- Hay otros dos datasets del mismo autor: `BMO_BASE_TEXT` (278 filas) y
  `BMO_vicuna_function` (149 filas), también en inglés.

**Uso realista:** traducir al español 300-500 diálogos, quitar funciones y
nombres fijos, revisarlos a mano y mezclarlos con nuestra semilla. Eso acelera
mucho el dataset sin copiar el canon. No entrenar con las 8.811 filas en inglés:
el LoRA aprendería a contestar en inglés.

### 4. Baymax: no hay un corpus del personaje

- Los «Baymax» de Hugging Face (`samarth1029/Gemma-2-2b-baymax`,
  `Gemma-2-9b-baymax`) son **asistentes médicos** entrenados con ChatDoctor, no
  el personaje de *Big Hero 6*.
- Los DialoGPT de Baymax (`lizz27/DialoGPT-medium-BaymaxBot`,
  `soop/DialoGPT-medium-BaymaxBot`, etc.) son modelos pequeños, ingleses y
  antiguos; no hay dataset asociado.
- La transcripción de la película está en wikis de fans y tiene copyright. Se
  puede leer para captar el tono, pero no es un corpus limpio para entrenar y
  publicar.
- Para la parte «Baymax» de Parker es mejor **escribir diálogos originales**:
  frases cortas, calma, cuidado, sin diagnosticar y sin prometer cuerpo físico.

### 5. GitHub: proyectos parecidos, pero sin LoRA entrenado

Búsquedas `bmo llm`, `bmo lora`, `bmo ollama`, `bmo chatbot`, `baymax llm` y
`baymax chatbot` en la API de GitHub. Ninguno publica un adaptador de texto;
lo que hay son prompts y arquitecturas:

| Proyecto | Qué aporta | Licencia |
|---|---|---|
| [`coreyms/bmo`](https://github.com/coreyms/bmo) | BMO con LLM local, Piper, Vosk y cara en pygame para Raspberry Pi 5 | Sin licencia declarada |
| [`FelixLiu339/bmo_AI_project`](https://github.com/FelixLiu339/bmo_AI_project) | Robot de escritorio trilingüe en Raspberry Pi 5, inferencia local/GPU | `NOASSERTION` (revisar) |
| [`junkatori95/BMO-AI-Companion`](https://github.com/junkatori95/BMO-AI-Companion) | Llama 3.2 3B, visión y voz; inglés/vietnamita | MIT |
| [`ivegotanheadache/BMO`](https://github.com/ivegotanheadache/BMO) | Compañero local con prompt de personalidad | `NOASSERTION` |
| [`sHuCkLe1/local-bmo-agent`](https://github.com/sHuCkLe1/local-bmo-agent) | Ollama + faster-whisper, cara animada, memoria | MIT |
| [`AmrMantawi/paroli-daemon`](https://github.com/AmrMantawi/paroli-daemon) | TTS Piper con aceleración **RK3588 NPU**; no es LLM, pero es el mismo autor de los BMO RKLLM | MIT |
| [`longy2k/obsidian-bmo-chatbot`](https://github.com/longy2k/obsidian-bmo-chatbot) | Perfiles/prompts para Ollama/LM Studio | MIT |

## El camino rápido: RKLLM en el NPU del RK3588

La placa es una Orange Pi 5 Pro con RK3588S. He comprobado en ella:

- `/usr/lib/librkllmrt.so` **está instalado** (11,5 MB, 29/08/2024).
- No está el módulo Python `rkllm`; el runtime C existe, pero falta el binding.
- 7,7 GB de RAM total, 4,4 GB disponibles ahora mismo, 38 GB libres en disco.
- El modelo BMO RKLLM pesa **3,76 GB** por variante. Cabe en disco, pero cargarlo
  con Parker en marcha puede quedarse corto de RAM: hay que probarlo con Parker
  parado y medir.

Esto no es un cambio de una tarde: hay que compilar/instalar el runtime RKLLM,
cargar el `.rkllm` y adaptar el cliente. Pero es la vía más prometedora para que
el cerebro local deje de depender de la CPU. **No lo he integrado ni medido**
todavía; solo he comprobado que el runtime existe y que el modelo está publicado.
Además, ese BMO es inglés y sin licencia: primero hay que ver si responde en
español y si su tono encaja.

## Dónde entrenar el LoRA

Este PC no tiene GPU y la Orange Pi tampoco entrena. Opciones realistas para un
QLoRA de 3B:

| Opción | VRAM | Coste orientativo | Notas |
|---|---:|---|---|
| [Google Colab](https://colab.research.google.com/) T4 | 16 GB | Gratis / ~0,12 $/h de referencia | Suficiente para 3B en 4 bits; guarda el adaptador en Drive antes de que se cierre |
| [Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) T4/P100 | 16 GB | Gratis, cuota semanal (~30 h) | Buena alternativa si Colab no da GPU; descarga el adaptador al terminar |
| [RunPod](https://www.runpod.io/pricing) RTX 4090 Community | 24 GB | ~0,34 $/h (2-3 h ≈ 0,7-1 $) | Más predecible; el disco del pod es temporal, usa volumen o descarga |
| [Vast.ai](https://vast.ai/pricing) RTX 4090 | 24 GB | ~0,2-0,5 $/h según oferta | Marketplace; puede ser interrumpible, guarda checkpoints |
| [Lambda](https://lambda.ai/pricing) V100/A100 | 16/40 GB | ~0,79 / 1,99 $/h | Sobra para un 3B; útil si ya tienes cuenta |
| GPU local 8 GB | 8 GB | 0 $/h + luz | Posible con microbatch 1; este PC no tiene NVIDIA |

Precios orientativos y cambiantes: confirma la tarifa al lanzar la instancia.
Un T4 de 16 GB es suficiente; no hace falta A100 para esta tanda.

**Recomendación:** empieza en Colab o Kaggle; si se corta o no hay GPU, alquila
un 4090 en RunPod por 2-3 horas. Guarda `training/salida/parker-lora/` fuera de
la VM antes de apagarla.

## Recomendación final

1. **No usar** los adaptadores vacíos de `amrmantawi` ni los BMO 7B/8B como
   cerebro: no hay prueba de español, contexto ni licencia suficiente.
2. **Sí usar** `BMO_BASE_1.0` como fuente de tono: traducir 300-500 diálogos,
   limpiarlos y revisarlos. Es la forma más rápida de tener un corpus BMO en
   español sin inventarlo todo.
3. **Nuestro LoRA** sigue siendo la vía principal: Qwen2.5-3B + semilla neutral
   + diálogos traducidos/revisados. El banco de evaluación ya está listo.
4. **RKLLM** es la vía de velocidad a medio plazo: el runtime existe en la placa,
   pero falta integrarlo y el único BMO RKLLM publicado es inglés y sin licencia.
   Medir antes de prometer.
5. **Baymax**: escribir diálogos originales de calma y cuidado; no copiar la
   película ni usar los modelos médicos.
6. **Legal**: que sea un proyecto fan no autoriza a publicar o monetizar la
   propiedad intelectual de Adventure Time/Big Hero 6. Para uso personal se
   puede estudiar el tono; para distribuir, mejor una personalidad original
   inspirada (robot amable, curioso, tranquilo) y no copiar diálogos del canon.
