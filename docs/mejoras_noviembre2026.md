---
tema: TREC
bloc: 7
estat: viu
---
# Mejoras aplicadas — noviembre 2026

> **Qué es esta nota.** El registro de lo que se implementó en Parker el
> 02/11/2026 (memoria de hechos, búsqueda híbrida, apoyo emocional y prosodia),
> con las medidas reales de la placa, el estado del despliegue y una ficha de
> cada herramienta que se usa, explicando qué hace y de dónde sale. No es una
> lista de deseos: lo que está aquí está en el código y probado en la Orange Pi.

## 1. Qué se ha aplicado

| Pieza | Fichero | Qué hace |
|---|---|---|
| Hechos exactos | `modulos/hechos.py` | Guarda datos dichos por la persona (dentista, alergia, mascota, edad…) como slots en SQLite. Van siempre en el bloque estable del system, así que no cuestan prefill por turno. |
| Memoria híbrida | `modulos/memoria.py` | Suma a la búsqueda semántica de Chroma un índice léxico FTS5/BM25 en SQLite aparte, y funde ambos rankings con RRF. |
| Apoyo emocional | `modulos/cerebro.py` | Máquina de estados `normal → explorar → consolar → actuar` inspirada en ESConv; una crisis se responde de forma determinista con 024/112, sin pasar por el LLM. |
| Prosodia | `modulos/prosodia.py` | Mide RMS (dB), F0 y densidad de voz en cada turno y compara la tendencia de los últimos 3 días con la base de 14. Solo decide si preguntar cómo está; nunca diagnostica. |
| Ganchos | `parker.py`, `modulos/personalidad.py`, `config.yaml` | Registro de prosodia antes de normalizar el audio, extracción de hechos por turno, check-in de bienestar y borrado completo de los datos nuevos. |
| Herramientas | `tools/hechos.py`, `tools/mide_cerebro.py` | Listar/probar/borrar hechos y medir el TTFB del cerebro local con y sin hechos. |
| Pruebas | `tests/test_memoria_hechos.py`, `test_prosodia.py`, `test_apoyo.py`, `test_memoria_hibrida.py` | 24 comprobaciones nuevas, ejecutables sin pytest (`python tests/…`). |

## 2. Qué se ha medido (placa, 02/11/2026)

Cerebro local `qwen3.5-local:2b` en Ollama, `num_thread: 4`, `num_ctx: 2048`,
seis turnos calientes con el prompt real, Parker vivo compartiendo CPU:

| Medición | p50 |
|---|---:|
| TTFB sin hechos | **2.803 ms** |
| TTFB con hechos | **2.811 ms** |

- **El bloque de hechos no añade coste**: la diferencia (8 ms) es ruido. Viaja
  en el prefijo estable y se cachea.
- **El objetivo <1 s no se alcanzó.** El cuello es el prefill del mensaje de
  usuario (~450 tokens) más la generación en CPU a 7-9 tok/s con Parker vivo.
  El 01/11, con la placa libre, la misma familia dio 13,4 tok/s; la diferencia
  es carga compartida, no una regresión del cambio.
- En frío (modelo sin cargar) el primer turno tarda 11-13 s.

Pruebas en verde en la placa: `test_memoria_hibrida` 4/4 (con Chroma real),
`test_memoria_hechos` 5/5, `test_prosodia` 7/7, `test_apoyo` 8/8,
`test_config` 2/2 y `test_cerebro_doble` 14/14.

**Tres pruebas ya fallaban con el respaldo viejo** (están desfasadas respecto a
la ficha viva, no las rompió este cambio): `test_rendimiento` exige
`[CARA:emocion]` en la identidad, `test_personalidad` espera «silbar con el
altavoz» y `test_conversacion` cuenta `charlas` donde hoy se guarda
`interacciones`.

## 3. Cómo funciona cada herramienta (y de dónde sale)

La recopilación interna que originó estas decisiones está en
[[investigacion_oct2026]]. Los enlaces de cada apartado son la fuente oficial
consultada para entender y aplicar la herramienta.

### 3.1 ESConv y el marco de apoyo emocional

