# LoRA de personalidad y LoRA de voz: qué es cada cosa

> Documento de trabajo, 30/10/2026. La idea: que Parker hable con la actitud
> amable de BMO/Baymax y, si se quiere, con una voz propia. Son **dos**
> proyectos distintos y no se estorban.

## 1. LoRA no es solo para imágenes

LoRA (*Low-Rank Adaptation*) es una técnica de entrenamiento: en vez de
reentrenar todos los pesos de un modelo, se congelan y se añaden unas matrices
pequeñas que aprenden el cambio. Funciona igual en:

- un **modelo de texto** (Qwen, Llama, Mistral...) → cambia cómo habla, su
  actitud, su forma de responder;
- un **modelo de voz/TTS** (XTTS, Piper, F5-TTS...) → cambia el timbre, el
  acento o la forma de interpretar;
- un modelo de imagen (Stable Diffusion), que es donde más se conoce el nombre.

Una misma técnica, tres usos. Lo que cambia es el **modelo base** y los **datos**
con los que se entrena.

## 2. Lo que queremos: actitud + voz

| Pieza | Qué se entrena | Dónde se ejecuta | Qué cambia |
|---|---|---|---|
| **LoRA de personalidad** | Qwen3-1.7B / Qwen2.5-3B (texto) | Placa, en Ollama, como cerebro local | Que diga las cosas con la actitud de Parker (BMO amable + Baymax tranquilo), no solo el prompt |
| **LoRA de voz** | Piper (CPU) o XTTS-v2 (GPU) | Piper sí cabe en la placa; XTTS no | El timbre y la forma de hablar; **no** la personalidad |
| **Edge TTS** | No se entrena: es un servicio cerrado | Nube de Microsoft | Voz natural ya, sin entrenar |

**Edge TTS no impide el LoRA de personalidad.** Son capas separadas: el cerebro
decide *qué* dice y la voz decide *cómo suena*. Si más adelante se cambia a una
voz entrenada, se cambia el motor de voz y el cerebro sigue igual. Si se quiere
volver a Piper: `voz.motor: piper`.

## 3. LoRA de personalidad (el que de verdad cambia la actitud)

### 3.1 Datos

No hace falta un libro: hacen falta **conversaciones de ejemplo** con el tono
que quieres. Mínimo viable:

- 300-800 intercambios (usuario + Parker), en español y catalán;
- 20-40 conversaciones multi-turno para que aprenda a seguir el hilo;
- etiquetas de emoción (`[CARA:feliz]`) solo si se quieren conservar;
- ejemplos negativos: lo que **no** debe decir (frases de asistente genérico,
  promesas de acciones físicas, invenciones).

Se pueden sacar de los logs de Parker, pero hay que limpiarlos: quitar pruebas,
datos personales y respuestas malas. Un dataset pequeño y bueno gana a uno
grande y sucio.

**No fijes el nombre de la persona en los ejemplos.** Di «tu amigo» o «tú»; si
un diálogo necesita nombre, varíalo. El nombre real lo pone el estado de Parker
en cada conversación, no el LoRA.

