# Parker 🤖

Parker es un acompañante digital autónomo y empático, con forma de personaje
robotico: no es una terminal de comandos ni un altavoz inteligente clásico.
Está pensado para **estar ahí para ti sin que tengas que estar pendiente de él**:
mantiene su propia vida (parpadea, mira alrededor, bosteza), te habla por su
cuenta si llevas mucho rato sin decir nada, y recuerda quién eres a través del
tiempo. También puede mostrar todo su repertorio con «Parker, modo demo»: la
intro, las 8 expresiones y los 11 gestos del catálogo, una vez, y vuelve solo
a su cara normal («para la demo» lo corta).

Corre en una **Orange Pi 5 Pro (8 GB RAM)** con una pantalla circular de
240×240, altavoz, micrófono y carcasa metálica de refrigeración.

Desde la **v6** el cerebro es doble: **oye, transcribe, habla, recuerda y pone
la cara en local**, y solo la redacción de la frase viaja a una API compatible
con OpenAI (por defecto Groq) para que conteste en ~1 s en vez de 9. Si no hay
internet, o si se pone `online.activo: false` en `config.yaml`, todo vuelve a
ser 100 % local sin cambiar nada más. Ver
[docs/cerebro_doble.md](docs/cerebro_doble.md).

---

## Empezar aquí

| Quiero… | Documento |
|---|---|
| **Encender la placa y que Parker arranque solo** | [docs/inicio.md](docs/inicio.md) |
| Entender las siglas (STT, TTFB, NPU, tokens…) | [docs/conceptos.md](docs/conceptos.md) |
| Ver por qué responde en ~4 s y cómo se mide | [docs/rendimiento.md](docs/rendimiento.md) |
| Cablear la pantalla, SPI/GPIO y diagnóstico de hardware | [docs/placa.md](docs/placa.md) |
| Cómo está montado por dentro | [docs/arquitectura.md](docs/arquitectura.md) |
| **Ver la historia completa: del planteamiento en papel a hoy** | [docs/historia.md](docs/historia.md) |
| Cómo puede evolucionar su carácter con el tiempo (diseño) | [docs/evolucion.md](docs/evolucion.md) |
| Qué medir y cambiar cuando haya placa (STT, cerebro, evolución) | [docs/plan_mejoras.md](docs/plan_mejoras.md) |
| Entender el cerebro doble (nube + local) y volver a 100 % local | [docs/cerebro_doble.md](docs/cerebro_doble.md) |
| Ponerle alarmas, temporizadores y citas | [docs/agenda.md](docs/agenda.md) |
| Qué modelos, memorias y funciones se investigaron (octubre 2026) | [docs/investigacion_oct2026.md](docs/investigacion_oct2026.md) |
| Darle rutinas, apuntes, el tiempo, música y apagarlo con la voz | [docs/dia.md](docs/dia.md) |
| Ver qué hay en cada copia de seguridad y qué cambió | [docs/respaldos.md](docs/respaldos.md) |

**Arranque rápido en la placa** (ya está instalada allí):

```bash
ssh orangepi@192.168.1.130
tail -f ~/parker.log        # ver qué hace
~/parker/tools/arrancar.sh  # arrancar a mano si hace falta
```

Al enchufar la placa, cron ejecuta `tools/arrancar.sh`: espera a Ollama, lanza
Parker en modo `offscreen` y se pone a escuchar. Detalles y reinstalación del
autostart en [docs/inicio.md](docs/inicio.md) §5.

---

## Stack

| Capa | Tecnología |
|---|---|
| Cara / interfaz | PySide6 (QGraphicsScene vectorial 400×400, ventana frameless) |
| Pantalla física | GC9A01 240×240 por SPI (`modulos/display_spidev.py`) |
| Escucha (STT) | Whisper — `faster-whisper` `base` int8 + VAD (≈1,7 s), o `openai-whisper` |
| Cerebro (LLM) | Doble: nube primaria (`openai/gpt-oss-20b` en Groq) + Ollama local de respaldo (`qwen2.5:3b`), con streaming |
| Memoria | ChromaDB + `paraphrase-multilingual-MiniLM-L12-v2` |
| Voz (TTS) | Edge TTS `es-ES-XimenaNeural` (Microsoft, natural) con Piper (`es_ES-davefx-medium`) cargado como respaldo local |
| Autonomía | Hilos propios: escucha continua (VAD por volumen) + agenda (alarmas/temporizadores/citas) + día (dormir, parte, apagado) + **bandit** de iniciativa que aprende cuándo y de qué hablar |
| Relación | Vínculo 0-100 % que crece con los días y las charlas: no finge conocerte el primer día |

