# Rendimiento y latencia

Objetivo: que Parker **empiece a responder antes de que notes la espera**.
Este documento recoge el presupuesto medido en la Orange Pi 5 Pro, qué se ha
cambiado para llegar ahí y las alternativas que quedan por explorar. Todos los
números son de la placa, no estimaciones.

---

## 1. Cómo medir

Parker imprime cada etapa en el log:

```
[Latencia] STT: 1.79s
[Latencia] Primer token del cerebro: 1.04s
[Latencia] Fin de frase lista para hablar: 1.38s
[Latencia] Turno completo (voz oída + respuesta hablada): 4.4s
```

Lo que importa es **cuándo empieza a sonar**: silencio de corte + STT + primera
frase + síntesis de esa primera frase. El resto (terminar de generar, hablar
frases siguientes) ya ocurre mientras Parker habla.

Tests sin hardware:

```bash
python tests/test_pipeline.py       # streaming, corte de frases, cola de voz
python tests/test_personalidad.py   # prompt, ánimo, integración con el cerebro
python tests/test_rendimiento.py    # top_k/umbral, formato de recuerdos, config
```

`test_rendimiento.py` protege el modelo, historial, memoria, STT y silencio de
corte configurados para esta versión; la latencia también se protege con tests.

## 2. Presupuesto medido (17/10/2026)

| Etapa | Antes | Ahora | Cómo |
|---|---|---|---|
| Corte de silencio | 1,3 s fijo | **0,6 s** | `escucha.silencio_corte_seg` |
| STT | 4,8-5,3 s (`small`) | **1,6-1,8 s** (`base` int8) | modelo + `hotwords: Parker` |
| Recuperar recuerdos | 0,15-0,18 s | 0,15-0,18 s | ChromaDB + MiniLM (no es el cuello) |
| Primer token del LLM | 6,5-7,8 s (`3b`, prompt 660 tok) | **0,9-1,9 s** (`1.5b`, prompt 398 tok) | modelo + prompt recortado + prefijo cacheado |
| Primera frase completa | 7,5-9 s | **1,3-2,1 s** | reacción corta en el prompt |
| TTS de la primera frase | 0,7-1,4 s | **0,5-0,9 s** | primera frase más corta |
| **Hasta que empieza a sonar** | **15-20 s** | **4,2-4,7 s** | — |

La primera respuesta tras arrancar Parker no comparte carga de CPU con la
escucha: `llama.precalentar: true` carga el modelo antes de activar el micrófono.
La duración depende de que Ollama ya lo tenga cargado (puede tardar 10-40 s si
el runner está frío); se evita que esa espera se mezcle con el primer turno.

## 3. Qué se cambió y por qué

### 3.1 Modelo: `qwen2.5:3b` → `qwen2.5:1.5b`

Medido en la placa con el mismo prompt:

| Modelo | Primer token | Generación | Respuesta completa |
|---|---|---|---|
| `qwen2.5:3b` | 6,5-7,8 s | 9,5 tok/s | 15,5-15,8 s |
| `qwen2.5:1.5b` | 2,1-3,4 s | 17-19 tok/s | 3,1-6,4 s |

`3b` respondía cosas más largas y también citaba el ánimo palabra por palabra y
encadenaba cuatro preguntas; `1.5b` es más corto y más fácil de encauzar con
reglas. En nuestra prueba concreta, el 3B fue mucho más lento (20,8 s/turno
frente a 3,9 s de media para 1.5B) y divagó más; lo dejamos fuera de la
configuración recomendada. Cualquier comparación futura debe usar el mismo
prompt y varios turnos.

**Actualización 24/10/2026 — se vuelve a `qwen2.5:3b`.** Decisión del dueño:
«útil que tarde» gana a «rápido y tonto»: el 3b procesa mejor los contextos y
los recuerdos de Chroma. Con los arreglos de la sesión (`num_ctx: 2048` —el
prompt real llega a ~1067 tok y con 1024 Ollama lo RECORTABA—, identidad
cortada a ~1609 chars y regla «Recuerdos = pasado opcional»), medido con
`tools/eval_cerebro.py` en la placa: **primer token p50 7,6 s** (3,7 s en
frío; 10-12 s cuando los big cores cruzan el trip pasivo de 75 °C),
generación 8,9 tok/s, turno completo p50 ~11,5 s. El 1.5b sigue instalado
como alternativa rápida: cambiar es una línea en `config.yaml`.

