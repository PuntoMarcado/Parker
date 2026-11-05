# Cerebro doble (v6): nube para pensar, local para todo lo demás

## 1. Por qué

El cerebro local (`qwen2.5:3b` en la RK3588) entiende el contexto y los
recuerdos, pero en la placa tarda **8,75 s de mediana** en decir la primera
palabra (mín. 3,99 / máx. 12,40; turno completo p50 13,45 s) y genera a 9,3
tok/s. Una conversación así no se siente como hablar con alguien.

Medido en el PC el 25/10 con el **prompt real de Parker** (3 turnos, mismo
código de limpieza):

| Motor | Modelo | Primer token | Generación |
|---|---|---|---|
| Nube (Groq) | `openai/gpt-oss-20b` | **0,56 s** | 742 tok/s |
| Nube (Groq) | `openai/gpt-oss-120b` | 0,58 s | 415 tok/s |
| Nube (Groq) | `qwen/qwen3.8-27b` | 0,71 s | 240 tok/s (un turno en blanco) |
| Local (placa) | `qwen2.5:3b` | 8,75 s | 9,3 tok/s |

Y medido en la placa con la ruta completa (`tools/eval_cerebro.py`, ver §6):
el primer token baja a ~1 s, que es el límite que impone el resto de la cadena
(Whisper 1,6-2,0 s + arranque de Piper), no la generación.

## 2. Qué hace cada cerebro

```
micrófono ──► VAD local ──► Whisper local ──► ¿dato seguro? (fecha, nombre)
                                                     │ sí ──► respuesta directa (0 ms)
                                                     │ no
                                                     ▼
                                        ┌──────────────────────────┐
                                        │ CEREBRO · ¿hay red?      │
                                        └──────────┬───────────────┘
                                     sí            │            no / falla
                          ┌──────────────────┐     │     ┌────────────────────┐
                          │ NUBE (Groq)      │     │     │ LOCAL (Ollama)      │
                          │ gpt-oss-20b      │     │     │ qwen2.5:3b          │
                          └────────┬─────────┘     │     └─────────┬──────────┘
                                   └───────────────┴───────────────┘
                                                   ▼
                            limpieza de etiquetas/frases (local) ──► Piper ──► altavoz
```

Sigue siendo local **todo lo que no debe salir de casa**: micrófono, VAD,
transcripción, voz, cara, ánimo, vínculo y los recuerdos de Chroma. A internet
solo viaja el texto del prompt (identidad + ánimo + 3 recuerdos recortados +
lo que se acaba de decir) y vuelve la frase.

## 3. Configuración (`config.yaml`)

```yaml
online:
  activo: true
  base_url: "https://api.groq.com/openai/v1"   # compatible OpenAI: sirve cualquier proveedor
  modelo: "openai/gpt-oss-20b"
  api_key_env: "GROQ_API_KEY"                  # la clave vive en .env
  max_tokens: 160
  temperature: 0.6
  reasoning_effort: "low"                      # gpt-oss razona aparte: bajo = habla antes
  timeout_conexion: 3.0                        # si no conecta en 3 s, contesta el local
  timeout_lectura: 10.0
  reintento_seg: 60                            # tras un fallo no se reintenta en cada turno
llama:            # ahora es el RESPALDO
  modelo: "qwen2.5:3b"
```

Apagar la nube y volver a «100 % local» es una línea: `online.activo: false`.
Cambiar de proveedor es cambiar `base_url` + `modelo` + el nombre de la clave.

## 4. Cómo falla (y qué se nota)

| Situación | Qué pasa | Lo que se oye |
|---|---|---|
| La nube responde | camino normal | respuesta en ~1 s |
| Sin internet / clave inválida | el mismo turno se contesta con el local | la respuesta llega en 4-12 s, sin avisos raros |
| Corte a mitad de frase | se acaba ahí, no se repite | frase corta, no una repetición |
| La nube vuelve | tras `reintento_seg` se prueba sola | vuelve a ir rápido sin tocar nada |

Al fallar se imprime `[Cerebro] Nube KO (...)` y, tras cada turno,
`[Cerebro] Motor del turno: nube|local`. El *circuit breaker* existe para que
una caída **no cueste 3 s en cada turno**: si falla, se va directo al local
durante un minuto.

El modelo local se carga al arrancar (25 s después, en segundo plano) para que
el respaldo esté caliente: si cae internet, la primera frase no paga los ~50 s
de carga. Para ahorrar CPU/RAM: `llama.precalentar: false`.

## 5. La marca de versión