## Estructura del repositorio

```
parker.py              Bucle principal: ventana, hilos, cola de voz, VAD
config.yaml            Configuración global (cerebro, escucha, voz, memoria, autonomía)
modulos/
  personalidad.py      Quién es Parker: gustos, sueños, manías, miedos y ánimo
  cara_parker.py       Cara vectorial + los 12 principios de animación + lip-sync
  cerebro.py           LLM por Ollama con streaming y etiquetas [CARA:...]
  escucha.py           STT con dos backends (faster-whisper / openai-whisper)
  memoria.py           Memoria vectorial (ChromaDB + embeddings multilingües)
  voz.py               TTS: Edge TTS (nube) o Piper local (respaldo)
  acciones.py          Órdenes sin LLM: volumen, silencio y silbido
  agenda.py            Alarmas, temporizadores y calendario local (sin LLM)
  rutinas.py           El día: dormir, despertar, parte del día y apagado ordenado
  apuntes.py           Notas, listas y contadores («litros de agua») por voz
  tiempo.py            El tiempo (Open-Meteo, sin clave) y la ciudad como variable
  musica.py            Música por API (Deezer, sin clave) con ffmpeg en memoria;
                       y distingue tu voz de la canción («OyenteMusica»/duck)
  sonidos.py           Silbido y campana del aviso, generados para el altavoz
  display_spidev.py    Driver SPI/GPIO de la pantalla circular GC9A01 (solo Linux/SBC)
tests/
  test_pipeline.py     Tests offline del pipeline de respuesta (sin Ollama/audio)
  test_personalidad.py Ficha del personaje, ánimo, persistencia e iniciativa
  test_rendimiento.py  Presupuesto de latencia: prompt, recuerdos y configuración
  test_acciones.py     Volumen, silencio y silbido (órdenes sin LLM)
  test_agenda.py       Alarmas, temporizadores y citas con hora fija
  test_dia.py          Rutinas, apuntes, tiempo y música resueltos sin LLM
  test_rutinas.py      El día: dormir/despertar, silencio temporal y parte
  test_apuntes.py      Notas, listas y contadores de la persona
  test_tiempo.py       El tiempo y el cambio de ciudad por voz
  test_musica.py       Búsqueda, decodificación, volumen, duck y voz sobre la música
  test_bandit.py       Iniciativa con aprendizaje (brazos, premios y persistencia)
  test_modelos_nube.py Si el proveedor retira el modelo, elige otro solo
  test_sonidos.py      Silbido, campana y chime de «micro listo»: banda y pico
  test_microfono.py    El micro USB que aparece después del arranque (PortAudio)
  test_animacion.py    Los 12 principios de animación, gestos y cierre limpio
  test_cara.py         Tests de la animación (estagger, expresiones, parpadeo)
  test_render.py       Smoke test offscreen del render de la cara
tools/
  respaldo.py          Copia completa del proyecto en backups/<fecha>/
  arrancar.sh          Arranque autónomo (cron/systemd), sin sudo
  parker.service       Unidad systemd alternativa a cron
  medir_latencia.py    Latencia de 5 turnos con los módulos reales (sin micrófono)
  recuerdos.py         Ver y borrar los recuerdos guardados
  probar_agenda.py     Prueba real del aviso: mide con el micro que la campana suena
  probar_dia.py        Prueba real en la placa: tiempo, música, apuntes y apagado
  probar_musica_escucha.py  Prueba real en la placa: te oye por encima de la música
  probar_memorias.py   Prueba real de la memoria: escala, umbral y fidelidad
docs/
  inicio.md            Encender, arrancar, comprobar y arreglar
  conceptos.md         Glosario: STT, TTFB, NPU, tokens, NPU/RKNN…
  arquitectura.md      Módulos, hilos, señales y flujo de datos
  rendimiento.md       Latencia, optimizaciones aplicadas y alternativas estudiadas
  agenda.md            Alarmas, temporizadores y citas: frases y reglas
  dia.md               Rutinas, apuntes, tiempo, música, apagado y aprendizaje
  historia.md          La historia completa: papel, prototipo y placa
  historia_original.md Texto original del autor (catalán, sin retocar)
```

