---
tema: TREC
bloc: 1
estat: esborrany
---
# 01 · Pla de recerca

> Aquesta nota és la versió ordenada del que la guia del centre demana a la
> primera entrevista: **què s'investiga, com, per què i per a què**. Els detalls
> tècnics no van aquí; van al [[TREC/03 Marc practic|marc pràctic]].

## 1. Títol provisional

**Parker: disseny i construcció d'un company de sobretaula amb veu, memòria i
doble cervell.**

Alternatives per triar amb el tutor:

- «Parker: un assistent conversacional de sobretaula amb memòria local i
  respostes en menys de dos segons.»
- «Del paper a la placa: disseny, mesura i optimització d'un company
  conversacional de baix cost.»

El títol ha de ser **clar, precís i ajustat al contingut** (guia TREC, §4.3.A).
Si al final pesa més la part de mesura que la de construcció, el segon títol és
més honest.

## 2. Objecte d'estudi

L'objecte no és «un robot» en abstracte, sinó **una cadena completa de
conversa** que ha de complir tres condicions alhora en un ordinador de 60-70 €:

1. **Entendre** el que diu una persona per veu, en català o castellà.
2. **Recordar** fets rellevants d'ella entre sessions, sense inventar-los.
3. **Respondre** en un temps que permeti conversar (objectiu de disseny:
   començar a parlar en menys de 2 s).

La cara, la música, l'agenda i les rutines no són l'objecte principal: són la
prova que el sistema és **usable** i no una demo de laboratori.

## 3. Pregunta de recerca

> **Es pot construir un company conversacional de sobretaula, amb memòria local
> i veu natural, que respongui en menys de 2 segons i continuï funcionant sense
> internet, amb un pressupost de maquinari inferior a 300 €?**

Preguntes secundàries:

- On és realment el coll d'ampolla: el model, la transcripció, la síntesi de veu
  o la placa?
- Quants records pot desar i recuperar ChromaDB abans que la qualitat caigui?
- Què es pot deixar en local i què cal enviar al núvol sense trencar la
  privacitat promesa?
- Una cara expressiva i una iniciativa pròpia canvien la percepció d'usuari, o
  són decoració?

## 4. Hipòtesi

La guia demana una hipòtesi que es pugui sotmetre a comprovació. Se'n plantegen
tres, independents:

| # | Hipòtesi | Com es comprova | On |
|---|---|---|---|
| **H1** | Un sistema híbrid —núvol per redactar, local per oïda, memòria i veu— pot baixar el temps fins a la primera paraula per sota de 2 s en una placa de 8 GB. | Mesura de TTFT i de torn complet, amb el mateix prompt i la mateixa placa, abans i després. | [[TREC/05 Resultats]] |
| **H2** | Una base vectorial local pot recuperar records rellevants amb prou precisió per a una conversa, però **no** per a preguntes curtes de dades exactes. | Prova d'escala (200/1.000/3.000 records) i de recuperació amb 8 preguntes conegudes. | [[TREC/05 Resultats]] §4 |
| **H3** | Un model local petit, usat com a respostal, entén el context però **inventa** quan la memòria no és concloent; per això el núvol ha de ser el primari. | Comparació de fidelitat núvol vs local amb 12 fets i 3 preguntes que no hi són. | [[TREC/05 Resultats]] §5 |

H1 i H3 es poden acceptar o rebutjar amb dades. H2 és **parcialment acceptada**:
el tema sí que es recupera, el detall exacte no. Aquesta distinció és important
perquè el tribunal no vegi una conclusió triomfalista.

## 5. Objectius

### Objectiu general

Dissenyar, construir i **avaluar** un prototip funcional de company
conversacional de sobretaula, amb memòria local i veu, capaç de mantenir una
conversa bàsica i de continuar operatiu sense connexió.

### Objectius específics

1. **Integrar** en una sola aplicació l'oïda (STT), el cervell (LLM), la memòria
   (ChromaDB), la veu (TTS) i la cara (pantalla SPI).
2. **Mesurar** la latència per etapa i reduir el temps fins a la primera paraula
   almenys un 70 % respecte del primer prototip.
3. **Comprovar** l'abast real de la memòria: quants records, amb quina precisió
   i amb quins límits.
4. **Dissenyar** una arquitectura de doble cervell que caigui al local quan no
   hi hagi internet, i mesurar què es nota.
5. **Documentar** cada decisió amb l'evidència que la sosté, incloent-hi els
   intents que van fallar.

## 6. Metodologia

El treball és un **projecte tecnològic** (tipus 1 de la guia) amb **mètode
experimental**. No es tracta de demostrar una teoria, sinó de construir un
artefacte i mesurar-lo. El cicle de treball ha estat sempre el mateix:

```
mesurar → formular una hipòtesi de coll → canviar UNA cosa → tornar a mesurar
   ↑                                                              │
   └──────────────── documentar i fer prova de regressió ─────────┘
```

Cada iteració deixa tres rastres:

1. **Una mesura** abans i després (log `[Latencia]`, eines de `tools/`).
2. **Una prova** que el canvi no trenca res (`tests/`).
3. **Una nota** amb la causa, el arreglo i la versió (`docs/plan_mejoras.md`,
   `modulos/version.py`).

Això és el que permet explicar el projecte com una recerca i no com un diari de
programació. El desenvolupament complet és a [[TREC/04 Metodologia i proves]].

### Instruments