`modulos/version.py` es la única fuente de verdad de qué código corre.
Se imprime en la primera línea del log y se pinta 6 s en la base de la cara al
arrancar (`v6.0.0-doble-cerebro`). Cada respaldo lo guarda en su `LEEME.txt`.

```bash
ssh orangepi@192.168.1.130 'head -3 ~/parker.log; tail -40 ~/parker.log | grep Cerebro'
```

## 6. Cómo se comprueba

```bash
# En el PC o en la placa: mide el camino real (nube) con el prompt de Parker
python tools/eval_cerebro.py --solo-latencia --turnos 6
# Y el respaldo local, con el mismo banco
python tools/eval_cerebro.py --solo-latencia --turnos 6 --local
# Contextos/memoria (anáfora, recuerdo de Chroma, conflicto con el presente)
python tools/eval_cerebro.py --solo-contextos
# Sólo la nube, modelo por modelo, comparando (usa el .env del proyecto)
python tools/bench_online.py

# Las pruebas del doble cerebro: respaldo, circuit breaker, corte a mitad
QT_QPA_PLATFORM=offscreen python tests/test_cerebro_doble.py
```

## 6-bis. Cambiar de cerebro por voz (v6.7.0, 27/10/2026)

Pedido: «poder cambiar del cerebro de Groq al local y al revés por voz, con
mensajes programados por si falla». Hay **tres modos** y se cambian hablando:

| Modo | Qué hace |
|---|---|
| `auto` (por defecto) | Nube primaria + local de respaldo. Lo de siempre |
| `local` | **No intenta la nube ni una vez** (ni paga los 3 s de timeout) |
| `nube` | La nube a la fuerza; si no llega, avisa y sigue con el local |

| Se le dice | Qué hace |
|---|---|
| «ponte en local», «cambia al cerebro local», «usa el cerebro de casa» | Modo `local` |
| «vuelve a la nube», «cambia al cerebro de internet», «modo online» | Modo `nube` |
| «modo automático», «decide tú» | Modo `auto` |
| «¿qué cerebro usas?», «¿estás con el local?» | Lo cuenta: modo, modelo y con qué oído te escucha |

Las órdenes se resuelven **sin LLM** (`acciones.interpretar_orden_cerebro`, 0 ms)
y el modo se guarda en `parker.cerebro.json`: si lo dejas en local porque el
internet va mal, un reinicio **no** lo devuelve a la nube a escondidas.
`config.yaml → online.modo_inicial` es solo el punto de partida.

### Avisos hablados (config `online.avisar_por_voz`, por defecto sí)

- Al caer la nube: «Me he quedado sin internet, así que sigo con el cerebro de
  casa: te oigo igual, pero pensaré más despacio.»
- Si el proveedor frena por exceso de peticiones (429): «Me están frenando por
  pedir demasiado seguido; un rato con el cerebro de casa y vuelvo.»
- Si contesta mal por otra razón: «El cerebro de internet no me contesta; sigo un
  rato con el de casa.»
- Al volver: «Ya tengo internet otra vez: vuelvo al cerebro de la nube.»

Cada aviso se dice **una sola vez por caída** (no en cada turno) y solo cuando
Parker no está hablando, para no pisar una respuesta.

### Lo que el oído hace con estas frases (placa, 27/10)

Estas órdenes son cortas y el STT las destroza; medido en la placa diciéndolas
por su propio altavoz:

| Dicho | Oído |
|---|---|
| «Ponte en local» | «Ponte en local» / «Jonte el local» / «Ponte en lo caldo» |
| «Vuelve a la nube» | «Voy a la nube» / «Voy a dar nube» / «Huele a las nubes» |

Por eso el reconocedor tiene tres redes: las frases canónicas, la regla «frase
corta que **termina** en el destino» y, como último recurso, parecido global
(`difflib`, ≥ 0,80) contra las formas canónicas — solo en frases de hasta seis
palabras y nunca en preguntas, así que «¿qué es la nube?» o «vamos a la nube
mañana» no cambian nada. Verificado por voz en la placa en las dos direcciones.

## 7. Lo que se descartó (y por qué)

- **`qwen2.5:1.5b` local**: 2,1 s al primer token, pero respuestas sin sentido y
  nombres inventados. Se retiró de la placa.
- **SmolLM3-3B**: descargado como candidato, nunca dio mejor español que el 3b
  en el banco. Retirado de la placa (1,9 GB libres para recuerdos).
- **`llama3.2:3b`, `gemma3n:e2b`, `qwen3.5:2b`, draft especulativo**: peores en
  el bake-off del 24/10 (detalle en [rendimiento.md](rendimiento.md) §7).