## Instalación

> En el PC de desarrollo sigue los pasos de abajo. **Para montarlo en la
> Orange Pi 5 Pro, usa [docs/placa.md](docs/placa.md)** (incluye paquetes del
> sistema, SPI/GPIO y el paso de archivos).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Modelos (una sola vez):

```bash
# Voz (Piper)
#   assets/voz/es_ES-davefx-medium.onnx  (+ .onnx.json)
# Embeddings (se descargan solos la primera vez)
#   paraphrase-multilingual-MiniLM-L12-v2
# STT
pip install faster-whisper        # recomendado; la primera vez baja el modelo
```

Cerebro local:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b       # cerebro actual (listo); qwen2.5:1.5b = alternativa rápida
```

## Arranque

```bash
python parker.py
```

- **ESC** sale del programa.
- En la SBC, la ventana es *fullscreen frameless* y se centra la escena de
  400×400; si la pantalla SPI GC9A01 está disponible se vincula automáticamente.
- Sin hardware SPI (por ejemplo en un PC de desarrollo) el programa arranca
  igual: simplemente avisa `[Display] Módulo SPI no disponible`.

## Configuración rápida (`config.yaml`)

```yaml
llama:
  modelo: "qwen2.5:3b"    # cerebro actual; 1.5b si algún día urge velocidad
  max_tokens: 90         # respuestas cortas = menos espera
  num_ctx: 1024
  historial_mensajes: 2  # solo el último intercambio (se reprocesa cada turno)
  keep_alive: "24h"      # evita que Ollama descargue el modelo a los 5 min
escucha:
  backend: "auto"        # faster-whisper si está instalado
  modelo_faster: "base"  # small: +3 s; tiny: ilegible
  silencio_corte_seg: 0.6
voz:
  motor: "edge"                 # edge (Microsoft) | piper (100 % local)
  edge_voz: "es-ES-XimenaNeural"
  velocidad: 0.9
  volumen: 0.9                  # en la placa, 0.55
