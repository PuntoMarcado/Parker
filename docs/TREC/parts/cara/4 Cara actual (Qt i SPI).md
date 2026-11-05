---
tema: TREC
bloc: 3
part: cara
etapa: 4
estat: viu
---
# Cara 4 · Cara actual (Qt i SPI)

[[TREC/parts/Cara]] · [[TREC/parts/00 Index de les parts]] · [[arquitectura]] · [[placa]]

> **La quarta etapa és la que està construïda avui.** No és la «intenció
> d'animar» del document: és una escena vectorial de **400×400** pintada amb
> **PySide6**, amb un motor de vida propi, i mostrada en una **GC9A01 de
> 240×240** per **SPI**. La placa arrenca en mode `offscreen`: no cal HDMI ni
> escriptori.

## 1. Què és

- **Escena vectorial** de 400×400, escalada a la pantalla circular de 240×240.
- **16 fps reals** a la placa (el coll és el SPI i la CPU, no el dibuix).
- **Motor de vida** amb respiració, flotació, parpelleig i gestos.
- **Lip-sync** a 110 ms mentre sona la veu.
- **Intro de ~4,5 s**: desperta, mira als costats, badalla i mira al davant.
- **Director de gestos** segons el silenci: despert, sol o avorrit.

![[img/evolucion/cara_vector_v6.png|260]]

## 2. Què la fa diferent de la cara vectorial del document

| Document (etapa 3) | Implementació actual (etapa 4) |
|---|---|
| Vectors per expressió | Vectors + **motor d'animació** |
| Expressions estàtiques combinades | **Interpolació** i moviment continu |
| Sense audio | **Lip-sync** amb la veu |
| Sense pantalla física | **SPI** a la GC9A01 |
| Sense gestos | **Director de gestos** i 12 principis |

### Els 12 principis

El codi té un diccionari `PRINCIPIOS` que diu on és cada principi al fitxer:
anticipació, *squash & stretch*, superposició, acció secundària, exageració,
etc. No són una llista decorativa: cada un té una funció i un efecte visible.

### Acció superposada

Els ulls arrenquen sols; la cap +40 ms, la boca +65 ms i les celles +90 ms. La
cara no es mou «en bloc»: cada part té el seu retard, i això és el que la fa
semblar viva.

## 3. Incidències reals

| Símptoma | Causa | Arreglo |
|---|---|---|
| Pantalla en blanc | Seqüència d'inici del GC9A01 incompleta | Gamma + inversió `0x21` |
| Cara congelada o a salts | Dues instàncies competint pel SPI i el micròfon | Una sola instància i *lock* |
| Els ulls s'allargaven amb el temps | El motor acumulava desplaçament | Tornar a la pose base i limitar l'acumulació |
| Cara borrosa | Resolució/SPI i escalat | Ajustar mida i refresc |

## 4. Com funciona avui

1. `parker.py` arrenca la finestra o el mode `offscreen`.
2. `modulos/cara_parker.py` pinta l'escena i calcula l'estat.
3. `modulos/display_spidev.py` envia el fotograma a la GC9A01.
4. La veu i la cara comparteixen el senyal de parla per fer el lip-sync.
5. Si no hi ha pantalla, la cara no bloqueja la resta del sistema.

## 5. Evidència

- `modulos/cara_parker.py`, `modulos/display_spidev.py`.
- `tests/test_animacion.py`, `tests/test_cara.py`, `tests/test_render.py`.
- [[arquitectura]] §5 i §10.
- [[TREC/errades/Pantalla SPI en blanc]].
- [[TREC/05 Resultats]]: els 16 fps i la latència.

## 6. Etapes

- Anterior: [[TREC/parts/cara/3 Cara vectorial]]
- Tornar al resum: [[TREC/parts/Cara]]
