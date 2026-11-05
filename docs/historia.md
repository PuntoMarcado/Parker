# Historia de Parker: del planteamiento en papel al robot de sobremesa

> **Qué es este documento.** Une las dos mitades de la historia del proyecto:
> lo que el autor había escrito antes de tener código (transcrito en
> [historia_original.md](historia_original.md)) y lo que realmente se construyó
> después, tal como está documentado en este repositorio. Sirve para explicar el
> proceso completo —en una presentación, a un tribunal o a un inversor— sin
> mezclar lo que se planeó con lo que se midió.
>
> **Cómo se ha escrito.** El documento original está en catalán y se conserva
> literal. Esta versión está en español y añade fechas, cifras y enlaces al
> código. Las fechas de la etapa actual no son estimaciones: salen de
> `modulos/version.py`, de las medidas de
> [rendimiento.md](rendimiento.md) y de los nombres de las copias de seguridad
> en `backups/`. Lo que no está documentado no se inventa: se dice que falta.
> **Actualizado el 30/10/2026**; la última versión publicada es la **v6.8.1**
> (30/10/2026).

---

## 1. La historia en tres actos

| Acto | Cuándo | Qué había | Qué quedó |
|---|---|---|---|
| **I. El papel** | Agosto de 2026 | Ni ordenador, ni código, ni tecnología: solo la lista de funciones mínimas | El diseño del doble cerebro, la memoria vectorial, la cara y el presupuesto |
| **II. El prototipo** | Antes de la placa (sin fecha documentada) | Un PC, Pygame, la barra espaciadora y Groq | La primera Parker que hablaba, recordaba y ponía caras |
| **III. El dispositivo** | 17–30 de octubre | Una Orange Pi 5 Pro con pantalla redonda, micro y altavoz | Parker v6.8.1: oye, habla, recuerda, tiene rutinas y una cara con vida propia |

La idea que atraviesa los tres actos es siempre la misma: **que Parker no sea
una terminal de comandos ni un altavoz, sino alguien que está ahí**. Todo lo
demás —el doble cerebro, Chroma, las caras, la agenda— son medios para eso.

---

## 2. Acto I: el planteamiento (lo que había antes de programar)

El documento original empieza con una frase que resume bien esa etapa: *«la
creació de Parker va començar sense ordinador ni codi ni cap tecnologia»*. Lo
primero no fue programar, sino decidir **qué funciones mínimas** hacen que el
proyecto sea un proyecto y no una idea. Salieron cuatro:

| Pieza | Qué debía hacer | Cómo se imaginó |
|---|---|---|
| **Cerebro** | Entender y responder | Doble: Groq en la nube (rápido) + Ollama en local (sin internet) |
| **Oído** | Convertir voz en texto | Micrófono del PC, un `.wav` por turno |
| **Memoria** | Recordar a la persona | ChromaDB local con RAG |
| **Cara** | Expresar lo que dice | Primero imágenes de BMO; luego una cara propia |

### 2.1 El doble cerebro del papel

El diseño inicial ya era el que hoy está funcionando, aunque por motivos
distintos. Groq daba respuestas rápidas y de más calidad, pero dependía de
internet, del coste y de los límites de tokens. Ollama funcionaba sin conexión
y no sacaba los datos de casa, pero en un miniordenador pequeño sería lento.
La motivación escrita fue exactamente esta: **evitar que Parker dejara al
usuario «incomunicat» si no había red**, sin aceptar a cambio una lentitud
permanente.

La historia del documento tiene tres pasos, y conviene contarlos en orden
porque el tercero se revirtió después:

1. **Se diseña el doble cerebro** (Groq + Ollama).
2. **Se simplifica a solo Groq** durante el prototipo en el PC, para no mantener
   dos caminos de ejecución mientras se construían memoria, voz y expresiones.
   El modelo concreto era `llama-3.3-70b-versatile`.
