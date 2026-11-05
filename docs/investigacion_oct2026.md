# Investigación externa para Parker — octubre 2026

> **Qué es esto:** el resultado de tres búsquedas independientes (Hugging Face,
> GitHub y documentación de proveedores) hechas el 30/10/2026 para responder a
> una pregunta: *¿hay algo ya hecho que haga a Parker más listo, más rápido o
> más útil sin cambiar su hardware?* No es una lista de deseos: cada cosa lleva
> su fuente, su tamaño y lo que costaría probarla. **Nada de esta lista está
> instalado todavía**; lo que se implementó ese día es lo de
> `docs/plan_mejoras.md` (charlas reales + agenda segura).

## 1. Modelos: qué probar para el cerebro local

El local actual es `qwen2.5:3b` en Ollama. La placa es una Orange Pi 5 Pro
(RK3588S, CPU-only, 8 GB). Los benchmarks de la misma familia de SoC que se
encontraron (Turing Pi RK3588, **no** la Orange Pi exacta) dan:

| Modelo local (Q4_K_M) | Tokens/s generando | RAM pico aprox. |
|---|---:|---:|
| Llama 3.2 3B | 11,25 | ~4 GiB |
| Qwen2.5 1.5B | 22,6 | ~2 GiB |
| Qwen2.5 7B | 5,44 | ~8,68 GiB (no cabe con holgura) |

Fuente: <https://turingpi.com/llm-inference-benchmarks-rk3588-gguf-quantization/>

Eso no promete nada para la Orange Pi, pero marca la dirección: **en 8 GB, un
1,5-2,5B Q4 es el sitio razonable; un 7B no**.

