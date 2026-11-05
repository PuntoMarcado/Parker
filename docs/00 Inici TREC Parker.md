---
tema: TREC
bloc: 0
estat: viu
---
# Parker · TREC 2025-27

> **Què és aquesta bóveda.** És la capa d'organització del TREC: notes curtes, en
> català, que ordenen tot el material tècnic que ja existeix en aquesta mateixa
> carpeta (`arquitectura.md`, `rendimiento.md`, `placa.md`…). No substitueix els
> documents tècnics: els enllaça, els resumeix i els dona l'estructura que
> demana la guia del centre.

**Estat del projecte:** Parker **v6.13.0-demo-cara** · 24+ fitxers de proves · Orange Pi 5 Pro
**Data d'aquesta nota:** 2 de novembre de 2026

---

## En 60 segons

Parker va començar com un paper sense codi: un company de sobretaula amb quatre
peces (cervell, oïda, memòria i cara) i un dubte de fons: **pot una màquina
petita conversar de veritat, recordar el que li expliques i no ser un altaveu?**

La resposta es va construir mesurant. El primer prototip trigava **15-20 s** a
començar a parlar. Amb un treball sistemàtic —model, prompt, transcripció,
termes i arquitectura— es va arribar a **~1,6 s** de punta a punta, mantenint la
memòria i la cara en local. Pel camí es va descobrir que el coll d'ampolla no era
el model sinó la placa, i que la solució era **repartir el treball**: la placa
posa els ulls, les orelles, la boca i els records; el núvol només redacta la
frase. Si cau internet, el cervell local torna a respondre.

El TREC no és només «fer un robot»: és **demostrar amb dades** per què cada
decisió és la que és, i què es va provar que no funcionava.

---

## Com llegir-ho segons qui ets

| Si ets…                           | Comença per…                                               | Després…                                                                            |
| --------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **El tribunal** (vol el resultat) | [[TREC/07 Conclusions\|Conclusions]]                       | [[TREC/05 Resultats\|Resultats]] → [[TREC/10 Defensa oral\|Defensa]]                |
| **El tutor** (vol el procés)      | [[TREC/01 Pla de recerca\|Pla]]                            | [[TREC/04 Metodologia i proves\|Metodologia]] → [[TREC/12 Diari de recerca\|Diari]] |
| **Has de redactar**               | [[TREC/09 Redaccio de la memoria\|Redacció de la memòria]] | [[TREC/02 Marc teoric\|Marc teòric]] → [[TREC/03 Marc practic\|Marc pràctic]]       |
| **Has de muntar-lo**              | [[TREC/14 Annex. Muntatge i esquemes electrònics\|Guia de muntatge]] | [[TREC/08 Annex. Criteris de muntatge\|Criteris]] · `placa.md`, `inicio.md`            |
| **Vols entendre els errors**      | [[TREC/06 Errades i solucions\|Errades i solucions]]       | Les cinc notes de `TREC/errades/`                                                   |

---

## Mapa de la bóveda

El graf té **quatre nivells**: portada → bloc → part → etapa. Aquesta taula és
el primer nivell; cada bloc conté les seves notes, les parts tenen el seu propi
índex i, quan una part va canviar de solució, les etapes tenen el seu node.

> **El bloc 03 és el relat pràctic.** Explica el disseny, el maquinari, les
> iteracions, els resultats i els límits; el muntatge tècnic viu a l'annex 14 i
> el codi complet, a l'annex 15. El 08 només recull els criteris de verificació.

| Bloc | Nota | Què hi ha |
|---|---|---|
| 1 · Plantejament | [[TREC/01 Pla de recerca]] | Pregunta, hipòtesi, objectius, metodologia i calendari |
| 2 · Marc teòric | [[TREC/02 Marc teoric]] | Neurona, LLM, latència, RAG, veu, API, maquinari i privacitat |
| 3 · Marc pràctic | [[TREC/03 Marc practic]] | Relat pràctic: disseny, maquinari, iteracions, resultats i límits |
| 3b · Les parts | [[TREC/parts/00 Index de les parts]] | Cervell, oïda, veu, memòria, cara, personalitat, agenda, maquinari i document original. La cara té quatre nodes d'etapa: [[TREC/parts/Cara]] |
| 4 · Proves i resultats | [[TREC/04 Metodologia i proves]] · [[TREC/05 Resultats]] | Com es mesura i què es va obtenir |
| 5 · Errors | [[TREC/06 Errades i solucions]] | Taula mestra i cinc casos desenvolupats |
| 6 · Tancament | [[TREC/07 Conclusions]] · [[TREC/09 Redaccio de la memoria]] · [[TREC/10 Defensa oral]] · [[TREC/11 Checklist TREC]] | Conclusions, redacció, defensa i revisió |
| 7 · Annexos | [[TREC/08 Annex. Criteris de muntatge\|Criteris]] · [[TREC/14 Annex. Muntatge i esquemes electrònics\|Muntatge]] · [[TREC/15 Annex. Codi font complet\|Codi]] · [[TREC/12 Diari de recerca]] · [[TREC/13 Bibliografia i webgrafia]] | Criteris, esquemes, codi, cronologia i fonts |

