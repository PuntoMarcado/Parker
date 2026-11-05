---
tema: TREC
bloc: 6
estat: viu
---
# 09 · Redacció de la memòria

> **Aquesta nota és el pont entre el projecte i el document que es lliura.** La
> guia del centre fixa una estructura i unes normes de presentació; aquí es diu
> **què va a cada apartat**, **d'on surt** i **quant ha d'ocupar**. L'extensió
> recomanada és de **50 pàgines** (portada, índex i annexos inclosos; els annexos
> poden anar a part).

## 1. Normes formals (obligatòries)

| Element | Norma |
|---|---|
| Llengua | **Català** (excepte treballs de llengua estrangera) |
| Paper | A4, una cara |
| Tipografia | Times New Roman 12, Arial 11 o Verdana 11 |
| Taules | Cos 9 |
| Interlineat | **1,5** |
| Marges | **2,5 cm** als quatre costats |
| Sagnia | **No**; doble espai entre paràgrafs |
| Alineació | Justificada |
| Numeració | A baix a la dreta; portada i índex **sense numerar** |
| Estil | Impersonal (o primera persona del plural de modèstia) |
| Cites | Entre cometes i amb referència a la font |
| Faltes | Resten 0,1 punts fins a un màxim de 2 |

**Consell de la guia:** «molts punts i poques comes». Una idea per paràgraf,
frases curtes, sense subordinades innecessàries.

## 2. Estructura i repartiment de pàgines

| Apartat | Pàgines | Què hi va | D'on surt |
|---|---:|---|---|
| Portada | 1 | Títol, autor, curs, tutor, centre, localitat | — |
| Full en blanc | 1 | — | — |
| **Abstract + Resum** | 1 | Català i anglès; motivació, mètode, conclusions | aquesta nota §3 |
| Índex | 1-2 | Tots els capítols i subapartats, amb pàgina | es fa al final |
| Agraïments (opcional) | 0-1 | Persones i centres | — |
| **1. Introducció** | 3-4 | Tema, hipòtesi, objectius, motivació, metodologia, estructura | [[TREC/01 Pla de recerca]] |
| **2. Marc teòric** | 10-12 | LLM, STT/TTS, RAG, maquinari, referents, privacitat | [[TREC/02 Marc teoric]], [[conceptos]], [[investigacion_oct2026]] |
| **3. Marc pràctic** | 18-22 | Disseny, construcció, iteracions, errors, resultats | [[TREC/03 Marc practic]], [[TREC/04 Metodologia i proves]], [[TREC/05 Resultats]] |
| **4. Conclusions** | 3-4 | Veredicte, límits, línies futures, opinió breu | [[TREC/07 Conclusions]] |
| **5. Bibliografia** | 2-3 | Fonts amb ressenya i comentari d'ús | [[TREC/13 Bibliografia i webgrafia]] |
| Annexos | a part | Diari, logs, taules, muntatge, codi i manuals | [[TREC/12 Diari de recerca]] · [[TREC/14 Annex. Muntatge i esquemes electrònics]] · [[TREC/15 Annex. Codi font complet]] |

> **Regla d'or:** el marc teòric **no pot ser més extens** que el pràctic. Si el
> teòric creix, es retalla; el valor del treball és el que s'ha construït i
> mesurat.

## 3. Abstract i resum (pàgina 1)

Ha de dir, en 120-180 paraules: **per què** s'ha fet, **com**, **què s'ha
aconseguit** i **què no**. No és una introducció; és un resum del resultat.

### Esborrany en català

> Aquest treball dissenya, construeix i avalua Parker, un company conversacional
> de sobretaula muntat sobre una Orange Pi 5 Pro de 8 GB. L'objectiu és
> comprovar si un sistema de baix cost pot escoltar, recordar i respondre per
> veu en menys de dos segons, i continuar funcionant sense internet. La
> metodologia combina la construcció d'un prototip amb mesures repetides de
> latència, proves de recuperació sobre una base vectorial local i una
> comparació entre un cervell al núvol i un de local. Els resultats mostren una
> reducció del temps fins a la primera paraula de 15-20 s a aproximadament
> 1,6 s, gràcies a un disseny híbrid que deixa en local l'oïda, la memòria, la
> veu i la cara. La memòria recupera el tema en el 85-100 % dels casos, però
> falla en 4 de 8 preguntes curtes de dades exactes; el model local, a més,
> inventa més que el del núvol. Es conclou que el prototip és viable, però que
> la memòria de detall i la privacitat per defecte són límits reals que cal
> declarar i continuar treballant.

