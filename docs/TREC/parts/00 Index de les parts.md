---
tema: TREC
bloc: 3
part: index
estat: viu
---
# 00 · Índex de les parts

> **Per què aquesta carpeta.** El [[TREC/03 Marc practic|marc pràctic]] explica el
> conjunt; aquí cada **responsabilitat** té la seva pròpia nota, amb el mateix
> guió: **què és → què deia el document original → com ha evolucionat → com
> funciona avui → què va fallar → quina evidència ho sosté**. Així no queda res
> «metido dentro de otro»: si una part creix, creix la seva nota.

## Com està jerarquitzat

La bóveda té **quatre nivells**, no una xarxa plana:

| Nivell | Què hi ha | Exemple |
|---|---|---|
| **0 · Portada** | Una sola nota que obre el TREC | [[00 Inici TREC Parker]] |
| **1 · Blocs** | Els apartats oficials (01-13) | [[TREC/03 Marc practic]] |
| **2 · Parts** | Les nou responsabilitats d'aquest índex | [[TREC/parts/Cervell]] |
| **3 · Etapes i evidències** | Subnodes d'una part, errors, mesures | [[TREC/parts/cara/1 BMO (imatges)]] |

Un enllaç pot significar quatre coses diferents: **jerarquia** (pare → fill),
**seqüència** (etapa → etapa), **evidència** (afirmació → mesura o codi) o
**vegeu també** (relació lateral). Les tres primeres dibuixen l'arbre; l'última
és la que fa que el graf sembli més dens del que és.

## Les nou parts (nivell 2)

| Part | Responsabilitat | Estat | Nota |
|---|---|---|---|
| **Cervell** | Decidir què dir i amb quin model | Viu | [[TREC/parts/Cervell]] |
| **Oïda** | Convertir veu en text | Viu | [[TREC/parts/Oida]] |
| **Veu** | Convertir text en àudio | Viu | [[TREC/parts/Veu]] |
| **Memòria** | Recordar fets entre sessions | Viu, amb límits | [[TREC/parts/Memoria]] |
| **Cara** | Expressar i acompanyar | Viu | [[TREC/parts/Cara]] |
| **Personalitat** | To, ànim i iniciativa | Viu | [[TREC/parts/Personalitat]] |
| **Agenda i el dia** | Alarmes, rutines, apunts, temps i música | Viu | [[TREC/parts/Agenda i el dia]] |
| **Maquinari i desplegament** | Placa, pantalla, so, versions i còpies | Viu | [[TREC/parts/Maquinari i desplegament]] |
| **Document original** | El pla escrit abans del codi | Tancat | [[TREC/parts/Document original]] |

### La cara, que és l'única part amb subnodes d'etapa

La resta de parts tenen la seva evolució **dins** de la nota (una taula). La
cara no, perquè va canviar de llenguatge visual quatre vegades i cada etapa té
prou entitat per ser un node:

| Etapa | Node |
|---|---|
| 1 · Imatges estàtiques de BMO | [[TREC/parts/cara/1 BMO (imatges)]] |
| 2 · Pàgina web local | [[TREC/parts/cara/2 Web local]] |
| 3 · Cara vectorial | [[TREC/parts/cara/3 Cara vectorial]] |
| 4 · Cara actual (Qt + SPI) | [[TREC/parts/cara/4 Cara actual (Qt i SPI)]] |

Si una altra part es parteix en etapes amb prou entitat (per exemple, la memòria
en «anglesa», «multilingüe» i «segona memòria»), es farà el mateix: un node per
etapa, i la nota mare queda com a resum.

## Com es relacionen

```
                    ┌──────────────┐
                    │  Personalitat │  (to i iniciativa)
                    └──────┬───────┘
                           │ modula
micròfon ──► Oïda ──► Cervell ──► Veu ──► altaveu
             │           │
             │           └──────► Memòria (Chroma)
             │
        Maquinari (micròfon, placa, pantalla)
                           │
                        Cara (expressió)
                           │
                  Agenda i el dia (funcions)
```

No és un diagrama de flux únic: la **personalitat** no és una etapa, és una capa
que dona to a totes les altres. I la **memòria** no és una entrada del cervell:
és una consulta que es fa abans de generar.

## Per què no hi ha una nota per fitxer

Perquè un fitxer no és una part. `cerebro.py` fa de cervell, però també conté
filtres, streaming i el mode local; `personalidad.py` no parla, però decideix
quan parlar. Les notes són **responsabilitats**, no carpetes. Dins de cada nota
hi ha les subpeces (per exemple, dins de «Agenda i el dia» hi ha alarmes,
rutines, apunts, temps i música).

Sí que hi ha un node per **etapa** quan l'etapa és una manera diferent de fer la
mateixa cosa: és el cas de la cara. No és fragmentar per fragmentar; és que les
quatre cares són quatre solucions successives, no quatre funcions del mateix
dia.

Si una subpeça arriba a tenir prou entitat —per exemple, la segona memòria de
coneixement o el LoRA de personalitat—, se li farà la seva pròpia nota.

## El mapa temporal

Per veure l'evolució de totes les parts alhora, obre
[[TREC/Evolucio de les parts.canvas]]. És una matriu: cada fila és una part,
cada columna una etapa (paper → prototip → placa → doble cervell → avui).

## Com llegir el graf sense que sembli una teranyina

El graf d'Obsidian dibuixa **tots** els enllaços iguals, però no ho són:

- **Jerarquia:** portada → bloc → part → etapa. És l'arbre que cal explicar.
- **Evidència:** nota → `rendimiento.md`, `plan_mejoras.md`, `tests/` o codi.
- **Vegeu també:** relacions laterals entre parts. Són útils per navegar, però
  no volen dir que una part depengui de l'altra.

Per això hi ha nodes que tenen moltes línies: són **índexs** (la portada i el
marc pràctic), no conceptes connectats per semblança. Si vols veure només
l'arbre, filtra el graf per `path:"TREC/parts"` o obre el canvas, que és una
layout manual i no una teranyina de força.

## Convenció de fonts

Cada nota distingeix:

- **Document original** → `historia_original.md`, text del 11/08/2026.
- **Mesura** → `rendimiento.md`, `plan_mejoras.md`, logs de la placa.
- **Codi** → mòdul i funció concreta.
- **Prova** → `tests/` o protocol manual.
- **Decisió** → per què es va triar una opció i què es va descartar.

Si una afirmació no té una d'aquestes cinc, es marca com a **línia futura** o
com a **observació qualitativa**.
