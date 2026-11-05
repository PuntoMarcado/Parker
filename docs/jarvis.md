# Mejoras tomadas del patrón Jarvis (desk-robot)

> **Qué es este documento.** El proyecto `desk-robot` (un Jarvis de sobremesa)
> separa el turno de conversación en piezas que se pueden **cancelar**: orejas,
> pensamiento y boca no son un bloque único que hay que esperar. Parker ya tenía
> la idea de frases en streaming y look-ahead; lo que faltaba era poder
> **abandonar un turno a mitad** sin dejar el bucle sordo. Esto es lo aplicado
> en la versión **v6.12.14**.

## El problema que resolvía

El 01/11/2026, con el barge-in de v6.12.9, «Parker, para» cortaba el altavoz
(`[Voz] Reproducción detenida`) pero Parker **no volvía a escuchar**. El log se
quedaba sin `Turno completo` y el proceso seguía vivo. No era un cuelgue de la
cara ni del micro: era el hilo del turno esperando algo que ya no iba a llegar.

La causa tenía dos capas:

| Capa | Qué pasaba |
|---|---|
| Altavoz | `sd.wait()` esperaba al stream aunque `sd.stop()` ya hubiera parado el sonido; el turno no soltaba `ocupado`. Se cambió por una espera que consulta el stream y el evento de corte cada 20 ms, y cierra el stream al terminar. |
| Cerebro | `for delta in deltas` solo miraba el evento **cuando llegaba un token**. Si el modelo se callaba a mitad de respuesta, el hilo se quedaba bloqueado esperando; el `close()` del generador desde el monitor lanzaba `generator already executing` si el hilo lector estaba dentro. |

## Lo que se aplicó

### 1. Monitor de barge-in separado (ya existía; se conserva)

Mientras Parker habla, un hilo aparte abre el micrófono, transcribe ventanas de
1,4 s (con 0,4 s de solape) y compara cada frase con las que están sonando para
no confundir su propia voz con una orden. Solo corta con «Parker, para»,
«Parker, cállate», «Parker, basta» o variantes; una pregunta como «¿para qué?»
no cuenta. Si el micro no admite entrada y salida a la vez, el monitor sale en
silencio y el turno normal sigue.

### 2. Hilo lector de tokens + cola con espera corta

`Parker._deltas_con_corte()` lee el stream del cerebro en un **hilo daemon** y
deja cada token en una `queue.Queue`. El bucle del turno espera como máximo
**0,2 s** por token y, entre espera y espera, consulta el evento de barge-in.
Así una orden de parada se atiende aunque el modelo no mande nada. La cola está
limitada a 32 elementos: si el consumidor se va, el lector no crece sin freno.

### 3. Cancelación del stream y limpieza del turno

Al oír la orden:

1. Se marca `_barge_in`.
2. Se para el altavoz con `VozParker.detener()`.
3. Se intenta cerrar el generador actual (`_cancelar_stream_actual`), pero **no
   se depende de ello**: el hilo lector es quien desbloquea el bucle.
4. El turno descarta la síntesis y la reproducción pendientes.
5. `preparar_turno()` limpia el evento al empezar el turno siguiente; si no, la
   primera frase nueva se descartaría sola y Parker se quedaría mudo.

`VozParker.sintetizar()` y `reproducir()` también comprueban el evento: un audio
sintetizado después del corte ya no suena.

### 4. Cierre del stream de salida

`VozParker.reproducir()` cierra el `OutputStream` al terminar cada frase. Antes
`sd.stop()` lo paraba pero no siempre lo cerraba, y el siguiente proceso recibía
`Device or resource busy`. Esto explica parte de los fallos de audio de las
pruebas del 01/11.

## Pruebas

### En el PC (sin micrófono ni altavoz)

```bash
cd /d/TREC/parker_v5
venv/Scripts/python.exe tests/test_barge_in.py
venv/Scripts/python.exe tests/test_voz.py
venv/Scripts/python.exe tests/test_pipeline.py
```

Resultado del 01/11/2026:

* `test_barge_in.py`: **6/6**. Incluye `test_cancelar_stream_desbloquea()`
  (un generador que se queda callado a mitad, cerrado desde el monitor, deja de
  bloquear el hilo) y `test_lector_con_corte_no_bloquea()` (el lector abandona
  la cola al primer aviso de corte aunque el modelo no mande más tokens).