3. **Se decide descartar el doble cerebro y quedarse solo con Ollama**, porque
   Groq no compensaba la complejidad, el coste, la dependencia de internet y el
   hecho de que las conversaciones salieran del dispositivo. El argumento era
   razonable: Parker no necesita razonar mucho; sobre todo necesita recordar lo
   que le has contado, y eso ya vive en Chroma.

El cuarto capítulo de esa historia no estaba en el papel y es el que cambió
todo: **cuando se midió el Ollama local en la placa, el doble cerebro volvió**
(§4.3). No por capricho, sino porque 8,75 s hasta la primera palabra no es una
conversación. La solución no fue elegir entre listo y rápido, sino **repartir el
trabajo**: la placa pone los oídos, la boca, la cara y la memoria; la nube solo
redacta la frase.

### 2.2 El oído del primer prototipo

El primer prototipo no escuchaba solo: **había que pulsar la barra espaciadora**.
Al pulsarla, el bucle de Pygame mandaba una señal por una cola para poner la
cara en «escuchando», abría el micrófono y grababa un `.wav` temporal. Era un
turno manual, de laboratorio: servía para probar la cadena voz → texto →
respuesta → voz sin depender de detectar cuándo empiezas a hablar.

La diferencia con hoy es grande y se ve en la placa: Parker **escucha siempre**
por VAD (detección de actividad de voz), corta el turno tras 0,6 s de silencio y
no hay que tocar nada. La barra espaciadora desapareció, pero el concepto
—micrófono → archivo temporal → transcripción— sigue siendo el mismo.

### 2.3 La memoria: un diario vectorial

El documento explica ChromaDB mejor que muchos manuales: no es un archivo de
texto donde la IA busca línea a línea, sino una base de datos de **vectores**
que representa el significado. El proceso se llama **RAG** y tiene tres pasos:

1. **Recuperar** los recuerdos más parecidos a la conversación actual.
2. **Aumentar** el prompt con esos recuerdos.
3. **Generar** la respuesta teniendo en cuenta lo de ahora y lo de antes.

El ejemplo que usa el documento es perfecto para explicarlo: si un día dices
«estoy a dieta y siempre tengo que comer pasta y carne», eso se guarda como un
vector; semanas después, cuando dices «no sé qué comer hoy», Chroma recupera
aquel vector y Parker puede contestar «tienes que comer carne y pasta, estás a
dieta». Eso es memoria episódica, no un historial de chat.

La **segunda actualización** del documento cuenta que la primera versión de la
memoria estaba pensada para inglés y fallaba en catalán y castellano. Se
corrigieron tres cosas, y las tres siguen hoy en el código:

| Problema | Cambio | Estado actual |
|---|---|---|
| El modelo de embeddings era casi monolingüe | `paraphrase-multilingual-MiniLM-L12-v2` (>50 idiomas, local) | Es el que usa `modulos/memoria.py` |
| El umbral del 75 % era demasiado exigente y «olvidaba» si decías lo mismo con otras palabras | Bajarlo al 50 % | Hoy en 0,58 (`memoria.umbral_relevancia`) |
| Se vectorizaba el turno entero (tu frase + la respuesta de Parker) y el significado se diluía | Vectorizar **solo** el mensaje de la persona | Es lo que se guarda hoy |

El documento original mezcla tres estados de la memoria (diseñada, en
actualización y pendiente, según el apartado). Hoy no hay ambigüedad: está
implementada, guarda en `parker.db/` y se puede inspeccionar con
`tools/recuerdos.py`.

### 2.4 La cara: tres lenguajes visuales antes del actual

El documento describe tres etapas y anuncia una cuarta:

1. **Imágenes estáticas de BMO**, el personaje de *Adventure Time* que inspiró a
   Parker. Se usaron mientras lo importante era que la lógica funcionara.
2. **Una página web local** conectada a Python: cada parte de la cara (ojos,
   boca) era un elemento separado, lo que permitía más expresiones que una
   imagen fija.
3. **Una cara vectorial**, ya en la segunda actualización: en vez de imágenes,
   se dibujan formas y se combinan para obtener expresiones.