Si quieres acelerar el corpus, existe
[`BMO_BASE_1.0`](https://huggingface.co/datasets/bibidentuhanoi/BMO_BASE_1.0)
con **8.811 diálogos de BMO en inglés** (sin licencia). Traduce 300-500,
quita funciones y nombres fijos y revísalos a mano; no entrenes con el corpus
entero en inglés. Detalle en
`training/recursos_externos.md`.

Formato recomendado (ChatML, el que usa Ollama/Qwen):

```json
{"messages": [
  {"role": "system", "content": "Eres Parker..."},
  {"role": "user", "content": "Hoy estoy cansado"},
  {"role": "assistant", "content": "Pues ven aquí, que hoy no hay que hacer nada. ¿Te apetece que te cuente una tontería?"}
]}
```

### 3.2 Entrenamiento

En el PC o en la nube, **nunca en la Orange Pi** (no tiene GPU para entrenar).
Con una GPU de 8 GB:

- QLoRA 4-bit sobre Qwen3-1.7B o Qwen2.5-3B;
- `r=16`, `alpha=32`, `dropout=0.05`, LR `1e-4`, 2-3 épocas;
- longitud de contexto 2048;
- guardar checkpoints y evaluar en un conjunto aparte.

Herramientas: `unsloth` (la más rápida para Qwen/Llama), `peft` + `transformers`,
o `axolotl`. Para pasar a Ollama: fusionar el adaptador, convertir a GGUF
(`llama.cpp`) y `ollama create parker-lora -f Modelfile`.

### 3.3 Evaluación

Antes de ponerlo en la placa:

1. mismas 30 preguntas con el modelo base y con el LoRA;
2. medir: coherencia, contexto, invenciones, longitud y latencia;
3. probar los casos que fallan hoy: nombres, recuerdos de Chroma, no contradecir,
   no prometer cuerpo físico;
4. si empeora en algo crítico, no se despliega.

En la placa se prueba como `llama.modelo: parker-lora` y se compara con
`qwen2.5:3b`. El modo `auto` sigue usando la nube; el LoRA solo entra si falla
internet o si se pide `modo local`.

## 4. LoRA de voz (lo que probablemente querías decir)

### 4.1 Qué se necesita

- 10-30 minutos de audio limpio (mejor 1 hora), una sola voz, sin música ni eco;
- transcripción exacta de ese audio;
- consentimiento: voz propia o con licencia; no clonar a otra persona sin permiso;
- GPU para entrenar (XTTS) o CPU para un fine-tune pequeño de Piper.

### 4.2 Opciones

| Modelo | Calidad | Entrenar | Ejecutar en placa | Nota |
|---|---|---|---|---|
| **Piper** | Buena, robótica si se fuerza | Fine-tune pequeño | Sí, CPU, tiempo real | La opción realista para la placa |
| **XTTS-v2** | Muy natural, clona con poco audio | GPU | No (demasiado pesado) | Se puede usar en el PC o en la nube |
| **F5-TTS / StyleTTS2** | Muy natural | GPU | No | Más experimentales |
| **Edge TTS** | Muy natural | No se puede | Solo nube | Ahora mismo, la voz de Parker |

Para la actitud amable, el **texto** hace el 80 %: aunque la voz sea la misma,
las palabras y el ritmo cambian la sensación. Para el timbre, hace falta el
modelo de voz.

### 4.3 Ruta recomendada

1. **Ahora**: Edge TTS `es-ES-XimenaNeural` (ya instalado) para que Parker hable
   natural; Piper queda de respaldo.
2. **Corto plazo**: LoRA de personalidad sobre Qwen3-1.7B con 300-500 diálogos.
   Eso es lo que cambia la actitud; se prueba en local y se compara.
3. **Medio plazo**: si la voz de Ximena no basta, fine-tune de Piper con 30-60
   min de una voz propia (o XTTS en el PC para frases pregrabadas). Piper es el
   único que puede correr en la placa sin GPU.
4. **Largo plazo**: un modelo TTS pequeño en la NPU (RKLLM/RKNN) si sale soporte;
   hoy no hay una ruta madura para este caso.

### 4.4 Por qué Edge TTS no bloquea nada

Edge TTS solo devuelve audio. No toca el cerebro, ni Chroma, ni el prompt, ni el
LoRA de texto. Si mañana se entrena una voz propia, se añade otro motor a
`modulos/voz.py` y se elige en `config.yaml`; el resto de Parker no cambia. Si
Edge TTS empieza a fallar o Microsoft cambia la voz, el respaldo Piper ya está
cargado y la frase sale igual.

## 5. Qué haría falta para empezar hoy

- [ ] Grabar 30-60 min de la voz que se quiera (o decidir usar Ximena).
- [ ] Escribir 100 diálogos de Parker con la actitud deseada.
- [ ] Elegir GPU/Colab para entrenar (la placa no entrena).
- [ ] Medir el modelo base con `tools/eval_cerebro.py --local` antes de tocar nada.
- [ ] Entrenar, evaluar y desplegar solo si mejora.

Mientras tanto, Parker ya puede usar Edge TTS y el cerebro de la nube; la
personalidad se sigue controlando con el prompt y la memoria de Chroma.

La tubería concreta (dataset, QLoRA, exportación a Ollama y evaluación) está en
`training/README.md`; este documento solo explica la
diferencia entre los dos tipos de LoRA.