**Qué es.** El artículo *Towards Emotional Support Dialog Systems* (ACL 2021)
define la tarea de conversación de apoyo emocional y publica ESConv: 1.300
conversaciones sobre 10 problemas, anotadas con estrategias de ayuda. Su marco
tiene tres etapas —**exploración, consuelo y acción**— apoyadas en la teoría de
habilidades de ayuda: primero se entiende qué pasa, luego se acompaña y solo
después se propone un paso práctico.

**Cómo se usa en Parker.** No se entrena ningún modelo con ESConv: se copia la
estructura como máquina de estados en `cerebro.py`. Las frases de la persona
deciden la transición (`_avanzar_apoyo`), y una instrucción corta en el prompt
(`_instruccion_apoyo`) le dice al cerebro en qué etapa está. La detección de
crisis es independiente y determinista.

Fuentes: <https://aclanthology.org/2021.acl-long.269/> ·
<https://github.com/thu-coai/Emotional-Support-Conversation>

### 3.2 ChromaDB (memoria semántica)

**Qué es.** Base de datos vectorial embebida: guarda cada recuerdo con su
embedding y metadatos en una colección, y responde consultas por similitud
(coseno) sin servidor aparte. En Parker la colección es `recuerdos_parker`.

**Cómo se usa.** Recupera los recuerdos más parecidos al turno actual. Su
límite —conocido y medido— es que un embedding de 384 dimensiones no recupera
con fiabilidad un nombre propio o un dato aislado; de ahí los hechos exactos y
la búsqueda léxica.

Fuente: <https://docs.trychroma.com/>

### 3.3 sentence-transformers y MiniLM multilingüe

**Qué es.** `paraphrase-multilingual-MiniLM-L12-v2` convierte una frase en un
vector de 384 dimensiones entrenado para que frases con el mismo significado
queden cerca, también entre español y catalán. Corre en CPU.

**Cómo se usa.** Es el modelo que alimenta a Chroma; no se ha cambiado, solo se
ha medido su límite con preguntas cortas de hechos.

Fuente:
<https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2>

### 3.4 SQLite FTS5 y BM25 (memoria léxica)

**Qué es.** FTS5 es el módulo de búsqueda de texto completo de SQLite: construye
un índice invertido y permite `MATCH` con tokenización `unicode61` (sin
diacríticos, importante en español). La función `bm25()` ordena los resultados
con una fórmula probabilística que premia términos raros y documentos cortos.

**Cómo se usa.** Un SQLite derivado (`parker_fts.sqlite`, junto a Chroma pero
separado de su interior) guarda los mismos recuerdos. Así «dentista» encuentra
el recuerdo aunque el embedding no lo acerque. Se sincroniza al guardar y al
borrar.

Fuentes: <https://www.sqlite.org/fts5.html> ·
<https://www.sqlite.org/fts5.html#the_bm25_function> ·
<https://dl.acm.org/doi/10.1561/1500000019>

### 3.5 Reciprocal Rank Fusion (RRF)

**Qué es.** El método de Cormack, Clarke y Büttcher (SIGIR 2009) para combinar
listas ordenadas de distintos buscadores: cada documento suma `1 / (k + rank)`
en cada lista donde aparece, con `k = 60`. No necesita que las puntuaciones de
los buscadores sean comparables, solo sus puestos.

**Cómo se usa.** Funde el ranking semántico de Chroma y el léxico de FTS5. Por
eso, con la búsqueda híbrida activa, el umbral de coseno deja de filtrar: RRF
ordena y el umbral solo vuelve a actuar si se desactiva la híbrida.

Fuentes: <https://dl.acm.org/doi/10.1145/1571941.1572114> ·
<https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf>

### 3.6 Silero VAD

**Qué es.** Una red neuronal pequeña (ONNX) que recibe ventanas de audio y
devuelve la probabilidad de que haya voz humana, distinguiéndola del ruido sin
depender del volumen. En Parker se aplica sobre una copia con ganancia
automática, para oír voces lejanas sin abrir turno con la televisión.

**Cómo se usa.** Es el detector de turno (`vad_motor: silero`), integrado en
faster-whisper. Sustituyó al VAD por RMS, que obligaba a casi gritar.