4. **La intención declarada**: animaciones para que Parker tenga fluidez al
   hablar y al expresarse.

La cuarta etapa es la que hoy está construida, pero con otra implementación:
PySide6 y una escena vectorial de 400×400, los **12 principios de animación**,
lip-sync con la voz y salida a una pantalla circular GC9A01 de 240×240 por SPI.
La cara vectorial del documento y la de hoy comparten la idea, no el código.

### 2.5 El cuerpo: 250 € y tres planes

Gracias a un inversor, el proyecto pasó a tener **250 €** y tres caminos:

| Plan | Idea | Ventaja | Problema |
|---|---|---|---|
| 1 | Ampliar el presupuesto | Más hardware | No resuelve la arquitectura |
| 2 | Pantalla pequeña junto al monitor, cerebro en el PC | Barato y rápido de construir | Depende de la RAM y del PC |
| 3 | Asistente de cocina que dicta la receta | Uso muy concreto | No era el corazón del proyecto |

Lo que se construyó se parece al **plan 2 en la forma** —un dispositivo pequeño
de sobremesa con su propia pantalla— pero con una diferencia importante: **no
depende del PC**. La placa lleva su propio cerebro local de respaldo, su memoria
y su voz. El plan 3 (la cocina) sigue siendo una aplicación posible, no una
función terminada; lo que sí existe ya es la base para usarlo hablando: recetas
no, pero música, apuntes, alarmas y el tiempo sí.

---

## 3. Acto II: el prototipo en el PC (la etapa que el documento no fecha)

El documento no pone fechas a esta etapa, pero deja claro el orden en que se
construyó: **primero las funciones, luego la memoria, luego la cara**. En el PC
Parker ya tenía:

- un bucle de Pygame con la cara y la cola de estados;
- un turno manual con la barra espaciadora y un `.wav` temporal;
- Groq con `llama-3.3-70b-versatile` como único cerebro;
- ChromaDB con el modelo de embeddings equivocado (inglés) y el umbral del 75 %;
- una cara que pasó de imágenes de BMO a una web local y luego a vectores.

Esa etapa es la que produjo las preguntas que el repositorio actual responde con
medidas: ¿cuánto tarda de verdad?, ¿entiende el contexto o solo recuerda
palabras?, ¿se puede tener una cara fluida sin gastar CPU?, ¿qué pasa si no hay
internet? El documento las plantea; la placa las numera.

---

## 4. Acto III: la construcción real (octubre de 2026)

Aquí cambia la naturaleza de la historia: ya no se decide en el papel, se mide
en una Orange Pi 5 Pro de 8 GB con pantalla circular, micro USB y altavoz. Cada
decisión deja un número en el log (`[Latencia] STT`, `Primer token`, `Turno
completo`) y una copia de seguridad en `backups/`.

### 4.1 17 de octubre — el primer presupuesto de latencia

El punto de partida era el Parker local del prototipo: **15–20 s** desde que
dejabas de hablar hasta que empezaba a sonar. Se atacaron cinco cosas a la vez,
y el resultado fue **4,2–4,7 s**:

| Etapa | Antes | Después | Cómo |
|---|---|---|---|
| Corte de silencio | 1,3 s | **0,6 s** | `escucha.silencio_corte_seg` |
| Transcripción | 4,8–5,3 s (`small`) | **1,6–1,8 s** (`base` int8) | modelo más pequeño + `hotwords: Parker` |
| Primer token | 6,5–7,8 s (3b) | **0,9–1,9 s** (1.5b) | modelo + prompt recortado + prefijo cacheado |
| Primera frase | 7,5–9 s | **1,3–2,1 s** | reacción corta en el prompt |
| Voz de la primera frase | 0,7–1,4 s | **0,5–0,9 s** | frase más corta |

Las copias de esa semana cuentan el orden real del trabajo: latencia
(`1416_latencia-optimizada`), caché de prefijo (`1504`), base de datos de
memoria (`1515`), arranque automático y documentación (`1527`), identidad,
vínculo y voz (`1559`), frases/térmica/RKLLM (`1805`), fecha y relleno (`1847`).

