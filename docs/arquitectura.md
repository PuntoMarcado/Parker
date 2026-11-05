# Arquitectura de Parker

Este documento describe cómo se organizan los módulos, los hilos y el flujo de
datos en tiempo real. Es la referencia para tocar el código sin romper el
equilibrio entre "cara siempre viva" y "respuesta inmediata".

---

## 1. Visión general

```
                       ┌────────────────────────────────────────────┐
   micrófono ─────────►│  hilo escucha (parker.py)                  │
   (sounddevice)       │  1. VAD por volumen: espera voz            │
                       │  2. Graba hasta 0,6 s de silencio o 20 s   │
                       │  3. STT → texto                            │
                       └───────────────┬────────────────────────────┘
                                       │ texto
                                       ▼
                       ┌────────────────────────────────────────────┐
                       │  hilo principal Qt                          │
                       │  (señales SenalesCara → cara + etiqueta)    │
                       └───────────────┬────────────────────────────┘
                                       │
                                       ▼
                       ┌────────────────────────────────────────────┐
                       │  CerebroParker (streaming NDJSON)           │
                       │  · recupera recuerdos (ChromaDB)            │
                       │  · Ollama /api/chat stream=true             │
                       │  · etiquetas [CARA:emoción] + texto         │
                       └───────┬──────────────────────┬──────────────┘
                    fragmentos │                      │ recuerdo guardado
                               ▼                      ▼ (al terminar de generar)
                       ┌──────────────────────┐  ┌──────────────────┐
                       │ frases cortadas      │  │ Memoria vectorial│
                       │ (dividir_oraciones)  │  │ ChromaDB + SBERT │
                       └──────────┬───────────┘  └──────────────────┘
                                  │ cola (queue.Queue)
                                  ▼
                       ┌────────────────────────────────────────────┐
                       │  hilo orador: Piper sintetiza + sd.play     │
                       │  emite señal hablando=True/False            │
                       └────────────────────────────────────────────┘

   Cara (PySide6 QGraphicsScene 400×400) ──► ventana fullscreen
                                 └──────────► captura 240×240 ──► SPI GC9A01
```

## 2. Módulos

| Módulo | Responsabilidad | Interfaz pública |
|---|---|---|
| `parker.py` | Orquestación: ventana, hilos, VAD, cola de voz, autonomía | `Parker`, `ParkerWindow`, `SenalesCara` |
| `modulos/cerebro.py` | Generación de respuesta con Ollama + etiquetas de emoción | `hablar_stream()`, `hablar()`, `hablar_proactivo()`, `pensar()`, `calentar()` |
| `modulos/escucha.py` | STT con backend conmutable | `EscuchaParker.transcribir(audio)` |
| `modulos/voz.py` | TTS Piper en memoria | `VozParker.hablar(texto, bloquear=True)` |
| `modulos/memoria.py` | Recuerdos vectoriales | `guardar_recuerdo()`, `recuperar_recuerdos_formateados()` |
| `modulos/personalidad.py` | Quién es Parker: gustos, sueños, manías, miedos y ánimo persistente | `PersonalidadParker.system_prompt()`, `contexto_volatil()`, `instruccion_proactiva()`, `latido()`, `rotacion()` |
| `modulos/acciones.py` | Órdenes sin LLM: volumen, silencio y silbido | `AccionesParker.procesar(texto) -> (frase, sonido)` |
| `modulos/agenda.py` | Alarmas, temporizadores y citas guardadas en local | `AgendaParker.procesar(texto) -> frase`, `vencidos()`, `marcar_avisado()`, `frase_aviso()` |
| `modulos/sonidos.py` | Silbido, campana y despertador generados con numpy | `silbar()`, `campana()`, `despertador(volumen)` |
| `modulos/rutinas.py` | El día: dormir/despertar, silencio temporal, parte del día y apagado | `RutinasParker.procesar()`, `parte_del_dia()`, `debe_callarse()`, `toca_parte()` |
| `modulos/apuntes.py` | Notas, listas y contadores sin hora («litros de agua») | `ApuntesParker.procesar()` |
| `modulos/tiempo.py` | El tiempo (Open-Meteo, sin clave) y la ciudad variable | `TiempoParker.procesar()`, `cambiar_ciudad()`, `respuesta_clima()` |
| `modulos/musica.py` | Música por API (Deezer): busca, descarga y decodifica; y distingue tu voz de la canción cuando suenan las dos | `MusicaParker.procesar(sonando=)`, `buscar()`, `preparar()`, `ganancia()`, `ganancia_objetivo()`, `duck`; `OyenteMusica.observar()` |
| `modulos/cara_parker.py` | Cara + Alive Motion Engine + lip-sync + los 12 principios | `FaceController.set_expression()`, `iniciar_habla()`, `detener_habla()`, `guino()`, `bostezo()`, `doble_toma()`, `gesto()`, `set_silencio()`, `dormirse()`, `despedida()` |
| `modulos/display_spidev.py` | Driver SPI/GPIO GC9A01 (solo Linux/SBC) | `GC9A01Display.attach_scene(scene)` |

