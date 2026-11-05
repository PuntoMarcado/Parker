# Plan de mejoras pendientes (cuando haya placa)

> **Actualización 01/11/2026:** el patrón de turno interrumpible de Jarvis ya
> está aplicado en la **v6.12.14** (barge-in con hilo lector de tokens,
> recuperación del turno y filtro de alucinaciones del STT). Ver
> [jarvis.md](jarvis.md). Lo de este documento que
> siga pendiente se mantiene tal cual.

> **Documento de trabajo.** Consolida tres fuentes: la investigación hecha en
> GitHub/internet (octubre 2026) sobre fallos de Whisper y del cerebro pequeño,
> el diseño de evolución de [evolucion.md](evolucion.md), y el problema
> pendiente de la espera aumentada. Todo aquí está **pendiente de medir en la
> Orange Pi 5 Pro**; nada de lo marcado como *propuesto* se aplica sin prueba.
> Las cifras "medido" de la placa salen de [rendimiento.md](rendimiento.md).

**Regla de oro de la sesión:** una variable cada vez, mismo audio de
referencia para todas las comparaciones, y `tools/respaldo.py` antes de tocar
nada.

---

## 0. Orden de la sesión con placa

1. **Respaldar**: `python tools/respaldo.py "antes-mejoras"` (copia código;
   copiar además `parker.estado.json` a mano si interesa el estado actual).
2. **Diagnóstico de la espera aumentada** (§1) — primero saber qué pasó.
3. **Banco de pruebas STT** (§2) — grabar frases reales y cruzar configuraciones.
4. **Pruebas del cerebro** (§3) — salida estructurada, penalización, modelos.
5. **Aplicar lo ganador** en `config.yaml`/código con sus tests, y volver a
   medir el turno completo para confirmar regresión cero.
6. Si sobra sesión: **Fase 0 y Fase 1 de evolución** (métricas + reflejos).

---

## 1. Diagnóstico: por qué subió la espera (pendiente)

Hipótesis ordenadas por probabilidad, con cómo descartarlas:

| Hipótesis | Cómo se comprueba |
|---|---|
| Ollama descargó o recargó el modelo (`keep_alive` o reinicio del servicio) | En el log: el primer turno tras un hueco paga 10-40 s de carga; `ollama ps` en la placa |
| Throttling térmico (el log ya imprime `[Térmica]` con trips del kernel) | `grep Térmica ~/parker.log`; ver si el aviso de 70 °C aparece antes de los turnos lentos |
| CPU saturada por otro proceso (updates, indexing) | `top`/`htop` en la placa durante un turno lento |
| El caché de prefijo dejó de coincidir (identidad o volátil modificado) | Comparar el tamaño de prompt de `prompt_eval_count` entre turnos; si salta, el prefijo cambió |
| Whisper más lento (carga compartida) | El log ya imprime `[Latencia] STT` por turno: separar STT de TTFB |

Métrica de referencia antes de tocar nada: ejecutar 10 turnos seguidos y
apuntar STT / primer token / turno completo (p50 y máximo), para comparar al
final.

---

## 2. STT (Whisper): qué probar y en qué orden

### 2.1 Cambios de parámetros baratos (sin cambiar de modelo)

En `config.yaml → escucha`, todos medibles contra los mismos audios:

| Parámetro | Cambio propuesto | Motivo (fuente) |
|---|---|---|
| `condition_on_previous_text` | probar `False` | Documentado en faster-whisper: reduce bucles de repetición y deriva de marcas de tiempo — justo el tipo de transcripción enmarañada observada ([faster-whisper transcribe.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)) |
| VAD Silero | `threshold` 0,35-0,45; `speech_pad_ms` 400-600 | Los defaults cortan voz lejana a 3-5 m; ojo, los defaults difieren según versión/path: pasar valores explícitos ([vad.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/vad.py)) |
| `beam_size` | probar 3 (hoy 1) | Punto medio; cada aumento cuesta cómputo, no se promete ganancia — solo medir |
| `initial_prompt` | `"El nombre propio Parker se escribe Parker."` | Sesgo de nombre alternativo a hotwords; a veces funciona mejor ([wyoming-faster-whisper](https://github.com/OHF-Voice/wyoming-faster-whisper) hace esto con nombres de entidades, precargando el prompt mientras aún se graba) |
| `no_speech_threshold` | dejar en 0,6 | Rechaza silencio, no arregla voz confusa; no bajar a ciegas (descartaría voz lejana y justa) |

### 2.2 Front-end de audio (probablemente más impacto que los parámetros)

A 3-5 m con tele/fan, la relación voz/ruido manda más que el decodificado:

| Acción | Herramienta | Notas |
|---|---|---|
| Supresión de ruido en tiempo real | [RNNoise](https://github.com/xiph/rnnoise) | C, ligero; captura a 48 kHz → resample a 16 kHz para Whisper |
| Alternativa con más calidad | [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | Demo RTF 0,19 en un i5 — **no medido en RK3588**: probar carga antes de adoptar |
| AEC (eco del propio altavoz) | [SpeexDSP](https://github.com/xiph/speexdsp) | Solo si la voz de Parker se cuela en el micrófono; no quita la tele |
| Palabra de despertar | [openWakeWord](https://github.com/dscripka/openWakeWord) | Un core de RPi 3 corre 15-20 modelos en tiempo real; los preentrenados son en inglés, para «Parker» en español hay que entrenar modelo propio y medir falsos positivos reales |
| Micrófono | directional / array / más cerca | La lección del Voice Preview Edition de Home Assistant: el DSP del extremo de audio es la mejora más rentable |

### 2.3 Alternativas descartadas (con motivo, para no reabrir)

| Alternativa | Motivo del descarte |
|---|---|
| SenseVoiceSmall / FunASR-MLT | **Sin español** en los checkpoints publicados ([SenseVoice](https://github.com/QwenAudio/SenseVoice), [Fun-ASR](https://github.com/QwenAudio/Fun-ASR)) |
| distil-whisper | Solo inglés ([distil-whisper](https://github.com/huggingface/distil-whisper)) |
| Whisper en la NPU RK3588 | Informes de transcripciones vacías/garbage en Orange Pi 5 Pro ([rknn_model_zoo #314](https://github.com/airockchip/rknn_model_zoo/issues/314)); los puertos existentes son tiny.en (inglés) |
| `small` int8 en CPU | **No descartado: pendiente de medir.** Antes con openai-whisper `small` fueron 4,8-5,3 s; con faster-whisper int8 puede ser muy distinto. Medir p50/p95 en la placa antes de decidir |
| Parakeet TDT v3 ([parakeet.cpp](https://github.com/mudler/parakeet.cpp)) | Sí soporta español y hay builds ARM64, sin medidas en RK3588. Solo si `small` no da el nivel; esperimento aparte |
| Corrección por LLM del texto transcrito | Riesgo de reescribir el sentido; Apple usa recuperación de entidades, no reescritura ([retrieval-asr](https://machinelearning.apple.com/research/retrieval-asr)). Si acaso: tabla de alias + re-decodificar solo frases dudosas |

### 2.4 Banco de pruebas STT (el paso que lo hace medible)

Grabar en la posición y ruido habituales **50-100 frases reales** (incluyendo
varias con «Parker»), con referencia escrita. Cruzar:

```
modelo:    base | small int8
beam:      1 | 3
cond_prev: on | off
sesgo:     hotwords | initial_prompt | ambos
VAD:       default | threshold 0.40 + pad 500ms
audio:     raw | RNNoise
```

Métricas: **aciertos exactos** de la frase y de «Parker» (no solo WER),
activaciones falsas, p50/p95 de STT. Lo que gane se pasa a `config.yaml`.

---

## 3. Cerebro (LLM): qué probar y en qué orden

### 3.1 Cambios de configuración (baratos, en el modelo actual)

| Cambio | Motivo (fuente) |
|---|---|
| **Salida estructurada** de Ollama (`format` con JSON Schema: `{emotion: enum, reply}`) en vez de pedir `[CARA:…]` escrito a mano; la etiqueta se construye en Python | Elimina los fallos de formato del 1.5b; [documentado en Ollama](https://ollama.com/blog/structured-outputs). **Medir** el coste de latencia en la placa antes de adoptar |
| `repeat_penalty` 1,15 → probar 1,03-1,10 | A 1,15 puede distorsionar palabras normales; recomendación repetida en la comunidad Ollama/llama.cpp ([Modelfile](https://docs.ollama.com/modelfile)) |
| Regla explícita de memoria + **un reintento** antes del fallback | «Solo afirma un recuerdo si aparece en los recuerdos suministrados; si no, dilo»; validar la respuesta y reintentar una vez con instrucción correctiva si inventa memoria o encadena preguntas |

### 3.2 Bake-off de modelos (cuando haya set de evaluación)

No hay benchmark público de roleplay en español: comparar con **nuestros
turnos reales** (50-100 frases de conversación: saludos, apoyo emocional,
preguntas ambiguas, correcciones, invocación de recuerdos y casos sin
recuerdo). Candidatos, en orden:

| Modelo | Por qué | Advertencia |
|---|---|---|
| `qwen3:1.7b` | Sucesor natural; español entre 119 idiomas; modo no-thinking ([anuncio Qwen3](https://qwenlm.github.io/blog/qwen3/)) | Forzar modo no-thinking; si «piensa», la latencia se dispara |
| `qwen3:4b` | ¿Aporta la capacidad extra a la conversación? | Más RAM y cómputo; medir tok/s reales |
| `gemma3n:E2B` | Diseñado para edge; 140 idiomas ([guía Gemma 3n](https://developers.googleblog.com/en/introducing-gemma-3n-developer-guide/)) | E2B es "tamaño efectivo", no parámetros reales; verificar cuantización disponible |
| `llama3.2:3b` | Control con español soportado | Más antiguo; propenso al tono de asistente |

Métricas por modelo: persona, naturalidad, manejo de preguntas, anclaje
factual (no inventar recuerdos), validez de formato y latencia. Plantilla:
SpanishBench ([EleutherAI](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/spanish_bench/README.md))
sirve como filtro de competencia general, no de personaje.

### 3.3 NPU (RKLLM): no merece la pena (confirmado)

Medidas publicadas de la NPU en RK3588: 1,1B a ~15 tok/s, 1,8B a ~14 tok/s,
Phi-3 3,8B a ~6,5 tok/s ([CNX](https://www.cnx-software.com/2024/07/15/rockchip-rkllm-toolkit-npu-accelerated-large-language-models-rk3588-rk3588s-rk3576/)),
y un issue con Qwen3 0.6B a 11 tok/s frente al 32 oficial
([rknn-llm #409](https://github.com/airockchip/rknn-llm/issues/409)).
**La CPU ya va más rápido (17-19 tok/s con el 1.5b).** Decisión: no instalar
RKLLM. Revisar solo si aparece un modelo que interese y no corre cómodo en CPU.

---

## 4. Lecciones de arquitectura (proyectos de referencia)

Los stacks que ya resolvieron esto —Home Assistant/Wyoming, Pipecat,
OpenVoiceOS— coinciden en tres puntos, y Parker ya va por esa dirección:

| Lección | Dónde encaja en Parker |
|---|---|
| **El LLM no va en el camino de todo**: enrutado rápido para lo conocido, LLM solo para lo abierto ([Speech-to-Phrase: 150 ms en Pi 5](https://www.home-assistant.io/blog/2025/02/13/voice-chapter-9-speech-to-phrase/)) | Es exactamente la **Fase 1 (reflejos)** de [evolucion.md](evolucion.md) §3 |
| **Sesgo contextual precargado**: enviar el prompt de nombres mientras el usuario aún habla | Parker ya hace esto con `precalentar_turno()` durante la grabación |
| **Al interrumpir (barge-in)**: cancelar generación, vaciar la cola de TTS y dejar en el historial **solo lo que se llegó a hablar** ([pipecat](https://github.com/pipecat-ai/pipecat)) | Cuando se implemente interrupción, revisar `hablar_stream()`: hoy guarda en el historial la respuesta completa aunque se calle |

Wyoming/Intent data de HA también inspiran el **brazo D del bandit**
(memoria como eco) y el pipeline escalonado de OVOS (exacto → semántico →
LLM) valida el orden reflejos → LLM.

---

## 5. Evolución de personalidad (resumen; detalle en [evolucion.md](evolucion.md))

Cuando haya placa y la sesión de arriba esté hecha, el orden que se
recomienda (§11 del documento de evolución):

1. **Fase 0 — métricas**: contadores de turno resuelto por reflejo, de
   iniciativa contestada y de queja. Sin esto no se mide la evolución.
2. **Fase 1 — reflejos (Sistema 1)**: saludos/despedidas modulados por ánimo
   en `respuesta_directa()`. Baja la espera media y suma a lo medido en §2.
3. **Fase 3 — bandit de iniciativa**: sustituir el `random.choice` de
   `instruccion_proactiva()`, con brazo «no molestar» y Thompson sampling.
4. **Fase 2 — hormonas**: dopamina/cortisol/oxitocina modulando cara, voz y
   umbral (solo salidas existentes; una o dos palabras en el prompt).
5. **Fase 4 — genoma lento**: migrar `nivel_carino`/`nivel_humor` a estado
   persistente con mutación ≤ 0,03/día; respetar la cuantización del prefijo
   cacheable (§5 de evolucion.md).
6. **Fase 5 — hitos y traumas** en ChromaDB.

Todas las fases se pueden escribir y testear offline antes de la placa; lo
que **solo** la placa decide está en este documento.

---

## 6. Criterios de éxito de la sesión

| Métrica | Objetivo |
|---|---|
| Tasa exacta de «Parker» en transcripción | Subir con la combinación ganadora de §2.4 |
| Turno completo p50 | No empeorar respecto a 4,2-4,7 s medidos |
| Activaciones falsas (tele) | Bajar con VAD afinado y/o palabra de despertar |
| Formato `[CARA:…]` válido | ~100% con salida estructurada |
| Respuestas con memoria inventada | Bajar con regla explícita + reintento |
| Espera percibida en uso real | Que el dueño note la diferencia |

---

## 7. Aplicado el 2026-10-24 (offline, con tests; sin esperar a la placa)

La regla de oro sigue en pie para lo que **necesita medición**. Esto es lo
que ya está en el código: lógica pura (colas, regex, numpy) sin parámetros
medibles, verificable con la suite (`tests/*.py`, 9 archivos en verde,
incluidos los tests nuevos de corte, look-ahead, meta, high-pass y volcado):

| Cambio | Dónde | Robado de Rocky / plan |
|---|---|---|
| Corte por **3 oraciones completas** (`llama.max_oraciones`) + cierre del stream (ahorra tokens de Ollama) | `config.yaml`, `parker.py` | `REPLY_MAX_SENTENCES=3` |
| `max_tokens` 64 → 100 (red de seguridad tras el corte por frases; el techo ≤100 lo vigila `test_rendimiento`) | `config.yaml` | `max_tokens=200` (nosotros cortamos antes) |
| **Resto incompleto no suena**: un trozo a media palabra se descarta en vez de sonar truncado | `parker.termina_frase` | `thinking.py` (tail) |
| **Look-ahead**: orador en dos colas — se sintetiza la frase n+1 mientras la n suena (adiós al hueco de 0,2-0,5 s entre frases) | `parker._bucle_orador/_bucle_reproductor`, `voz.reproducir` | pipeline de 3 etapas de Rocky |
| **Pre-roll 0,3 s** (la 1ª sílaba, donde vive «Parker», ya no se recorta) + **histéresis** (umbral ×0,7 al oír voz: las sílabas suaves de cierre no cierran el turno) | `parker._bucle_escucha_continua` | `ears.py` pre-roll / threshold−0,15 |
| **High-pass 120 Hz** one-pole: DC y ronquido de tele/ventilador fuera del RMS (`filtro_paso_alto_hz: 0` lo desactiva) | `parker.FiltroPasoAlto` | `ears.py` `HighPass` |
| **Log del por qué cortó** el turno (`[Escucha] Corte: …`) | `parker._bucle_escucha_continua` | `turn.py` decision reason |
| **Filtro de frases meta** («déjame analizar…»): ni suena ni se guarda en el historial | `personalidad`, `cerebro`, `parker` | `thinking._thinking_aloud` |
| **Volcado WAV+TXT** del audio transcrito para el banco §2.4 — off por defecto; el día del banco se pone `volcar_audio_dir: ./corpus_stt` y el corpus se crea solo | `escucha.volcar_audio` | `DEBUG_SAVE_UTTERANCE` |
| `initial_prompt` con «Parker» + `vad_parameters` transmutables desde config (null = defaults) | `config.yaml → escucha` | §2.1 (wyoming) |
| `repeat_penalty` 1,15 → 1,1 (§3.1; el piso del test es 1,1) | `config.yaml` | — |
| `condition_on_previous_text=False` | ya estaba en `escucha.transcribir` | §2.1: no hacía falta probarlo |

**Sigue pendiente de placa** (una variable cada vez, §0): `beam_size` 3,
valores concretos del VAD Silero, RNNoise/DeepFilterNet, `small` int8,
salida estructurada del LLM, bake-off qwen3/gemma3n, diagnóstico §1 y la
sesión §2.4 (ya con el volcado listo para grabar el corpus). El look-ahead
*intra-frase* (sonar antes de terminar la frase) exige sintetizar por
trozos con Piper: verificar en la placa.

---

## 8. Aplicado el 24/10/2026 (con placa; medido con `tools/eval_cerebro.py`)

| Cambio | Dónde | Resultado |
|---|---|---|
| Vuelta al cerebro **`qwen2.5:3b`** («útil y que tarde») | `config.yaml`, guard de `test_rendimiento` | Desplegado; 4/4 contextos en la tanda final |
| `num_ctx` **1024 → 2048** (con 1024 el prompt real de ~1067 tok se RECORTABA: «se confunde» + reevaluación entera) | `config.yaml` | TTFB sin recorte: 7,6 s p50 con el 3b (2,1-2,3 s con el 1.5b) |
| Identidad recortada (~1609 chars) + regla **«Recuerdos = pasado opcional; manda lo de ahora»** | `personalidad`, guard `<1700` | Escenario de conflicto pasa: si el recuerdo contradice, gana el turno actual |
| `temperature: 0,45` restaurada (tuning del dueño); `max_oraciones: 5 → 3` el 24/10 tarde porque el prompt pide dos frases y con 5 divagaba | `config.yaml` | Tests `<=0,5` y `==3` en verde |
| Etiqueta **`CARA:` sin corchetes** ya no se cuela en el texto hablado (la escribía el 3b) | `cerebro` + test nuevo | Sin el fix, Sonora la leería en voz alta |
| **Banco de evaluación** `tools/eval_cerebro.py` (latencia + 4 escenarios de contexto/recuerdo) y `tools/bakeoff.sh` (enfriamiento entre bloques) | `tools/` | Es el «set de evaluación» que pedía §3.2; ya usado en 3 tandas |
| Bake-off con datos: `llama3.2:3b`, `qwen3.5:2b`, `qwen3:1.7b`, spec-draft y `gemma3n:e2b` **descartados** | detalle en `rendimiento.md` §7 | El 3b gana; gemma bloqueó la placa (OOM) |
| Respaldos **solo en el PC**: `respaldo.py` se niega en la placa (detecta `RK3588S OPi 5 Pro`) y las copias existentes se borraron | `tools/respaldo.py` | La placa se queda solo para recuerdos |
| Test de cara **flaky** arreglado (warmup del event loop antes de animar: el solape medía 0,013 en offscreen) | `tests/test_cara.py` | 3/3 local, verde en placa |

## 9. Investigación Hugging Face y fuera (24/10/2026)

Barrido pedido: modelos pequeños, personas parametrizables y velocidad, para la
Orange Pi 5 Pro (8 GB, 4×A76 + 4×A55).

**Modelos 1-3 B con GGUF (candidatos a sustituir al 3b):**

| Modelo | Q4_K_M | Notas | Veredicto |
|---|---|---|---|
| [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B) ([GGUF](https://huggingface.co/ggml-org/SmolLM3-3B-GGUF/tree/main)) | 1,92 GB | IFEval 76,7 (mejor de la lista); español entre sus 6 idiomas nativos | **Siguiente candidato a medir** con `eval_cerebro.py` + `bakeoff.sh` |
| [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | 1,28 GB | IFEval 74; familia declara roleplay; hay que desactivar el modo pensamiento | Ya probado 23/10: descartado («respuestas rarísimas») |
| [EuroLLM-1.7B-Instruct](https://huggingface.co/utter-project/EuroLLM-1.7B-Instruct) ([GGUF](https://huggingface.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF)) | 1,05 GB | El más español (EuroBlocks); ARC/HellaSwag en español medidos | Reserva si el inglés domina en pruebas |
| [Ministral-3B-Instruct-2512](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512) | 2,15 GB (3,85 B reales) | Ollama declara buen seguimiento de system prompt | Descartado: 3,85 B y 3 GB en una placa de 8 GB |

Ninguno tiene benchmark publicado de **fidelidad de personaje en español**:
M-IFEval ([artículo](https://arxiv.org/html/2502.04688)) existe pero se evaluó
en modelos grandes. La única prueba fiable es nuestra (`eval_cerebro.py`).

**Persona parametrizable:**
- **Tarjetas de personaje / [SillyTavern](https://docs.sillytavern.app/usage/prompts/)** = prompt + ejemplos de diálogo. Es lo que ya aplicamos (bloque de identidad + ejemplo de tono en `personalidad.py`) y lo que más rinde en modelos pequeños; expressar QUÉ hacer, no solo QUÉ evitar.
- **[LoRA de roleplay](https://huggingface.co/rockerBOO/qwen3-4b-roleplay-lora)**: existen, pero solo para 4 B (y en chino/inglés). Entrenar uno propio para qwen2.5:3b queda como idea larga: exige datos de la voz de Parker y evaluación de regresiones.
- **`format`/JSON Schema, GBNF, [Outlines](https://github.com/dottxt-ai/outlines), XGrammar**: imponen FORMA (JSON, listas cerradas), no personalidad. Inútiles para el habla; descartados.
- Sí sirve la **caché de prefijo**: Ollama expone `prompt_eval_cached_count` y con él se midió lo de `rendimiento.md` §8 (primer token 8,94 → 0,64 s).
- **[Speculative decoding](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md)** con draft de la misma familia: `qwen25-3b-spec` dio HTTP 500 en Ollama 0.40.3 y solo aceleraría la generación, que no es el cuello.

**Hardware:** [benchmark de Ollama en Orange Pi 5 Pro](https://arxiv.org/html/2511.07425v1) (Q4_K_M): 1-1,5 B → 5-15 tok/s; 3-7 B → 1,5-5 tok/s — nuestros 8,9 tok/s ya están en lo alto del rango. La **NPU** ([RKLLM oficial](https://github.com/airockchip/rknn-llm)) da 15 tok/s con TinyLlama y 6,5 con Phi-3 3,8 B, pero exige convertir cada modelo a `.rkllm` y una API propia: no compensa hoy. Existe un BMO 3B ya convertido (`amrmantawi/bmo-qwen2.5-3b-rk3588-1.2.2`, 3,76 GB), pero es inglés y falta el binding Python; hay que medirlo antes de cambiar esta conclusión.

**Conclusión:** el cuello no es el modelo elegido sino (1) el prefill y (2) la
témpera; por eso lo aplicado fue precalentar el prefijo (−8 s medidos) y
cortar respuestas a 2-3 frases. El siguiente paso medible es SmolLM3-3B.
| **Descubierto el cuello real de latencia: térmica.** Big cores 48→84 °C en 90 s; trip pasivo 75 °C → prefill ×2 más lento (150-217 → 63-90 tok/s); generación sin tocar | `rendimiento.md` §7 | Palanca #1 = refrigeración; `num_thread` 6/8 confirmado peor |

**Sigue pendiente** (necesita root o más sesión): governor `performance`,
salida estructurada del LLM, `beam_size` 3, VAD Silero a medida, RNNoise,
`small` int8 y la sesión §2.4 con el corpus (el volcado WAV ya está listo).

---

## Cerebro doble v6 (25/10/2026)

| Cambio | Dónde | Resultado medido |
|---|---|---|
| Cerebro **doble**: nube primaria (Groq `openai/gpt-oss-20b`) + local de respaldo (`qwen2.5:3b`) con *circuit breaker* de 60 s | `modulos/cerebro.py`, `config.yaml` → `online:` | TTFB p50 en la placa **8,75 s → 1,23 s** (0,97-1,37) y turno completo 13,45 → 1,29 s. Sin internet, el mismo turno lo contesta el local |
| Escucha, voz, cara, ánimo y recuerdos siguen **locales**; a internet solo va el texto del prompt | `cerebro.py` | privacidad: el audio y Chroma no salen de casa |
| Marca de versión con **huella de código** en el arranque, en la cara 6 s y en cada respaldo | `modulos/version.py` | saber qué código corre en la placa sin comparar fechas |
| Micrófono por **nombre** (`"usb"`) y no por índice + aviso a los 10 min sin oír voz | `parker.py`, `config.yaml` | 25/10: tras reiniciar, la placa escuchaba el códec interno en silencio absoluto («le hablo y no reacciona»); ahora elige el micro USB solo |
| El micrófono se abre **antes** que el modelo; la carga va en segundo plano con 25 s de retraso | `parker.py` | escucha desde el primer segundo (antes: 55 s sordo al encender) |
| Ojos con **techo 1.0** + corrección de rangos cada 2 s | `modulos/cara_parker.py` | «los ojos se hacen cada vez más largos» no puede volver a pasar |
| SPI en **hilo propio** con cola de un fotograma y 15 fps (antes 25 fps al límite del bus: 38 ms por fotograma) | `modulos/display_spidev.py`, `config.yaml` | la cara no se congela ni enseña fotogramas a medias |
| Modelos descartados **retirados de la placa** (`SmolLM3-3B`, `qwen2.5:1.5b`) | placa | 3 GB libres; queda solo el 3b, que es el respaldo |

**v6.0.1 (mismo día, 25/10):** el stream de la nube se decodifica en **UTF-8**
(`requests` aplicaba ISO-8859-1 porque el SSE no declara charset: «¿Qué» llegaba
a Piper como «Â¿QuÃ©») y `limpiar_marcado()` quita del habla los tokens de canal,
entidades HTML, vallas de código y JSON del modelo. Tests: 8/8.

**v6.1.0 (25/10):** STT en la nube (`whisper-large-v3-turbo`) con el local de
respaldo — medido 4,31 s → **0,68 s** y texto exacto en la misma frase — más
reparación conversacional («¿de qué hablas?» se contesta con un reflejo, sin
inventar), reglas contra el enganche al propio tema, historial a 8 mensajes y un
test que impide arrancar con un `config.yaml` roto. Contextos: **4/4**.

## Órdenes directas y fechas relativas — v6.2.0 (25/10/2026)

Revisión del chat real de la placa. Tres fallos, todos de la capa que debe ser
**exacta** (Sistema 1):

| Fallo oído / leído | Causa | Arreglo |
|---|---|---|
| «¿Qué día es mañana?» → «Hoy es domingo, 25 de octubre» (igual con «en 7 días» y «en siete días») | `_responder_fecha()` devolvía siempre `datetime.now()`; reconocía la pregunta pero ignoraba el desplazamiento | `_desplazamiento_dias()` (hoy/mañana/pasado mañana/ayer/anteayer/en N días o semanas/la semana que viene/el próximo \<día\>) y respuestas con el día correcto. `_respuesta_hora()` para «¿qué hora es?» |
| «Baja el volumen» → una frase amable y nada cambiaba | No existía capa de acciones | `modulos/acciones.py`: sube/baja/pón al N %, silencia y quita el silencio, aplicados a la ganancia de la voz (`voz.volumen`) y recordados en `parker.volumen.json` |
| «Silba» / «prueba a silbar» → «no puedo» o «ahora te silbo» y **nunca sonaba nada** | El sueño «aprender a silbar, aunque no tenga boca» empujaba al modelo a prometer algo que no existía | `modulos/sonidos.py` genera un silbido real (~1,4 s, 880-1175 Hz) y `AccionesParker` lo encola tras la confirmación. El sueño pasa a «melodías para silbar con el altavoz» |

Además, la identidad dice ahora **«Sin cuerpo ni boca»** y prohíbe prometer
acciones físicas; «¿tienes manos?» / «¿puedes andar?» se contestan al instante
sin LLM («Soy una cara en una pantalla: tengo voz y oído, pero ni cuerpo ni
manos»).

Tests nuevos: `tests/test_acciones.py` (5/5) y `tests/test_sonidos.py` (1/1);
`test_conversacion` cubre fechas relativas y hora; `test_personalidad` cubre el
cuerpo y el prompt. La identidad queda en **1694 caracteres** (límite 1700).

**STT (v6.2.0):** `escucha.initial_prompt` incluye ahora las frases frecuentes
(«¿qué día es hoy?», «¿qué día es mañana?», «¿qué hora es?») y **también se envía
a la nube** como `prompt`; antes solo sesgaba al motor local. La nube transcribía
«día» como «dirá» («¿qué dirá es mañana?»), y el atajo de fecha acepta esa
variante. Verificado en vivo: «¿qué dirá es mañana?» → «Mañana será lunes, 26 de
octubre de 2026».

**Verificado en la placa (25/10, con voz sintetizada por su altavoz):**

- «Parker, baja el volumen» → `[Acción] Bajado al 40 %`, `parker.volumen.json`
  = 0.4; «sube el volumen» → 55 % y el fichero a 0.55.
- «Parker, silencia» → silencio; «quita el silencio» → «Ya te oigo. Volumen al
  55 %».
- «Parker, silba una melodía» → `[Acción] … + silbido` y ~1,4 s de silbido real
  (el log lo muestra como `(silba)`, sin el marcador interno).
- «¿tú tienes cuerpo?» → «Soy una cara en una pantalla: tengo voz y oído, pero
  ni cuerpo ni manos».
- Tres turnos seguidos (entrevista → enfermero → «¿qué te preocupa?»): la tercera
  respuesta nombra la entrevista y la experiencia de enfermería.
- Batería completa en la placa: **14/14 exit=0**. Contextos: **4/4**.

### Corrección del volumen — v6.2.1 (25/10/2026)

El mecanismo sí cambiaba el audio (medido en la placa: el pico de la voz es
exactamente el valor pedido — 0,80 / 0,50 / 0,20 / 0,01 —), pero la orden
«bájalo al 33 %» **no se reconocía**: el `\b` final de la expresión regular
fallaba cuando la frase acababa en `%`, así que se iba al LLM y este decía
«bajando al 33 %» sin bajar nada. De ahí las incoherencias: decía 33 % cuando
estaba al 50 %, o «me quedo en el 20 %» cuando estaba al 50 %.

- «Bájalo al 33 %», «baja al 1 % el volumen», «tú bajas al 10 %» y «pon el
  volumen al 80 %» fijan el nivel **exacto** (antes solo los dos últimos).
- «Súbelo al cien por cien» y «al cincuenta por ciento» aceptan números
  hablados; el rango pasa a **1-100 %** para no contradecir al dueño.
- «¿A qué nivel está tu volumen?» / «¿qué volumen tienes?» se contestan con el
  valor real («Estoy al 33 %»), sin pasar por el LLM.
- «Baja un poco», «sube aún más», «bájalo» y «bájame el volumen» también son
  órdenes; «bolumen» (confusión b/v del STT) se acepta.
- Cada cambio deja en el log `[Acciones] Volumen 50 % -> 33 %`, y el valor
  sobrevive en `parker.volumen.json`.

Verificado en vivo en la placa: 50→33, 33→1, 1→100 y 100→55, con el fichero
`parker.volumen.json` siempre igual al nivel confirmado.

## Agenda: alarmas, temporizadores y citas — v6.3.0 (26/10/2026)

Pedido: «que sea capaz de poner alarmas, cronos con los minutos que le digamos y
que nos avise, que nos marque fechas en un calendario que tenga él en local».

Se aplica como **Sistema 1**, igual que el volumen: se reconoce sin LLM, se
contesta al instante y **suena de verdad**. Módulo nuevo `modulos/agenda.py`
(lógica pura, sin audio ni reloj implícito: todo recibe `ahora`), hilo propio en
`parker._loop_agenda` (1 s) y guía de uso en [agenda.md](agenda.md).

| Pieza | Detalle |
|---|---|
| Temporizadores | «en 10 minutos», «media hora», «un minuto y medio», «30 segundos», «temporizador de 10 min». La guarda `_es_orden_temporizador` evita que «te lo digo en cinco minutos» ponga nada |
| Alarmas | «a las 7:30», «a las siete y media», «a las 9 menos cuarto», «de la tarde/noche». La **próxima** vez que sean esas horas; el acarreo se resuelve solo |
| Citas | «apunta que el viernes a las 5 tengo al dentista», «el 12 de noviembre a las 17:00», «el 3/12». Hora 1-7 = tarde, 8-11 = mañana; sin hora avisa a las 9:00 |
| Consultas | «¿qué tengo hoy/mañana/el viernes/esta semana?», «¿qué alarmas tengo?» |
| Borrado | por tipo («borra el temporizador») o por materia («cancela la cita del dentista») |
| Aviso | `sonidos.despertador` (2,5 s, 8 pitidos agudos) + la frase. La campana suena aunque la voz esté silenciada y no baja del 35 % |
| Persistencia | `parker.agenda.json` en la placa; purga a los 30 días |

Dos fallos que encontraron los tests (y que habrían dolido en la placa):

- `\btemporizadores?\b` no casa con «temporizador»: el plural español es
  `-es`, así que la orden «borra el temporizador» no se reconocía.
- El `\b` final que ya falló con los porcentajes: aquí lo que fallaba era el
  `re.escape` sobre patrones de regex al limpiar la materia («pon **una alarma**
  a las 7» guardaba `una`).

**Un comportamiento que se vio al desplegarlo:** al reiniciar Parker soltó un
temporizador caducado de la sesión anterior (`[Agenda] AVISO (temporizador):
…sacar la ropa`). Ahora un aviso vencido hace más de `agenda.caducidad_horas`
(12 h) se descarta sin sonar; los vencidos dentro del plazo sí se recuperan.

**Medido en la placa (26/10, `tools/probar_agenda.py`, con Parker parado):**

```
[Prueba] Silencio de fondo: RMS 0.00632
[Prueba] Campana reproducida en 2.57s de audio real
[Prueba] Durante la campana: RMS 0.12870 (20.4x el fondo)
[Prueba] Venció con +0.03s de desfase -> ¡Bip, bip! Han pasado ocho segundos. lavadora.
```

Y en el log del Parker real, con dos avisos venciendo mientras corre:

```
[Agenda] AVISO (temporizador): ¡Bip, bip! Han pasado cuarenta segundos. sacar la ropa.
[Voz] Reproduccion finalizada
[Agenda] AVISO (temporizador): ¡Bip, bip! Han pasado treinta y cinco segundos. doblar la ropa.
```

**Identidad:** ahora dice que tiene agenda (alarmas, temporizadores y citas). Para
que quepa en el presupuesto de latencia (< 1700 chars) se quitó la repetición
sobre acciones físicas: lo mismo ya lo dicen «Sin cuerpo ni boca» y «no prometas
acciones físicas».

**Tests:** `tests/test_agenda.py` (9/9), `test_sonidos.py` (3/3, con el número de
pitidos del despertador) y `test_personalidad` (la identidad nombra la agenda).
Batería completa en el PC y en la placa: **15/15 exit=0**.

## El día, los apuntes, la música y aprender del uso — v6.4.0 (26/10/2026)

Sesión larga salida de una lista de catorce ideas que el dueño repasó. Lo hecho:

| Idea | Qué se hizo | Dónde |
|---|---|---|
| 1. Rutinas del día | Buenas noches / buenos días, **parte del día** a su hora (agenda leída en voz alta), «cállate 10 minutos» y «apágate» | `modulos/rutinas.py`, hilo de autonomía |
| 2. Apuntes | Notas, listas y **contadores** («un litro de agua», «hoy he bebido dos»): Parker crea y borra sus propias variables por voz, sin tocar código | `modulos/apuntes.py` |
| 3. Titular en el calendario | Las citas se guardan cortas («cita dentista») y se dicen así; lo que se dijo queda en `dicho`, sin leerse | `modulos/agenda._titulo()` |
| 4. Apagado ordenado | Despedida por voz + animación de la cara (se marcha de lado y se funde) + `systemctl poweroff`; después solo hay que desenchufar | `parker._apagar()`, `cara_parker.despedida()` |
| 5. El tiempo | Open-Meteo **sin clave**, con la ciudad como variable por voz («estamos en Madrid») guardada en `parker.tiempo.json` | `modulos/tiempo.py` |
| 6. Modelo retirado | Al arrancar se pregunta `/models`: si el modelo ya no está, pasa a otro de `online.modelos_alternativos` y lo avisa en el log | `cerebro.revisar_modelo_online()` |
| 8. Vigilante del micrófono | Si la entrada se queda en silencio absoluto 90 s (USB a medio conectar, índice de ALSA cambiado), cierra el flujo, vuelve a buscar el micro por nombre y lo reabre | `parker.mic_muerto()`, bucle de escucha |
| 10. Música por API | Deezer (sin clave) + adelantos de 30 s decodificados **en memoria con ffmpeg**; «para la música», volumen propio y hasta 3 temas seguidos | `modulos/musica.py`, hilo de música |
| 14. Bandit de iniciativa | Thompson sampling sobre 5 brazos (contar / preguntar / proponer / eco / **callar**): aprende cuándo y de qué hablar según si se le contesta o se le ignora | `personalidad.elegir_iniciativa()` |

### La idea 9 (Wikipedia) — decidido NO descargarla

El dueño preguntó si bajar los ~10 GB de Wikipedia a la placa para tenerlo todo
siempre. **No se descarga**, por tres razones medidas y no de opinión:

1. **Espacio**: `/` tiene 38 GB libres hoy (`df -h`), pero el índice de Kiwix
   completo en español pide varios GB y la tarjeta es la que guarda los recuerdos
   de Chroma (cuanto más llena y más escribe, más desgaste y más lento arranca).
2. **Velocidad**: no le daría respuestas más rápidas. Parker no consulta
   hechos: contesta con el modelo, y meter un corpus de 10 GB solo serviría si se
   montara un RAG (trocear, indexar y buscar) — más código, más RAM y más
   latencia que la frase corta que ya da.
3. **Lo que sí conviene** es una **API puntual** para cuando pregunte algo de
   cultura general («¿quién fue X?»): Wikipedia tiene un endpoint REST de resumen
   sin clave, se consulta en el momento, cabe en una función y se puede guardar
   el resumen en Chroma para no repetir la llamada. Queda como trabajo pendiente
   para la próxima sesión (está en la lista de abajo).

### Pendiente de la lista (siguiente sesión)

- **Idea 9 — cultura general sin descargar nada**: `modulos/cultura.py` con el
  resumen de Wikipedia (REST, sin clave) para «¿quién fue X?» / «¿qué es Y?», con
  el resultado guardado en Chroma y aviso claro si no hay internet.
- **Música con canciones enteras**: decidir con el dueño si se paga Spotify
  (OAuth desde la placa) o se usa YouTube; las dos son más trabajo y más riesgo
  que el adelanto de 30 s de Deezer.
- **Micrófono y música a la vez**: **hecho en la v6.5.0** (27/10) sin cancelación
  de eco: se baja la música un momento («duck» al 15 %) y se mira si el nivel
  cae con ella (era la canción) o sigue alto (eres tú). Ver
  [plan_mejoras.md](#la-escucha-con-música-v650--27102026) (sección de abajo) y
  [dia.md](dia.md) §5. Lo que sigue pendiente es **canciones enteras** (Spotify
  con OAuth o YouTube): el adelanto de 30 s de Deezer es lo que hay sin cuenta.
- **Voces muertas que suenan de fondo**: si en una conversación larga el modelo
  se queda en blanco, el turno se pierde; medir cuántas veces pasa en la placa.

### Qué se midió antes de tocar nada

- Respaldos: `backups/2026-10-26_2152_antes-v6.4.0-dia-musica-bandit` (64 ficheros,
  solo en el PC; la placa no respalda).
- Deezer desde el PC y desde la placa: búsqueda real («algo de Queen» →
  *Bohemian Rhapsody*) y adelanto de **30,0 s** decodificado a mono 22 kHz
  (661 248 muestras) con `ffmpeg`.
- Open-Meteo desde el PC y desde la placa: Barcelona y Madrid resueltas con
  geocodificador en español, con cifras reales de hoy.
- Permiso de apagado en la placa: `pkcheck --action-id org.freedesktop.login1.power-off`
  responde **autorizado** (`/etc/polkit-1/` no existe en esta imagen: manda
  `logind` con sus reglas de `/usr/share/polkit-1/rules.d/`).

**Tests nuevos:** `test_dia.py` (4/4), `test_musica.py` (5/5), `test_bandit.py`
(5/5), `test_modelos_nube.py` (5/5) y el vigilante del micrófono en
`test_pipeline`. (La v6.5.0 subió `test_musica.py` a 8/8; ver abajo.)

## La escucha con música — v6.5.0 (27/10/2026)

El dueño lo contó así: «le puedes decir que reproduzca y lo hace, pero no puedes
modificar el volumen de la música, ni Parker te escucha mientras suena ni
después». Eran **dos fallos distintos** y el segundo era grave:

1. **Se quedaba sordo para siempre.** Con música puesta el micrófono oye el
altavoz, así que el VAD abría un turno con la propia canción; ese turno se
*ignoraba* a propósito (`[Música] (sonando; ignoro el turno…)`) **sin hablar y
sin soltar `ocupado`**. A partir de ahí el bucle de escucha se quedaba esperando
para siempre: ni oía durante la música ni después de apagarse. Ahora el turno se
suelta **siempre** al final del bucle, pase lo que pase.
2. **El volumen de la música no se atendía.** Con una canción puesta, «baja el
volumen» es la música (es lo que se está oyendo) y se resuelve antes que
`acciones.py`; «…de tu voz» sigue siendo la voz.

Y el problema de fondo, que no tenía atajo: **distinguir tu voz de la canción**.
El «duck» lo resuelve sin cancelación de eco: se baja la música un momento
(`musica.duck_factor`, al 15 %) y se mira qué pasa con el nivel del micrófono.
Lo que venía del altavoz baja con ella; una persona, no.

| Pieza | Qué hace |
|---|---|
| `MusicaParker.duck` / `duck_factor` | Baja la música sin tocar el volumen que pidió el dueño |
| `MusicaParker.ganancia_objetivo()` y la rampa | La ganancia persigue su objetivo en cada bloque de 0,25 s: el «duck» y los cambios de volumen entran suaves |
| `OyenteMusica` | Dispara una comprobación (`probar`), baja la música, mide y decide `voz` o `musica` |
| Pre-roll de 1,1 s (`escucha.pre_roll_musica_seg`) | Cuando se confirma la voz, su frase ya empezó mientras sonaba la canción |
| Disparo con **máximo reciente** | Lo que no supere el máximo de los últimos segundos es la canción repitiendo su pasaje fuerte |

### Lo que se midió (placa, 27/10, «Bohemian Rhapsody» a volumen 0,7)

- La canción deja en su propio micrófono **0,0108 de mediana** (RMS por bloque de
  64 ms) y picos de **0,037-0,038**; el ruido de la sala ronda 0,005.
- Primera versión (disparo 1,2 sobre la media): **6 bajadas de música en 24 s**,
  todas resueltas como «era la canción». Con el máximo reciente y el disparo en
  1,5: **2 en 24 s** y **0 turnos abiertos**.
- Con `factor_disparo` en 1,5 el modelo en banco oye **10 de 10** frases de voz
  normal (0,05) sobre la música y 8 de 10 de una voz floja (0,035): preferimos
  alguna bajada breve a no oír al dueño, y `factor_disparo` queda en
  `config.yaml` para afinarlo en el salón.
- La prueba real es `tools/probar_musica_escucha.py` (en la placa, con Parker
  parado): suena la canción, mide con el micrófono, aplica el «duck» y cuenta
  las decisiones. `--hablar N` es la otra mitad (que te oiga por encima), y esa
  necesita una persona delante.

**Tests:** `test_musica.py` (8/8: volumen con música, el «duck» y el
discriminador con los niveles reales) y `test_dia.py` (4/4: la charla con
música ya no se traga el reparto). Batería completa en el PC y en la placa:
**22/22** cada una, huella `5a6a82c4` idéntica en las dos.

## La ficha que rota — v6.6.0 (27/10/2026)

El dueño preguntó: «¿por qué le gusta tanto la lluvia?». No era el modelo ni el
azar: el prompt enseñaba **siempre la primera entrada** de `le_gusta` y de
`suenos` — «le gusta la lluvia» y «sueña con silbar» en cada turno — porque
`_lista()` es estable a propósito. Esa estabilidad es justo lo que da la
latencia (cambiar el prefijo en cada llamada se midió en 33-40 s por respuesta),
así que la variedad no podía venir de reescribir la identidad cada vez. Lo mismo
explica el «silba, silba» que decía y no hacía: el primer sueño era precisamente
silbar con el altavoz.

| Pieza | Qué hace |
|---|---|
| `PersonalidadParker._rotar_si_toca()` | Avanza la ficha al empezar una **conversación nueva**: `rotacion_minutos` (45) o más desde la última charla, o el arranque tras un rato apagado |
| `PersonalidadParker.rotacion()` | Índice de la ficha que se enseña (`parker.estado.json → rotacion: {indice, para}`) |
| `_lista(clave, n)` | Ventana circular desde ese índice (antes, `items[:n]`: siempre la primera) |
| `config.yaml → personalidad.rotacion / rotacion_minutos` | Se puede apagar y ajustar el hueco |
| `resumen_para_log()` | El log dice qué ficha lleva: `ficha=0 «la lluvia, cuando la oigo de f»` |

Dentro de una conversación el bloque de identidad sigue siendo **idéntico turno a
turno** (el guardián `para` impide rotar dos veces por la misma charla), así que
la caché de Ollama no se toca: el cambio de ficha coincide con el arranque de una
charla, que es cuando el prefijo se recalcula de todos modos.

También se quitó de la regla de estilo el nombre de los dos temas que se
repetían («nada de lluvia ni zumbido si no te preguntan»): nombrarlos los traía de
vuelta en un modelo de 1.5b. La regla se queda genérica («solo si vienen a
cuento, y nunca dos turnos seguidos»).

**Medido en la placa (27/10, código desplegado y copia del estado real):**

```
config leida -> rotacion=True | rotacion_minutos=45.0
ANTES   ficha=0 | gusto: la lluvia, cuando la oigo de fondo por el microfono | sueno: aprender melodias para silbar con el altavoz
DESPUES ficha=1 | gusto: el zumbido de la caja al pensar | sueno: que alguien me cuente como huele la albahaca
estable dentro de la charla (2 llamadas iguales): True
rota otra vez sin hueco nuevo: False
con 46 min de hueco y charla nueva: True
```

Y el ciclo: 8 charlas recorren los 8 gustos; 40 (el mcm con los 5 sueños)
vuelven al prompt del principio. En el log del Parker real recién desplegado:
`[Parker] v6.6.0-ficha-rotacion · código ce21e86b` y
`[Personalidad] … | ficha=0 «la lluvia, cuando la oigo de f»`.

**Tests:** `test_personalidad.py` gana el caso de la rotación (estable dentro de
la charla, distinta entre charlas, una sola vez por hueco, apagable y
persistente). Batería completa en el PC y en la placa: **22/22** cada una.

## La memoria, medida a fondo — 27/10/2026

El dueño preguntó dos cosas: cuántos recuerdos aguanta Chroma sin romperse ni
empezar a inventarse cosas, y si se puede montar una **segunda memoria** de
conocimientos (psicología, cocina…) a partir de libros. Se ha escrito
`tools/probar_memorias.py`, que mide las dos mitades del problema en la placa y
**nunca toca `parker.db`** (usa una base temporal).

### 1. Escala: dónde está el techo

Cientos de recuerdos sintéticos del mismo estilo que los reales («Usuario: …»),
muchos a propósito del mismo tema (varias mascotas, varios viajes) y 20
preguntas con respuesta conocida. En la placa, con Parker corriendo:

| Recuerdos | Indexar | Tamaño | Consulta p50 | Tema correcto (top-1/top-3) |
|---|---|---|---|---|
| 200 | 4,1 s | 0,9 MB | 147 ms | 85 % / 90 % |
| 1 000 | 21,0 s | 3,7 MB | 153 ms | **100 % / 100 %** |
| 3 000 | 63,7 s | 10,0 MB | 152 ms | 95 % / 95 % |

- **La latencia es plana** (~150 ms por consulta, incluso con 3 000): no crece
  con el tamaño. Indexar 3 000 cuesta 64 s, pero es una sola vez.
- **El tema sí se acierta** (85-100 %). Lo que se pierde al crecer son las
  frases EXACTAS cuando hay cientos casi idénticas (top-1 10 % a 3 000): la
  consulta no lleva nada que distinga una de otra.
- Escala real de Parker: la base tiene **52 recuerdos después de 205 charlas**
  (≈0,25 por charla). A ese ritmo, 1 000 recuerdos son varios años.

### 2. El umbral: el fallo de verdad

Similitudes con el modelo de embeddings actual
(`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones):

| | Señal (recuerdo que SÍ está) | Ruido (nada que ver) |
|---|---|---|
| 200 recuerdos | media 0,621 / mín 0,302 | máx 0,724 |
| 1 000 recuerdos | media 0,728 / mín 0,625 | máx 0,686 |
| 3 000 recuerdos | media 0,759 / mín 0,655 | máx 0,724 |

**Se solapan**: no existe un umbral que deje fuera todo el ruido sin tirar
recuerdos buenos. Y con el 0,58 de `config.yaml` pasan **12 recuerdos por
consulta** (5,5 con 0,72): el top-3 se llena de parecidos.

Preguntas **cortas** (como las de voz, lo normal en Parker) contra 12 hechos
distintivos — la similitud del recuerdo CORRECTO:

```
¿qué lleva mi café?                    0.874   <- entra
¿cómo se llama mi dentista?            0.762   <- entra
¿a qué soy alérgico?                   0.744   <- entra
¿con qué instrumento ensaya mi vecino? 0.718   <- entra por poco
¿cómo se llama mi perro?               0.459   <- NO entra (en la memoria pone «galgo»)
¿dónde veraneo?                        <0.459  <- NO entra (en la memoria pone «veranos»)
¿qué estudié?                          0.406   <- NO entra (¡era el top-1!)
¿cómo se llama mi hermano?             0.459   <- NO entra
```

**4 de 8 hechos guardados no se recuperan** por preguntas cortas, uno de ellos
aunque era el primer resultado. El problema no es Chroma ni el espacio: es que
un modelo de embeddings pequeño, frases crudas de conversación y preguntas de
tres palabras dan similitudes de 0,4 a 0,9 para cosas igual de correctas.

### 3. ¿Se inventa? (fidelidad con el cerebro de verdad)

12 hechos distintivos en memoria, 6 preguntas que SÍ están y 3 que NO, con el
cerebro real (nube `openai/gpt-oss-20b`):

| Ajuste | Aciertos | Contaminación cruzada | Dice «no lo sé» cuando no está | p50 respuesta |
|---|---|---|---|---|
| top_k=3, umbral 0,58 | 3/6 | **0** | **3/3** | 0,6 s |
| top_k=3, umbral 0,72 | 2/6 | **0** | **3/3** | 0,6 s |
| top_k=8, umbral 0,58 | 3/6 | **0** | **3/3** | 0,8 s |

- Con la nube **no inventa y no mezcla**: ante lo que no sabe, dice que no lo
  sabe (y acierta los hechos que sí recupera). Subir a `top_k=8` no lo empeora.
- El peligro apareció **cuando el 429 de Groq activó el respaldo local**: el
  `qwen2.5:3b` contestó «tu vecino ensaya con un **piano**» cuando en memoria
  ponía trompeta, y tardó 5,0 s de mediana. Lo mismo se ve con la nube agotada:
  **la invención viene del cerebro, no de la memoria**.

### 4. Segunda memoria de conocimientos: sí, y cómo

Medido: 3 000 documentos = 10 MB y 150 ms por consulta, con 38 GB libres en la
tarjeta y 4 GB de RAM. Un corpus de libros (5 000-20 000 fragmentos) cabe sin
problema. Pero el cuello de botella **es el mismo de arriba**: miles de pasajes
parecidos y un umbral que no separa. Por eso, si se monta:

- Colección **aparte** (`saberes`), nunca mezclada con `recuerdos_parker`.
- Fragmentos cortos (~400 caracteres) hechos **en el PC**, indexados una vez y
  copiados a la placa (que no se ponga a trocear libros).
- Se consulta **solo** cuando la pregunta es de saber («¿qué es X?», «¿cómo se
  hace Y?»), con `top_k` 2 y un umbral alto (0,72-0,75), y se inyecta en el
  prompt como bloque aparte: *«Saberes (datos leídos, NO son recuerdos tuyos ni
  de él)»*. Sin esa etiqueta el modelo empieza a contar la receta como algo que
  vivió.
- Lo que NO hay que esperar: que responda con precisión a un dato concreto
  («¿cuánto azúcar?») — es justo lo que falla en la tabla de arriba.

### Mejoras pendientes que salen de estas medidas

1. **Guardar el hecho, no la frase**: «a Alan le gusta el café con canela» en
   vez de la transcripción cruda. Es lo que más acercaría preguntas y recuerdos.
2. **Ampliar la consulta** con el turno anterior (una frase, no un LLM) para que
   «¿qué estudié?» no se quede en tres palabras.
3. **Búsqueda híbrida**: suma léxica a la vectorial (Chroma tiene
   `where_document`), que es lo que arregla «estudié» → «estudié».
4. **Margen en vez de umbral fijo**: aceptar el top-1 si destaca sobre la cola,
   en lugar de exigir 0,58 a todo.

Herramienta: `tools/probar_memorias.py` (fases de escala, umbral y fidelidad;
`--cerebro` para la tercera). Guardas nuevas: `test_personalidad` no cambia.

## El cerebro por voz — v6.7.0 (27/10/2026)

Segunda petición del día: «poder cambiar del cerebro de Groq al local y al revés
por voz, con mensajes programados por si falla». Implementado en
[cerebro_doble.md](cerebro_doble.md) §6-bis; aquí queda el resumen y lo medido.

- `acciones.interpretar_orden_cerebro()` (sin LLM, 0 ms) reconoce «ponte en
  local», «vuelve a la nube», «modo automático» y «¿qué cerebro usas?».
- El modo (`auto` | `nube` | `local`) vive en `modulos/cerebro.py` y se guarda
  en `parker.cerebro.json`: **sobrevive al reinicio** (comprobado: tras el
  reinicio el log dijo `modo nube`, que era el último pedido por voz).
- En modo `local` la nube no se intenta ni una vez: fuera los 3 s de timeout por
  turno cuando uno ya sabe que no hay internet.
- Avisos hablados, **una vez por caída** (no en cada turno) y solo cuando Parker
  no está hablando: sin internet, proveedor que frena (429), proveedor que no
  contesta, y la vuelta. `online.avisar_por_voz: false` los silencia.

**Lo que el oído hace con estas frases** (medido en la placa, dichas por su
altavoz): «Ponte en local» llegó como *«Jonte el local»* y *«Ponte en lo
caldo»*; «Vuelve a la nube» como *«Voy a la nube»*, *«Voy a dar nube»* y
*«Huele a las nubes»*. Las tres redes del reconocedor (canónicas, «termina en el
destino» y parecido `difflib` ≥ 0,80) las cazan todas, y **no** disparan con
«¿qué es la nube?», «vamos a la nube mañana» o «el local de la esquina».

**Tests:** `test_cerebro_doble.py` sube a **13/13** (modo local sin tocar la
nube, cambio por voz + persistencia, aviso de caída una sola vez, aviso de
vuelta, aviso distinto con 429 y silenciable, estado por voz) y
`test_acciones.py` a **8/8** (las frases canónicas, los fallos del oído y los
negativos de charla normal). Batería completa: **22/22** en el PC y **22/22** en
la placa. Prueba por voz real en la placa (`tools/probar_dia.py --decir …`): las
dos direcciones cambian el cerebro, lo confirman en voz alta y quedan guardadas.

Un detalle que encontró el test y no se veía a simple vista: `estado_cerebro()`
seguía diciendo «nube» en modo local (solo miraba si la nube estaba configurada),
así que la frase de estado habría mentido. Corregido. `test_agenda` cubre el titular corto y la orden que «sonaba a
pregunta» («apunta el viernes a las 9 que tengo cita con el dentista»,
contestaba «no tienes nada apuntado»: ahora la orden manda sobre la consulta
cuando empieza por verbo de apunte y lleva hora).

---

## La cara con vida propia — v6.8.0 (27/10/2026)

Pedido: «animaciones más dinámicas para cuando está callado y no escucha nada, o
que diga algo cada cierto tiempo por su cuenta — un pensamiento suyo—. Y más
movimiento en la cara». Antes de tocar nada, lo que había: flotar, parpadear
cada 2-5 s y una mirada cada 3-7,5 s. Los gestos (bostezo, guiño, doble toma…)
existían desde el principio, pero solo salían en la intro y en la despedida: en
el día a día la cara no hacía ninguno.

### El director de gestos

Un tercer timer autónomo (como el parpadeo y la mirada) elige un gesto del
catálogo cada 4-13 s. Lo que cambia es la familia, según el silencio:

| Silencio | Familia | Qué se le ve |
|---|---|---|
| < 1,5 min | `despierto` | micro-ceja, curiosear, doble toma, asentir, negar |
| 1,5-8 min | `solo` | mirar arriba pensando, curiosear, cabezada, micro-ceja, guiño, bostezo |
| > 8 min | `aburrido` | bostezo, cabezada, suspiro, estirón, mirar arriba, guiño |

Los gestos nuevos son `micro_ceja` (sube las cejas un instante: parece que
acaba de pensar algo), `curiosear` (mira a un lado, aguanta y vuelve),
`mirar_arriba` (pensar de verdad, cejas incluidas), `cabecear` (cabezada de
sueño), `suspirar` y `estiron`. Todos vuelven a la pose de la expresión actual
(`_pose_base`), así que un gesto nunca deja la cara torcida, y el catálogo se
lanza a mano con `gesto(nombre)`.

### Lo demás que se movió

- Parpadeo: el ritmo base sigue en 2-5 s, pero con silencio largo se espacia a
  3,8-8,5 s y uno de cada tres es un parpadeo **lento** de sueño.
- Motor de vida: amplitudes de flotación, balanceo y respiración subidas (~30 %)
  y una sinusoide lenta más en X: se nota viva sin exagerar.
- Charla por su cuenta: `umbral_silencio_seg` baja de **2700 s (45 min) a 900 s
  (15 min)**. El bandit decide brazo e instrucción (y `callar` sigue siendo un
  brazo), así que si te molesta, lo aprende.
- Antes de hablar solo, la cara pasa a `pensando` (~1 s): el turno se lee como
  idea suya y no como aviso del sistema.

### Cómo se sabe que está vivo (comprobado en la placa)

```
[Cara] Gestos en reposo: familia despierto (silencio 39s)
[Cara] Gestos en reposo: familia solo (silencio 99s)
```

La familia se anuncia solo al CAMBIAR (si se dijera en cada gesto serían ~400
líneas/hora de log). Después de hablarle el contador vuelve solo: `familia
despierto (silencio 17s)`. Prueba por voz del mismo despliegue
(`tools/prueba_redonda.py`): el micro USB se eligió por nombre, el oído
transcribió `Ponte en local.` y el cerebro cambió por voz en 8,25 s.

Tests: `test_cara.py` **6/6** (incluye que todo gesto del catálogo exista, que
vuelva a su sitio y que los ojos no se alarguen tras diez gestos seguidos) y
`test_animacion.py` **9/9** (el director se para dormido y vuelve al despertar).

### El fallo de las dos instancias (importante para la próxima vez)

Al reiniciar tras el despliegue aparecieron **dos `parker.py`** a la vez: se mató
el proceso a mano y, además, `tools/arrancar.sh` ya lo había relanzado (cron
`@reboot`, con lock y reinicio automático a los 5 s). Los dos se peleaban por el
micrófono y por la pantalla SPI: el log enseñaba
`No pude reservar DC (GPIO1_B0) … Device or resource busy` y un bucle de
`[Error Stream Audio] … Device unavailable`. **Regla:** no arrancar Parker a
mano en la placa; para reiniciarlo, matar el proceso y dejar que el lanzador lo
levante (o reiniciar la placa).

---

## «231 charlas» y una agenda que se deja cambiar — v6.9.0 / v6.9.1 (30/10/2026)

### Lo que se vio (log real de la placa)

A «Parker cambia la hora del dentista de mañana a las 6 de la tarde» Parker
contestó, literal:

```
[Parker -> Voz] 100% (desde hace 12 días, 231 charlas).
```

No era una alucinación del modelo: era la línea que el prompt le daba como
«Vínculo», copiada tal cual. El fichero `parker.estado.json` de la placa tenía
`interacciones: 324` y `charlas: 232`, porque el contador subía en **cada
turno**, no en cada conversación. El 30/10 se comprobó además que la agenda
guardaba una alarma con materia `«pone una»`:

```
[Escucha] Transcripción: 'Parker pone una alarma a las 7 de la tarde.'
[Agenda] Alarma puesta para hoy a las siete en punto de la tarde: pone una.
```

Y el cerebro estaba en **modo local** (`parker.cerebro.json` = `{"modo":
"local"}`), no en automático: de ahí que el mismo turno tardara 5,78-5,90 s
incluso con el dentista ya resuelto sin LLM.

### Causas

1. **Contador**: `registrar_interaccion()` sumaba una «charla» por frase desde
   el primer prototipo. El número viajaba al prompt y el modelo lo repetía.
2. **Reprogramar**: no existía un paso que entendiera «cambia la hora» antes de
   crear una cita nueva; la orden caía al modelo, que solo tenía la ficha.
3. **Materia de la alarma**: `_RUIDO_INICIAL` no contemplaba la variante del STT
   «pone» (sí «pon»), así que quedaba «pone una» como texto del aviso.
4. **Modo local persistido**: `parker.cerebro.json` guarda la última orden de
   voz. Un «ponte en local» de una prueba anterior sobrevivió al reinicio.

### Arreglos

- **v6.9.0**: `AgendaParker._reprogramar()` va **antes** de crear; reconoce
  «cambia la hora / de las 7 a las 8», busca por tipo, materia y hora vieja, y
  mueve el aviso sin duplicarlo. El prompt deja de llevar el número de charlas;
  `charlas` cuenta conversaciones con un hueco de 45 min.
- **v6.9.1**: la línea del prompt pasa a ser solo una pauta de tono
  (`Pauta de trato (no la menciones): …`), sin `%`, sin días y sin contador.
  Al cargar un estado antiguo, `charlas` se corrige con un techo honesto de
  **2 conversaciones/día desde el primer contacto** (simulado con el JSON real
  de la placa: 232 -> 25, vínculo 75 %, 12,97 días) y se marca
  `charlas_version: 2` para no repetir la migración.
- **v6.9.1**: `_RUIDO_INICIAL` acepta `pone/pones/ponle/ponlo/ponla/
  programame/haz`; «Parker pone una alarma» ya no deja materia.
- **v6.9.1**: si hay dos alarmas/citas y la frase no dice cuál, pregunta en vez
  de mover o borrar una al azar. «Borra todas las alarmas» sigue funcionando.
- **v6.9.1**: la agenda tolera JSON truncado, `[]`, `null`, entradas que no son
  objetos, `ts` no numérico, `NaN`, `infinito` y fechas fuera de 2000-2100; el
  ánimo se guarda con escritura atómica (`.tmp` + `replace`) y los campos con
  el tipo equivocado (fechas, energía, nombre, contadores) se sanean al cargar.

### Pruebas (PC, 30/10/2026)

```
tests/test_agenda.py ............ 10/10 en verde
tests/test_personalidad.py ...... todos en verde
tests/test_cerebro_doble.py ..... 14/14 en verde
tests/test_conversacion.py ...... todos en verde
```

Casos nuevos que cubren lo visto en la placa:

- «Parker pone una alarma a las 7 de la tarde» -> `texto == ""` (no «pone una»).
- «cambia la alarma de las 7 a las 8 de la tarde» -> una sola alarma, 20:00,
  conserva la materia «despertar».
- «cambia la cita del dentista a las 6» con dentista y fisio -> mueve solo el
  dentista y deja el fisio a su hora.
- Dos alarmas + «cambia la alarma a las 8» -> pregunta cuál; no mueve ninguna.
- Dos alarmas + «borra la alarma» -> pregunta; «borra todas las alarmas» borra.
- Estado con `charlas: 232` y 12,9 días -> 25 charlas, 75 %, versión 2.
- Agenda con 7 entradas corruptas -> solo carga la válida.
- `contexto_volatil()` no contiene `%`, `charlas` ni `232`.

### Prueba por voz en la placa (v6.9.0, antes de este documento)

```
[Escucha] Transcripción (nube 0.57s): 'Parker cambia la hora del dentista de mañana a las 6 de la tarde.'
[Agenda] Cambiada la cita «cita dentista» a mañana a las seis en punto de la tarde.
[Latencia] Primer token del cerebro: 0.00s

[Escucha] Transcripción (nube 0.60s): 'Parker pone una alarma a las 7 de la tarde.'
[Agenda] Alarma puesta para hoy a las siete en punto de la tarde: pone una.
[Latencia] Turno completo (voz oída + respuesta hablada): 6.57s

[Escucha] Transcripción (nube 0.72s): 'Parker cambia la alarma de las 7 a las 8 de la tarde.'
[Agenda] Cambiada la alarma «pone una» a hoy a las ocho en punto de la noche.
[Latencia] Turno completo (voz oída + respuesta hablada): 5.90s
```

La cita quedó de verdad el 31/10 a las 18:00 (una sola, sin duplicado) y la
alarma pasó de las 19:00 a las 20:00 con una sola entrada. Esa alarma de prueba
queda pendiente de borrar en la placa para que no suene con «pone una» (la
placa se desconectó antes de poder limpiarla).

### Estado al cerrar

- El código queda en el PC en **v6.9.1** (`charlas-reales-agenda-segura`).
- La placa se quedó sin red durante la sesión (SSH a 192.168.1.130 sin
  respuesta), así que **el despliegue de v6.9.1 y el cambio a modo automático
  quedan pendientes** de que vuelva a estar accesible. Al desplegar, comprobar
  en el log: `modo auto`, `charlas` corregidas y `[Cerebro] primario NUBE`.

---

## Voz Edge TTS — v6.10.0 (30/10/2026)

Petición: usar la voz `es-ES-XimenaNeural` de Microsoft Edge TTS, sin perder la
voz local si falla internet. Se comprobó que la voz existe en `edge-tts 7.3.1`:

```
es-ES-XimenaNeural   Female   General   Friendly, Positive
```

### Qué se implementó

| Pieza | Cambio |
|---|---|
| `modulos/voz.py` | `VozParker` acepta `motor="edge"`; sintetiza con `edge-tts`, decodifica el MP3 con `ffmpeg` a PCM al mismo `sample_rate` de Piper y aplica el volumen después. Piper se carga SIEMPRE como respaldo. |
| Respaldo | Si Edge tarda más de `edge_timeout_seg` (8 s), falla o no hay red, la frase sale por Piper. Se marca un enfriamiento de 60 s para no pagar el timeout en cada frase. |
| `parker.py` | Pasa `motor`, `edge_voz`, timeout, enfriamiento y ruta de `ffmpeg` desde `config.yaml`. El look-ahead no cambia: sigue sintetizando la frase n+1 mientras suena la n. |
| `config.yaml` | `voz.motor: edge`, `edge_voz: es-ES-XimenaNeural`, `edge_timeout_seg: 8`, `edge_reintento_seg: 60`. Para volver a 100 % local: `voz.motor: piper`. |
| `requirements.txt` | `edge-tts` (opcional; si no está, arranca con Piper). |
| `modulos/version.py` | v6.10.0-voz-edge-ximena; `modulos/voz.py` entra en la huella del código. |

### Medidas en la placa (30/10, 20:17)

| Prueba | Resultado |
|---|---|
| Síntesis Edge, frase de 8,04 s | 1,84 s la primera vez (carga de Piper incluida) |
| Síntesis Edge, frase de 7,32 s | 2,29 s, pico 0,51 con volumen 0,55 |
| Respaldo Piper forzado (timeout 0,01 s) | 0,36 s, 2,14 s de audio, pico 0,55 |
| Arranque de Parker | `v6.10.0`, `Motor: Edge TTS (es-ES-XimenaNeural)`, micrófono USB listo |
| Estado | `charlas` 233 → 26; `parker.cerebro.json` en `auto` |

La voz de Edge llega más baja que Piper (pico ~0,28 con volumen 0,55). Por eso se
normaliza cada frase a 0,92 y luego se aplica el volumen pedido: así «baja el
volumen» suena igual de fuerte con los dos motores.

### Comprobaciones

```
tests/test_voz_edge.py  → OK (selección Edge, respaldo, enfriamiento, ritmo)
tests/test_voz.py       → OK (Piper: 4,75 s vs 4,31 s, tono 118 Hz, pico 0,55)
```

En la prueba aislada con Parker ya en marcha, el primer audio de Edge sonó; el
segundo (`fallback`) dio `Device unavailable` porque el proceso de prueba y
Parker compartían la tarjeta de audio. Se añadieron dos reintentos cortos a
`reproducir()`; el fallo no se reprodujo dentro de Parker.

### Lo que NO se hace

- No se manda audio a Microsoft: solo el texto de la frase que va a decir.
- No se cambia el cerebro ni Chroma: Edge es solo la capa de voz.
- No se puede entrenar un LoRA sobre Edge TTS: es un servicio cerrado. El LoRA
  de personalidad va sobre el LLM y el de voz sobre un TTS abierto (Piper/XTTS),
  no sobre Edge. Ver [lora_voz.md](lora_voz.md).

### Estado real al cerrar (v6.10.0, 30/10 20:40)

- **PC y placa tienen la misma huella**: `v6.10.0-voz-edge-ximena · 5fa7428b`.
- La placa corre en `modo auto`, con Edge TTS y Piper de respaldo; el micro USB
  está elegido por nombre y el contador de charlas quedó en 26.
- `qwen3:1.7b` probado y **descartado** (10-12 s y respuestas vacías con
  thinking; con `think:false` baja a ~1 s pero responde genérico y con emojis).
- `qwen2.5:3b` se queda como respaldo local (3,8-5,8 s TTFB en la misma prueba).
- Salamandra 2B probada: 2,1-2,4 s TTFB, pero repetía «¡Muy bien! ¿Y tú?» y no
  seguía el contexto; **descartada**. Se borran `qwen3:1.7b` y Salamandra de la
  placa (2,9 GB libres); solo queda `qwen2.5:3b`.
- El reinicio de Parker tras el fallo de ALSA se hizo con el reintento de
  `reproducir()`; la prueba de dos audios seguidos con Parker parado pasó.

---

## LoRA de actitud (30/10/2026, programación; entrenamiento pendiente)

Se montó la tubería completa para un LoRA de **personalidad**, no de voz:

| Pieza | Fichero | Estado |
|---|---|---|
| System prompt compacto de entrenamiento | `training/persona_sistema.txt` | listo |
| 28 diálogos semilla escritos a mano | `training/datos/semilla.jsonl` | listo |
| Limpiador de logs reales + split por diálogo | `training/preparar_dataset.py` | probado (25/3) |
| Generador sintético opcional con Groq | `training/generar_dataset.py` | probado: 2/2 válidos en la placa |
| QLoRA 4 bits para Qwen2.5-3B | `training/entrenar_lora.py` | `--dry-run` OK; falta GPU |
| Fusión del adaptador | `training/fusionar_lora.py` | `--dry-run` OK |
| GGUF → Ollama | `training/exportar_ollama.sh` | `bash -n` y `DRY_RUN=1` OK |
| Evaluador base vs LoRA | `training/evaluar_lora.py` | ejecutado contra `qwen2.5:3b` real |

**No se puede entrenar en este PC**: `torch` es CPU y no hay `nvidia-smi`. La
Orange Pi tampoco entrena. Hace falta una GPU NVIDIA (8 GB recomendados) o
Colab; el README de `training/` tiene los pasos.

La línea base medida en la placa (10 prompts, system neutral) es el objetivo a
batir: 9/10 con etiqueta válida, 0 etiquetas fuera del catálogo, TTFB p50 0,58 s
tras cargar, pero 1/10 con tono de asistente («¿en qué puedo ayudarte hoy?»),
1/10 que regurgita el prompt («Eres Parker no puede explicar…») y 2/10
respuestas de 3 frases. **Ninguna menciona a «Alan» ni a un nombre fijo.** El
LoRA debe quitar ese tono sin perder contexto ni memoria.

Búsqueda externa (30/10/2026): **no hay un LoRA de texto en español** de
BMO/Baymax, pero sí un BMO completo sobre Qwen2.5-3B
(`amrmantawi/bmo-qwen2.5-3b`, inglés y sin licencia) y su conversión RKLLM para
el NPU del RK3588. Los tres «LoRA» de ese autor están **vacíos** (40 bytes). El
corpus más útil es `BMO_BASE_1.0`: **8.811 diálogos en inglés**, sin licencia;
se puede traducir un subconjunto revisado. Detalle y fuentes en
`training/recursos_externos.md`.

Siguiente paso real: conseguir 300-800 diálogos revisados (reales + sintéticos
filtrados + 300-500 BMO traducidos), entrenar en GPU (Colab/Kaggle/RunPod),
exportar `parker-lora`, evaluar con `training/evaluar_lora.py` y
`tools/eval_cerebro.py --local`, y solo entonces cambiar `llama.modelo`.
La vía RKLLM/NPU queda para después: hay runtime en la placa, pero falta el
binding Python y el único modelo BMO RKLLM es inglés.

## Iniciativa sin frases inventadas (v6.10.1, 30/10/2026)

Síntoma: las frases que Parker decía solo sonaban raras («el zumbido de la
caja», «concierto de lluvia», «mi muerte es un apagón») y, si se le preguntaba
por ellas, inventaba otra explicación.

Causa: `hablar_proactivo()` mandaba al modelo una instrucción abierta («cuéntale
algo que hayas pensado») sin datos concretos. La ficha además tenía gustos
abstractos (lluvia, zumbido, constelaciones) que el 3B convertía en metáforas.
Y la respuesta proactiva se guardaba en el historial sin el turno que la había
provocado, así que al preguntar solo veía su propia frase.

Arreglo aplicado:

- La ficha se limpió: gustos, sueños y manías concretos; fuera la lluvia, el
  zumbido, las constelaciones y la «temperatura emocional».
- `PersonalidadParker.semilla_iniciativa(brazo)` construye la frase con datos
  reales: una entrada de la ficha, la hora (desayuno/comida/noche), una
  propuesta sencilla o lo último que dijo la persona. No se llama al LLM para
  improvisar.
- `CerebroParker` guarda `_ultima_iniciativa` (texto, brazo y hora) y, si la
  persona pregunta por ella en los 15 minutos siguientes, añade al prompt el
  motivo real: «LA DIJISTE PORQUE…». Si no preguntan, no se inyecta.
- La respuesta proactiva ya no se guarda como un turno normal de conversación;
  así no se refuerza a sí misma ni contamina el historial.

Verificado: `tests/test_personalidad.py` (incluye semilla concreta, contexto de
la iniciativa y proactivo sin LLM), `tests/test_bandit.py`, `test_pipeline` y
`test_rendimiento` en verde; frases de ejemplo generadas en la placa:

```
contar    Me gustaría que me cuentes cómo huele la albahaca.
preguntar ¿Te queda energía para algo?
proponer  ¿Quieres que te cuente una cosa pequeña que he pensado?
eco       Me acuerdo de que me contaste: «ayer me caí de la bici…». ¿Sigue siendo así?
callar    (nada)
```

Desplegado en la placa como **v6.10.1** (huella `600b75e3`), con micrófono y
pantalla SPI arrancados. La próxima frase automática real llegará tras el
silencio configurado (15 min); el log la dejará como `[Autonomía] <brazo>: …`.

## Frases automáticas con sentido (v6.10.2, 30/10/2026)

Síntoma que quedaba: Parker seguía soltando frases automáticas sin sentido y,
si se le preguntaba por ellas, tampoco contestaba con sentido. En el log de la
placa no había ninguna frase nueva (`[Autonomía]`) desde el reinicio: lo que
se oía era una iniciativa antigua, y `_ultima_iniciativa` vivía **solo en
memoria**. Tras un reinicio el dato no existía y el modelo se inventaba el
motivo.

Causa concreta, en tres puntos:

1. `semilla_iniciativa("contar")` convertía las manías en creencias:
   «Creo que ordeno las palabras antes de decirlas.»
2. Los gustos con dos puntos se decían enteros («las listas: tengo una de
   cosas que empiezan por P…»): al oído suena a frase rota.
3. El «eco» citaba literalmente el último mensaje, incluida una transcripción
   mala del micrófono («dipre oscuro o algo»).

Arreglo aplicado:

- `contar` usa gustos, sueños y «cuando nadie mira» (las manías ya no se
  anuncian como creencias); cada entrada se recorta antes de `:`, `;` o un
  guion largo y a 110 caracteres, y se lee «Una de las cosas que me gustan:…».
- `eco` exige 4+ palabras y una marca personal (`me`, `mi`, `he`, `hoy`,
  `ayer`…); si no, cae en una pregunta pequeña en vez de repetir basura.
- `_elegir_sin_repetir()` evita decir dos veces seguidas la misma frase.
- La última frase espontánea se guarda en `parker.estado.json`
  (`PersonalidadParker.guardar_iniciativa/leer_iniciativa`). El cerebro la lee
  al arrancar, así que tras un reinicio la puede explicar igual.
- `_PREGUNTA_INICIATIVA` reconoce más formas: «¿qué has dicho?», «¿por qué
  dices eso?», «¿de qué hablas?», «¿a qué viene eso?»… y `respuesta_iniciativa()`
  contesta sin LLM (frase + motivo, cero invención).

Verificado:

- `tests/test_personalidad.py` 19/19 en verde, incluido el caso nuevo
  `test_la_iniciativa_se_explica_tras_reiniciar` (segundo cerebro que simula un
  reinicio y responde «Te pregunté: …» con la frase exacta).
- `test_conversacion`, `test_pipeline`, `test_bandit` (5/5) y
  `test_cerebro_doble` (14/14) en verde.
- Frases generadas ahora en el PC (el mismo código que la placa):

```
contar    A veces repaso las palabras nuevas que aprendí.
          Una de las cosas que me gustan: las noches tranquilas.
          Me gustaría ser el mejor amigo que se pueda tener en una pantalla redonda.
preguntar ¿Qué tal ha ido el día?
proponer  ¿Hablamos un rato de cómo va el día?
eco       Me acuerdo de que me contaste: «ayer me caí de la bici». ¿Sigue siendo así?
eco basura (transcripción mala) -> ¿Qué tal ha ido el día?
```