El resultado era rápido, pero **tonto**: el modelo `1.5b` se inventaba nombres y
divagaba. Y ahí llegó la decisión que define el resto del proyecto.

### 4.2 24 de octubre — «prefiero útil y que tarde a rápido y que sea tonto»

Se volvió a `qwen2.5:3b`. Para que fuera útil hubo que arreglar cosas que no se
veían desde fuera:

- **`num_ctx` de 1024 a 2048**: el prompt real llegaba a ~1067 tokens y Ollama
  lo estaba **recortando**. Parker no «se olvidaba» del contexto: se lo cortaban
  antes de leerlo.
- **Identidad recortada** a ~1.630 caracteres, estable entre turnos, para que el
  prefijo siga siendo cacheable.
- **«Recuerdos = pasado opcional»** en el prompt: los recuerdos no son órdenes
  actuales; si no vienen al caso, no se usan.
- **`max_oraciones: 3`** y un ejemplo de tono: menos frases sin sentido y menos
  coletillas de asistente.

El banco de pruebas (`tools/eval_cerebro.py` + `tools/bakeoff.sh`, con
enfriamiento entre modelos) dejó una tabla que sigue siendo la referencia:

| Modelo | Primer token p50 | Generación | Contextos críticos | Veredicto |
|---|---|---|---|---|
| **`qwen2.5:3b`** | 7,6 s | 8,9 tok/s | 4/4, 2/4, 4/4 | **se queda** |
| `llama3.2:3b` | 9,0 s | 7,4 tok/s | 4/4 | divaga en español y suelta etiquetas |
| `qwen3.5:2b` | 14–20 s | 13 tok/s | — | inventa y no emite `[CARA:…]` |
| `gemma3n:e2b` | — | — | — | **OOM**: 5,7 GB no caben con Whisper y Chroma |

Y apareció el límite que nadie había puesto en el papel: **la temperatura**. En
inferencia sostenida los núcleos grandes suben de 48 a 84 °C en ~90 s; al cruzar
el trip pasivo de 75 °C, el *prefill* cae de 150–217 a 63–90 tok/s y el primer
token se duplica. La refrigeración de la caja no es un detalle: es la palanca
más grande del cerebro local.

También se arregló un fantasma que parecía de personalidad y era del prompt:
Parker llamaba «Piper» (y el oído entendía «Dipper») al usuario porque la
identidad decía que *Piper* deletreaba los rellenos. Se quitó la palabra del
prompt, se añadió `corregir_nombre()` y un test que falla si vuelve.

Con el prefijo precalentado **al detectar voz** (no al transcribir, para no
competir con Whisper), el primer token pasó de 8,94 s a **0,64 s**. Aun así, el
turno completo seguía en ~11,5–13,5 s: el techo no era el modelo, era la placa.

### 4.3 25 de octubre — vuelve el doble cerebro (v6.0)

La idea descartada en el papel volvió, pero **no como estaba pensada**. Esta vez
el reparto es:

```
micrófono → VAD → Whisper local → ¿dato seguro? → respuesta directa (0 ms)
                                        │ no
                                        ▼
                              nube (Groq) o local (Ollama)
                                        ▼
                          limpieza local → Piper → altavoz
```

Lo que se queda en casa: micrófono, VAD, cara, voz, ánimo, vínculo y los
recuerdos de Chroma. Lo que viaja: el **texto** del prompt (identidad + ánimo +
3 recuerdos recortados + el último turno). Si no hay internet, el mismo turno lo
contesta el local; si la nube falla, un *circuit breaker* evita pagar 3 s de
timeout en cada turno.

| Motor | Modelo | Primer token | Generación |
|---|---|---|---|
| Nube (Groq) | `openai/gpt-oss-20b` | **0,56 s** (PC) | 742 tok/s |
| Local (placa) | `qwen2.5:3b` | 8,75 s (p50) | 9,3 tok/s |