### Convenciones de las etiquetas

El cerebro antepone `[CARA:emoción]` a su respuesta
(`feliz, triste, pensando, confundido, sorpresa, neutral, escuchando, carino`).
En `parker.py` conviven tres funciones:

- `extraer_emocion(texto)` → última emoción del texto en streaming.
- `limpiar_etiquetas(texto)` → quita la etiqueta antes de pasar la frase a
  Piper y también el markdown (`**cariño**`) y los signos que quedan huérfanos.
  La etiqueta se reconoce sin distinguir mayúsculas y admite `[Cara: neutral]`
  o `[Neutral]` sueltas: los modelos pequeños no siempre copian el formato.
- `dividir_oraciones(texto)` → separa frases **completas** del resto incompleto
  para poder empezar a hablar antes de terminar de generar.

## 3. Hilos y concurrencia

| Hilo | Origen | Qué hace |
|---|---|---|
| Qt principal | `main()` | Render de la cara, timers de parpadeo/mirada/lip-sync, señales |
| Carga inicial | `main()` → `threading.Thread` | Construye `Parker` (memoria, escucha, cerebro, voz) sin congelar la UI |
| Escucha continua | `Parker.__init__` | VAD, grabación y transcripción; llamada bloqueante al pipeline |
| Orador | `Parker.__init__` | Consume `self._cola_voz` y ejecuta Piper + `sd.play` |
| Autonomía | `Parker.__init__` | Cada 30 s mira el reloj: parte del día a su hora, silencio temporal, caducidad de la iniciativa y (cada 300 s) conversación propia si sigue el silencio |
| Música | `Parker.__init__` | Consume `_cola_musica` y suena los adelantos por bloques de 0,25 s (parables a media canción; la ganancia va en rampa, así el «duck» y los cambios de volumen no dan golpes) |
| Agenda/día | `Parker.__init__` | Cada 1 s mira si algún aviso venció (campana + frase) |
| Agenda | `Parker.__init__` | Cada 1 s mira si algún aviso venció: campana + frase (ver `docs/agenda.md`) |

Compartición de estado:

- `Parker.ocupado` evita que la escucha y la respuesta se pisen (flag simple
  que comprueban el bucle de escucha, el de autonomía y el de la agenda: un
  aviso espera a que Parker termine de hablar antes de sonar). **Se suelta
  SIEMPRE** al final del turno, pase lo que pase: un camino que no lo soltara
  dejaba a Parker sordo para siempre (visto el 27/10 con la música: el turno
  nacido de la canción se ignoraba sin hablar y sin soltar el turno).
- `Parker._lock_voz` (threading.Lock) serializa la voz: la escucha, la agenda y
  el hilo de autonomía nunca hablan a la vez; si llegan a la vez, el segundo
  espera a que termine el primero. La música **no** coge este cerrojo: suena en
  su propio flujo y se corta antes de que hable nadie (un aviso de la agenda
  para la música y luego suena la campana).
- `Parker.musica_sonando` es el modo música. Con la canción puesta el micrófono
  oye el altavoz, así que el bucle de escucha **no abre turno por nivel**: llama
  a `OyenteMusica`, que prueba bajando la música (`musica.duck`, al 15 % por
  defecto) y mira si el nivel cae con ella (era la canción, no se abre nada) o
  sigue alto (eres tú: abre turno con un pre-roll de 1,1 s). El turno se atiende
  con la música baja y al terminar vuelve a su volumen (rampa de 0,25 s por
  bloque). Mientras suena, las órdenes de música van primero: «baja el volumen»
  es la música, no la voz. La iniciativa y el parte del día esperan a que la
  canción termine.
- `SenalesCara` (QObject con `Signal`) es el **único** puente entre hilos y la
  cara: Qt encola automáticamente las señales cruzando hilos.
