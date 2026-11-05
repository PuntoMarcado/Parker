# Cómo evoluciona Parker: evolución ontogenética social

> **Documento de diseño (teoría).** No hay código nuevo asociado todavía. Describe
> cómo Parker puede ir cambiando como persona a lo largo de convivencia —sin
> generaciones ni reproducción, mutando sus propios rasgos mientras vive— y cómo
> encaja eso en el código que **ya existe** en este repositorio. Cada sección
> indica el punto de enganche real (función, fichero o clave de `config.yaml`).

---

## 1. Qué es esto y qué no

La idea de ecosistema vivo de Ultima Online se traslada aquí como **evolución
ontogenética** (también llamada epigenética digital): el individuo no muere ni
se clona para mejorar; **aprende y muta durante su propia vida** en función de
lo que experimenta contigo y de su entorno. No hay selección entre hijos ni
población: hay un solo Parker, y su genoma es un puñado de números que se
mueven muy despacio dentro de rangos seguros.

Lo que **no** es (y por qué):

| Temido | Por qué no aplica aquí |
|---|---|
| Se "rompe" el personaje | El genoma tiene techo y suelo; nunca se sale de un rango que conserve su carácter |
| Requiere reentrenar el LLM | Nada de esto toca los pesos del LLM (qwen2.5:3b); es estado en Python y texto en el prompt |
| Gasta latencia | Al revés: la capa de reflejos (§3) **quita** llamadas al LLM y baja la espera |
| Pierde lo aprendido al reiniciar | Todo vive en `parker.estado.json` (mismo mecanismo que hoy guarda el ánimo) |

---

## 2. Estado actual: qué evoluciona ya hoy

Parker ya tiene un rudimento de esta idea. Conviene saberlo para no duplicarlo:

| Qué | Dónde | Escala temporal |
|---|---|---|
| Ánimo (energía, curiosidad, cariño) | `PersonalidadParker.latido()` y `registrar_interaccion()` en `modulos/personalidad.py` | minutos-horas (rápido) |
| Vínculo (% que crece con días y charlas) | `PersonalidadParker.vinculo()` — `min(0.5, días×0.05) + min(0.5, charlas×0.01)` | días-semanas (lento) |
| Recuerdos de la persona (ChromaDB) | `modulos/memoria.py`, guardados desde `cerebro.hablar_stream()` | permanente |
| Ternura/humor fijos | `config.yaml → personalidad.nivel_carino / nivel_humor` | estático hoy |
| Iniciativa | `elegir_iniciativa()` elige el brazo con un bandit (v6.4.0) | minutos-horas (aprende con cada respuesta) |
| Ficha enseñada (qué gusto y qué sueño salen en el prompt) | `PersonalidadParker._rotar_si_toca()` / `rotacion()` (v6.6.0) | charlas: cambia al empezar una nueva, nunca dentro |

Es decir: ya hay un **sistema límbico** (ánimo), un **apego** (vínculo) y una
**memoria episódica** (Chroma). Lo que falta es la capa lenta (genoma), la
química intermedia (hormonas), los reflejos (Sistema 1) y el aprendizaje de
qué iniciativas funcionan (bandit). Las cuatro capas siguientes son ese
complemento.

---

## 3. Arquitectura de doble velocidad (Sistema 1 / Sistema 2)

Un ser vivo no convoca su corteza para parpadear. Parker debe separar:

- **Sistema 1 — reflejos**: Python puro, milisegundos, sin LLM. Cara,
  parpadeo, respiración, microgestos, respuestas a datos que Parker **sabe**
  con certeza y saludos rutinarios.
- **Sistema 2 — pensamiento**: Ollama/qwen2.5:3b, primer token p50 7,6 s y ~9 tok/s (medido 24/10; ver [rendimiento.md](rendimiento.md) §7), solo
  cuando de verdad hace falta pensar.