Medido en la placa con la ruta completa: **TTFB p50 1,23 s** y turno total p50
1,29 s. Es decir: **8,75 s → 1,23 s** sin tocar oído, voz, memoria ni cara.

Los parches de esos dos días tienen su propia historia, porque cada uno arregla
algo que se oía:

- **v6.0.1**: Groq manda el SSE sin `charset`; `requests` asumía ISO-8859-1 y
  «¿Qué» llegaba a Piper como «Â¿QuÃ©». Además, el modelo escribía tokens de
  canal, entidades HTML y JSON que Piper leía en voz alta («comillas, dos
  puntos, llave»). Ahora se decodifica siempre en UTF-8 y se limpia el marcado.
- **v6.1.0**: la transcripción también se va a la nube
  (`whisper-large-v3-turbo`): **4,31 s → 0,68 s** y texto exacto. Sin Whisper en
  la CPU desaparecen los turnos de 29 s que coincidían con la carga del modelo.
- **v6.2.0**: órdenes directas sin LLM («baja el volumen», «silencia», «silba»),
  fechas relativas y la regla de que Parker no tiene cuerpo y no promete
  acciones físicas.
- **v6.2.1**: volumen exacto («bájalo al 33 %») y respuestas con el valor real.

### 4.4 26 de octubre — el día entero (v6.3 y v6.4)

Con la conversación resuelta, el siguiente salto fue **dejar de ser solo una
conversación**. En dos versiones:

- **v6.3.0 — agenda local**: alarmas («a las 7:30»), temporizadores («en 10
  minutos») y citas («apunta que el viernes a las 5 tengo al dentista»), con
  consulta («¿qué tengo mañana?»), borrado y aviso real por el altavoz desde un
  hilo propio. Se guarda en `parker.agenda.json`, solo en la placa.
- **v6.4.0 — el día y lo que se aprende**: rutinas («buenas noches», «buenos
  días» con parte del día, «cállate 10 minutos», «apágate»), apuntes y listas y
  contadores que Parker crea y borra por voz, el tiempo con Open-Meteo (sin
  clave), música por Deezer (sin clave), títulos cortos para las citas, y un
  **bandit** que aprende cuándo y de qué tomar la iniciativa según si le
  contestas o le ignoras.
- Además: si el proveedor retira el modelo de la nube, Parker elige otro solo
  (`/models` + lista de alternativos); y un vigilante del micrófono rearma el
  flujo si la entrada se queda en silencio absoluto.

### 4.5 27 de octubre — la cara y la voz (v6.5–v6.8)

- **v6.5.0 — música con orejas**: mientras suena la canción, el micro oye el
  altavoz. Parker baja la música un momento («duck») y mira si el nivel cae con
  ella (era la canción) o sigue alto (eres tú). Así se puede hablar con música
  puesta y «baja el volumen» afecta a la música, no a la voz. Se arregló además
  un turno que podía dejar a Parker sordo para siempre.
- **v6.6.0 — la ficha que rota**: el prompt enseñaba siempre la primera entrada
  de gustos y sueños; de ahí venía la obsesión con la lluvia y con silbar. Ahora
  rota una entrada por conversación, sin romper el prefijo cacheable.
- **v6.7.0 — el cerebro por voz**: «ponte en local», «vuelve a la nube», «modo
  automático» y «¿qué cerebro usas?» se resuelven sin LLM (0 ms) y el modo se
  guarda en `parker.cerebro.json`, así que un reinicio no lo cambia a escondidas.
  Si se cae internet, lo dice una vez; si el proveedor frena (429), también.
- **v6.8.0 — la cara con vida propia**: un director de gestos elige uno cada
  pocos segundos (micro-ceja, curiosear, mirar arriba, cabezada, suspiro,
  estirón, bostezo, doble toma, guiño) y la familia cambia con el silencio:
  despierto → solo (1,5 min) → aburrido (8 min). Antes de tomar la iniciativa,
  la cara se pone en «pensando», y la iniciativa llega a los 15 min de silencio
  (antes, 45).

### 4.6 30 de octubre — el oído a tiempo (v6.8.1)