| Instrument | Què mesura | On |
|---|---|---|
| Logs `[Latencia]` | STT, primer token, primera frase, torn complet | `parker.py`, `modulos/cerebro.py` |
| `tools/eval_cerebro.py` | TTFT, generació, context (4 casos) | [[rendimiento]] |
| `tools/medir_latencia.py` | Pipeline amb veu sintètica | `tools/` |
| `tools/bakeoff.sh` | Comparació de models | [[rendimiento]] §7 |
| `tools/probar_memorias.py` | Escala, llindar i fidelitat de Chroma | [[TREC/05 Resultats]] §4 |
| 24 fitxers de `tests/` | Regressions de comportament | `tests/` |
| Prova manual a la placa | Veu real, cara, agenda, música | [[TREC/12 Diari de recerca]] |

## 7. Abast

### Què entra

- Un prototip físic sobre **Orange Pi 5 Pro** (8 GB), pantalla circular
  GC9A01 per SPI, micròfon i altaveu USB.
- Conversa per veu en català/castellà, amb memòria entre sessions.
- Mode núvol (primari) i mode local (respostal), amb canvi per veu.
- Funcions del dia: alarmes, cites, rutines, apunts, temps i música.
- Avaluació quantitativa de latència i memòria; avaluació qualitativa d'ús.

### Què no entra (i per què)

- **Entrenar un model des de zero**: fora de l'abast d'un TREC i del maquinari.
- **Un estudi amb molts usuaris**: el prototip s'ha provat amb el seu autor; no
  hi ha mostra suficient per generalitzar. Es diu a les limitacions.
- **Una carcassa definitiva**: hi ha hagut proves d'encastat, però el disseny
  físic final queda com a línia futura.
- **Privacitat absoluta per defecte**: el mode híbrid envia text (i àudio, si el
  STT és al núvol) fora de casa. Això es tracta com una **decisió de disseny amb
  contrapartides**, no com un oblit.

## 8. Planificació

La guia del centre fixa les dates de les entrevistes; aquest calendari és el de
**treball tècnic** i s'ha d'encaixar amb el calendari oficial.

| Fase              | Quan                  | Què es fa                                       | Evidència                       |
| ----------------- | --------------------- | ----------------------------------------------- | ------------------------------- |
| 0. Idea i abast   | Agost 2026            | Quatre peces mínimes, doble cervell, pressupost | `historia_original.md`          |
| 1. Prototip al PC | Setembre-octubre 2026 | Pygame, barra espaiadora, Groq, primera memòria | [[historia]] §3                 |
| 2. Primera placa  | 17/10/2026            | Mesurar i baixar de 15-20 s a 4,2-4,7 s         | [[rendimiento]] §2              |
| 3. Cervell local  | 24/10/2026            | Tornar al 3b, `num_ctx`, preescalfament         | [[rendimiento]] §7-8            |
| 4. Doble cervell  | 25/10/2026            | Núvol primari + local respostal, STT al núvol   | [[cerebro_doble]]               |
| 5. Dia complet    | 26/10/2026            | Agenda, rutines, apunts, temps, música          | [[dia]], [[agenda]]             |
| 6. Cara i veu     | 27-30/10/2026         | Gestos, Edge TTS, micro que arriba tard         | [[TREC/06 Errades i solucions]] |
| 7. Estabilització | 30-31/10/2026         | Frases amb sentit, proves, documentació         | [[TREC/12 Diari de recerca]]    |

## 9. Estructura prevista de la memòria

La guia oficial obliga a dos grans blocs: **marc teòric** i **marc pràctic**, i
el teòric no pot ser més extens que el pràctic. La distribució està detallada a
[[TREC/09 Redaccio de la memoria]]:

| Part | Pàgines aprox. |
|---|---:|
| Portada, full en blanc, abstract i índex | 4-5 |
| Introducció | 3-4 |
| Marc teòric | 10-12 |
| Marc pràctic (disseny, construcció, resultats) | 18-22 |
| Conclusions | 3-4 |
| Bibliografia | 2-3 |
| Annexos (a part) | — |

## 10. Riscos i com s'han gestionat

| Risc | Probabilitat | Impacte | Mesura |
|---|---|---|---|
| El model local és massa lent | Alta | Alt | Mode híbrid; local com a respostal |
| La placa s'escalfa i baixa el rendiment | Alta | Mitjà | Mesurar temperatura; ventilació; no usar el 3b en calent |
| El proveïdor retira el model | Mitjana | Alt | Selecció automàtica entre models; alternativa local |
| Es perd el treball | Baixa | Molt alt | Copia al PC abans de cada canvi; versió i empremta |
| El STT falla amb veu real | Mitjana | Alt | STT al núvol amb respostal local; proves amb veu pròpia |
| La memòria recupera records equivocats | Alta | Mitjà | Top-k limitat, llindar, dir «no ho sé»; limitació documentada |

## 11. Per què aquest treball és un TREC

No és un tutorial de muntatge. Té:

- **Una pregunta** que es pot respondre amb dades (H1-H3).
- **Una metodologia** replicable (mesura → canvi → prova → document).
- **Uns resultats** que inclouen el que no va funcionar (memòria, al·lucinació
  local, latència tèrmica).
- **Una conclusió** que distingeix el que s'ha demostrat del que només s'ha
  dissenyat.

El que el diferencia d'un projecte de classe és la **traçabilitat**: cada xifra
d'aquest mapa es pot reproduir amb l'ordre que hi ha a
[[TREC/04 Metodologia i proves]].