* `test_voz.py`: **4,68 s calmada vs 4,33 s normal**, tono 120 Hz frente a
  119 Hz, pico 0,55.
* `test_filtro_stt.py`: **3/3**. Alucinaciones conocidas y repeticiones se
  descartan; «sí», «no» y «vale» pasan; las métricas solo actúan con señales
  fuertes.
* `test_escucha_nube.py`: **5/5**, incluida la lectura de `verbose_json` y sus
  tres métricas.
* `test_pipeline.py`: **todo en verde** (stream, look-ahead, corte por frases,
  resto incompleto, cola del orador, térmica, borrado de memoria y vigilante
  del micro).

### En la placa (Orange Pi 5 Pro)

Desplegado y arrancado con **v6.12.10**:

```
[Cerebro] v6.12.10-barge-in | primario NUBE (...) + respaldo LOCAL (...)
[Voz] Motor: Edge TTS (es-ES-XimenaNeural); respaldo Piper 22050Hz
[Escucha] Micrófono elegido por nombre: [3] USB PnP Audio Device: Audio (hw:3,0)
[Escucha] Micrófono listo; aviso sonoro.
```

En el log de la placa se ha visto el monitor activo y, en la prueba anterior,
el reconocimiento real de la orden:

```
[Barge-in] «Parker, para.» -> corto la voz
[Voz] Reproducción detenida
[Voz] Reproducción cortada por barge-in
```

**Lo que no quedó cerrado en esta sesión:** la prueba acústica de ida y vuelta
con el altavoz del PC como «voz del usuario» no volvió a reconocer la orden en
la última pasada: el STT transcribió ruido («No está hablando de parque»,
«¡Ah! ¡Ah! ¡Ah!») porque el micro de la placa está captando también la voz de
Parker y el ruido de la sala. El corte de voz y el desbloqueo están probados en
código y el monitor está activo, pero **la recuperación acústica después de un
barge-in real queda pendiente de repetir con el usuario hablando cerca del
micrófono**. No se debe presentar como «probado en voz real» hasta hacerlo.

### 5. Filtro de alucinaciones del STT (v6.12.11)

En la misma prueba salió el otro fallo: Parker contestaba a frases que Whisper
inventa con ruido o con la cola del altavoz. Ahora el STT pide `verbose_json`
a la nube (Groq devuelve `no_speech_prob`, `avg_logprob` y
`compression_ratio` por segmento) y el local lee las mismas señales de
faster-whisper. Un módulo pequeño, `modulos/filtro_stt.py`, descarta:

* alucinaciones conocidas («Gracias por ver el video», «¡Suscríbete al
  canal!», «Hasta la próxima»);
* interjecciones sueltas («¡Ah!», «eh», «mmm») y repeticiones («¡Ah! ¡Ah!
  ¡Ah!»);
* `no_speech >= 0,80`, `compression_ratio >= 3,0` o `avg_logprob <= -1,5`.

Los umbrales son altos a propósito: «sí», «no», «vale», «gracias, Parker» y
«¿qué hora es?» siguen pasando. La frase descartada se queda en el log como
`[Escucha] Transcripción dudosa; ignoro: …`, sin ejecutar órdenes ni llamar al
cerebro.

**Medido con el corpus real de la placa (01/11/2026, v6.12.11):**

| Audio del corpus | Texto | Métricas | Filtro |
|---|---|---|---|
| `20261101-214445_363.wav` | «¡Suscríbete al canal!» | logprob -0,43; compresión 0,75 | **descarta** |
| `20261101-214649_315.wav` | «No, no, no.» | logprob -1,18; compresión 0,75 | **pasa** (puede ser énfasis real) |
| `20261101-214520_635.wav` | frase larga de una TV de fondo | logprob -0,13 | **pasa** (limitación) |

La tercera fila es importante: si hay una **voz humana real de fondo** (la tele
con una conversación), el filtro de texto no puede saber si es el usuario o la
tele. Eso necesita palabra de despertar, AEC o un micrófono direccional; no se
resuelve con una lista de frases.

En la placa (v6.12.11) también se vio el filtro en acción con una transcripción
larga de ruido:

```
[Escucha] Transcripción: 'en Japón, en el qual uno hace un monstruo...'
[Escucha] Transcripción dudosa; ignoro: 'en Japón, en el qual uno hace un monstruo...'
```