### 3.2 El prompt: menos tokens volátiles y reacción corta

La versión actual mantiene contexto suficiente para dos intercambios y tres
recuerdos relevantes; el tamaño del prompt depende de las frases recordadas y
se comprueba en la placa con `prompt_eval_count`.

| Parte | Tokens aprox. | Cambia |
|---|---|---|
| Identidad + reglas (`system`) | estable entre turnos; prompt medido al ejecutar | nunca (cacheable) |
| Historial (hasta 4 mensajes) | variable con la conversación | cada turno |
| Ánimo + hora + recuerdos + pregunta | variable; depende de los recuerdos recuperados | cada turno |

Lo que se hizo:

- `historial_mensajes: 4`: dos intercambios para mantener el tema reciente.
- `top_k_recuerdos: 3`, con relevancia mínima y tamaño acotado; solo se guardan
  recuerdos sobre la persona, no las respuestas del modelo.
- El ánimo se manda en abstracto (`energía media, curiosidad alta, cariño alto`):
  ocupa la cuarta parte y evita que el modelo recite la ficha.
- Se pide una respuesta concreta de una o dos frases, sin muletillas ni
  reacciones prefabricadas; el filtro adicional elimina saludos genéricos ya
  conocidos antes de sintetizar.
- `max_tokens: 100` (red de seguridad) con `max_oraciones: 3` (el corte REAL:
  frases COMPLETAS, estilo Rocky). 24/10 tarde: el prompt pide dos frases y con
  5 el 3b divagaba (coletillas y frases sin sentido) y cada frase extra costaba
  ~4 s a 8,9 tok/s.

La identidad actual ocupa aproximadamente 1.630 caracteres; se mantiene estable
para que Ollama pueda reutilizar su prefijo, y los tests vigilan el límite.

### 3.3 STT: `small` → `base` int8

Audio real de 5,9 s (voz Piper, español), `beam_size=1`, `vad_filter=True`:

| Modelo | Tiempo | Transcripción |
|---|---|---|
| `small` | 4,76-5,33 s | `Oye Parker, hoy he tenido un día tranquilo...` |
| `base` | 1,63-2,03 s | `Oye, parquear, hoy he tenido un día tranquilo...` |
| `tiny` | 1,01-1,33 s | `hoy es para que hoy he tenido un día...` (ilegible) |

`base` comete más erratas en nombres propios, y eso se arregla gratis con
`hotwords: "Parker"` (parámetro de faster-whisper 1.2): la transcripción pasa a
`Oye Parker, hoy he tenido un día tranquilo...`. `tiny` no se usa.

El corte de silencio bajó de 1,3 s a 0,6 s. Es una decisión de producto: sigue
siendo un silencio natural para ceder el turno, y se ahorra en **todas** las
respuestas.

### 3.4 El caché de prefijo: de dónde salían los 2-3 s de más

Midiendo con `/api/chat` se vio que Ollama evalúa el prompt a **60-200
tok/s**, así que cada token volátil cuesta entre 5 y 16 ms. El problema no era
solo el tamaño: era que **el prefijo no coincidía de un turno a otro**.

Dos fallos concretos, ambos corregidos en `modulos/cerebro.py`:

1. El historial guarda el **texto exacto enviado**, con el bloque volátil y
   la pregunta, para no romper el prefijo de Ollama; las respuestas se guardan
   ya limpias de saludos descartados para no enseñar al modelo a repetirlos.
   `test_rendimiento.py` y `test_conversacion.py` comprueban ambas propiedades.
2. Los recuerdos y la hora forman parte del bloque variable; su longitud real
   depende de los hechos recuperados en cada pregunta y se mide con las métricas
   de Ollama, no se supone una cifra fija.