```

## Tests

```bash
python tests/test_pipeline.py    # pipeline de respuesta, sin Ollama ni audio
python tests/test_microfono.py   # el micro USB que aparece tarde (PortAudio)
python tests/test_sonidos.py     # silbido, campana y chime de «micro listo»
python tests/test_dia.py         # rutinas, apuntes, tiempo y música (sin LLM)
python tests/test_musica.py      # búsqueda, decodificación y volumen de la música
python tests/test_bandit.py      # lo que aprende al tomar la iniciativa
python tests/test_personalidad.py # ficha, ánimo, persistencia e iniciativa
python tests/test_rendimiento.py  # presupuesto de latencia y configuración rápida
python tests/test_animacion.py   # los 12 principios y los gestos
python tests/test_cara.py        # animaciones: estagger, expresiones, parpadeo
python tests/test_render.py      # render offscreen de la cara (requiere Qt)
python tests/test_voz_edge.py    # Edge/Piper: selección, respaldo y enfriamiento
# en un servidor sin pantalla: añade QT_QPA_PLATFORM=offscreen
```

## Documentación

- [docs/00 Inici TREC Parker.md](docs/00%20Inici%20TREC%20Parker.md) — **bóveda Obsidian del TREC**: mapa de nodos, plan de investigación, marco teórico/práctico, bitácora de errores y guía de redacción.
- [docs/TREC/03 Marc practic.md](docs/TREC/03%20Marc%20practic.md) — capítulo práctico: diseño, hardware, iteraciones, resultados y límites.
- [docs/TREC/14 Annex. Muntatge i esquemes electrònics.md](docs/TREC/14%20Annex.%20Muntatge%20i%20esquemes%20electr%C3%B2nics.md) — guía de montaje, despiece, cableado SPI/GPIO y esquema eléctrico.
- [docs/TREC/15 Annex. Codi font complet.md](docs/TREC/15%20Annex.%20Codi%20font%20complet.md) — mapa del código y enlace al repositorio completo.
- [docs/TREC/Mapa de Parker.canvas](docs/TREC/Mapa%20de%20Parker.canvas) — mapa visual del proyecto (abrir con Obsidian).
- [docs/TREC/parts/00 Index de les parts.md](docs/TREC/parts/00%20Index%20de%20les%20parts.md) — una nota por pieza (cerebro, oído, voz, memoria, cara, personalidad, agenda, hardware, documento original).
- [docs/TREC/Evolucio de les parts.canvas](docs/TREC/Evolucio%20de%20les%20parts.canvas) — matriz de evolución: cada fila una pieza, cada columna una etapa.
- [docs/arquitectura.md](docs/arquitectura.md) — cómo encajan los módulos, hilos y señales.
- [docs/investigacion_oct2026.md](docs/investigacion_oct2026.md) — qué se encontró en
  Hugging Face/GitHub sobre modelos, memoria, latencia y funciones, con fuentes.
- [docs/rendimiento.md](docs/rendimiento.md) — presupuesto de latencia, mejoras aplicadas
  y alternativas evaluadas para cerebro (NPU RK3588), transcripción y cara.
- [docs/placa.md](docs/placa.md) — instalación completa en la Orange Pi 5 Pro:
  dependencias, modelos, paso de archivos y checklist de validación.
- [training/README.md](training/README.md) — tubería del LoRA de personalidad:
  dataset, QLoRA, exportación a Ollama y evaluación base vs LoRA.
- [training/recursos_externos.md](training/recursos_externos.md) — qué modelos y
  corpus de BMO/Baymax existen de verdad, qué adaptadores están vacíos y dónde
  entrenar (Colab, Kaggle, RunPod), con fuentes.

## Estado

Sistema funcional en desarrollo activo.

- ✅ **Pantalla circular GC9A01 operativa** en la Orange Pi 5 Pro: muestra la cara
  de Parker a ~16 fps reales por SPI. La causa de la pantalla "en blanco" era una
  **secuencia de init incompleta** (faltaban las tablas de gamma y la inversión
  `0x21`); el detalle y el diagnóstico están en
  [docs/placa.md](docs/placa.md) §7 y §9.
- ✅ Diálogo completo por voz (STT → cerebro → TTS) validado en la placa.
- ✅ **v6.10.2**: las frases automáticas salen de una semilla concreta (ficha,
  hora, propuesta o último mensaje), sin manías contadas como creencias ni
  ecos de transcripciones malas; no repiten la misma frase dos veces seguidas.
  La última frase espontánea se guarda en la ficha y, si preguntas por ella
  («¿qué has dicho?»), Parker contesta sin LLM con la frase y el motivo real,
  también después de un reinicio. Detalle:
  [docs/plan_mejoras.md](docs/plan_mejoras.md).
- ✅ **v6.10.0**: voz `es-ES-XimenaNeural` de Edge TTS con Piper de respaldo
  automático; si Microsoft falla o no hay red, Parker sigue hablando. Detalle:
  [docs/plan_mejoras.md](docs/plan_mejoras.md) y [docs/lora_voz.md](docs/lora_voz.md).
- ✅ **v6.8.1**: el micro USB aparece ~29 s después de encender la placa y
  PortAudio no lo veía; Parker se quedaba sordo con el códec interno. Ahora
  espera y refresca la lista al arrancar, y un chime avisa de que ya escucha.
  Detalle: [docs/placa.md](docs/placa.md) (tabla de lecciones, 30/10).
- ✅ **v6.8.0**: la cara con vida propia — un director de gestos en reposo (cinco
  gestos nuevos y tres familias que cambian con el silencio) y charla por su
  cuenta a los 15 min. Detalle: [docs/arquitectura.md](docs/arquitectura.md) §5.
- ✅ **v6.7.0**: cerebro por voz («ponte en local», «vuelve a la nube», «ponte
  en automático», «¿qué cerebro usas?») con avisos hablados si falla internet.
- ✅ **v6.4.0**: agenda, día (dormir/parte/apagado), apuntes, tiempo, música por
  API, vigilante del micrófono y bandit de iniciativa. Guía: [docs/dia.md](docs/dia.md).
- Pendiente: cierre limpio con ESC en el montaje final y la segunda memoria de
  conocimientos (diseño medido en [docs/plan_mejoras.md](docs/plan_mejoras.md)).

Diagnóstico de la pantalla sin arrancar Parker:

```bash
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py            # chips, spidev, pines + rojo/verde
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --parpadeo # ¿píxeles bajo control del software?
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --colores  # ¿distingue colores o solo brillo?
```
