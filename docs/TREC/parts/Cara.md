---
tema: TREC
bloc: 3
part: cara
estat: viu
---
# Cara (part gràfica)

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[arquitectura]] · [[TREC/errades/Pantalla SPI en blanc]]

> **Aquesta nota és el resum de la part.** Cada llenguatge visual té el seu propi
> node, amb el que era, per què es va fer i què en queda. Així la cara no queda
> «metida dentro de otro»: si una etapa creix, creix la seva nota.

## Les quatre etapes, en un cop d'ull

| Etapa | Què era | Estat | Node |
|---|---|---|---|
| **1. BMO** | Set imatges fixes amb nom d'emoció (`assets/caras/`) | Històric | [[TREC/parts/cara/1 BMO (imatges)]] |
| **2. Web local** | Pàgina local amb ulls i boca separats | Històric | [[TREC/parts/cara/2 Web local]] |
| **3. Vectorial** | Formes en lloc d'imatges; expressions per combinació | Històric | [[TREC/parts/cara/3 Cara vectorial]] |
| **4. Actual** | PySide6 + motor de vida + GC9A01 per SPI | **Viu** | [[TREC/parts/cara/4 Cara actual (Qt i SPI)]] |

La carpeta `assets/caras/` que hi ha al projecte és **la primera etapa**: set
PNG de BMO (`idle`, `feliz`, `triste`, `pensando`, `hablando`, `sorprendido`,
`dormido`). No és un residu: és el primer prototip gràfic documentat.

## 1. Per què la cara va canviar quatre vegades

La prioritat del projecte mai no va ser la cara: era **que la lògica
funcionés**. Per això les imatges de BMO van durar fins que la memòria i el
cervell van estar mínimament estables. Quan la cara va passar a vectorial, es va
poder animar sense dependre d'un dibuixant: cada emoció és una funció, no un
fitxer.

El canvi no va ser estètic. Cada etapa responia a un límit:

- **BMO**: una imatge no pot parpellejar ni moure la boca.
- **Web local**: un navegador no encaixa en una pantalla SPI ni en mode
  `offscreen`.
- **Vectorial**: la idea era bona, però faltava el motor d'animació.
- **Actual**: calia una cara viva en maquinari real, sense perdre la veu.

## 2. Què fa viva la cara d'avui

- **12 principis d'animació** (anticipació, *squash & stretch*, superposició,
  acció secundària, exageració…), amb un diccionari `PRINCIPIOS` que diu on és
  cada un al codi.
- **Respiració i flotació** contínues, amb sinusoides superposades.
- **Parpelleig asíncron** cada 2-5 s, amb doble parpelleig i *jitter*.
- **Director de gestos**: micro-cellera, curiositat, mirar amunt, cabotada,
  sospir, estirament, badall, doble presa, somriure…
- **Tres famílies segons el silenci**: despert (<1,5 min), sol (<8 min) i
  avorrit (a partir de 8 min), amb parpelleigs més lents.
- **Lip-sync** a 110 ms mentre parla; la boca no va amb retard.
- **Intro de ~4,5 s**: desperta, mira als costats, badalla i mira al davant.
- **Acció superposada**: els ulls arrenquen sols, la cap +40 ms, la boca
  +65 ms i les celles +90 ms.

## 3. Incidències que van portar la cara fins aquí

| Símptoma | Què es va trobar | Com es va resoldre |
|---|---|---|
| Pantalla en blanc | La seqüència d'inici del GC9A01 era incompleta | Completar la init i provar amb patrons de color |
| Cara congelada o a salts | Dues instàncies de Parker competint pel SPI i pel micròfon | Una sola instància; no arrencar a mà |
| Els ulls s'allargaven amb el temps | El motor acumulava desplaçament en els ulls | Tornar a la pose base i limitar l'acumulació |
| Cara borrosa | Resolució/SPI i escalat | Ajustar la mida i el refresc |

El detall tècnic és al node de la quarta etapa:
[[TREC/parts/cara/4 Cara actual (Qt i SPI)]].

## 4. Evidència

- [[historia]] §2.4: les tres etapes del document i la quarta construïda.
- [[arquitectura]] §5 i §10: motor de vida i 12 principis.
- [[TREC/errades/Pantalla SPI en blanc]]: el cas del maquinari.
- `modulos/cara_parker.py`, `modulos/display_spidev.py`,
  `tests/test_animacion.py`, `tests/test_cara.py`, `tests/test_render.py`.
- `assets/caras/`: els set PNG originals.

## 5. Relacions

Expressa l'ànim de la **Personalitat**; el lip-sync va amb la **Veu**; la
pantalla és al **Maquinari**. El primer prototip és
[[TREC/parts/cara/1 BMO (imatges)]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança; el diagrama de dades és al [[TREC/parts/00 Index de les parts]].
