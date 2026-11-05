# Proyectos abiertos tipo Jarvis — revisión del 01/11/2026

> **Para qué es esto.** El dueño pidió buscar proyectos de otras personas que
> hayan hecho un asistente tipo Jarvis que funcione de verdad, mirar si el
> código es libre y decidir qué se puede aprovechar en Parker. La conclusión
> corta: **no hay un Jarvis completo que se pueda instalar y usar tal cual**,
> pero sí hay cinco piezas muy concretas que resuelven justo lo que a Parker le
> falta (interrumpir, cerrar el turno, despertar, memoria y persona). No se ha
> instalado nada de esto en la placa en esta sesión; es una lista de decisiones
> para las siguientes.

Parker ya tiene lo difícil: STT en la nube con respaldo local, VAD Silero,
streaming de frases, Edge TTS con Piper de respaldo, Chroma y una cara propia.
Lo que falta no es «otro cerebro», sino **cómo se cede el turno** y **cómo se
interrumpe**.

## 1. Lo que sí merece la pena copiar

| Proyecto | Licencia | Qué copiar exactamente | Qué NO copiar |
|---|---|---|---|
| [Pipecat](https://github.com/pipecat-ai/pipecat) | BSD-2-Clause (confirmar el `LICENSE`) | La semántica de *barge-in*: cuando el usuario empieza a hablar se cancelan **las tres cosas** —el stream del LLM, la síntesis de la frase y la cola de audio—, no solo se baja el volumen. También la separación `UserStartedSpeaking` / `UserStoppedSpeaking` del resto del pipeline. | El transporte WebRTC/Daily: para un micro y un altavoz locales añade una vuelta de red y un stack que la placa no necesita. |
| [Smart Turn v3.2](https://github.com/pipecat-ai/smart-turn) · [pesos](https://huggingface.co/pipecat-ai/smart-turn-v3) | BSD-2-Clause | El modelo de *endpointing*: 8 MB en int8, ~8 M de parámetros, entrenado para decidir si el turno ha terminado de verdad. Declara español entre sus 23 idiomas. Se puede llamar desde Python sin Pipecat (`model.py` + `inference.py`). | Usarlo como única señal: se combina con Silero VAD, no lo sustituye. |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 (confirmar el `LICENSE`) | Palabra de activación local: `Model(...)` + `predict(frame)`, ~10 líneas, PCM 16 kHz. Tiene pipeline para entrenar una palabra propia en español («oye Parker») y *gating* con Silero VAD. | Los modelos preentrenados son en inglés; para español hay que entrenar uno. La supresión de ruido Speex solo trae rueda x86; en ARM64 hay que compilarla o usar WebRTC NS. |
| [OHF linux-voice-assistant](https://github.com/OHF-Voice/linux-voice-assistant) | Apache-2.0 (confirmar el `LICENSE`) | El conjunto de parámetros de un satélite real: `--refractory-seconds`, `--continue-conversation-delay 0.5`, `--listen-during-wake-sound`, `--stop-model`, `--mic-auto-gain`, `--mic-noise-suppression`. Es la referencia práctica para un micro USB normal. | Su «cerebro»: es un satélite de Home Assistant, no un asistente con LLM propio. |
| [OpenVoiceOS / ovos-persona](https://github.com/OpenVoiceOS/ovos-core) | Apache-2.0 (confirmar el `LICENSE`) | La idea de una **persona JSON** con un endpoint compatible con OpenAI (Ollama también) como **fallback** después de las órdenes locales. Es el orden que Parker ya hace a mano (`_responder_sin_llm` antes del LLM), pero expresado como configuración. | El framework entero: arrastra dependencias de la época de Mycroft y extras GPL; la imagen de OpenVoiceOS está descontinuada. |
| [mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | Las ideas: escribir recuerdos **después** de responder (no en mitad del turno), separar extracción de recuperación y no meter cada conversación entera en el vector. Su extracción requiere un LLM, así que en Parker sería una llamada extra. | La dependencia completa y OpenMemory (sunset en abril de 2026). Chroma ya cubre lo que Parker necesita. |

## 2. Lo que NO se debe adoptar entero

| Proyecto | Motivo |
|---|---|
| [Willow](https://github.com/HeyWillow/willow) | Es firmware ESP32-S3; no hay lógica Python reutilizable para la Orange Pi. |
| [Rhasspy `wyoming-satellite`](https://github.com/rhasspy/wyoming-satellite) | Archivado por el autor el 27/01/2026; el reemplazo es `OHF-Voice/linux-voice-assistant`. La idea del protocolo Wyoming sigue siendo útil, el toolkit no. |
| [Letta](https://github.com/letta-ai/letta) | El servidor Python está en una rama `archive` retirada; la versión actual es TypeScript. En una placa de 8 GB sería otro servicio Node para algo que se resuelve con dos tablas y un prompt. |
| Piper antiguo (`rhasspy/piper`) | El proyecto se movió a [`OHF-Voice/piper1-gpl`](https://github.com/OHF-Voice/piper1-gpl), **GPL-3.0**. Parker ya tiene el modelo local; si algún día se distribuye el dispositivo hay que decidir conscientemente si se acepta GPL-3.0. |
| [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) y [RealtimeVoiceChat](https://github.com/KoljaB/RealtimeVoiceChat) | MIT y muy interesantes, pero Parker ya tiene faster-whisper + Silero VAD + un bucle propio. Se puede copiar su idea de `feed_audio()` y los callbacks, no sustituir el motor entero. |

## 3. Qué haría con Parker, por orden

1. **Barge-in de verdad (prioridad alta).** Hoy, si Parker está hablando, el
   micrófono no debe abrir un turno nuevo sin más: hay que cortar la síntesis y
   vaciar la cola de audio, y luego escuchar. Es lo que más se nota en una
   conversación y no requiere cambiar de modelo.
2. **Smart Turn v3.2 int8 (prioridad media).** Permitiría bajar el corte de
   0,6 s a 0,3-0,4 s sin cortar al usuario a media frase. Cuesta 8 MB y una
   prueba A/B con el micro real; no se instala sin medir antes el p50/p95.
3. **Palabra de activación (prioridad media-baja).** openWakeWord con un modelo
   entrenado en español evitaría que cualquier ruido de la habitación abra un
   turno. Hoy Parker escucha siempre; la activación es una decisión de uso, no
   solo técnica.
4. **mem0/ovos-persona solo como ideas (prioridad baja).** No añadir otra capa
   de memoria ni otro servidor. Chroma + el enrutado actual ya son suficientes;
   lo que falta es escribir menos y con más intención.

## 4. Qué se ha verificado y qué no

- **Verificado leyendo el README del repositorio:** Pipecat documenta que la
  interrupción cancela el trabajo en curso; Smart Turn publica pesos, script de
  entrenamiento y licencia BSD-2; `openWakeWord` documenta el entrenamiento de
  palabras propias; `linux-voice-assistant` publica los parámetros y la
  compatibilidad aarch64; `ovos-persona` documenta el endpoint compatible con
  OpenAI y el orden de pipeline; mem0 explica su extracción con LLM.
- **No verificado en la Orange Pi:** latencia real de Smart Turn en RK3588S,
  calidad de los motores streaming de RealtimeSTT en aarch64 y cobertura actual
  del español en los plugins de OVOS. No se ha instalado nada.
- **Licencias:** las de la tabla son las que declara el README o el metadato del
  repositorio. Antes de distribuir el dispositivo hay que abrir el fichero
  `LICENSE` de cada proyecto y confirmar la versión exacta; en particular
  Pipecat, openWakeWord, linux-voice-assistant y Letta no se leyeron en el
  fichero, solo en la documentación.

## 5. Fuentes consultadas

- <https://github.com/pipecat-ai/pipecat>
- <https://docs.pipecat.ai/pipecat/learn/speech-input>
- <https://github.com/pipecat-ai/smart-turn>
- <https://huggingface.co/pipecat-ai/smart-turn-v3>
- <https://github.com/KoljaB/RealtimeSTT>
- <https://github.com/dscripka/openWakeWord>
- <https://github.com/OHF-Voice/linux-voice-assistant>
- <https://github.com/OpenVoiceOS/ovos-core>
- <https://github.com/mem0ai/mem0>
- <https://github.com/letta-ai/letta>
- <https://github.com/OHF-Voice/piper1-gpl>