Y, tras la respuesta, `[Error Stream Audio] Error opening InputStream: Device
unavailable`; de ahí el ajuste de v6.12.12 (esperar al monitor antes de reabrir
el micro).

### 6. El micrófono después de hablar (v6.12.12)

En la prueba de ida y vuelta aparecieron varios `Device unavailable` seguidos
justo después de una respuesta. El monitor de barge-in podía estar todavía
transcribiendo su última ventana y mantenía abierto su `InputStream`; el bucle
principal intentaba abrir el suyo al mismo tiempo. Ahora se espera hasta **5 s**
al monitor (antes 2 s) y, si sigue ocupado, se avisa en el log. El bucle
principal reintenta y el micro vuelve; no se queda sordo para siempre, pero el
aviso permite distinguir «estaba cerrando el monitor» de un fallo real.

## Lo que no se aplicó (y por qué)

| Idea de Jarvis | Estado | Motivo |
|---|---|---|
| Cancelación cooperativa del `requests` en curso | **No** | `requests` no permite cancelar un `iter_lines` desde otro hilo; por eso se usa el hilo lector + cola y se abandona el lector. Cerrar el generador desde fuera puede lanzar `generator already executing`. |
| AEC (cancelación de eco) con SpeexDSP | **No** | El micro USB está pegado al altavoz; sin AEC el monitor oye a Parker. Es la siguiente mejora acústica, pero necesita medir CPU y latencia en la RK3588S. |
| Palabra de despertar con openWakeWord | **No** | Los modelos preentrenados son en inglés; «Parker» en español exigiría entrenar y medir falsos positivos. |
| Turno con estado explícito (`idle → listening → thinking → speaking → idle`) | **Parcial** | Ya hay `ocupado`, `_sonando` y eventos, pero no un único objeto de estado. Se puede unificar cuando se toque el bucle principal. |
| Cancelar también la síntesis Edge en curso | **Parcial** | `sintetizar()` comprueba el evento antes de empezar; si Edge ya está dentro de la llamada, se espera a su `edge_timeout` (8 s) o a ffmpeg. El hilo lector evita que eso bloquee el turno, pero el audio pendiente se descarta. |

## Cómo probarlo de nuevo

```bash
# 1. En el PC: tests rápidos
cd /d/TREC/parker_v5
venv/Scripts/python.exe tests/test_barge_in.py
venv/Scripts/python.exe tests/test_pipeline.py

# 2. En la placa: comprobar versión y que el monitor arranca
ssh orangepi@192.168.1.130 'grep -a "6.12.10" ~/parker.log.1 | tail -2'
ssh orangepi@192.168.1.130 'grep -a "monitor activo" ~/parker.log.1 | tail -2'

# 3. Prueba acústica (con Parker hablando y el usuario cerca del micro)
#    - Pregunta larga por el altavoz de la placa.
#    - En cuanto empiece a hablar, decir «Parker, para» a 30-50 cm del micro.
#    - Comprobar en el log: «-> corto la voz» y, después, un turno nuevo.
ssh orangepi@192.168.1.130 'tail -n 30 ~/parker.log.1 | tr -d "\0" | grep -E "Barge-in|Turno completo|Parker -> Voz|Usuario"'
```

Si el monitor no oye la orden, el problema es acústico (distancia, eco o
ganancia), no el hilo del turno: el log debe mostrar `[Barge-in] monitor
activo` y las frases que va oyendo, pero no `-> corto la voz`.

## Dónde está en el código

| Archivo | Qué contiene |
|---|---|
| `modulos/barge_in.py` | Decisión de orden de parada y separación del eco. |
| `parker.py` | `_deltas_con_corte`, `_cancelar_stream_actual`, `_vigilar_barge_in`, `_hablar_stream_interno` y `preparar_turno`. |
| `modulos/voz.py` | `preparar_turno`, `detener`, comprobación en `sintetizar`/`reproducir` y cierre del stream de salida. |
| `modulos/filtro_stt.py` | Filtro de alucinaciones y repeticiones, con umbrales conservadores. |
| `modulos/escucha.py` | `verbose_json` en la nube y lectura de `no_speech/logprob/compresión` también en local. |
| `tests/test_barge_in.py` | 6 pruebas, incluida la cancelación del stream y del lector. |
| `tests/test_filtro_stt.py` | 3 pruebas del filtro de STT. |
| `modulos/version.py` | Historial y versión `6.12.14`. |