### Esborrany en anglès (ABSTRACT)

> This project designs, builds and evaluates Parker, a desktop conversational
> companion running on an 8 GB Orange Pi 5 Pro. It asks whether a low-cost
> system can listen, remember and answer by voice in under two seconds while
> remaining operational without internet. The method combines prototype
> construction with repeated latency measurements, retrieval tests on a local
> vector database and a comparison between a cloud and a local language model.
> Results show a reduction in time to first word from 15-20 s to about 1.6 s,
> achieved through a hybrid design that keeps listening, memory, voice and face
> on the device. Memory retrieves the right topic in 85-100 % of cases but fails
> 4 out of 8 short fact questions; the local model also hallucinates more than
> the cloud one. The prototype is feasible, but exact-fact memory and
> privacy-by-default remain real limits to be addressed.

**No copiar-ho literalment:** són esborranys per adaptar amb les teves paraules.
El tribunal coneix el teu estil i el de la guia.

## 4. Introducció: què ha de respondre

1. **Presentació:** què és Parker i per què no és un altaveu intel·ligent.
2. **Motivació:** per què un company de sobretaula i no una app.
3. **Objectius:** els cinc de [[TREC/01 Pla de recerca]] §5, en forma de llista.
4. **Hipòtesi:** H1-H3, en una frase cada una.
5. **Metodologia:** projecte tecnològic + mètode experimental; resum del cicle
   mesurar → canviar → provar.
6. **Estructura:** què hi ha a cada capítol.

No donar resultats aquí. La introducció es revisa **al final**, quan el treball
ja està acabat.

## 5. Marc teòric: ordre recomanat

> **Numeració de la bóveda:** aquest ordre es desplega a
> [[TREC/02 Marc teoric]] com a **2.1–2.7**. Cada apartat acaba amb un enllaç al
> lloc del pràctic on s'aplica, perquè no es converteixi en un glossari.

1. **Què és un LLM** i per què pot inventar (2 pàg.).
2. **Mida i latència del model**: paràmetres, quantització, TTFT i per què no n'hi ha prou amb «tok/s» (1 pàg.).
3. **STT i TTS**: Whisper, Piper, Edge; VAD (2 pàg.).
4. **Memòria**: embeddings, RAG, Chroma; els tres canvis de la segona
   actualització (2 pàg.).
5. **Maquinari encastat**: RK3588, NPU, límits tèrmics (2 pàg.).
6. **Referents**: BMO i Baymax com a disseny de personatge, no com a tecnologia
   (1 pàg.).
7. **Privacitat**: què surt i què no; el compromís (1 pàg.).

Cada concepte ha de tenir **una utilitat clara** per al projecte. Si un apartat
no s'usa després al marc pràctic, sobra.

## 6. Marc pràctic: l'ordre que explica millor el treball

> **Numeració de la bóveda:** el pràctic es desplega a
> [[TREC/03 Marc practic]] com a **3.1–3.11**. Cada bloc d'iteració acaba amb
> **«Què va fallar»**, perquè els errors no quedin en un annex separat.

| Ordre de redacció | Apartats de la bóveda |
|---|---|
| 1. Disseny | 3.1 |
| 2. Maquinari | 3.2 |
| 3. Primera iteració | 3.3 |
| 4. Placa i latència | 3.4 |
| 5. Doble cervell | 3.5 |
| 6. Memòria, oïda i veu | 3.6 |
| 7. Cara, personalitat i dia a dia | 3.7 |
| 8. Estabilització | 3.8 |
| 9. Resultats | 3.9 |
| 10. Discussió | 3.10 |

1. **Disseny del sistema** (2 pàg.): arquitectura, mòduls i flux d'un torn.
   Figura 1 (arquitectura).