El historial guarda el contenido exacto enviado y conserva dos intercambios,
para que el prefijo siga siendo cacheable y Parker no pierda el hilo. El
precalentado por turno existe como opción experimental, pero queda **apagado**:
al ejecutarlo concurrentemente con Whisper, el TTFB llegó a 24 s. Solo se carga
el modelo al arrancar y antes de activar el micrófono; cualquier cambio se
vuelve a medir con el pipeline real antes de activarlo.

### 3.5 Otras cosas que se probaron y no ayudaron

- **Fijar Ollama a los núcleos grandes (A76, `taskset -c 4-7`)** con un segundo
  servidor: prefill idéntico (2,13 s vs 2,12 s) y generación un poco peor. El
  planificador ya reparte bien; no merece tocar systemd.
- **`num_thread` 6 u 8**: más lento que 4 (contención entre clústeres). Se queda 4.
- **Quitar el historial del todo**: ahorra latencia, pero Parker pierde el hilo
  de la conversación; no compensa.
- **VAD desactivado**: mismo tiempo (el VAD de faster-whisper no es el coste).
- **Recortar los silencios antes del STT**: 1,54 s frente a 1,52 s; no compensa.
- **`cpu_threads` 4, 6 u 8 en faster-whisper**: 1,52 s con 4 y con 8 (6 fue un
  valor atípico). Se deja el valor por defecto del sistema.
- **`num_batch` 1024 en Ollama**: cada cambio de opciones recarga el modelo
  (4-5 s) y el prefill posterior salió más lento; no se toca.

## 4. Cerebro alternativo para RK3588: decisión informada

**Por ahora mantengo Ollama en CPU como runtime principal y no cambio el modelo
ni el servicio a ciegas.** En esta placa medimos Qwen2.5-1.5B a 17-19 tok/s y
3,9 s/turno de media en una prueba concreta. RKLLM es la vía Rockchip para
usar la NPU; la guía Radxa publica 15,44 tok/s para Qwen2.5-1.5B en RK3588,
pero no es una comparación controlada con nuestros mismos prompts, placa,
cuantización o TTFT. Los TOPS de la NPU tampoco se convierten directamente en
tokens/s. No hay datos suficientes para afirmar que la migración vaya a sentirse
más rápida o conversacionalmente mejor.

| Runtime | Ventaja | Coste/limitación | Decisión |
|---|---|---|---|
| **Ollama ARM64 + CPU** | Ya funciona en Parker, interfaz `/api/chat`, medición local y configuración conocida. | No utiliza automáticamente la NPU. | **Mantener como baseline**; menor riesgo y latencia ya razonable. |
| **RKLLM oficial de Rockchip** | Runtime pensado para inferencia LLM en NPU; existe ejemplo Qwen2.5-1.5B para RK3588 y medición publicada de 15,44 tok/s. | Conversión a `.rkllm` normalmente en PC Linux x86; dependen la imagen, kernel, driver NPU y versión del toolkit. El servidor/API no es idéntico a Ollama y el benchmark no aporta comparación fiable de TTFT. | **Mejor candidato para prueba aislada**, no para reemplazo inmediato. |
| **RKLLama comunitario** | Intenta ofrecer rutas compatibles con Ollama/OpenAI y soporte RKLLM/GGUF para RK3588. | No equivale a compatibilidad completa; más riesgo de mantenimiento y permisos que el upstream. | Solo evaluar en una instalación separada y sin exponer la API. |
| **llama.cpp upstream** | Servidor GGUF/OpenAI-compatible, control directo y buen baseline CPU ARM64. | El upstream no lista el acelerador Rockchip como backend estándar; las rutas NPU dependen de forks. | Alternativa CPU para comparar, no motivo para migrar ahora. |

### Qué debe ganar para justificar la migración

Probar primero Qwen2.5-1.5B-Instruct convertido específicamente para RK3588;
si la RAM de la placa lo permite, se puede comparar 3B, pero no asumir mejor
español solo por el tamaño. Mantener Qwen2.5-1.5B como baseline. Medir con los
mismos diálogos y respuestas comprobables: seguimiento del tema durante varios
turnos, nombres propios, hechos recordados, preguntas sin respuesta conocida,
streaming, primera carga, TTFT caliente, tokens/s, RAM y temperatura. Verificar
además que la API del runtime respete el formato que usa Parker. Las cifras de
Ollama de un prompt y el benchmark RKLLM no son equivalentes por sí mismos.