Fuente: <https://github.com/snakers4/silero-vad>

### 3.7 Whisper y faster-whisper (STT)

**Qué es.** Whisper es el modelo de transcripción de OpenAI; faster-whisper es
su reimplementación con CTranslate2 e int8, pensada para CPU. En Parker el
motor es `auto`: nube (`whisper-large-v3-turbo` en Groq) si hay red y clave, y
local (`base`) como respaldo.

**Cómo se usa.** Convierte la frase grabada en texto, que es la entrada del
cerebro. Se mantiene el modelo `base` local por latencia; el `small` transcribía
mejor pero se comía la CPU de la placa.

Fuentes: <https://github.com/openai/whisper> ·
<https://github.com/SYSTRAN/faster-whisper>

### 3.8 Ollama y Qwen (cerebro local)

**Qué es.** Ollama carga modelos GGUF y los sirve por una API REST local.
`keep_alive` mantiene el modelo en RAM entre turnos y el caché de prefijo evita
reevaluar el system si no ha cambiado. Qwen es la familia de modelos; en la
placa corre `qwen3.5-local:2b` (sin modo «pensar» para voz).

**Cómo se usa.** Es el cerebro de respaldo cuando no hay internet (y el
primario si se pide «modo local»). La medición de TTFB de esta nota es suya.

Fuentes: <https://github.com/ollama/ollama> ·
<https://ollama.com/library/qwen3>

### 3.9 Prosodia: RMS, F0 y densidad

**Qué es.** RMS es el nivel eficaz de la señal; en dB (`20·log10(rms)`) da una
medida comparable entre turnos. La F0 (frecuencia fundamental) se estima por
autocorrelación: se busca el periodo con el que la onda se repite (70-350 Hz) y
se descarta si el pico no es suficientemente periódico (~0,35). La densidad es
la fracción de tramas con voz.

**Cómo se usa.** Se guardan las tres medidas por turno, sin etiquetar emociones.
`tendencia()` compara los últimos 3 días con la base de 14 de esa misma persona;
si la voz suena más baja de lo habitual, la iniciativa puede preguntar «¿cómo
estás?». Es una señal débil, no un diagnóstico, y no cambia las respuestas.

Fuentes: <https://librosa.org/doc/main/generated/librosa.feature.rms.html> ·
<https://librosa.org/doc/main/generated/librosa.pyin.html> ·
<https://www.fon.hum.uva.nl/praat/> ·
<https://www.audeering.com/research/opensmile/>

### 3.10 Edge TTS y Piper (voz)

**Qué es.** Edge TTS usa las voces neuronales de Microsoft por red
(`es-ES-XimenaNeural`); Piper es un TTS local en ONNX que se carga siempre y
entra si Edge falla. Así Parker no se queda mudo sin internet.

**Cómo se usa.** Es la boca de Parker; no se ha cambiado en esta sesión, pero
es parte del turno que se mide.

Fuentes: <https://github.com/rany2/edge-tts> ·
<https://github.com/rhasspy/piper>

### 3.11 Groq (cerebro en la nube)

**Qué es.** API compatible con OpenAI que sirve modelos abiertos con muy baja
latencia. En Parker es el cerebro primario (`qwen/qwen3.8-27b`, con alternativas
si el proveedor retira el modelo).

**Cómo se usa.** Redacta la respuesta cuando hay red; el local solo entra como
respaldo o si se pide por voz.

Fuente: <https://console.groq.com/docs>

### Resumen de fuentes