2. **Maquinari** (3 pàg.): placa, pantalla, àudio, energia, calor i caixa.
   Figura 2 (dispositiu).
3. **Primera iteració: del paper al prototip** (2 pàg.): Pygame, barra
   espaiadora, Groq, primers errors.
4. **Segona iteració: la placa i la latència** (3 pàg.): 15-20 s → 4,2-4,7 s;
   taula per etapa; STT; preescalfament.
5. **Tercera iteració: el doble cervell** (3 pàg.): per què el local no n'hi
   havia prou; núvol primari; caiguda; privacitat; Figura 3.
6. **Quarta iteració: memòria, oïda i veu** (3 pàg.): records, llindar, fidelitat
   i síntesi.
7. **Cinquena iteració: cara, personalitat i dia a dia** (3 pàg.): agenda,
   rutines, apunts, música i gestos.
8. **Estabilització** (2 pàg.): una sola instància, arrencada i proves.
9. **Resultats** (4-5 pàg.): latència, STT, memòria (escala, llindar, fidelitat),
   proves. Figures 4-5 i taules.
10. **Discussió** (2 pàg.): què volen dir els números; límits; comparació amb
    l'estat de l'art.

**Consell:** cada subapartat ha de començar amb el problema, no amb la solució.
«El 3B trigava 8,75 s» és més honest que «vam canviar al núvol».

## 7. Figures i taules previstes

| Núm. | Què mostra | D'on surt |
|---|---|---|
| Figura 1 | Arquitectura de mòduls i flux d'un torn | [[TREC/03 Marc practic]] §3.1.2 |
| Figura 2 | El dispositiu muntat (placa, pantalla, micro, altaveu) | [[TREC/03 Marc practic]] §3.2 |
| Figura 3 | Doble cervell: núvol primari i local de reserva | [[TREC/03 Marc practic]] §3.5 |
| Figura 4 | Latència per etapa, abans i després | [[TREC/03 Marc practic]] §3.9.1 |
| Figura 5 | Escala de la memòria: consulta vs nombre de records | [[TREC/03 Marc practic]] §3.9.2 |
| Figura 6 | Estats de la cara i gestos | [[TREC/03 Marc practic]] §3.7.1 |

Totes les figures han de tenir **peu, número i comentari al text**. No es pot
posar una imatge i no dir què aporta. Les taules, cos 9.

## 8. Conclusions: què hi ha d'haver

- Resposta a la pregunta de recerca, amb matisos.
- Veredicte de les hipòtesis (acceptada / parcial / rebutjada).
- Objectius assolits i no assolits.
- Dificultats trobades i com s'han gestionat.
- Valoració de la metodologia: què canviaries.
- Línies futures (memòria de fets, LoRA, refrigeració, estudi d'usuaris).
- Opinió personal **breu i argumentada**, sense «ha estat molt interessant».

No repetir el treball: **sintetitzar**.

## 9. Bibliografia i autoria

- Cada font: **ressenya completa + comentari** de quina informació s'ha usat.
- Ordre alfabètic i **un sol sistema** de citació.
- No incloure el que s'ha consultat i no s'ha usat.
- **No copiar** textos de les guies, de la documentació tècnica ni d'aquestes
  notes. Es pot citar, però cal dir la font.
- Les notes d'aquesta bòveda són **ajuda de treball**, no text per enganxar.

## 10. Abans de lliurar: revisió en fred

1. Llegeix-ho en veu alta: si una frase no es pot dir d'una tirada, és massa
   llarga.
2. Comprova que **cada afirmació** té dada, cita o referència.
3. Busca paraules buides: «molt», «bastant», «interessant», «en definitiva».
4. Revisa que el marc teòric sigui **més curt** que el pràctic.
5. Comprova que totes les figures estan numerades i comentades.
6. Passa el corrector i torna-ho a llegir; una falta resta 0,1 fins a 2 punts.
7. Comprova marges, interlineat, tipografia i numeració.
8. Fes l'índex **al final**, amb la paginació real.
9. Imprimeix una còpia i mira-la en paper: els errors de maquetació es veuen
   millor.

La llista completa és a [[TREC/11 Checklist TREC]].