La memoria factual y las reglas deterministas (nombre, hechos del usuario,
recuerdos recuperados) ayudan más con exactitud que cambiar de backend; un LLM
pequeño todavía puede confundir palabras o alucinar. Mantener los recuerdos
vinculados explícitamente al usuario y no guardar saludos evita reforzar errores.
Ningún runtime garantiza el cumplimiento de políticas por sí solo: los límites
y validaciones de la aplicación siguen siendo necesarios.

**No instalaría todavía otro kernel ni driver ni usaría contenedores privilegiados
en el equipo activo.** Primero haría la evaluación en un medio/instalación
separado, conservando Ollama y la memoria original. No se debe aplicar una receta
Radxa directamente a la imagen Orange Pi sin verificar kernel y driver.

Fuentes: [especificación Orange Pi 5 Pro](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5-Pro.html), [RKLLM oficial](https://github.com/airockchip/rknn-llm), [guía y benchmark RKLLM Qwen2.5-1.5B](https://docs.radxa.com/en/rock5/rock5b/app-development/ai/rkllm-usage), [limitaciones del servidor RKLLM](https://localai.io/docs/features/rkllm/), [Ollama Linux ARM64](https://docs.ollama.com/linux), [RKLLama comunitario](https://github.com/NotPunchnox/rkllama), [llama.cpp upstream](https://github.com/ggml-org/llama.cpp).

## 5. Temperatura: interpretar el sensor real

En la Orange Pi conectada durante esta revisión, el kernel expuso `soc-thermal`
con trips `passive 75 °C`, `passive 85 °C`, `critical 115 °C`; las zonas de CPU
separadas mostraron trip crítico a 115 °C. En reposo se leyeron ~36-41 °C. Esos
son los valores medidos en esta imagen; Parker los detecta y los registra en
vez de asumirlos a partir del índice de zona.

Una lectura de **60 °C bajo carga no demuestra por sí sola una anomalía**. No
hay una temperatura “normal” universal que se pueda deducir de un solo muestreo:
importan el sensor, la temperatura ambiente, la caja, la ventilación y la carga.
Los nombres `thermal_zone0`, `thermal_zone1`, etc. pueden cambiar. Parker ahora
registra el `type`, temperatura y trip points que exponga cada zona, y avisa al
superar `temperatura.aviso_c` (70 °C por defecto). Ese aviso es preventivo, no
un límite oficial, no significa throttling y tampoco reemplaza la protección
integrada del kernel.

Como referencia solamente, el Device Tree upstream citado para RK3588 define
trips pasivos de CPU en 85 °C y trips críticos en 115 °C; **no asumir esos
valores para esta Orange Pi**. La imagen y el kernel instalados pueden diferir.
Consulta los trips impresos por Parker o inspecciona `/sys/class/thermal/`
(incluyendo `type`, `trip_point_*_temp` y `trip_point_*_type`). A 60 °C no
reduzcas automáticamente `num_thread`: 4 hilos fueron más rápidos que 3 en la
prueba concreta de Parker. Revisa refrigeración si la temperatura sube de forma
sostenida, se aproxima al trip pasivo real de la imagen, o hay evidencia de
throttling/frecuencia reducida. Fuentes: [kernel thermal sysfs](https://docs.kernel.org/driver-api/thermal/sysfs-api.html), [trips upstream RK3588](https://lists.infradead.org/pipermail/linux-arm-kernel/2024-May/926227.html), [Orange Pi 5 Pro](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5-Pro.html).

## 6. Palancas si vuelve a ir lento

Por orden de impacto medido:

1. **Refrigeración de la placa** (medido §7: los big cores tapan el trip
   pasivo de 75 °C y el prefill se queda a la mitad).
2. `llama.modelo`: hoy `3b` (decisión «útil y que tarde»); `1.5b` es la
   palanca si algún día urge velocidad (una línea).
3. Historial exacto y prefijo cacheable; el precalentado **por turno está ENCENDIDO**
   desde el 24/10 tarde: medido con el prompt real, calentar el prefijo justo al
   DETECTAR voz (no al transcribir) baja el primer token de 1,74-8,9 s a 0,62 s.
   El desastre de 24 s de TTFB era de la versión que competía con Whisper: si
   vuelve, mirar `[Latencia] STT` y apagarlo en `config.yaml`.
3. `escucha.modelo_faster` (`base`; `small` cuesta +3 s).
4. `llama.historial_mensajes` (4 = dos intercambios, para mantener tema).
5. `memoria.top_k_recuerdos` (3), umbral y `max_caracteres_recuerdo`.
6. `llama.max_tokens` (100; el corte real es `max_oraciones: 3`).
7. `escucha.silencio_corte_seg` (0,6).

Antes de tocar cualquiera, mirar el log: `[Latencia] STT`, `Primer token`,
`Fin de frase lista para hablar`. En temperatura, comparar el `type` más caliente
y el trip real de la imagen; no decidir por el número de `thermal_zone0` solo.

## 7. Bake-off de cerebros y límite térmico (24/10/2026)

Banco nuevo: **`tools/eval_cerebro.py`** (latencia + 4 escenarios fijos de
contexto/recuerdo con memoria falsa, reproducible) y `tools/bakeoff.sh`
(candidatos en serie con ENFRIAMIENTO entre bloques: sin esto, el orden de
prueba decide el resultado). Mismos turnos para todos, en la Orange Pi:

| Modelo | TTFB p50 | Generación | Contextos (4 críticos) | Veredicto |
|---|---|---|---|---|
| **`qwen2.5:3b`** | **7,6 s** (3,7 en frío) | **8,9 tok/s** | 4/4 · 2/4 · 4/4 (3 tandas) | **EN CONFIG**: el más estable en coherencia y en contexto |
| `llama3.2:3b` | 9,0 s | 7,4 tok/s | 4/4 | Descartado: divaga en español («la lluvia», «pan tostado», «una vacuna de viaje») y suelta etiquetas `[Ternura]` |
| `qwen3.5:2b` (23/10) | eval 14-20 s | 13 tok/s | — | Descartado: se inventa las matemáticas y no emite `[CARA:…]` |
| `qwen3:1.7b` (23/10) | eval 11-19 s | — | — | Descartado: respuestas rarísimas (hablaba de la lluvia) |
| `qwen25-3b-spec` (draft 1.5b) | — | — | — | Descartado: HTTP 500 en Ollama 0.40.3; además solo aceleraría la generación, que no es el cuello |
| `gemma3n:e2b` (5,7 GB) | — | — | — | Descartado **por RAM**: su carga bloqueó la placa ~20 min (SSH inaccesible) y el OOM mató Ollama; en 8 GB no convive con Whisper+Chroma |

Flags medidos con el 3b: `num_thread` 6/8 **peor** (5,9/7,1 t/s frente a 8,9;
reconfirmado), `num_batch` 1024 ≡ 512, governor `ondemand` (cambiarlo a
`performance` necesita root en la placa; queda pendiente del dueño).

**Límite térmico = la palanca de latencia más grande.** En inferencia
sostenida los big cores suben de 48 a 84 °C en ~90 s y, al cruzar el trip
pasivo de 75 °C de `soc-thermal`, el **prefill cae de 150-217 tok/s (frío) a
63-90 tok/s (caliente)** —el primer token se duplica—, mientras la generación
se mantiene (~9 tok/s). Serie medida: 48→58→69→79→84 °C a los
3/15/27/39/51 s. En una conversación seguida la placa ya está caliente y el
turno 4+ paga ~12 s de prefill. **Refrigeración (disipador + ventilador) es
lo que más se va a notar**; sin ella, ningún ajuste de software quita ese ×2.

## 8. El «Dipper» era «Piper» y el prefill se puede ocultar (24/10/2026)

**Nombre raro («Piper»/«Dipper»).** La identidad decía *«No escribas rellenos
como "mmm": **Piper** los deletrea»* y el 3b tomó esa palabra como el nombre de
Alan (log: *«¡Oh! Claro, eres tú, Piper»*). Tres defensas:

1. «Piper» fuera del prompt (ahora «la voz los deletrea»); test que falla si
   vuelve a aparecer en la identidad.
2. `corregir_nombre()` también sustituye vocativos con nombres AJENOS tras un
   saludo o tras «tú,» (`¡Hola, Piper!` → `¡Hola, Alan!`).
3. Se aplica en `cerebro` ANTES de guardar en el historial: si no, el nombre
   malo se refuerza turno a turno.

**Frases sin sentido.** Dos causas medibles: `max_oraciones` 5 cuando el prompt
pide dos, y cierres genéricos de asistente. Ahora: `max_oraciones: 3`, un
EJEMPLO de tono/longitud en el prompt (sin etiqueta de rol: el 3b copiaba el
«Amigo:» y respondía en su lugar) y filtro de cierres («¿Hay algo más?»,
«¿En qué puedo ayudarte?», «Estoy aquí para ayudarte…»).

**Prefijo precalentado = la palanca de TTFB.** Medido con el prompt real:

| | primer token | prefill | tokens (cacheados) |
|---|---|---|---|
| sin precalentar (placa caliente) | 8,94 s | 8,90 s | 635 (353) |
| precalentado 0,5 s antes | **0,64 s** | 0,60 s | 635 (619) |

Se lanza al DETECTAR voz (no al transcribir), así que no compite con Whisper;
de ahí `precalentar_turno: true` (estaba apagado por un caso de 24 s de TTFB en
cuando competía con el STT). Eval completa tras los cambios: **4/4 contextos**,
TTFB sin precalentar p50 8,3 s (3,8-12,5 s: la termal de §7 sigue mandando).
El barrido de Hugging Face está en `plan_mejoras.md` (sección «Investigación
Hugging Face»): ningún candidato 1-3 B demostró superar al 3b en persona en
español, así que se sigue con él.


## 9. Cerebro doble (v6, 25/10/2026): la nube piensa, la placa oye y habla

El techo del cerebro local no era el modelo sino la placa: 8,75 s de mediana al
primer token (mín. 3,99 / máx. 12,40) con `qwen2.5:3b`, turno completo p50
13,45 s y 9,3 tok/s de generación. Con una conversación así no se puede charlar.
La solución no fue elegir otro modelo pequeño, sino **cambiar de sitio la parte
lenta**: la generación de la frase.

| Motor | Modelo | Primer token (PC) | Generación |
|---|---|---|---|
| Nube (Groq) | `openai/gpt-oss-20b` | **0,56 s** | 742 tok/s |
| Nube (Groq) | `openai/gpt-oss-120b` | 0,58 s | 415 tok/s |
| Nube (Groq) | `qwen/qwen3.8-27b` | 0,71 s | 240 tok/s (un turno salió en blanco) |
| Local (placa) | `qwen2.5:3b` | 8,75 s | 9,3 tok/s |

Medido con `tools/bench_online.py` (3 turnos, prompt de identidad real) y con
`tools/eval_cerebro.py` **en la placa** (ruta completa de Parker, 4 turnos):

```
[Latencia] TTFB p50 1,23s (min 0,97 / max 1,37) | turno total p50 1,29s
[Cerebro] Nube lista en 0,57s (openai/gpt-oss-20b)
```

Es decir: **8,75 s → 1,23 s** sin tocar micrófono, voz, recuerdos ni cara.
Lo que queda por delante es la otra mitad de la cadena, que ya era local y no
ha cambiado: STT `base` 1,6-2,0 s (se paga mientras la persona termina de
hablar, en parte solapado) y arranque de Piper ~0,2-0,4 s.

Lo que **no** se hace: mandar audio, recuerdos de Chroma ni estado de ánimo a la
nube (solo viaja el texto del prompt: identidad + ánimo + 3 recuerdos
recortados + el último turno). Y si internet falla, el mismo turno lo contesta
`qwen2.5:3b` en local: Parker sigue funcionando, más lento.

Detalle de configuración y de cómo se prueba: [cerebro_doble.md](cerebro_doble.md).

## 10. STT en la nube (v6.1.0): el contexto se perdía en la entrada

Con el cerebro rápido, el cuello siguiente era la transcripción. Misma frase de
6,1 s grabada por el micro USB de la placa:

| Motor | Tiempo | Resultado |
|---|---|---|
| local `faster-whisper base` int8 | 4,31 s | «estuve en **al** médico» (error) |
| nube `whisper-large-v3-turbo` | **0,68 s** | texto exacto |

Y en un turno real completo, medido en la placa:

```
[Escucha] Transcripción (nube 0.64s): 'Parker, mañana tengo una entrevista de trabajo y estoy nervioso.'
[Latencia] STT: 0.65s (nube)
[Latencia] Primer token del cerebro: 0.67s
[Parker -> Voz] Oye Alan, esa entrevista va a ser genial. ¿Qué tema de la empresa te preocupa más?
```

De punta a punta (dejar de hablar → primera frase sonando): **~1,6 s**
(STT 0,65 + cerebro 0,67 + arranque de Piper ~0,3), frente a los 8,75 s de
mediana que había solo en el cerebro. Efecto secundario medido: sin Whisper en
la CPU desaparecen los turnos de 29 s que coincidían con la carga del modelo
local.

Privacidad: con `escucha.motor: "auto"` el audio del turno va a Groq; con
`"local"` no sale de casa (4,3 s y algún error). Documentado en
[cerebro_doble.md](cerebro_doble.md) §9.

## Medición del 30/10/2026: nube vs. modo local

Dos medidas del mismo día, con la misma arquitectura de streaming:

| Dónde | Motor | TTFT | Turno completo | Nota |
|---|---|---:|---:|---|
| PC (fibra) | Groq `openai/gpt-oss-20b` | **0,51 s** | **0,56 s** | respuesta corta de saludo, una sola frase |
| Placa | Ollama `qwen2.5:3b` (modo local guardado) | — | **5,78-5,90 s** | orden de agenda resuelta sin LLM; el tiempo es voz + Piper + cara |

La diferencia no era el código de agenda: `parker.cerebro.json` tenía
`{"modo":"local"}` de una prueba anterior, así que Parker estaba pensando con
el 3B en la CPU. En modo `auto` el primario es la nube y el local solo entra si
falla internet o el proveedor. Al volver a desplegar hay que comprobar en el
log `modo auto` y `[Cerebro] primario NUBE`.

La prueba de PC no es un benchmark de la placa: la red y el modelo son los
mismos, pero el cuello de botella de la placa es el audio/Piper, no Groq. Sirve
para separar «la nube es lenta» de «el modo local es lento».

## 11. Edge TTS (v6.10.0): voz natural sin perder la local

Medido en la placa el 30/10/2026, con `edge-tts 7.3.1` y `ffmpeg 4.4.2`:

| Motor | Frase | Síntesis | Audio | Pico a volumen 0,55 |
|---|---|---:|---:|---:|
| Edge `es-ES-XimenaNeural` | 8,04 s | 1,84 s (incluye cargar Piper) | 8,04 s | 0,51 (normalizado) |
| Edge `es-ES-XimenaNeural` | 7,32 s | 2,29 s | 7,32 s | 0,51 |
| Piper `es_ES-davefx-medium` | 2,14 s | 0,36 s | 2,14 s | 0,55 |

Edge tarda ~1,8-2,3 s por frase en la red de casa, pero el orador sintetiza la
frase siguiente mientras suena la actual, así que en una respuesta de 2-3 frases
solo se paga entero el arranque de la primera. Si Edge falla, Piper responde en
~0,36 s y Parker no se queda mudo.

El pico de Edge sin normalizar era 0,28 (se oiría bajo); se normaliza a 0,92 y
se aplica el volumen de `config.yaml`, con lo que queda en 0,51. Es el mismo
valor que se pide a Piper, así que «baja el volumen» funciona igual con los dos.

Nota: la primera prueba de reproducción aislada coincidió con Parker usando la
tarjeta; ALSA devolvió `Device unavailable` en la segunda frase. Se añadieron
dos reintentos de 150/300 ms en `VozParker.reproducir()`.