- La cola `queue.Queue` del orador ordena las frases: nunca se solapan.

## 4. Ciclo de una interacción

1. **Escucha pasiva**: RMS por encima de `umbral_silencio` → cara en `escuchando`.
2. **Corte**: `silencio_corte_seg` (0,6 s por defecto) o
   `duracion_maxima_grabacion` (20 s).
3. **STT**: `EscuchaParker.transcribir()` → texto (se imprime `[Latencia] STT`).
   El modelo ya fue cargado antes de abrir el micrófono. No se precalienta cada
   turno: la prueba mostró que competir con Whisper perjudicaba la latencia.
4. **Limpieza de voz**: antes de pasar cada frase a Piper, corrige el vocativo y
   retira saludos/fórmulas genéricas repetidos en una conversación en curso;
   deja el contenido concreto para no descartar información útil.
5. **Cerebro**: `hablar_stream()` recupera recuerdos y abre un stream NDJSON.
   El historial guarda el mensaje **exacto** que se envió (con el bloque
   volátil), para que el prefijo coincida token a token con el turno anterior:
   sin eso Ollama reevalúa todo el historial y el primer token sube 2-3 s.
6. **Primer token**: se imprime `[Latencia] Primer token del cerebro`. Si el
   modelo estaba descargado, `calentar()` se ejecutó antes de activar el
   micrófono y evita competir por CPU con Whisper.
7. **Primera frase completa**: se encola → `[Latencia] Fin de frase lista para
   hablar`. El hilo orador emite `hablando=True` y la cara abre la boca
   (lip-sync a 110 ms).
8. **Mientras suena**, el modelo sigue generando y la cola va recibiendo frases.
9. **Fin**: se guarda el recuerdo en ChromaDB, `hablando=False`, cara a `neutral`.

## 5. Motor de vida (cara)

- `_tick_alive_engine` (33 ms): flotación, micro-inclinación y respiración
  (squash & stretch) superponiendo sinusoides.
- Parpadeo asíncrono cada 2–5 s con 28 % de probabilidad de doble parpadeo;
  cierre rápido (~75 ms) y apertura más lenta con rebote, con cejas como
  acción secundaria. Duraciones con jitter para que no se repita idéntico. El
  ritmo base (2-5 s) se espacia con el silencio (v6.8.0), con parpadeos lentos
  de sueño cuando lleva mucho rato solo.
- **Director de gestos en reposo** (v6.8.0): un tercer timer autónomo lanza un
  gesto cada 4-13 s de una familia que cambia con el silencio — `despierto`
  (< 1,5 min), `solo` (< 8 min) y `aburrido` (a partir de ahí: bostezos y
  cabezadas) —. El catálogo está en `FAMILIAS_GESTOS` con pesos relativos, y
  el silencio llega por la señal `SenalesCara.silencio` → `set_silencio()`.
  Cada gesto (`micro_ceja`, `curiosear`, `mirar_arriba`, `cabecear`,
  `estiron`, `suspirar`, más los de siempre: `guino`, `bostezo`, `doble_toma`,
  `asentir`, `negar`) vuelve a la pose de la expresión actual (`_pose_base`),
  y `gesto(nombre)` los lanza a mano (lo usa `parker.py` antes de la charla
  propia). No gesticula mientras habla (manda el lip-sync) ni dormido:
  `dormirse()` para el timer y `despertarse()` lo vuelve a programar.
- **Acción superpuesta (`GRUPOS_ANIMACION`)**: en cada cambio de expresión los
  ojos arrancan solos, la cabeza +40 ms, la boca +65 ms y las cejas +90 ms,
  con duraciones ligeramente distintas. La cara nunca se mueve "en bloque".
- **Mirada en arco**: los ojos hacen una sacada rápida (OutExpo), el eje
  vertical va más lento (dibuja un arco) y la cabeza los sigue con retardo.
- `set_expression()` aplica anticipación (squash previo, con jitter) + rebote
  `OutBack` al asentarse, todo con superposición entre grupos.
- Lip-sync: `_animar_fonemas_habla` a 110 ms mientras `iniciar_habla()`
  (ruta sin estagger para que la boca no se retrase).
- `FaceController.detener()` para todos los temporizadores para un cierre
  limpio (se llama al salir con ESC y en `closeEvent`).

## 6. Autonomía temporal