| Herramienta | Para qué en Parker | Enlace |
|---|---|---|
| ESConv (ACL 2021) | Estructura del apoyo emocional | <https://aclanthology.org/2021.acl-long.269/> |
| ChromaDB | Memoria semántica | <https://docs.trychroma.com/> |
| MiniLM multilingüe | Embeddings de los recuerdos | <https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2> |
| SQLite FTS5 / BM25 | Memoria léxica y ranking | <https://www.sqlite.org/fts5.html> |
| RRF (SIGIR 2009) | Fusión de los dos rankings | <https://dl.acm.org/doi/10.1145/1571941.1572114> |
| Silero VAD | Detección de voz | <https://github.com/snakers4/silero-vad> |
| faster-whisper | Transcripción local | <https://github.com/SYSTRAN/faster-whisper> |
| Ollama + Qwen | Cerebro local | <https://github.com/ollama/ollama> |
| RMS / F0 / Praat | Medidas de prosodia | <https://www.fon.hum.uva.nl/praat/> |
| Edge TTS / Piper | Voz | <https://github.com/rany2/edge-tts> |
| Groq | Cerebro en la nube | <https://console.groq.com/docs> |

## 4. Despliegue en la placa y vuelta atrás

- **Fecha:** 02/11/2026, Orange Pi 5 Pro (`ssh orangepi@192.168.1.130`), código
  en `~/parker`.
- **Copia previa:** `~/parker_backup_2026-11-02.tar.gz` (código, configuración,
  pruebas y herramientas del estado anterior).
- **Integridad:** los md5 de `parker.py`, `config.yaml` y los módulos tocados
  coinciden entre el PC y la placa.
- **Arranque:** tras reiniciar, el log muestra
  `[Memoria] Búsqueda híbrida activa (semántica + léxica FTS5)` y
  `[Hechos] Tabla de hechos lista`; el proceso queda vivo con el relanzador
  `tools/arrancar.sh`.
- **Vuelta atrás:** `tar xzf ~/parker_backup_2026-11-02.tar.gz` desde `~`.

## 5. Pendiente

### Corrección aplicada el 02/11 (v6.12.17)

El log de la placa mostró el fallo con datos: el VAD abría turno con ruido de
sala (rms 0,0015-0,0026 y AGC ×6) y Whisper lo convertía en «Gracias.» o
«¡Suscríbete al canal!»; además, el eco del altavoz se colaba como «oído
local, oído local». Se corrigió en cuatro puntos: `vad_rms_minimo` sube de
0,0015 a **0,0035** (la voz real medida empieza en 0,004);
`es_repeticion_sin_sentido` detecta bloques cortos repetidos; el turno normal
descarta el eco de lo hablado en los 12 s posteriores a una respuesta; y el
monitor de barge-in aplica el mismo filtro antes de decidir un corte.El arranque imprime el mínimo real para poder verificarlo en el log.

### Modo local/online (v6.12.18)

«Modo local» y «modo online» solo cambiaban el cerebro; la voz seguía en Edge
y el oído en auto, y `parker.modo.json` lo reflejaba (`voz: edge`). Ahora esas
dos órdenes cambian los tres; «cerebro local» / «cambia el cerebro a local»
siguen siendo el cambio parcial. La persistencia ya guardaba los tres, así que
al reiniciar se mantiene lo elegido.

### Robustez (v6.12.19)

La auditoría encontró un `AttributeError` en `_borrar_memoria` cuando un
Parker parcial (tests) no tenía `hechos`/`prosodia`; ahora se usan con
`getattr`. También se corrigió la limpieza de Chroma en Windows en
`test_memoria_hibrida`. `test_pipeline` y el resto de la suite vuelven a verde.

1. **TTFB < 1 s.** Medir con la placa libre (Parker parado) para separar carga
   compartida de coste real, y decidir después: precalentar el turno, recortar
   el bloque volátil o asumir el límite del hardware.
2. **Tres pruebas desfasadas** de la placa (ver §2): corregirlas o documentarlas
   como deuda.
3. **Hechos en uso real:** la tabla arrancó con 0 activos; falta comprobar que
   se llena con conversaciones normales y que no guarda órdenes ni preguntas.
4. **Prosodia:** solo hay una muestra por turno; la tendencia necesitará días
   de uso antes de ser útil.

## 6. Enlaces internos

- [[rendimiento]] — el presupuesto de latencia y las medidas anteriores.
- [[plan_mejoras]] — el plan del que salen estas piezas.
- [[investigacion_oct2026]] — la recopilación externa con fuentes.
- [[TREC/12 Diari de recerca]] — la cronología del proyecto.
- [[TREC/05 Resultats]] — las cifras que van a la memoria.