| Prioridad | Modelo / repo | Tamaño y licencia | Por qué encaja | Riesgo / coste |
|---|---|---|---|---|
| 1 | [Qwen3-1.7B-GGUF](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF) | 1,7B, **Apache-2.0** | Roleplay, multi-turno y español/catalán declarados; pensado para no-thinking. | Hay que apagar el «thinking» y limitar contexto/salida. Sin benchmark en la placa. |
| 2 | [Salamandra 2B Instruct](https://huggingface.co/BSC-LT/salamandra-2b-instruct) + [GGUF Q4_K_M](https://huggingface.co/Novaciano/salamandra-2b-instruct-Q4_K_M-GGUF) | 2,25B, **Apache-2.0** | El BSC sobremuestreó catalán y lenguas cooficiales; es el más específico para Cataluña. | Vocabulario de 256K y sin GQA: el tamaño real en RAM puede ser mayor de lo que sugiere el número de parámetros. No está alineado con RLHF. |
| 3 | [LFM2.5-2.6B-GGUF](https://huggingface.co/LiquidAI/LFM2.5-2.6B-GGUF) | 2,6B, licencia propia LFM | Diseñado para dispositivo; Q4 oficial y ejemplo llama.cpp; español. | No declara catalán; revisar licencia. |
| 4 | [Qwen2.5-3B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) | 3,09B, **Qwen Research License** (no Apache) | Es el control contra el que comparar; su card dice que mejora roleplay y español. | Licencia no permisiva para uso comercial/distribuido. |

**Recomendación:** no cambiar el modelo a ciegas. Medir en la placa, con el mismo
guion de 10 turnos: (a) qwen2.5:3b actual, (b) qwen3:1.7b sin thinking, (c)
Salamandra 2B Q4. Comparar primer token, tokens/s, RAM pico, temperatura y
calidad de 10 respuestas. El ganador sustituye al respaldo local; la nube sigue
siendo el cerebro primario.

## 2. Personaje: LoRA y datos

- No se encontró un fine-tune **español/catalán** de un personaje tipo BMO que
  se pueda usar tal cual. Sí existen modelos BMO **en inglés**:
  [`amrmantawi/bmo-qwen2.5-3b`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b)
  (Qwen2.5-3B completo, 6,18 GB, sin ficha ni licencia) y su conversión
  [`rk3588-1.2.2`](https://huggingface.co/amrmantawi/bmo-qwen2.5-3b-rk3588-1.2.2)
  para el NPU (2 × 3,76 GB `.rkllm`). Sus tres «LoRA» están **vacíos** (40 bytes),
  así que no sirven como adaptador. El corpus
  [`BMO_BASE_1.0`](https://huggingface.co/datasets/bibidentuhanoi/BMO_BASE_1.0)
  tiene **8.811 diálogos en inglés**, sin licencia; se puede traducir un
  subconjunto revisado para tono, no copiar entero. Lo más parecido a un
  fine-tune de roleplay es
  [Nora0.1-1.7B-Finetune](https://huggingface.co/uniqueplayer9102/Nora0.1-1.7B-Finetune):
  LoRA Apache-2.0 sobre Qwen3-1.7B, 4.302 conversaciones de roleplay, con GGUF.
  Es **inglés**, parte del material es adulto y su propia card avisa de que
  pierde detalles y deriva a las ~20 respuestas. Sirve como **receta**, no como
  modelo de Parker.
- [Qwen3-4B-RPG-Roleplay-V2](https://huggingface.co/Chun121/Qwen3-4B-RPG-Roleplay-V2)
  es inglés, 2K de contexto, licencia contradictoria y 4B: demasiado para la
  placa y no encaja con el personaje.
- [PIPPA](https://huggingface.co/datasets/PygmalionAI/PIPPA) y
  [Combined Roleplay](https://huggingface.co/datasets/agentlans/combined-roleplay)
  no son corpus limpios en español.
- [TheFinAI/es-instruction-tuning](https://huggingface.co/datasets/TheFinAI/es-instruction-tuning)
  es datos de instrucciones en español (17,1K filas), no un corpus de personaje.

**Lo sensato:** crear un set pequeño y revisado a mano de diálogos **originales**
de Parker (español y catalán), con ejemplos de: no inventar un recuerdo, decir
«no lo sé», pedir que le repitan, mantener el personaje sin copiar a BMO. Se
puede usar el corpus BMO en inglés como **referencia de tono** y traducir 300-500
diálogos revisados, pero no entrenar con las 8.811 filas en inglés. Entrenar un
LoRA de Qwen3-1.7B o Qwen2.5-3B **fuera de la placa** y comparar. Un LoRA cambia
la voz; no arregla la memoria factual.

## 3. Memoria: dos colecciones con intención, no por accidente

Chroma ya permite colecciones separadas y metadatos; no hace falta cambiar de
base de datos. Fuentes:
<https://docs.trychroma.com/docs/collections/manage-collections> ·
<https://docs.trychroma.com/docs/querying-collections/metadata-filtering>

Diseño recomendado:

- `parker_personal`: recuerdos del dueño, con `source_turn_id`, cita exacta,
  fecha, tipo (`explicit_preference`, `event`, `correction`) y estado
  (`confirmed`/`inferred`).
- `parker_conocimiento`: recetas, psicología, libros; cada chunk con `source`,
  `title`, `page`/`url`.
- **Enrutado explícito**, no por similitud: agenda/alarmas -> agenda
  estructurada; «¿qué te conté de…?» -> personal; «¿cómo se hace…?» ->
  conocimiento. Si es ambiguo, preguntar o buscar en las dos y etiquetar la
  fuente.
- Escribir solo lo que el usuario dijo; no convertir una frase generada por
  Parker en recuerdo del usuario. Si se infiere algo, guardarlo como
  `inferred` y confirmarlo antes de usarlo como hecho.
- Ante una pregunta personal sin recuerdo confirmado: decir «no lo recuerdo» o
  preguntar, no rellenar con una historia plausible.

Herramientas que se miraron y **no** se van a integrar ahora: Mem0 (Apache-2.0,
pero añade otra capa y un LLM de extracción), Graphiti (grafo temporal, mucho
más esfuerzo) y Letta (fuera del alcance de la placa). Sirven como referencia
para el diseño de procedencia.

## 4. Latencia: qué falta de verdad

Parker **ya** hace streaming de frases: el cerebro entrega deltas, se cortan en
oraciones completas y se encolan a Piper sin esperar la respuesta entera
(`parker._hablar_stream_interno`). Eso es lo que la investigación recomienda
como cambio nº 1, y ya está.

Lo que se midió en la placa el 30/10: STT 0,57-0,72 s; primer token 0,00 s en
órdenes de agenda; turno completo 5,78-5,90 s **en modo local**. El modo local
persistido era la causa principal de la lentitud, no la arquitectura.

Lo que sí se puede probar después, por orden de rentabilidad:

1. **VAD/endpointing más corto**: Silero VAD tarda <1 ms por chunk de 30 ms;
   Pipecat documenta `stop_secs=0.2`. Parker corta con 0,6 s de silencio; bajar
   a 0,3-0,4 s ahorra 0,2-0,3 s, con riesgo de cortar al usuario.
   <https://github.com/snakers4/silero-vad> ·
   <https://docs.pipecat.ai/pipecat/learn/speech-input>
2. **ASR en streaming** (sherpa-onnx / whisper.cpp stream / Vosk) para no
   esperar al transcript final. sherpa-onnx declara Linux ARM64 y RK3588.
   <https://github.com/k2-fsa/sherpa-onnx>
3. **Caché de prefijo**: Groq la hace automática para GPT-OSS 20B/120B (50% de
   descuento en tokens cacheados, sin coste extra); el prompt estable ya va
   primero. <https://console.groq.com/docs/prompt-caching>
4. **Modelos**: Groq mantiene `openai/gpt-oss-20b` como producción; el viejo
   `llama-3.1-8b-instant` se apagó el 16/08/2026 (salvo enterprise). El código
   ya elige sustituto si retiran el modelo.
   <https://console.groq.com/docs/models> ·
   <https://console.groq.com/docs/deprecations>
5. **TTS**: Piper medium es ~RTF 0,10 en RK3588; Kokoro en Raspberry Pi 4 mide
   RTF 2,774 (más lento que tiempo real) y no es una mejora de velocidad.
   Mantener Piper. <https://turingpi.com/whisper-cpp-piper-tts-arm64-turing-pi-rk3588/>

Objetivo realista: **1-3 s desde que el usuario calla hasta el primer audio**,
no 1 s en todos los turnos. Para eso hay que instrumentar por stage (fin de voz,
endpoint, transcript, primer token, primera frase, primer audio) y medir p50/p95.

## 5. Funciones que encajarían (para hablar, no implementadas)

| Idea | Qué aporta | Esfuerzo | Riesgo |
|---|---|---|---|
| **Repetir alarmas** (diaria, laborables) | Lo más pedido por el uso real; ya hay agenda base. | Medio | Cambia el modelo de datos; hay que migrar avisos. |
| **Posponer / parar alarma por voz** («cinco minutos más», «para») | Cierra el ciclo del aviso; hoy solo suena. | Bajo-medio | Hay que distinguir «para» de «para la música». |
| **Aviso previo** («10 min antes de la cita») | Utilidad inmediata para dentista/médico. | Bajo | Fechas y zona horaria. |
| **Parte del día** (mañana: citas + alarmas + tiempo) | Parker toma la iniciativa con algo útil. | Bajo | Ya existe `rutinas`; solo falta el resumen. |
| **Listas de compra / notas** | «Apunta leche», «¿qué tenía que comprar?». | Medio | No confundir con agenda; `apuntes` ya tiene contadores. |
| **Segunda colección de conocimiento** | Recetas/psicología separadas de los recuerdos. | Medio | Enrutado y calidad de fuentes. |
| **Kiwix offline** | Wikipedia/recetas sin internet en la placa. | Medio-alto | Ocupa tarjeta; hay que elegir un ZIM pequeño y no la Wikipedia entera. |
| **Rutina de repaso de español** | Flashcards con repetición espaciada. | Bajo-medio | No es el objetivo principal; puede esperar. |
| **Home Assistant** | Luces/enchufes por voz. | Medio | Depende de tener HA y red estable. |
| **Estados de cara tipo BMO-ESP32** | 25 moods, lip-sync, reacciones al tacto. | Bajo (ideas) | La cara ya tiene gestos; no copiar el stack cloud. |

Fuentes de las ideas: [OVOS alerts](https://github.com/OpenVoiceOS/ovos-skill-alerts) ·
[Home Assistant local calendar](https://www.home-assistant.io/integrations/local_calendar/) ·
[BMO-ESP32](https://github.com/AlleyBo55/BMO-ESP32) ·
[Reachy Mini conversation app](https://github.com/pollen-robotics/reachy_mini_conversation_app) ·
[Robot Buddy](https://github.com/0mdb/robot-buddy) ·
[Kiwix tools](https://github.com/kiwix/kiwix-tools) ·
[OpenVoiceOS](https://github.com/OpenVoiceOS/ovos-core)

## 6. Lo que NO se recomienda

- Meter un 7B local en 8 GB: no cabe con holgura y baja a ~5 tokens/s.
- Cambiar Piper por Kokoro «porque es pequeño»: en Raspberry Pi 4 mide más
  lento que tiempo real; no hay dato de Orange Pi que lo justifique.
- Entrenar un LoRA con PIPPA o diálogos de BMO copiados: licencias y personaje
  ajeno. Mejor datos propios y originales.
- Bajar el endpoint a 0,1 s sin probar: se corta al usuario a media frase.
- Usar la wiki entera de 10 GB en la tarjeta de arranque: mejor un subconjunto
  en NVMe o Kiwix bajo demanda.

## 7. Qué haría yo primero (cuando la placa vuelva)

1. Desplegar v6.9.1 y poner `parker.cerebro.json` en `{"modo":"auto"}`.
2. Medir 10 turnos reales con `tools/medir_latencia.py` en modo auto y local;
   guardar p50/p95 por stage.
3. Probar `qwen3:1.7b` como respaldo local con el mismo guion; si gana, cambiar
   `config.yaml` y repetir.
4. Implementar «repetir alarma» + «posponer 5 minutos» + «parar alarma» (es lo
   que más se usa y no necesita modelo).
5. Solo después: segunda colección de conocimiento y enrutado.

---

## Prueba local del 30/10/2026: qwen3:1.7b contra qwen2.5:3b

Se descargó `qwen3:1.7b` (1,4 GB) y se midió en la Orange Pi 5 Pro con el prompt
real de Parker (`tools/eval_cerebro.py --local`).

| Modelo | TTFT (thinking por defecto) | Respuesta | Veredicto |
|---|---:|---|---|
| `qwen3:1.7b` | **10,0-12,5 s** | vacía (el *thinking* consume los 100 tokens) | No sirve así |
| `qwen2.5:3b` | **3,8-5,8 s** | coherente, en español, sin marcado | Se queda |

Con `think: false` en la API, `qwen3:1.7b` baja a **0,4-1,0 s** al primer token,
pero en las dos pruebas respondió «¿Cómo te llamas?» y metió emojis; el 3B
contestó con más sentido y sin emojis. Para Parker manda el contexto y la
coherencia, no solo el TTFT: **no se cambia el modelo local**.

Nota: `qwen3:1.7b` tiene *thinking* activado por defecto en Ollama y
`CerebroParker` no manda `think: false`; si algún día se quisiera usar, habría
que añadir esa opción al payload y volver a evaluar calidad, no solo latencia.

Salamandra 2B (BSC, español/catalán) se descargó y se midió al final:

| Modelo | TTFT | Total | Respuesta típica | Veredicto |
|---|---:|---:|---|---|
| Salamandra 2B | **2,1-2,4 s** | 2,9-3,5 s | «¡Muy bien! ¿Y tú?» repetido; una vez recuperó el tema del silbido | Rápida, pero no mantiene contexto |

Salamandra es la más rápida de las tres, pero en 3 de 4 turnos contestó lo
mismo y no siguió la conversación. **No se cambia**: `qwen2.5:3b` sigue siendo
el respaldo local por coherencia, aunque tarde 1-2 s más. Los dos modelos
probados se borran de la placa para no ocupar espacio (2,9 GB).

Conclusión: para este caso, bajar de 3B a 1.7-2B no compensa; la latencia que
importa es la de la nube y el respaldo local debe entender el contexto. La
mejora real del local tendría que venir de un LoRA de personalidad sobre un
modelo que ya sea coherente, no de otro modelo más pequeño.

## 8. Proyectos abiertos tipo Jarvis (01/11/2026)

Se revisaron los proyectos de asistentes abiertos que más se acercan a Parker.
No hay un «Jarvis» completo que se pueda instalar tal cual, pero sí piezas
concretas: la interrupción de Pipecat, el *endpointing* de Smart Turn v3.2, la
palabra de activación de openWakeWord y el orden de persona/fallback de
OpenVoiceOS. El detalle, con licencias y qué no adoptar, está en
[[proyectos_jarvis]].