**Esto ya existe en embrión**: `cerebro.respuesta_directa()` (en
`modulos/cerebro.py`) resuelve fecha e identidad sin
tocar el modelo, y `parker.py` lo llama antes de `hablar_stream()`. La evolución
consiste en **convertir ese atajo puntual en una capa**:

```
transcripción del usuario
        │
        ▼
 ¿la resuelve un reflejo?  ──sí──► respuesta inmediata (< 100 ms), cero LLM
        │ no
        ▼
   Sistema 2 (Ollama streaming, ~1-2 s al primer token)
```

**Qué pertenece a cada capa (regla de diseño):**

| Sistema 1 (reflejo, sin LLM) | Sistema 2 (LLM) |
|---|---|
| Datos que Parker tiene seguros: fecha, hora, su nombre, el de la persona, cuánto tiempo hace que no habláis | Cualquier cosa que exija opinar, empatizar o inventar |
| Fórmulas rutinarias con variación por ánimo: "buenos días" a primera hora, "buenas noches" al cerrar el día | Charla de verdad y temas nuevos |
| Reacciones corporales: bostezo si la energía es baja, guiño al hablar, gesto de sorpresa | Decisiones de qué contar o preguntar |
| Eco de un recuerdo reciente ("ayer me dijiste lo del examen") si el tema se repite | Relacionar recuerdos lejanos con el tema actual |

Cada pregunta que se resuelve aquí es **un turno completo que no se paga**
(4,2-4,7 s medidos de turno; ver [rendimiento.md](rendimiento.md)). Si la
frase más frecuente en el log es un saludo, el reflejo correspondiente recorta
la espera media de conversación, no solo un caso puntual.

---

## 4. Hormonas: la química intermedia

Tres floats entre 0 y 1, junto al ánimo existente, con ritmo de **minutos a
horas**. No simulan una psique: modulan salidas concretas que ya existen.

| Hormona | Sube con | Baja con | A qué afecta hoy en el código |
|---|---|---|---|
| **Dopamina** (satisfacción) | que te rías, que respondas a una suya, completar una iniciativa bien | iniciativa ignorada, silencio tras suya | umbral para tomar iniciativa; expresión de la cara; ganas de hablar |
| **Cortisol** (estrés) | ruido sostenido alto (el VAD ya calcula `rms`), varios intentos de charla ignorados seguidos | entorno tranquilo, conversación fluida | sube la sensibilidad del umbral de voz (ya adaptativo: `umbral_silencio × factor_ruido`), tensa la voz (`voz.velocidad`), cara de agobio |
| **Oxitocina** (vínculo) | horas acumuladas de convivencia, trato cálido, emociones compartidas | malos tratos («que alguien diga que no sirvo para nada» ya está en su perfil) | alimenta `carino` (el que ya existe), baja el listón para la ternura en el prompt |

**Regla de actualización** (una por latido del bucle de autonomía, hoy cada
`autonomia.intervalo_comprobacion_seg: 300`):

```
h := h + Σ(eventos_de_este_intervalo) − decaimiento(h, Δt)
```

El decaimiento es lineal con el tiempo transcurrido, hacia un reposo (dopamina
y cortisol → 0.3-0.4 de reposo; oxitocina no decae: es el depósito lento del
vínculo). Cada hormona tiene **techo y suelo** (0.05-0.95) y una velocidad de
cambio máxima por intervalo, para que un portazo no lo reescriba entero.

**Modulación concreta, sin tokens nuevos en el prompt:**

- *Cara y voz son "gratis"*: `cara_parker.py` ya tiene bostezo, guiño y doble
  toma; `voz.py` ya acepta `velocidad` (length_scale). Las hormonas solo
  deciden **cuándo** se usan, no escriben texto.