La cara aparecía en pantalla, pero al hablarle Parker no reaccionaba. El log lo
delataba: `ningún micrófono contiene «usb»` y `Entrada de audio muerta
(0.00009)`. El micro estaba bien: `arecord -l` lo veía en la tarjeta 3. Lo que
pasaba es que el USB **enumera a los ~29 s del arranque** y PortAudio cachea su
lista de dispositivos al importar; Parker abría el audio antes y se quedaba
enganchado al códec interno, en silencio absoluto. El rearme no servía porque
seguía mirando la lista vieja.

Ahora el primer intento **espera hasta 25 s** y refresca PortAudio
(`_terminate`/`_initialize`) hasta encontrar el micro por nombre. Cuando el
oído queda abierto suena un **chime corto de dos notas** (distinto de la campana
de la agenda): la cara llega antes que el oído, y sin esa señal no se sabe
cuándo empezar a hablar.

Verificado en vivo: v6.8.1, huella `8473cad9` idéntica en PC y placa, micro
`[3] USB PnP`, chime y `tools/prueba_redonda.py` → «Hola, Parker, ¿me oyes?» →
«Oye, Alan, te escucho sin problema» (turno 8,70 s, con la Piper de la prueba
compitiendo por la CPU). Test nuevo: `tests/test_microfono.py` (2/2), que simula
la aparición tardía del USB. Queda confirmarlo con un ciclo de corriente real.

### 4.7 31 de octubre y 1 de noviembre — la cara que se congelaba (v6.10.3)

El 31/10, hablando con Parker, la cara se quedó congelada. Al cambiar el
cerebro al local volvió, y luego se congeló otra vez. El log de esa sesión
demostró dos cosas: el panel SPI no daba ni un error (`errors = 0`, `timedout =
0`) y la orden «Parker, cambio el cerebro en local» **no se ejecutó**: el
reconocedor solo aceptaba «cambia al cerebro local», así que siguió en la nube
y el modelo se inventó que había cambiado.

La causa más probable del congelado es la que ya estaba documentada en
[TREC/errades/Dues instancies i el micro](TREC/errades/Dues%20instancies%20i%20el%20micro.md):
dos procesos de Parker peleándose por el mismo SPI y el mismo micrófono. El
lanzador `arrancar.sh` tenía su *lock*, pero no cubría un `python parker.py`
lanzado a mano. Ahora el propio programa toma un candado en
`~/.parker.runtime.lock`; la segunda instancia sale con un aviso y no toca el
hardware. Además, un vigilante reinicia el GC9A01 si el panel deja de recibir
fotogramas, y un latido anota en el log cualquier bloqueo del hilo gráfico de
más de 1,5 s.

Verificado en la placa el 1/11 con la v6.10.3 (huella `079c39f8`): una sola
instancia, el segundo Parker sale solo, la cara sigue a 15,4 fps en reposo y a
14–15 fps durante un turno local completo. La orden de voz, probada por la
cadena real altavoz → micrófono, cambia a local y vuelve a automático. El
turno local tardó 5,44 s en el primer token, pero la cara no se congeló. El
congelado original no se pudo reproducir en el momento de la prueba; se
atacaron las dos causas que el log y la documentación señalan.

---

## 5. Qué se conservó del plan original y qué cambió

Esta es la tabla que responde a la pregunta «¿en qué quedó todo lo que estaba
pensado?».

