"""
modulos/version.py
==================
Marca de versión de Parker: la ÚNICA fuente de verdad sobre qué código corre.

Se imprime al arrancar (primeras líneas del log) y viaja en cada respaldo
(`LEEME.txt`), así que en cualquier momento se puede saber qué versión está
ejecutando la placa sin adivinar por la fecha de los ficheros.

Subir la versión al cambiar algo que se note en el comportamiento:
    MAYOR  cambio de arquitectura (v6 = cerebro doble nube+local)
    MENOR  función nueva
    PARCHE arreglo de un fallo

Historial:
    6.13.0  02/11  Modo demo de la cara (02/11): «Parker, modo demo» o
                  «muéstrame todas tus animaciones» recorre la intro, las 8
                  expresiones y los 11 gestos del catálogo, y vuelve solo a
                  neutral; «para la demo» lo corta. No toca cerebro, oído ni
                  voz: es una orden sin LLM.
    6.12.19 02/11  Blindaje de memoria (02/11): borrar memoria o procesar un
                  turno en un Parker parcial ya no peta si faltan `hechos` o
                  `prosodia`; se usa getattr. `test_pipeline` vuelve a verde.
    6.12.18 02/11  Modo local/online de verdad (02/11): «modo local» y «modo
                  online» solo cambiaban el cerebro y la voz seguía en Edge;
                  ahora cambian cerebro, oído y voz. El cambio parcial queda
                  para «cerebro local» / «cambia el cerebro a local».
    6.12.17 02/11  Turnos fantasma (02/11): el VAD abría conversación con
                  ruido de sala (rms 0,0015-0,0026) y Whisper lo convertía en
                  «Gracias.» o «¡Suscríbete al canal!»; el eco del altavoz se
                  colaba como «oído local, oído local». Se sube el mínimo de
                  señal a 0,0035, se descartan los bloques repetidos y el eco
                  reciente en el turno normal, y el monitor de barge-in aplica
                  el mismo filtro. El arranque muestra el mínimo real.
    6.12.16 01/11  Barge-in sin `close()` (01/11): cerrar el generador del
                  cerebro desde el hilo del monitor o del hook de prueba podía
                  bloquearse (o lanzar «generator already executing»). Basta
                  con marcar el evento: el hilo lector abandona la cola y el
                  turno sigue.
    6.12.15 01/11  Reinicio tras barge-in (01/11): si Edge deja una síntesis
                  colgada, el turno ya no espera para siempre. Pasados 2 s se
                  abandonan las colas viejas y se arrancan hilos de voz nuevos;
                  así Parker vuelve a escuchar y el audio viejo se descarta.
    6.12.14 01/11  Prueba de barge-in (01/11): con PARKER_TEST_BARGE=1,
                  `kill -USR1` simula el corte y permite comprobar en la placa
                  que el turno se desbloquea y vuelve a escuchar sin depender
                  del altavoz del PC. El hook se instala en el hilo principal
                  (Parker se construye en otro; allí signal.signal falla).
    6.12.13 01/11  Interjecciones y «oído local» (01/11): un «¡Ah!» suelto de
                  ruido ya no despierta al cerebro, y una transcripción de
                  ruido «oído local» ya no cambia el STT sin «Parker» o un
                  verbo. El modo guardado en la placa se restaura a `auto`.
    6.12.12 01/11  Micro tras el barge-in (01/11): el monitor podía seguir
                  transcribiendo su última ventana y mantener abierto el
                  InputStream; el bucle principal recibía «Device unavailable»
                  al volver a escuchar. Se espera hasta 5 s al monitor y se
                  avisa si sigue ocupado.
    6.12.11 01/11  Filtro de alucinaciones (01/11): Whisper inventaba frases con
                  ruido o la cola del altavoz («Gracias por ver el video»,
                  «¡Suscríbete al canal!», «¡Ah! ¡Ah! ¡Ah!») y Parker les
                  contestaba. Se pide `verbose_json` a la nube para leer
                  no_speech/logprob/compresión, y un filtro conservador tira
                  solo alucinaciones conocidas, repeticiones de golpes y
                  señales fuertes; «sí», «no» y «vale» siguen pasando.
    6.12.10 01/11  Barge-in que desbloquea (01/11): al oír «para» se marca el
                  corte, se para el altavoz Y se abandona el stream del cerebro
                  (hilo lector + cola con espera de 0,2 s). Antes la voz paraba
                  pero el turno seguía esperando un token y Parker no volvía a
                  escuchar. `preparar_turno()` limpia el corte al empezar de
                  nuevo y `sintetizar()` descarta audio de un turno cortado.
    6.12.9  01/11  Barge-in (01/11): mientras Parker habla, un monitor aparte
                  abre el micro y transcribe ventanas cortas. Si oye «Parker,
                  para» / «Parker, cállate» y no es eco de su propia voz, corta
                  la reproducción y descarta la síntesis pendiente. El monitor
                  se compara con las frases que están sonando; si el micro no
                  admite entrada y salida a la vez, se desactiva solo.
    6.12.8  01/11  STT sin prompt (01/11): con audio poco claro la nube
                  devolvía el `initial_prompt` como si fuera el usuario
                  («Parker se escribe Parker.»), y se procesaba como charla.
                  Se quita el prompt del STT; el nombre lo cubre `hotwords` y
                  la fecha ya acepta «dirá». Sin prompt no hay texto que
                  alucinar.
    6.12.7  01/11  Voz que no se descarta (01/11): el prompt del STT incluía
                  preguntas entre «» y Whisper devolvía «¿qué día es hoy?».;
                  el filtro de eco exigía una comilla suelta y tiraba el turno
                  entero, así que Parker parecía sordo. Ahora el prompt solo
                  lleva el nombre, una comilla suelta se limpia y solo se
                  descarta el eco con el par «…». «borra memoria» / «vacía tu
                  memoria» y «reiníciate» se reconocen con más variantes.
    6.12.6  01/11  Memoria y reinicio por voz (01/11): «borra tu memoria»
                  vacía Chroma en dos pasos (la segunda orden, dentro de 60 s,
                  borra de verdad) y limpia también el historial de la sesión;
                  agenda, apuntes y personalidad no se tocan. «Parker,
                  reiníciate» se despide y sale con código 75 para que
                  `arrancar.sh` o systemd lo levanten otra vez sin tocar
                  memoria ni ajustes. `tools/recuerdos.py --borrar` usa el
                  mismo `MemoriaParker.borrar_todos()`.
    6.12.5  01/11  Menos invenciones y router de música (01/11): «¿de qué estás
                  hablando?» ya no se confunde con «¿qué está sonando?»
                  (contestaba «la música está desactivada»). El prompt ya no
                  ofrece música de sintetizador ni el sueño de silbar como
                  tema; todos los modelos volvían siempre a eso. Se prohíben
                  las actividades inventadas («he estado escuchando…») y un
                  filtro determinista descarta esas frases y los recuerdos que
                  no están en Chroma («la receta de pasta que te mencioné»).
                  Cerebro de nube: qwen3.8-27b (0,51 s de mediana, 0/12
                  vacíos en la prueba) en vez de gpt-oss-20b.
    6.12.4  01/11  Cambio de modo fantasma y música fuera (01/11): Whisper
                  devolvió el `initial_prompt` y Parker ejecutó «cambia el
                  cerebro al local» sin que nadie lo dijera. Se quitaron las
                  órdenes del sesgo del STT y cualquier transcripción con
                  comillas de prompt se ignora antes de ejecutar nada. La
                  música queda desactivada (`musica.activo: false`) hasta
                  estabilizar el audio.
    6.12.3  01/11  Órdenes cortas otra vez (01/11): el mínimo de 7 chunks/0,8 s
                  dejaba fuera «Parker, ¿qué hora es?» (1,2 s, 5 chunks). Vuelve
                  a 5/0,6 s; el enfriamiento de 2 s y el mínimo de RMS evitan
                  que la cola del altavoz abra un turno. La etiqueta de versión
                  ya refleja el canal nuevo.
    6.12.2  01/11  Español de España y turnos más cortos (01/11): el 2B local
                  decía «qué onda» aunque el prompt pidiera España; ahora el
                  prompt lo prohíbe y un filtro cambia las palabras
                  inequívocas («qué onda» → «qué tal», «carro» → «coche»).
                  El enfriamiento tras hablar sube a 2 s y se exigen 0,8 s/7
                  chunks de voz: los turnos vacíos del ruido de sala se
                  reducen. El historial baja de 8 a 4 mensajes en local para
                  recortar el prefill de cada turno (la memoria larga sigue en
                  Chroma).
    6.12.1  01/11  Turnos limpios y cerebro local 2B (01/11): tras hablar, el
                  micrófono captaba la reverberación del altavoz y Parker se
                  contestaba a sí mismo (dos respuestas a «son las 6 y 34»).
                  Ahora hay 0,9 s de enfriamiento al terminar cada frase y un
                  mínimo de señal bruta (0,0025) para que el AGC no confunda
                  el ventilador con voz. El cerebro local pasa de
                  `qwen2.5:3b` (turno ~12 s) a `qwen3.5-local:2b` (turno p50
                  5,5 s, 4/4 contextos en el banco de pruebas); el 1,5B era
                  más rápido pero incoherente. Se apaga el precalentado del
                  prefijo en local: tardaba 20 s y competía con el turno.
    6.12.0  01/11  Oído de lejos y CPU liberada (01/11): el VAD por volumen se
                  sustituye por Silero v6 (ya incluido en faster-whisper) con
                  ganancia automática, así una voz lejana entra sin gritar y
                  el ruido de sala no abre el turno. Whisper baja de `small`
                  a `base` y de 8 a 4 hilos: `small` se quedó 45 min
                  transcribiendo con 14 hilos nativos y dejó la placa al 92 %,
                  con la cara congelada y el cerebro local a 4-9 tok/s. Las
                  respuestas locales se cortan a 2 oraciones. El filtro de
                  estado ya no deja pasar «energía…/Pauta de trato…» al TTS.
                  «Cambia el cerebro al local» avisa si la voz sigue en Edge.
    6.11.0  01/11  Modo local completo y oído de lejos (01/11): «modo local
                  completo», «todo local» o «desconecta internet» cambian a la
                  vez cerebro (Ollama), oído (Whisper en la placa) y voz
                  (Piper), y el conjunto se guarda en `parker.modo.json` para
                  sobrevivir a un reinicio. También hay órdenes separadas
                  («cambia la voz al local», «cambia el oído a la nube»). El
                  micrófono USB sube a ganancia máxima al arrancar y el VAD
                  baja de 0,02 a 0,007: antes había que gritar para que
                  Parker oyera a distancia.
    6.10.3  01/11  La cara que se congelaba (31/10): dos Parker podían pelearse
                  por el SPI y el micrófono. Ahora el propio Parker toma un
                  candado en `~/.parker.runtime.lock` y una segunda instancia
                  sale con un aviso claro. Además, en la placa (offscreen) la
                  `QGraphicsView` ya no repinta un lienzo que nadie ve (en el PC
                  de desarrollo bajó del 16,7 % al 0,6 % de un núcleo; en la
                  placa el ahorro es pequeño porque esa vista ya no se pintaba).
                  Si el panel deja
                  de recibir fotogramas, un vigilante reinicia el GC9A01 sin
                  reiniciar a Parker, y un latido anota en el log cualquier
                  bloqueo del hilo gráfico. La orden «cambio el cerebro en
                  local» (oída el 31/10) ya se reconoce: antes no cambiaba nada
                  y el modelo se inventaba que sí.
    6.10.2  30/10  Frases automáticas con sentido (30/10): las manías ya no se
                  cuentan como creencias («Creo que ordeno las palabras antes
                  de decirlas» no significaba nada), los gustos se recortan
                  antes del «:» para no sonar a frase rota, el «eco» no repite
                  una transcripción mala (solo confidencias con marca personal)
                  y no repite la misma frase dos veces seguidas. La última
                  frase espontánea se guarda en la ficha: tras un reinicio
                  Parker sigue sabiendo qué dijo y por qué (antes, al no
                  tenerla, el modelo se inventaba el motivo). «¿Qué has
                  dicho?» y «¿a qué viene eso?» se contestan sin LLM.
    6.10.1  30/10  Iniciativa sin frases inventadas: las automáticas ya no
                  nacen de una instrucción abierta (que llenaba el 3B de
                  «zumbidos», «lluvia» y metáforas). Salen de una semilla
                  concreta: la ficha, la hora, una propuesta o lo último que
                  dijo la persona. Si preguntan por la frase, el modelo recibe
                  el motivo real y no lo improvisa. La ficha también se limpió
                  de gustos abstractos que alimentaban esas espirales.
    6.10.0 30/10  Voz de Edge TTS (30/10): `es-ES-XimenaNeural` de Microsoft
                  como motor principal (más natural que Piper) y Piper local
                  cargado SIEMPRE como respaldo. Si Edge no contesta en 8 s,
                  falla o no hay red, la frase sale por Piper y se reintenta
                  Edge al cabo de un minuto; el volumen y el look-ahead no
                  cambian. Para volver a 100 % local: `voz.motor: piper`.
    6.9.1  30/10  «231 charlas» y agenda a prueba de golpes (30/10): el estado
                  guardaba 232 charlas porque el contador subía por turno; al
                  cargar se corrige con un techo honesto (2/día desde el
                  primer contacto) y la ficha del prompt ya no lleva ni
                  porcentaje, ni días, ni contador que el modelo pueda copiar.
                  La agenda limpia «Parker pone una alarma» (antes guardaba
                  «pone una» como materia), pide cuál cambiar/borrar si hay
                  varias y no elige una al azar, y sobrevive a JSON truncado,
                  listas, NaN e infinitos. El ánimo se guarda de forma atómica.
    6.9.0  30/10  Agenda que entiende cambios (30/10): «cambia la hora del
                  dentista de mañana a las 6» reprograma la cita existente en
                  vez de crear otra o contestar con el bloque de vínculo.
                  Además: «charlas» cuenta conversaciones (hueco de 45 min), no
                  turnos; el número ya no va en el prompt (el modelo lo copiaba
                  literal: «231 charlas») y se filtran esas fugas del habla; si
                  pregunta, contesta con los días reales. Agenda con guardado
                  atómico y tolerancia a entradas corruptas.
    6.8.1  30/10  El oído llega tarde (30/10): al encender la placa, el micro
                  USB aparecía ~29 s después de que Parker abriera el audio,
                  así que se quedaba con el códec interno en silencio absoluto
                  («le hablo y no reacciona»). Ahora, en el primer intento,
                  espera hasta 25 s y refresca la lista de PortAudio (que la
                  cachea al importar); al quedar listo suena un chime corto de
                  dos notas, porque la cara aparece antes que el oído.
    6.8.0  27/10  La cara con vida propia (27/10, «que tenga más dinamismo y que
                  diga algo por su cuenta»): el reposo deja de ser flotar +
                  parpadear. Un DIRECTOR DE GESTOS elige uno cada pocos
                  segundos (micro-ceja, curiosear, mirar arriba, cabezada,
                  suspiro, estirón, bostezo, doble toma, guiño) y la familia
                  de gestos cambia con el silencio: despierto → solo (1,5 min)
                  → aburrido (8 min), con parpadeos más espaciados y lentos
                  según el rato. La cara se pone a «pensar» antes de tomar la
                  iniciativa, y esta llega a los 15 min de silencio (antes 45).
    6.7.0  27/10  Cerebro por voz: «ponte en local», «vuelve a la nube»,
                  «modo automático» y «¿qué cerebro usas?» se resuelven sin LLM
                  (0 ms) y el modo se guarda en `parker.cerebro.json`, así que
                  un reinicio mantiene lo pedido. Además, avisos hablados: dice
                  cuando se queda sin internet, cuando el proveedor le frena
                  (429) y cuando vuelve — una sola vez por caída, y sin pisar
                  una respuesta. `online.avisar_por_voz: false` los silencia.
    6.6.0  27/10  Ficha que rota: sus gustos y sueños ya NO son siempre los
                  mismos. El prompt enseñaba la primera entrada de `le_gusta` y
                  de `suenos` en todos los turnos (por eso «le gusta la lluvia»
                  y «sueña con silbar» salían una y otra vez: era lo único que
                  veía de sí mismo). Ahora rota una entrada por conversación
                  (al empezar, o tras 45 min de silencio) y dentro de una charla
                  el bloque de identidad sigue idéntico — es el prefijo que
                  cachea Ollama, cambiarlo cada turno costaba 33-40 s.
                  La línea que nombraba «lluvia» y «zumbido» para prohibirlos se
                  queda genérica: nombrarlos los traía de vuelta.
    6.5.0  27/10  Música con orejas (27/10): mientras suena la canción, el
                  micrófono oye el altavoz, así que Parker baja la música un
                  momento («duck») y mira si el nivel cae con ella (era la
                  canción, no se abre turno) o sigue alto (eres tú: abre turno
                  y te atiende). «Baja el volumen» con música sonando es la
                  música (independiente del de la voz) y se puede charlar con
                  la canción puesta. ARREGLO gordo: un turno ya no puede dejar
                  a Parker sordo — se suelta SIEMPRE (antes, un turno nacido de
                  la propia canción se ignoraba sin hablar y sin soltar
                  `ocupado`: ni escuchaba durante la música ni después).
    6.4.0  26/10  El día entero y lo que se aprende:
                  - Rutinas: «buenas noches», «buenos días» con parte del día,
                    «cállate 10 minutos» y «apágate» (despedida en la cara,
                    guardado y apagado de la placa; solo queda desenchufar).
                  - Apuntes: notas, listas y contadores («litros de agua») que
                    Parker crea y borra por voz, sin tocar código.
                  - Tiempo: Open-Meteo sin clave, con la ciudad como variable
                    («estamos en Madrid» la cambia y lo confirma con la zona).
                  - Música por API (Deezer, sin clave): adelantos de 30 s
                    decodificados con ffmpeg, con «para la música» y volumen.
                  - Citas con TITULAR corto («cita dentista», no la frase entera).
                  - Si el proveedor retira el modelo de la nube, Parker elige
                    otro solo (/models + lista de alternativos de config.yaml).
                  - Vigilante del micrófono: si la entrada se queda en silencio
                    absoluto, rearma el flujo y vuelve a buscar el micro.
                  - Bandit de iniciativa (docs/evolucion.md §6): aprende cuándo
                    y de qué hablar según si se le contesta o se le ignora.
    6.3.0  26/10  Agenda local: alarmas («a las 7:30»), temporizadores («en 10
                  minutos») y citas («apunta que el viernes a las 5 tengo al
                  dentista»), con consulta («¿qué tengo mañana?»), borrado y
                  aviso de verdad: campana por el altavoz + frase, desde un hilo
                  propio. Se guarda en `parker.agenda.json` (solo en la placa).
    6.2.1  25/10  Volumen exacto: «bájalo al 33 %» fija 33 (el `\b` final lo
                  mandaba al LLM), «al cien por cien» = 100 %, rango 1-100 %
                  y las preguntas de nivel se contestan con el valor real.
                  Medido: pico de voz 0,80/0,50/0,20/0,01.
    6.2.0  25/10  Órdenes directas sin LLM: «baja el volumen» cambia la voz,
                  «silencia» la apaga y «silba» hace sonar un silbido real.
                  Fechas relativas («mañana», «en 7 días») y la hora ya no
                  contestan siempre la fecha de hoy; Parker sabe que no tiene
                  cuerpo y no promete acciones físicas.
    6.1.0  25/10  STT en la nube (whisper-large-v3-turbo) con el local de
                  respaldo: 4,31 s -> 0,68 s y texto exacto. Reparación
                  conversacional («no te entiendo») y reglas contra el
                  enganche a su propio tema.
    6.0.1  25/10  el SSE se lee en UTF-8 (antes, ISO-8859-1: «¿Qué» llegaba a
                  Piper como «Â¿QuÃ©») y el marcado (tokens <|channel|>,
                  entidades HTML, vallas de código, JSON) no se pronuncia.
    6.0.0  25/10  cerebro doble: nube primaria + local de respaldo.
"""