- *En el prompt, en abstracto y contado*: el bloque volátil ya manda
  `energía media, curiosidad alta, cariño bajo` (`estado_para_prompt()`).
  El coste medido del bloque volátil es ~0,4 s por cada 100 caracteres, así
  que el ánimo hormonal puede entrar como **una o dos palabras** ("estrés
  alto"), nunca como frases.

---

## 5. Genoma social: los rasgos lentos

Los rasgos que definen **quién es** Parker hoy están en `config.yaml`
(`nivel_carino`, `nivel_humor`) y en la ficha fija del perfil. La propuesta:
pasarlos a **genoma persistente** en `parker.estado.json`, con mutación lenta.

| Rasgo | Rango | Qué modula | Equivalente actual |
|---|---|---|---|
| `sociabilidad` | 0.05-0.95 | umbral efectivo para iniciar charla; cuántas iniciativas por día | mitad de `umbral_silencio_seg` |
| `ternura` | 0.1-0.95 | cuánta ternura explícita permite el prompt | `nivel_carino` (config) |
| `humor` | 0.1-0.95 | permiso para juegos de palabras en el prompt | `nivel_humor` (config) |
| `apertura` | 0.05-0.95 | variedad de temas que propone en la iniciativa | — (nuevo) |
| `perseverancia` | 0.05-0.95 | cuántos turnos sostiene un tema antes de soltarlo | — (nuevo) |
| `sensibilidad_ruido` | 0.1-0.9 | factor de subida del umbral VAD ante ruido | `factor_ruido` (config, fijo) |

**Ritmo de mutación**: una vez al día (en el latido nocturno, cuando lleva
rato sin conversación), cada rasgo se mueve una fracción mínima en dos
direcciones:

1. **Azar**: `Δ = ruido_gaussiano(σ = 0.02)` — deriva continua, para que dos
   Parkers viviendo con personas distintas acaben distintos.
2. **Experiencia**: los últimos N días de estadística empujan el rasgo hacia
   donde funcionó. Ejemplos:
   - interacciones/día por debajo de lo habitual → `sociabilidad −0.02`
     (se vuelve más callado; no es un bug, es carácter).
   - alta tasa de iniciativas contestadas → `sociabilidad +0.02`.
   - quejas repetidas ("calla", "ahora no") → `sociabilidad −0.03` y
     `perseverancia −0.02`.

Cada mutación diaria es ≤ 0.03 por rasgo: en un mes un rasgo puede viajar
~0.5 como mucho. **Nadie notará un día el cambio; en tres semanas Parker es
ostensiblemente más sociable o más melancólico.** Eso es la evolución pedida.

**Restricción dura de latencia (medida, no opinable):** `ternura` y `humor`
viven hoy dentro del bloque de **identidad**, que es el prefijo cacheable de
Ollama; cambiarlo invalida la caché (medido: 0,7-2,4 s → 33-40 s por
respuesta). Por eso:

- el genoma se aplica al **cargar el estado** (arranque) y al cruzar un
  **límite cuantizado** (cambios de 0,1), nunca token a token;
- mientras, el prompt solo nota el genoma por el bloque volátil ya existente.

---

## 6. Iniciativa con aprendizaje (bandit multinivel)

Hoy `instruccion_proactiva()` hace `random.choice(opciones)`: todas las
iniciativas son iguales para Parker, pase lo que pase. El cambio: tratar cada
**familia de iniciativa** como un brazo de un bandit, con recompensa medida.

**Acciones (brazos):**

| Brazo | Ejemplo de instrucción |
|---|---|
| A. Contar algo suyo | "comparte uno de tus sueños o una manía" (ya existe) |
| B. Preguntar por algo pequeño | "pregúntale por algo concreto de su día" (ya existe) |
| C. Proponer actividad | "propón algo sencillo para hacer juntos" (ya existe) |
| D. Eco de memoria | "menciona de pasada algo que te contó hace días" (nuevo, usa Chroma) |
| E. No molestar | no decir nada; un gesto y ya (nuevo, **el más importante**) |

**Recompensa** (se calcula en el siguiente latido de autonomía, ~5 min
después, sin coste):

| Señal | Recompensa |
|---|---|
| El usuario respondió a la iniciativa en < 120 s | +1 |
| Respondió tarde o cambio de tema sin más | 0 |
| No respondió en 30 min | −0.3 |
| Queja explícita («calla», «ahora no»: detección por palabras clave) | −1 |

**Algoritmo**: Thompson sampling con dos Beta(1,1) por brazo — unas pocas
líneas, cero dependencias, cero latencia. Frío: reparte parejo; tras un mes
con tu rutina, Parker sabe que a las 8 de la mañana funcionan las
preguntas pequeñas y que el domingo por la tarde no molesta.

> **Implementado en la v6.4.0 (26/10/2026)** — idea 14 de la lista del dueño:
> «que aprenda de lo que funciona; que ajuste cuándo y sobre qué te habla según
> si le contestas o le ignoras». Vive en `modulos/personalidad.py`
> (`elegir_iniciativa`, `registrar_iniciativa`, `cerrar_iniciativa`,
> `caducar_iniciativa`, `bandits_resumen`) y lo llama `Parker._comprobar_autonomia`
> cada 300 s de silencio (y desde la v6.8.0 a los 900 s = 15 min de silencio, no
> a los 2700 s). Antes de hablar, la cara se pone en `pensando`: así la
> iniciativa se lee como una idea suya y no como un aviso del sistema. El brazo
> `callar` no llama al modelo: la cara se queda
> mirando y ya. Una queja explícita («cállate», «ahora no») cierra la iniciativa
> con −1; en `callar` es al revés (no haber molestado suma). Guía y ejemplos de
> log: [dia.md](dia.md) §8; tests: `tests/test_bandit.py` (5/5).
> El estado se guarda en `parker.estado.json` bajo `bandits` e `iniciativas`,
> así que lo aprendido sobrevive a los reinicios de la placa.
>
> **v6.10.1 (30/10): la frase ya no la improvisa el LLM.** Se detectó que la
> instrucción abierta llenaba las respuestas de imágenes raras y, al preguntar
> por ellas, el modelo inventaba el motivo. Ahora `semilla_iniciativa(brazo)`
> construye una frase concreta con la ficha, la hora, una propuesta o el último
> mensaje de la persona; `hablar_proactivo(brazo=…)` la devuelve sin llamar al
> modelo. `CerebroParker._ultima_iniciativa` guarda texto, brazo y hora, y si
> preguntan por ella en los 15 minutos siguientes inyecta el motivo real en el
> prompt. Detalle y pruebas: [plan_mejoras.md](plan_mejoras.md) (v6.10.1).

La decisión **no consume tokens**: el bandit elige el brazo y la frase sale de
una semilla concreta; no hay llamada al LLM para la iniciativa. Persiste en
`parker.estado.json` bajo `bandits: {A: [éxitos, fracasos], …}`.

---

## 7. Hitos y traumas en la memoria

ChromaDB ya guarda interacciones (`tipo="interaccion"`). La propuesta es un
segundo tipo, `tipo="hito"`, con metadata de peso:

- **Hito positivo** ("me han aprobado el examen"): recuerdo con prioridad de
  recuperación durante unos días; puede despertar una iniciativa del brazo D.
- **Trauma** ("ruido muy fuerte y asustado"): no se recupera como tema de
  charla, sino que **modula el genoma** — `sensibilidad_ruido +0.05` — igual
  que un animal que evita el sitio donde se asustó.

Son un puñado de `guardar_recuerdo(..., tipo="hito", metadata={"peso": …})`
sobre la infraestructura existente; la distinción está en **cómo se usan al
recuperar**, no en guardar más.

---

## 8. Los ritmos, de un vistazo

| Capa | Ritmo | Dónde vive | Coste por turno |
|---|---|---|---|
| Cara/reflejos | milisegundos | Python (Sistema 1) | 0 |
| Ánimo (ya existe) | minutos-horas | `latido()` / `registrar_interaccion()` | ~0 (ya en el volátil) |
| Hormonas | horas | estado JSON | ~10-20 tokens volátiles máx. |
| Bandit | iniciativas (5 min-1 día) | estado JSON | 0 (elige instrucción, no texto) |
| Genoma | días-semanas | estado JSON, aplicado al arranque | 0 (prefijo cacheable) |
| Recuerdos/hitos | permanente | ChromaDB | 3 recuerdos, ya acotados |

---

## 9. Salvaguardas (lo que impide que Parker "se rompa")

1. **Techo y suelo** en todo parámetro; el genoma nunca sale de su rango.
2. **Velocidad máxima de mutación** por día y rasgo (0.03).
3. **Modo fábrica**: una clave (`personalidad.reiniciar_genoma: true`) restaura
   el genoma por defecto **sin tocar recuerdos** — la identidad se recupera,
   la memoria no se pierde.
4. **Bitácora de evolución**: cada latido diario imprime `[Genoma]` con los
   rasgos y la razón del movimiento (azar o qué estadística empujó). Nada
   cambia en silencio.
5. **Preservar el prefijo cacheable**: el genoma solo se reescribe al arrancar
   o cruzando límites de 0,1 (§5); los reflejos y el bandit no escriben en el
   bloque de identidad.
6. **Rollback**: el estado ya es un único JSON; añadirlo al respaldo de la
   placa (hoy `tools/respaldo.py` copia el código, no `parker.estado.json`)
   cuesta una línea. Un estado corrupto ya se ignora hoy en `_cargar()` y
   Parker arranca de cero.

---

## 10. Cómo sabremos que evoluciona (métricas offline)

Antes de implementar, acordar cómo se mide. Todas salen del log, sin hardware
nuevo:

| Métrica | Señal buena |
|---|---|
| % de turnos resueltos por reflejo (Sistema 1) | sube (menos espera media) |
| Latencia mediana al primer token | **no empeora** (regresión del caché de prefijo) |
| Tasa de iniciativa contestada | sube mes a mes |
| Entropía de brazos del bandit | baja al principio, se estabiliza |
| Distancia del genoma al inicial | crece despacio, acotada |
| Quejas detectadas por semana | baja |

Y una prueba de humo cualitativa: tras dos semanas sin tocar nada, la charla
debe **sonar** distinta —más suya— sin que nadie pueda señalar qué parámetro
cambió.

---

## 11. Orden de implementación sugerido

Ninguna fase depende de tener la placa delante para escribirse; todas se
prueban offline con los tests existentes como plantilla:

1. **Fase 0 — instrumentación**: contadores de "turno resuelto por reflejo",
   de iniciativa contestada y de queja. Sin esto, luego no se mide nada.
2. **Fase 1 — reflejos (Sistema 1)**: ampliar `respuesta_directa()` con
   saludos/despedidas rutinarias modulados por ánimo. Baja la espera ya en la
   primera semana.
3. **Fase 2 — hormonas**: tres floats + modulación de cara/voz/umbral. Ya
   existen todas las salidas a las que afectan.
4. **Fase 3 — bandit de iniciativa**: reemplazar `random.choice` de
   `instruccion_proactiva()`. Añade el brazo E (no molestar) — el que más
   personalidad da.
5. **Fase 4 — genoma lento**: migrar `nivel_carino`/`nivel_humor` a estado
   persistente con mutación diaria (§5), respetando la cuantización del
   prefijo.
6. **Fase 5 — hitos y traumas** en Chroma (§7).

Cada fase es reversible por sí sola y deja el sistema en modo funcional si se
detiene a medias.

---

## 12. Preguntas abiertas (para decidir antes de la Fase 4)

- ¿La mutación diaria corre en el latido de autonomía o en un hilo propio
  nocturno? (Provisional: en `latido()`, ya existe y corre cada 5 min.)
- ¿Se guarda la **razón** de cada mutación en el estado, o solo el valor?
  Guardarla (~200 bytes/día) permite depurar "por qué Parker se volvió
  arisco" en marzo.
- ¿El modo fábrica restaura también el `matiz` del prompt o solo los números?