| Idea del documento (agosto) | Qué pasó de verdad | Dónde está hoy |
|---|---|---|
| **Doble cerebro** Groq + Ollama | Se descartó en el papel; **volvió en la v6.0** al medir que el local tardaba 8,75 s | Nube primaria + local de respaldo (`modulos/cerebro.py`, [cerebro_doble.md](cerebro_doble.md)) |
| **Solo Ollama**, sin servicios externos | Se intentó; el techo era la placa, no el modelo | Sigue como modo `local` y como respaldo automático |
| **Groq con `llama-3.3-70b-versatile`** | El proveedor rota modelos; el proyecto aprendió a no depender de uno | `openai/gpt-oss-20b` + selección automática si desaparece |
| **Raspberry Pi** | El dispositivo real es una **Orange Pi 5 Pro de 8 GB** | [placa.md](placa.md) |
| **Pygame + barra espaciadora** | Se cambió a escucha continua por VAD; la interfaz es PySide6 | `parker.py`, `modulos/escucha.py`, `modulos/cara_parker.py` |
| **Cara con imágenes de BMO** | Evolucionó a web local y luego a vectores; hoy es una escena vectorial animada | Cara vectorial + 12 principios + pantalla SPI |
| **«Animaciones para la fluidez»** (intención) | Se construyó: lip-sync, gestos, parpadeo, respiración y familias según el silencio | v6.8.0 ([arquitectura.md](arquitectura.md) §5) |
| **Memoria en inglés, umbral 75 %, turno completo** | Los tres cambios de la 2ª actualización se aplicaron y siguen | `paraphrase-multilingual-MiniLM-L12-v2`, umbral 0,58, solo tu mensaje |
| **Memoria «pendiente»** | Está implementada y en uso | `parker.db/`, `tools/recuerdos.py` |
| **Diseño físico con 250 €** | Se materializó la forma del plan 2, pero sin depender del PC | Placa + pantalla circular + carcasa metálica |
| **Asistente de cocina** (plan 3) | No se construyó como tal; sí existe la base para usarlo hablando | Música, apuntes, alarmas y tiempo |

### La letra pequeña de la privacidad

El documento prometía que «les dades no surtin mai del dispositiu». Eso ya no es
exacto al 100 % y conviene decirlo en una presentación antes de que lo pregunte
el tribunal:

- **Siempre local**: micrófono, VAD, cara, voz, ánimo, vínculo y la base de
  recuerdos de Chroma.
- **Por defecto sale a la nube**: el **texto** del prompt (identidad, ánimo, tres
  recuerdos recortados y el último turno) y, desde la v6.1, **el audio del
  turno** para transcribir.
- **Se puede cerrar del todo**: `online.activo: false` y `escucha.motor: local`,
  o decírselo por voz («ponte en local»). Entonces nada sale de casa, a cambio
  de ~8–13 s por respuesta y algún error de transcripción.

Ese es el compromiso real: **privacidad total o velocidad**, y el interruptor
está en la voz.

---

## 6. Los números que resumen el viaje

| Métrica | 17/10 (antes) | 17/10 (después) | 24–25/10 (local 3b) | Ahora (nube) |
|---|---|---|---|---|
| Hasta empezar a oírse | 15–20 s | **4,2–4,7 s** | turno p50 13,45 s | **~1,6 s** de punta a punta |
| Primer token | 6,5–7,8 s | 0,9–1,9 s (1.5b) | 8,75 s p50 | 1,23 s p50 (ruta completa) |
| Transcripción | 4,8–5,3 s (`small`) | 1,6–1,8 s (`base`) | 4,31 s (prueba USB) | **0,68 s** (`whisper-large-v3-turbo`) |
| Generación | — | 17–19 tok/s (1.5b) | 9,3 tok/s (3b) | 742 tok/s (`gpt-oss-20b`) |
| Recuperar recuerdos | 0,15–0,18 s | 0,15–0,18 s | 0,15–0,18 s | 0,15–0,18 s |

La lectura correcta no es «el cerebro local se ha vuelto rápido». Es que **el
cerebro local ya no es el que responde normalmente**: quedó como respaldo, y el
que contesta en ~1 s es la nube. El local sigue entendiendo el contexto y los
recuerdos —por eso se eligió el 3b—, pero se nota que piensa.

---

## 7. Lo que aún queda del plan

Nada de esto está fingido: son cosas que el proyecto ya ha diseñado y todavía no
ha construido, o que están a medias.

1. **La segunda memoria de conocimientos** (recetas, psicología, manuales). El
   diseño está en [plan_mejoras.md](plan_mejoras.md): una colección aparte de
   Chroma, con su propio umbral y su propia decisión de a qué memoria preguntar,
   para no mezclar «lo que me contó Alan» con «lo que dice un libro».