`_loop_autonomia` duerme `intervalo_comprobacion_seg` (300 s) y llama a
`_comprobar_autonomia()`:

- Si llevas `umbral_silencio_seg` sin interacción (900 s = 15 min desde la
  v6.8.0; antes 2700 s), el bandit elige el brazo y la cara se pone en `pensando`
  antes de hablar: `cerebro.hablar_proactivo(brazo=brazo)`. Desde la v6.10.1 la
  frase sale de una semilla concreta (`semilla_iniciativa`: ficha, hora,
  propuesta o último mensaje), no de una instrucción abierta al LLM. Desde la
  v6.10.2 esa semilla se recorta y se elige sin repetir, y la última frase
  queda guardada en `parker.estado.json` (`guardar_iniciativa`) para poder
  explicarla aunque Parker se reinicie.
- `umbral_sedentario_seg` (3600 s) está en `config.yaml` pero **aún no se usa**:
  es el gancho previsto para sugerir agua/estirarse cuando la sesión es larga.

## 6 bis. Agenda (alarmas, temporizadores y citas)

`_loop_agenda` duerme 1 s (`agenda.intervalo_comprobacion_seg`) y pregunta a
`agenda.vencidos()`. Por cada aviso vencido llama a `_avisar_agenda()`, que
espera a que Parker no esté hablando, cambia la cara a `sorpresa`, suena
`sonidos.despertador` (con `forzar=True`: un aviso se pide a propósito y suena
incluso con la voz silenciada) y dice la frase con la cola normal de voz.

Las órdenes se resuelven en `_responder_sin_llm()`, antes que los datos fijos
(fecha/hora/nombre) y sin llamar al modelo; lo resuelto se apunta al historial
con `cerebro.registrar_suceso()`, para que el turno siguiente sepa que la alarma
existe (si no, el modelo diría que él no pone alarmas). Reglas y frases:
`docs/agenda.md`.

## 7. Memoria

- Colección ChromaDB en `./parker.db`, espacio coseno.
- El **embedding** se genera solo con el mensaje del usuario
  (`texto_embedding=...`), mientras que el **documento** guardado es el diálogo
  completo `Usuario: ...\nParker: ...` — así las búsquedas comparan pregunta
  contra pregunta y no se diluyen con las respuestas.
- `top_k_recuerdos=2`, `umbral_relevancia=0.5` y `max_caracteres_recuerdo=110`
  (los valores de `config.yaml`; el cerebro ya no ignora la configuración).
  Cada recuerdo se envía en una sola línea, sin tipo ni similitud, y los
  repetidos se descartan: son tokens que el modelo reprocesa en cada frase.
- Multilingüe por diseño del modelo.

## 8. Pantalla SPI (GC9A01)

`GC9A01Display.attach_scene()` pone un `QTimer` a 25 fps que:

1. Renderiza la escena 400×400 → `QImage` 240×240 `Format_RGB16` (con
   antialiasing).
2. Intercambia bytes Little→Big Endian en un `bytearray` plano.
3. Envía por SPI a 24 MHz (`0x2A/0x2B/0x2C`).

Los pines **no están cableados en el código**: `config.yaml` → `pantalla.dc_gpio`
/ `pantalla.rst_gpio` los declara por nombre (`GPIO1_B0`, `GPIO4_B3`) y el
driver resuelve el `/dev/gpiochipN` por el label del banco (`gpio1`, `gpio4`),
que es estable aunque la numeración de chips se desplace. Recablear no requiere
editar código. La tabla de cableado y la escalera de diagnóstico de pantalla
blanca están en [placa.md](placa.md) §7; el autotest es
`python modulos/display_spidev.py`.

## 9. Personalidad y ánimo

La identidad de Parker vive en `modulos/personalidad.py`, separada del motor del
LLM: ahí están sus gustos, sus sueños, sus manías, sus miedos y sus muletillas
(datos, no código), y ahí se construye el prompt que recibe Ollama.

La ficha que el prompt enseña (un gusto y un sueño) **rota entre
conversaciones**: `_rotar_si_toca()` avanza una entrada cuando la última charla
fue hace `personalidad.rotacion_minutos` (45) o más, o al arrancar tras un rato
apagado. Dentro de una conversación no cambia nada — el bloque de identidad es el
prefijo cacheable —, así que la variedad no cuesta latencia: sus ocho gustos y
sus cinco sueños van saliendo todos en vez de quedarse siempre el primero (era
exactamente lo que pasaba hasta la v6.6.0: el prompt decía «le gusta la lluvia»
y «sueña con silbar» en todos los turnos).

