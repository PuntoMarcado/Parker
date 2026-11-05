---
tema: TREC
bloc: 3
part: cara
etapa: 1
estat: historic
aliases: [Primer prototip, BMO]
---
# Cara 1 · Imatges estàtiques de BMO (primer prototip)

[[TREC/parts/Cara]] · [[TREC/parts/00 Index de les parts]] · [[TREC/parts/Document original]]

> **Primer prototip gràfic (etapa inicial, document del 11/08/2026).** La cara de Parker eren **set imatges
> fixes de BMO**, el personatge d'*Adventure Time* que va inspirar el projecte.
> No hi havia animació: cada estat era un PNG i el canvi de cara era un canvi de
> fitxer. És la carpeta `assets/caras/` que encara hi ha al projecte.

## 1. Què era

- Un bucle de **Pygame** amb una cua d'estats: el fil principal deia «escoltant»,
  «pensant», «parlant» o «feliç» i la cara canviava la imatge.
- Set PNG amb nom d'emoció, sense ulls ni boca separats.
- Cap animació, cap parpelleig i cap lip-sync: la boca era la de la imatge.

El document original ho explica així: mentre la lògica no funcionava, es va
prioritzar «la implementació, optimització i arquitectura de les funcions
lògiques» per sobre del disseny visual. La cara era l'últim que es tocava.

## 2. Les set emocions

| Fitxer | Estat | Quan s'usava |
|---|---|---|
| `bmo_idle.png` | Repòs | Sense torn actiu |
| `bmo_feliz.png` | Feliç | Resposta positiva o acudit |
| `bmo_triste.png` | Trist | Notícia dolenta o empatia |
| `bmo_pensando.png` | Pensant | Mentre el cervell genera |
| `bmo_hablando.png` | Parlant | Mentre sona la veu |
| `bmo_sorprendido.png` | Sorprès | Pregunta inesperada |
| `bmo_dormido.png` | Dormit | Repòs llarg o «bona nit» |

**Repòs** · ![[img/evolucion/bmo_idle.png|200]]

**Feliç** · ![[img/evolucion/bmo_feliz.png|200]]

**Trist** · ![[img/evolucion/bmo_triste.png|200]]

**Pensant** · ![[img/evolucion/bmo_pensando.png|200]]

**Parlant** · ![[img/evolucion/bmo_hablando.png|200]]

**Sorprès** · ![[img/evolucion/bmo_sorprendido.png|200]]

**Dormit** · ![[img/evolucion/bmo_dormido.png|200]]

> Les originals viuen a `assets/caras/` (fora de la bóveda). A `docs/img/evolucion/`
> n'hi ha una còpia només per poder-les veure en aquesta nota; el codi no les usa.

## 3. Per què es va fer així

Perquè el problema del moment no era el dibuix: era **demostrar que la cadena
funcionava** (micròfon → text → model → veu → cara). Una imatge fixa és la forma
més barata de provar l'últim esglaó. A més, BMO ja era el referent de
personalitat del projecte: un robot petit, ingenu i afectuós.

## 4. Per què es va deixar

Una imatge no pot fer el que demana una conversa real:

- no pot **parpellejar** ni mirar;
- no pot moure la boca al ritme de la veu;
- no pot expressar estats intermedis (mig pensant, mig trist);
- cada emoció nova és un fitxer, no una funció.

Per això la següent etapa va separar ulls i boca en una pàgina web local, i la
següent va dibuixar formes en lloc de carregar imatges.

## 5. Què en queda avui

- **Les set imatges originals**, a `assets/caras/`.
- El **referent BMO** a la personalitat (ingenu, afectuós, fa la seva vida).
- La lliçó de disseny: la cara no podia dependre d'un dibuixant ni d'un fitxer
  per expressió.

No en queda codi actiu: el visor de Pygame es va substituir quan la cara va
passar a PySide6. Per això aquesta etapa es documenta com a **història**, no com
un mòdul del repositori.

## 6. Evidència

- [[historia_original]] §3.4: «s'estan utilitzant les expressions estàtiques
  d'un dels personatges […] en BMO».
- [[historia]] §2.4: les tres etapes del document i la quarta construïda.
- `assets/caras/`: els set PNG.
- `docs/img/evolucion/`: còpia per a la bóveda.

## 7. Següent etapa

[[TREC/parts/cara/2 Web local]] — separar ulls i boca per obtenir més
expressions.