2. **Un Parker 100 % local que sea listo**. Hoy el local es el respaldo: entiende
   mejor que el 1.5b, pero tarda. Las vías son la NPU del RK3588 (RKLLM) y el
   ajuste fino (LoRA) para la voz del personaje; ambas necesitan probarse aparte.
3. **Wiki offline**. Se valoró descargar ~10 GB de Wikipedia y **se decidió no
   hacerlo**: la tarjeta guarda los recuerdos de Chroma, llenarla acelera su
   desgaste y no daría respuestas más rápidas, porque Parker contesta con el
   modelo y no consultando un corpus. Lo que sí queda pendiente es una consulta
   puntual a la API REST de Wikipedia («¿quién fue X?») con el resumen guardado
   en Chroma.
4. **Cocina**. El plan 3 del documento: dictar una receta paso a paso. La base
   (voz, pausas, agenda, listas) ya existe; falta la función.
5. **El acabado físico**: cierre limpio con ESC en el montaje final, carcasa
   definitiva y ventilación. La refrigeración no es estética: es la palanca que
   más afecta al cerebro local (§4.2).

---

## 8. Cómo contarlo (guion)

### En un minuto

> Parker empezó como una idea sin código: un acompañante con doble cerebro
> —uno en internet y otro en casa—, memoria y cara. Se construyó un prototipo en
> el PC con Pygame y Groq, y cuando llegó la placa se midió todo: el cerebro
> local tardaba 8,75 s en decir la primera palabra. La solución fue volver al
> plan original, pero repartiendo el trabajo: la placa oye, habla, recuerda y
> pone la cara; la nube solo escribe la frase. Así se pasó de 15–20 s a ~1,6 s,
> sin perder la memoria ni la cara. Hoy Parker tiene agenda, rutinas, apuntes,
> música y una cara que se mueve sola, y si se cae internet sigue funcionando
> con el cerebro de casa.

### En cinco minutos

1. **El problema** (30 s): no es un altavoz; es alguien que está ahí. Eso obliga
   a que sea listo, rápido y que recuerde.
2. **El papel** (1 min): las cuatro piezas y el doble cerebro; la decisión de
   quedarse solo con Ollama por privacidad y coste.
3. **El prototipo** (1 min): Pygame, barra espaciadora, `.wav`, Groq, BMO; los
   tres lenguajes visuales.
4. **La placa** (2 min): 15–20 s → 4,2 s; el 3b y el `num_ctx` ampliado a 2048;
   el techo térmico; el doble cerebro de la v6 y el 1,23 s; STT en la nube.
5. **Hoy y lo que falta** (30 s): agenda, rutinas, cara viva; segunda memoria,
   LoRA y el acabado físico.

---

## 9. Dónde está cada cosa

| Documento | Qué cuenta |
|---|---|
| [historia_original.md](historia_original.md) | El texto original del autor, en catalán y sin retocar |
| [arquitectura.md](arquitectura.md) | Cómo está montado Parker por dentro |
| [rendimiento.md](rendimiento.md) | Todas las medidas, incluidos los experimentos que fallaron |
| [cerebro_doble.md](cerebro_doble.md) | La nube y el local, modos, avisos y privacidad |
| [dia.md](dia.md) | Rutinas, apuntes, tiempo, música y apagado |
| [evolucion.md](evolucion.md) | Cómo podría cambiar su carácter con el tiempo (diseño) |
| [plan_mejoras.md](plan_mejoras.md) | Lo pendiente y cómo se medirá |
| [placa.md](placa.md) | Hardware, SPI, instalación y diagnóstico |
| [respaldos.md](respaldos.md) | Qué hay en cada copia y qué cambió |
| `modulos/version.py` | La marca de versión y el historial completo |

**Para mantener este documento vivo:** cada versión nueva añade una fila a §4 y
actualiza la tabla de §6; el documento original no se toca nunca.
