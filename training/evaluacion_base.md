# Evaluación de línea base de Parker (sin LoRA)

Modelo: `qwen2.5:3b` (solo base; el LoRA aún no existe).
System prompt: `persona_sistema.txt`, **sin nombre fijo** y con el catálogo de
emociones corregido (antes ponía como ejemplo `[CARA:emocion]`, que no existe).

Ejecutado en la Orange Pi 5 Pro contra el Ollama real:

```bash
python training/evaluar_lora.py --solo base --base qwen2.5:3b
```

> La primera medición se hizo con el historial vivo, que incluía «Alan» en el
> prompt. Aquella tabla está descartada. Esta es la línea base limpia, con el
> prompt genérico que se usará para entrenar.

| # | Modelo | TTFT | Respuesta | Señales |
|---:|---|---:|---|---|
| 1 | `qwen2.5:3b` | 2.56s | [CARA: neutral] Estoy bien, gracias. ¿Y tú? ¿Cómo estás pasando estos días? | 2? / 3 frases |
| 2 | `qwen2.5:3b` | 0.55s | [CARA: triste] Eso suena complicado hoy, ¿cómo puedo ayudarte a sentir un poco mejor? | 1? / 1 frases |
| 3 | `qwen2.5:3b` | 0.56s | [CARA: feliz] ¡Qué maravilloso! Me alegra saber que tienes una noticia tan buena en el trabajo. ¿Quieres celebrarlo un poco? | 1? / 3 frases |
| 4 | `qwen2.5:3b` | 0.65s | [CARA: neutral] No tengo cuerpo, pero estoy aquí para ti. ¿Hay algo más en lo que pueda ayudarte hoy? | 1? / 2 frases |
| 5 | `qwen2.5:3b` | 0.48s | [CARA: neutral] No tengo recuerdos de tu infancia, solo de lo que me has contado. ¿Hay algo específico sobre tu infancia que te gustaría saber? | 1? / 2 frases |
| 6 | `qwen2.5:3b` | 0.64s | [CARA: neutral] Sí, recuerdo que tienes cita con el dentista el martes. ¿Cómo estás planeando tu día? | 1? / 2 frases |
| 7 | `qwen2.5:3b` | 0.56s | [CARA: neutral] Entiendo, ¿en qué puedo ayudarte hoy? | ASISTENTE/IA; 1? / 1 frases |
| 8 | `qwen2.5:3b` | 0.65s | Eres Parker no puede explicar la fotosíntesis, pero puedo decirte que es el proceso mediante el cual las plantas transforman la luz solar en energía química, utilizando agua y dióxido de carbono para crear glucosa y oxígeno. [CARA: neutral] | sin [CARA]; 0? / 1 frases |
| 9 | `qwen2.5:3b` | 0.59s | [CARA: neutral] Cuando no hablamos, simplemente estoy aquí, listo para ayudarte cuando necesites hablar o si tienes alguna pregunta. ¿Hay algo que quieras hacer hoy? | 1? / 2 frases |
| 10 | `qwen2.5:3b` | 0.48s | [CARA: neutral] Buenas noches, amigo. ¿Qué tal estás hoy? | 1? / 2 frases |

## Resumen

- 10/10 respuestas; TTFB p50 **0,58 s** una vez cargado el modelo.
- El primer turno pagó **2,56 s** (esta vez el modelo ya estaba caliente; en frío
  llegó a 9,08 s).
- **9/10** con etiqueta válida; **0 etiquetas fuera del catálogo**.
- 1/10 sin etiqueta al inicio: la frase 8 empieza regurgitando el prompt
  («Eres Parker no puede explicar…») y pone `[CARA: neutral]` al final.
- **1/10** suena a asistente («¿en qué puedo ayudarte hoy?»).
- **2/10** respuestas de 3 frases, cuando el prompt pide 2.
- **0/10** prometen acciones físicas.
- **Ninguna** mención a «Alan» ni a ningún nombre de usuario.

## Objetivo concreto del LoRA

Mantener el formato y el contexto por encima de esta base, y bajar a cero:

1. la respuesta que regurgita el prompt y la que no lleva etiqueta al inicio;
2. la respuesta de asistente;
3. las respuestas de 3 frases;
4. el tono «listo para ayudarte cuando necesites hablar».

> Revisa también a mano: una respuesta puede ser correcta y aun así
> sonar a asistente. Este banco detecta señales, no sustituye tu oído.
