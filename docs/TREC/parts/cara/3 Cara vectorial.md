---
tema: TREC
bloc: 3
part: cara
etapa: 3
estat: historic
---
# Cara 3 · Cara vectorial

[[TREC/parts/Cara]] · [[TREC/parts/00 Index de les parts]] · [[TREC/parts/Document original]]

> **Tercera etapa (document original, 2a actualització).** Es deixa d'assemblar
> imatges i es **dibuixen formes**: la cara està composta per vectors que es
> combinen dinàmicament per obtenir les expressions. És la idea que arriba a la
> cara d'avui, però **no és el mateix codi**.

## 1. Què era

- Formes geomètriques (ulls, boca, celles) en lloc de PNG.
- Expressions generades **combinant paràmetres**, no triant un fitxer.
- Una cara que es pot escalar i canviar de mida sense perdre qualitat.
- Encara no era el motor d'animació actual: era la representació vectorial.

El document ho diu literalment: «En aquest moment de la segona actualització la
cara està composta per vectors. Utilitzant-los de manera dinàmica per obtenir les
diferents expressions per a la cara.»

## 2. Per què va ser el canvi clau

| Imatge | Vector |
|---|---|
| Un fitxer per expressió | Una funció per expressió |
| No es pot interpolar | Es pot interpolar entre estats |
| Depèn d'un dibuixant | Depèn de paràmetres |
| Escalar la perd | Escalar no la perd |

La vectorial va fer possible el que després seria el motor de vida: **parpelleig,
respiració, microgestos i lip-sync** no són imatges, són variables que canvien
amb el temps.

## 3. Què va faltar en aquesta etapa

La idea era correcta, però encara no hi havia:

- un **motor d'animació** amb principis (anticipació, *squash & stretch*,
  acció secundària);
- **lip-sync** amb l'àudio real;
- una **pantalla física** pròpia;
- un **director de gestos** que decidís quan moure's.

Això és exactament el que afegeix la quarta etapa, la cara actual.

## 4. Què en queda avui

- La representació **vectorial** de la cara.
- La idea que una expressió és una **funció**, no un actiu.
- El vocabulari visual (ulls, boca, celles) que avui anima `cara_parker.py`.

## 5. Evidència

- [[historia_original]] §3.4, 2a actualització: la cara vectorial.
- [[historia]] §2.4: «la cara vectorial del document i la d'avui comparteixen la
  idea, no el codi».
- [[arquitectura]] §5 i §10: el motor de vida i els 12 principis.

## 6. Etapes

- Anterior: [[TREC/parts/cara/2 Web local]]
- Següent: [[TREC/parts/cara/4 Cara actual (Qt i SPI)]]
