# Conceptos y siglas

Todo lo que sale en los logs, en `config.yaml` y en las conversaciones sobre
Parker, explicado en una línea (y con el detalle que importa para este proyecto).
Los números concretos están en [rendimiento.md](rendimiento.md).

---

## 1. El cerebro: LLM y compañía

| Término | Qué es |
|---|---|
| **LLM** | *Large Language Model*. Modelo que predice el siguiente trozo de texto. Aquí corre local: `qwen2.5:3b` dentro de **Ollama**. |
| **Ollama** | Servicio que carga y ejecuta modelos en local y expone una API HTTP (`localhost:11434`). Parker le habla por `/api/chat`. |
| **Token** | Unidad mínima de texto: una palabra corta, un trozo de palabra o un signo. En español suele haber ~2-3 caracteres por token. Todo se mide en tokens: prompt, respuesta, velocidad. |
| **tok/s** | Tokens por segundo. En la placa: **~17-19 tok/s generando** y **60-200 tok/s leyendo el prompt**. |
| **Prompt** | Todo lo que se le manda al modelo: identidad, historial, ánimo, recuerdos y la pregunta. El tamaño cambia con el historial y los hechos recuperados; se mide con `prompt_eval_count`. |
| **Prefill / prompt eval** | Fase en la que el modelo *lee* el prompt antes de escribir. Es la causante del primer token. |
| **Generación / eval** | Fase en la que va escribiendo la respuesta, token a token. |
| **TTFB** | *Time To First Byte* (aquí, *time to first token*): tiempo hasta el primer trozo de respuesta. Es lo que más se nota al hablar. En una tanda de placa se midió **0,9-1,9 s**; depende de carga y prompt. |
| **Streaming** | Recibir la respuesta a trozos (`stream: true`) en vez de esperar a que termine. Permite sintetizar la primera frase mientras el modelo sigue escribiendo. |
| **NDJSON** | *Newline Delimited JSON*: un JSON por línea. Es el formato en que Ollama manda el streaming. |
| **Caché de prefijo** | Ollama guarda lo que ya procesó al principio del prompt y, si la siguiente petición empieza igual, no lo vuelve a leer. Por eso el historial se guarda **tal cual se envió**: si cambia una coma, se pierde el atajo. |
| **KV cache** | Memoria interna del modelo con lo ya procesado. Es lo que hace posible el caché de prefijo. |
| **`num_ctx`** | Tamaño de la ventana de contexto (1024 aquí). Más grande = más RAM y más lento. |
| **`num_predict` / `max_tokens`** | Máximo de tokens a generar (64). Limita el largo de la respuesta. |
| **`temperature`** | Aleatoriedad (0 = más determinista, 1 = más creativo). Parker usa 0,45. |
| **`num_thread`** | Hilos de CPU para el modelo (4 en la configuración medida; cambiar solo tras comparar latencia y temperatura sostenida). |
| **`keep_alive`** | Cuánto tiempo deja Ollama el modelo cargado en RAM (`24h` aquí). Si se descarga, la siguiente frase paga 10-40 s de carga. |
| **Precalentar** | Cargar el modelo y cachear la identidad antes de activar el micro. El precalentado de cada turno está desactivado: compite por CPU con Whisper. |
| **Cuantización (Q4_K_M)** | Guardar los pesos con menos bits para que ocupen menos y vayan más rápido. `1.5b` en Q4_K_M ≈ 1,2 GB. |
| **int8** | Enteros de 8 bits: el formato rápido de Whisper/Piper en esta placa. |
| **Peso / parámetro** | `1.5b` = 1.500 millones de parámetros. Más parámetros pueden ayudar en tareas complejas, pero en esta placa `3b` fue mucho más lento y divagó más en la prueba real. |
| **Atajo de identidad** | Respuesta que Parker da **sin LLM** cuando la pregunta es un dato que sabe seguro ("¿cómo me llamo?"). Un modelo pequeño aquí inventa; esto es exacto y gratis en latencia. |
| **Vínculo (confianza)** | Porcentaje 0-100 que dice cuánto os conocéis: sube con los días (50 puntos en 10 días) y con las charlas (50 puntos en 50). Va en el prompt para que Parker no finja familiaridad el primer día. |
| **Vocativo** | Dirigirse a alguien por su nombre ("Hola, **Alan**"). Parker debe usarlo solo con el nombre de la persona, nunca con el suyo. |

## 2. El oído: STT

| Término | Qué es |
|---|---|
| **STT** | *Speech To Text*: pasar voz a texto. También **ASR** (*Automatic Speech Recognition*). En Parker lo hace `modulos/escucha.py`. |
| **Whisper** | Modelo de STT de OpenAI. En la placa se usa la variante **faster-whisper**, que es la misma red reimplementada con **CTranslate2** (más rápida en CPU). |
| **`base` / `small` / `tiny`** | Tamaños de Whisper. `base` tarda ~1,5 s con audio de 6 s; `small` ~5 s; `tiny` ~1,2 s pero escribe mal. |
| **RTF** | *Real Time Factor*: tiempo de proceso ÷ duración del audio. 0,26 significa que 6 s de voz se transcriben en 1,5 s. |
| **VAD** | *Voice Activity Detection*: detectar cuándo hay voz y cuándo silencio. Parker lo usa para abrir el turno y para cortarlo tras 0,6 s de silencio. |
| **`hotwords`** | Palabras que se le «sugieren» al STT. Con `hotwords: "Parker"` deja de transcribir «parquear». |
| **`beam_size`** | Cuántas hipótesis prueba el decodificador. 1 = rápido; 5 = algo más preciso y más lento. |
| **WER** | *Word Error Rate*: porcentaje de palabras mal transcritas. |
| **PCM / sample rate** | Audio en bruto. Whisper trabaja a **16 kHz** mono; Piper genera a 22,05 kHz (por eso se remuestrea). |