**Annex tècnic de l'última sessió:** [[jarvis|Mejoras Jarvis]] recull el patró de
cancel·lació del torn (barge-in, fil lector de tokens i represa) i el filtre
d'al·lucinacions del STT aplicats a la **v6.12.14**, amb les proves i el que
encara no s'ha pogut verificar amb veu real.

## Com llegir el graf

**Obsidian no calcula semblances.** Cada línia del graf és un enllaç que s'ha
escrit a mà; no hi ha cap connexió automàtica per «paregut» entre dos textos.
N'hi ha de quatre tipus:

| Tipus | Exemple | Què significa |
|---|---|---|
| **Jerarquia** | Inici → bloc → part → etapa | Aquesta nota pertany a aquesta branca |
| **Seqüència** | Paper → prototip → placa → avui | Una etapa porta a la següent |
| **Evidència** | Afirmació → mesura o error | La nota que ho demostra |
| **Vegeu també** | Dues parts que es toquen | Navegació, no dependència |

Els nodes amb moltes línies (Inici, 03, 06, 09) ho són perquè són **portades,
manuals o índexs**, no perquè tot estigui relacionat amb tot. Si vols comprovar una relació, obre la
nota: cada enllaç té una frase al costat que diu per què hi és. Al canvas, les
fletxes porten etiqueta.

A les notes de les parts s'han tret els enllaços laterals de «vegeu també» perquè
no sembli que tot depèn de tot. Les dependències reals (oïda → cervell → veu,
memòria → prompt, personalitat → cara) són al diagrama de
[[TREC/parts/00 Index de les parts]], no en una teranyina de relacions
aproximades.

> **Conseqüència pràctica:** si una connexió et sembla forçada, es pot treure
> sense trencar res. Les notes no depenen de la densitat del graf, sinó del text
> i de les fonts que citen.

---

## El mapa visual

- [[TREC/Mapa de Parker.canvas]] — **jerarquia**: inici → blocs → notes → parts.
- [[TREC/Evolucio de les parts.canvas]] — **matriu d'evolució**: cada fila és una
  part i cada columna una etapa (paper → prototip → placa → doble cervell → avui).

Tots dos són arrossegables i serveixen per explicar el projecte en veu alta o
per projectar-lo sense passar diapositives.

---

## Les xifres que cal recordar

| Què | Abans | Ara | On |
|---|---:|---:|---|
| Primera paraula (pipeline complet) | 15-20 s | **~1,6 s** | [[TREC/05 Resultats]] |
| Cervell local a la placa (TTFT) | 8,75 s p50 | igual (és el respaldo) | [[rendimiento]] §9 |
| Transcripció | 4,8-5,3 s | **0,68 s** | [[rendimiento]] §10 |
| Consulta a la memòria | — | **~150 ms** | [[TREC/05 Resultats]] |
| Recuperació del tema correcte | 85 % (200 records) | **95-100 %** (1.000-3.000) | [[TREC/05 Resultats]] |
| Proves automatitzades | 0 | **24 fitxers** | `tests/` |

**La frase que ho resumeix:** no hem fet un model més ràpid; hem tret la part
lenta del dispositiu i hem deixat en local tot el que no pot sortir de casa.

---

## Com s'obre això a Obsidian

1. Obsidian → **Obrir carpeta com a bóveda** → tria aquesta carpeta `docs/`.
2. Prem `Ctrl+G` per veure el **graf**; els colors per bloc ja estan configurats.
3. Obre `TREC/Mapa de Parker.canvas` per al mapa visual.
4. Els documents originals són en castellà; **la memòria del TREC s'ha d'escriure
   en català**. Aquestes notes ja hi són, però cal redactar-les amb paraules
   pròpies: copiar-les literalment seria un problema d'autoria.

## Per què hi ha fitxers que no són notes

El codi, les eines i els documents de `training/` viuen **fora** d'aquesta
carpeta. Obsidian només pot obrir fitxers de dins de la bóveda, així que els
documents els citen amb `ruta` i no amb enllaços. Si un document antic enllaça
amb `../`, el graf el mostra com un node sense obrir i, en clicar-lo, Obsidian
intenta crear la nota que falta: d'aquí l'avís «folder already exists». Ja no
queda cap enllaç d'aquest tipus.

| Fora de la bóveda | Què és | Cal per al TREC? |
|---|---|---|
| `modulos/cerebro.py` | Cervell doble, prompt, streaming i filtres | Sí, és el nucli |
| `modulos/personalidad.py` | Ànim, víncle, iniciativa i bandit | Sí, és la personalitat |
| `modulos/version.py` | Versió, data i empremta del codi desplegat | Sí, per traçabilitat |
| `tools/parker.service` | Alternativa systemd a cron | No: s'usa `arrancar.sh` + cron |
| `training/README.md` | Pipeline del LoRA de personalitat | No: línia futura |
| `training/recursos_externos.md` | Corpus BMO/Baymax i llocs d'entrenament | No: recerca prèvia |

> **Avís d'autoria.** Aquestes notes són una síntesi de material propi del
> projecte (codis, logs, mesures i documents). No són text per enganxar a la
> memòria: són l'índex i el guió. La redacció final ha de ser teva i en estil
> impersonal.
