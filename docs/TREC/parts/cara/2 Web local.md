---
tema: TREC
bloc: 3
part: cara
etapa: 2
estat: historic
---
# Cara 2 · Pàgina web local

[[TREC/parts/Cara]] · [[TREC/parts/00 Index de les parts]] · [[TREC/parts/Document original]]

> **Segona etapa (document original, 2a actualització).** La cara va deixar de
> ser una imatge sencera: una **pàgina web en local** connectada al Python de
> Parker dibuixava els ulls i la boca com a elements separats. Es podien
> combinar per obtenir més expressions que set PNG.

## 1. Què era

- Un servidor/pàgina local que rebia l'estat de Python.
- **Ulls i boca com a elements independents**: cada un es podia moure, tancar o
  canviar sense canviar l'altre.
- Més combinacions que les set imatges: ulls contents + boca trista, ulls
  adormits + boca oberta, etc.
- Encara **sense animació contínua**: era una composició d'estats, no un motor
  de gestos.

El document ho descriu com «una pàgina web en local que es connectava amb el codi
de Python que li enviava les instruccions, sent cada part de la cara, com els
ulls i la boca, elements separats».

## 2. Per què va ser un pas endavant

| Abans (BMO) | Ara (web local) |
|---|---|
| Una imatge per estat | Una composició d'elements |
| 7 expressions | Moltes combinacions |
| Canvi de fitxer | Canvi de propietats |
| La boca és part del dibuix | La boca es pot moure a part |

La idea important no és «web»: és **descompondre la cara**. Aquesta idea és la
que arriba fins a la cara vectorial d'avui, on cada tret és una funció.

## 3. Per què es va deixar

Quan el projecte va passar a la **pantalla circular de la placa**, una pàgina web
va deixar de encaixar:

- La GC9A01 es pinta per **SPI**, no és un navegador.
- Un navegador afegeix una capa que es pot penjar o desincronitzar de la veu.
- La cara ha de poder córrer **offscreen**, sense escriptori ni servidor web.
- Per al TREC, el que s'havia de demostrar era la integració amb maquinari real,
  no la composició en HTML.

No és que la web fos dolenta: és que **no era el camí** per al dispositiu final.
La lliçó es va conservar (ulls i boca separats); la tecnologia es va canviar.

## 4. Què en queda avui

- La **descomposició** d'ulls, boca, celles i pupil·les.
- La idea de combinar estats per obtenir expressions.
- El record, a `historia_original.md` i `historia.md`, d'una etapa que no ha
  deixat codi al repositori.

## 5. Evidència

- [[historia_original]] §3.4, 2a actualització: la pàgina web local.
- [[historia]] §2.4: la segona etapa i el pas a vectors.
- No hi ha mòdul actiu: la implementació es va substituir.

## 6. Etapes

- Anterior: [[TREC/parts/cara/1 BMO (imatges)]]
- Següent: [[TREC/parts/cara/3 Cara vectorial]]