## 3. La voz: TTS

| Término | Qué es |
|---|---|
| **TTS** | *Text To Speech*: pasar texto a voz. En Parker, `modulos/voz.py` con **Piper**. |
| **Piper** | Sintetizador neuronal ligero que corre en CPU. Usa ficheros `.onnx` (la red) y `.onnx.json` (los ajustes de voz). |
| **ONNX** | Formato abierto para guardar redes neuronales y ejecutarlas con **onnxruntime**. |
| **length_scale** | Cuánto alarga Piper cada sonido: >1 = habla más despacio **sin cambiar el tono**. Es la forma correcta de pedir calma; remuestrear la señal (lo que se hacía antes) baja el tono y la voz suena más grave. |
| **Ganancia / pico** | Nivel de la señal. Piper normaliza a 1.0 y luego aplica el volumen de `config.yaml`; a partir de ~0.7 suena a grito. |
| **Síntesis por frases** | Parker no espera a tener la respuesta entera: sintetiza y reproduce frase a frase, en una cola, mientras el modelo sigue generando. |

## 4. La memoria: embeddings y RAG

| Término | Qué es |
|---|---|
| **Embedding** | Un vector (lista de números) que representa el significado de un texto. Textos parecidos quedan cerca. |
| **`paraphrase-multilingual-MiniLM-L12-v2`** | El modelo que convierte frases en vectores. Multilingüe, ~120 MB, corre en CPU. |
| **Similitud coseno** | Cómo de parecidos son dos vectores (1 = idénticos). El **umbral** (0,5) decide si un recuerdo entra en el prompt. |
| **ChromaDB** | Base de datos de vectores. Guarda los recuerdos en `parker.db/`. |
| **RAG** | *Retrieval-Augmented Generation*: recuperar recuerdos relevantes y pegarlos al prompt para que el modelo los tenga en cuenta. |
| **`top_k`** | Cuántos recuerdos se recuperan (2 aquí). Cada uno son tokens que el modelo lee en **cada** respuesta. |

## 5. El hardware: RK3588 y la NPU

| Término | Qué es |
|---|---|
| **RK3588** | El SoC de la Orange Pi 5 Pro: 8 núcleos (4× Cortex-**A76** rápidos + 4× **A55** eficientes), GPU Mali y una **NPU**. |
| **NPU** | *Neural Processing Unit*: chip especializado en redes neuronales. El RK3588 tiene una de **6 TOPS** (billones de operaciones por segundo). |
| **TOPS** | Medida de potencia de la NPU. No es comparable 1:1 con un CPU: depende de la red y de la cuantización. |
| **RKNPU** | El driver de la NPU (aparece como `fdab0000.npu` en `dmesg`). |
| **RKNN / RKNN-Toolkit2** | Formato y herramientas de Rockchip para convertir modelos y ejecutarlos en la NPU (`rknnlite` en Python). |
| **RKLLM / rkllama** | Runtime de Rockchip para LLM en la NPU. `rkllama` imita la API de Ollama, así que sería cambiar `llama.host` en `config.yaml`. |
| **big.LITTLE** | Arquitectura de dos tipos de núcleos. El planificador reparte carga; en la práctica 4 hilos rinden mejor que 8 en este modelo. |
| **Governor** | Política de frecuencia del CPU (`ondemand` aquí): sube MHz cuando hay carga. |
| **SPI** | *Serial Peripheral Interface*: bus serie rápido con el que se habla la pantalla redonda (24 MHz aquí). |
| **GPIO** | Pines de propósito general; Parker los usa para `DC` y `RST` de la pantalla (`GPIO1_B0`, `GPIO4_B3`). |
| **GC9A01** | El controlador de la pantalla circular de 240×240. |
| **QPA / `QT_QPA_PLATFORM`** | Cómo dibuja Qt. `offscreen` = sin HDMI ni escritorio; la cara se renderiza y se envía por SPI. |

## 6. Del sistema

| Término | Qué es |
|---|---|
| **SSH** | Acceso remoto por red a la terminal de la placa. |
| **systemd / `systemctl`** | Gestor de servicios de Linux. `ollama.service` es uno; `parker.service` es la alternativa a cron para arrancar Parker. |
| **cron / `@reboot`** | Programador de tareas. `@reboot` ejecuta algo al encender; es lo que usa ahora Parker (no pide contraseña). |
| **venv** | Entorno Python aislado con las dependencias del proyecto (`~/env`). |
| **sudo** | Ejecutar como administrador. En la placa pide contraseña, por eso el arranque va por cron. |
| **md5** | Huella de un fichero. Se usa para comprobar que el PC y la placa tienen **exactamente** el mismo código. |
| **Log** | Registro de lo que pasa (`~/parker.log`). Cada etapa imprime su tiempo con `[Latencia]`. |

## 7. Las tres cifras que importan

```
silencio (0,6 s)  +  STT (1,2-1,5 s)  +  primera frase (1,3-2,1 s)  +  TTS (0,5-0,9 s)
= 4,2-4,7 s hasta que Parker empieza a hablar
```

Todo lo demás (terminar de generar, hablar las frases siguientes) ocurre
mientras ya está sonando, así que no se percibe.