El ánimo son tres números de 0 a 1 (`energia`, `curiosidad`, `carino`) más el
registro de interacciones, guardados en `parker.estado.json`. Sube al hablar y
baja con el silencio. De ahí salen dos comportamientos:

- `latido(silencio)` se llama desde el hilo de autonomía: con mucho silencio baja
  la energía y sube el cariño (te echa de menos).
- `instruccion_proactiva()` decide **qué** hace Parker cuando toma la iniciativa:
  contar algo suyo, preguntar por algo pequeño del día, confesar un sueño o decir
  que te ha echado de menos. Ya no saluda siempre igual.

### El orden del prompt importa (latencia)

Ollama reutiliza el prefijo ya procesado, así que el prompt se parte en dos:

| Parte | Dónde viaja | Cambia |
|---|---|---|
| Identidad + reglas | mensaje `system` | nunca (cacheable) |
| Ánimo, fecha, recuerdos, contexto | pegado al mensaje del usuario | en cada frase |

Medido en la placa: con el ánimo *dentro* del sistema, el historial se
reprocesaba entero en cada respuesta y el primer token tardaba 5-9 s (y hasta
33-40 s en la primera versión del prompt); moviéndolo al mensaje del usuario baja
a 0,9-1,9 s (con el prefijo cacheado y precalentado mientras se graba). Lo mismo
con el tamaño: cada token **volátil** se paga en cada frase,
de ahí que el bloque de identidad esté recortado a ~250 tokens y que el
historial conserve los dos últimos intercambios (`historial_mensajes: 4`).

El ánimo viaja en abstracto (`energía media, curiosidad alta, cariño alto`), no
como frases en primera persona: con `qwen2.5:1.5b` y `3b` las frases se citaban
palabra por palabra y Parker acababa leyendo su propia ficha.

### Presupuesto medido (17/10/2026, Orange Pi 5 Pro)

| Etapa | Antes | Ahora |
|---|---|---|
| Corte de silencio | 1,3 s | 0,6 s |
| STT (`small` → `base` int8) | 4,8-5,3 s | 1,6-1,8 s |
| Primer token (`3b` + prompt largo → `1.5b` + prompt recortado + prefijo cacheado) | 6,5-7,8 s | 0,9-1,9 s |
| Primera frase lista | 7,5-9 s | 1,3-2,1 s |
| TTS de la primera frase | 0,7-1,4 s | 0,5-0,9 s |
| **Hasta que empieza a sonar** | **15-20 s** | **4,2-4,7 s** |

El detalle y las alternativas estudiadas (NPU, whisper.cpp, Piper en NPU) están
en [rendimiento.md](rendimiento.md).

## 10. Los 12 principios en la cara

`cara_parker.py` exporta el diccionario `PRINCIPIOS` con los doce principios de
Thomas y Johnston y **dónde está cada uno en el código**; `tests/test_animacion.py`
falla si alguno desaparece o si el método que cita no existe.

Los que más se notan:

- **Squash y Stretch**: respiración continua en `_tick_alive_engine` y estirón al
  despertar en `reproducir_intro`.
- **Anticipación**: `set_expression()` hace primero el gesto contrario (se hunde
  antes de estirarse, se inclina al lado contrario antes de girar).
- **Continuación y superposición**: un muelle de segundo orden (`_integrar_muelle`)
  hace que el *dibujo* persiga la pose con retardo y sobreimpulso — la cabeza se
  pasa un poco y vuelve— sin tocar los valores lógicos, así que los tests siguen
  viendo los números exactos.
- **Acción secundaria**: al parpadear bajan las cejas y al hablar la cabeza
  acompaña las palabras.
- **Exageración**: `set_expression(nombre, exageracion=1.4)` escala la desviación
  respecto a la pose neutra (para reaccionar más o menos según el contexto).
- **Atractivo**: gestos propios con asimetría (`guino`, `bostezo`, `doble_toma`,
  `asentir`, `negar`) y una intro de ~4,5 s que despierta, mira a los lados,
  bosteza y termina mirando al frente.

`detener()` pone `_activo = False`, así que ningún gesto ya programado sigue
animando una escena que se está cerrando.

Si `spidev`/`gpiod` no existen (PC de desarrollo), el import falla de forma
controlada y Parker sigue funcionando solo con ventana.