- **LoRA / fine-tune de un personaje**: es la vía para tener voz propia 100 %
  local, pero necesita GPU para entrenar y hoy la prioridad es la latencia; con
  la nube el «personaje» se consigue con el prompt de identidad. Queda como
  fase aparte ([plan_mejoras.md](plan_mejoras.md)).

## 8. Habla limpia: ni marcado ni acentos rotos (v6.0.1)

Dos fallos que solo aparecen con la nube, y los dos se oían:

1. **Acentos rotos.** Groq responde SSE con `content-type: text/event-stream`
   **sin charset**; `requests` asume entonces ISO-8859-1 y
   `iter_lines(decode_unicode=True)` convierte «¿Qué» en «Â¿QuÃ©». Ese texto
   iba a Piper, que intentaba pronunciar «Â» y «Ã». Ahora los bytes se
   decodifican **siempre en UTF-8** (`_texto_de_linea`), con latín como red si
   alguna vez llegara de verdad.
2. **Marcado leído en voz alta.** El modelo puede escribir tokens de canal
   (`<|channel|>final<|message|>`), entidades HTML (`&quot;`), vallas de código
   con JSON (`{"cara":"feliz"}`) o corchetes. Piper lo lee letra a letra
   («comillas, dos puntos, llave…»). `cerebro.limpiar_marcado()` lo quita
   antes de hablar y antes de guardar el turno en el historial, y si alguna vez
   vuelve a aparecer queda anotado en el log:
   `[Cerebro] (marcado en la respuesta, ya corregido) ...`

Pruebas: `tests/test_cerebro_doble.py` (8/8), casos de acentos, entidades,
tokens de canal, vallas y JSON.

## 9. La transcripción también va a la nube (v6.1.0)

La transcripción es la **entrada** del cerebro. Si se equivoca, Parker contesta
a otra cosa y parece que «no coge el contexto». Medido en la placa con la misma
frase de 6,1 s grabada por el micro USB:

| Motor | Tiempo | Texto |
|---|---|---|
| local `faster-whisper base` int8 | **4,31 s** | «El otro día estuve en **al** médico…» (un error) |
| nube `whisper-large-v3-turbo` | **0,68 s** | «…estuve en el médico y me dijo que tengo que descansar más, que no puedo seguir durmiendo cuatro horas.» |

Además, al no transcribir en la placa el CPU queda libre: desaparecen los
turnos de 29 s que salían cuando coincidía con la carga del modelo local.

```yaml
escucha:
  motor: "auto"        # "auto" | "nube" | "local"
  modelo_nube: "whisper-large-v3-turbo"
  timeout_nube_seg: 8
  reintento_stt_seg: 60
```

- Con `"auto"` o `"nube"` **el audio del turno sale de casa** (a Groq). Con
  `"local"` no sale nada, pero se pierde precisión y ~3,5 s por turno.
- Si la nube falla, ese turno lo transcribe el local y no se reintenta durante
  60 s (`[Escucha] STT nube KO`).
- El corpus opcional (`volcar_audio_dir`) sigue funcionando igual.

**v6.2.0 — sesgo del STT también en la nube.** `escucha.initial_prompt`
("…Frases frecuentes: ¿qué día es hoy?, ¿qué día es mañana?, ¿qué hora es?")
ahora viaja a la API como `prompt`; antes solo se usaba en el motor local. La
nube transcribía «día» como «dirá» («¿qué dirá es mañana?»), y el atajo de fecha
acepta ya esa variante para no gastar un turno de LLM en un dato exacto.

### Reparación cuando la conversación se va

Con el texto entrando bien, quedaba el enganche al propio tema: a «No, no»
Parker se inventaba una historia y seguía por ahí. Tres arreglos:

1. Regla en el prompt: contestar **a lo último** (no a su idea anterior) y, si
   le dicen «no» o le corrigen, **no inventar**: decir que se ha liado.
2. Reflejo determinista sin LLM para «¿de qué hablas?», «no te entiendo», «te
   has liado»: «Tienes razón, me he liado. ¿Me lo repites?» (y variantes).
3. Prohibido sacar sus gustos si no vienen a cuento, y **un gusto por charla
   pero distinto en cada una** (v6.6.0: la ficha rota; antes el prompt
   enseñaba siempre la primera entrada y de ahí venía la lluvia y el zumbido).

Historial de conversación subido a **8 mensajes** (4 intercambios): con la nube
el prompt extra cuesta céntimos y es lo que permite seguir el hilo.

Medido después: **4/4 escenarios de contexto** (anáfora, recuerdo de Chroma,
recuerdo irrelevante que no se cuela, conflicto pasado/presente).