import hashlib
from pathlib import Path

VERSION = "6.13.0"
CANAL = "demo-cara"
COMPILADO = "2026-11-02 21:30"

BASE = Path(__file__).resolve().parents[1]
# Ficheros que definen el comportamiento: si la huella del PC y la de la placa
# coinciden, es EXACTAMENTE el mismo código (no hace falta comparar fechas).
_FIRMAS = ("parker.py", "config.yaml", "modulos/cerebro.py",
           "modulos/personalidad.py", "modulos/acciones.py",
           "modulos/agenda.py", "modulos/sonidos.py",
           "modulos/rutinas.py", "modulos/apuntes.py", "modulos/tiempo.py",
           "modulos/musica.py", "modulos/voz.py",
           "modulos/cara_parker.py", "modulos/display_spidev.py")


def etiqueta(corto: bool = False) -> str:
    """`v6.0.0-doble-cerebro` (o `v6.0.0` si `corto=True`)."""
    return f"v{VERSION}" if corto else f"v{VERSION}-{CANAL}"


def huella() -> str:
    """Huella corta del código que se está ejecutando (8 hex).

    `sha256` de parker.py + config.yaml + los módulos que cambian el
    comportamiento. Dos copias con la misma huella son el mismo programa.
    """
    h = hashlib.sha256()
    for nombre in _FIRMAS:
        ruta = BASE / nombre
        try:
            h.update(ruta.read_bytes())
        except OSError:
            h.update(f"(falta {nombre})".encode())
    return h.hexdigest()[:8]


def linea_arranque() -> str:
    """Línea que se imprime al arrancar: versión, compilación, huella y ruta."""
    return (f"[Parker] {etiqueta()} · compilado {COMPILADO} · "
            f"código {huella()} · {BASE}")
