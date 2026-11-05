---
tema: TREC
bloc: 5
estat: resolt
---
# La pantalla SPI es queda en blanc

[[TREC/06 Errades i solucions]] · [[TREC/03 Marc practic]] · [[placa]]

## Símptoma

La pantalla circular GC9A01 s'encén (se sent el *backlight*), el sistema detecta
`/dev/spidev0.0`, però **no es veu res**: ni la cara, ni un color, ni un patró de
prova. El codi no dona error; simplement escriu i la pantalla no respon.

## Context

- Orange Pi 5 Pro, GC9A01 240×240 per SPI0.
- `DC` = `gpiochip1` línia 8; `RST` = `gpiochip4` línia 11.
- Permisos resolts amb `/etc/udev/rules.d/99-parker-hw.rules` (`spidev*` i
  `gpiochip*` a `0666`).
- El projecte pintava la cara amb PySide6 i un *backend* SPI propi.

## Hipòtesi

El bus SPI funciona (el fitxer existeix i les escriptures no fallen), però **el
controlador no està inicialitzat del tot**. La seqüència d'arrencada del GC9A01
que s'havia copiat era incompleta.

## Comprovació

Es van fer tres proves independents, sense arrencar Parker:

```bash
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py            # xips, spidev i pines
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --parpadeo # píxels sota control?
QT_QPA_PLATFORM=offscreen python modulos/display_spidev.py --colores  # color o només brillantor?
```

Resultats:

- Els xips i els pins responien.
- El parpadeig **sí** que es veia: el software controlava la pantalla.
- Els colors **no** es distingien: tot sortia com a brillantor.

Això va demostrar que no era un problema de cablejat ni de permisos, sinó de
**configuració del controlador**.

## Causa

La seqüència d'inicialització no incloïa:

- les **taules de gamma** (correcció de color),
- la comanda d'**inversió** `0x21`,
- alguns ajustos de *madctl* i de tensió.

Sense això, el panell s'encén i accepta píxels, però la imatge resultant és
blanca o il·legible.

## Arreglo

1. Completar la seqüència d'init amb les taules de gamma i la inversió.
2. Validar amb un patró de colors sòlid (vermell, verd, blau) **abans** de
   provar la cara.
3. Deixar les eines de diagnòstic al repositori perquè el problema no es torni a
   diagnosticar a cegues.

## Verificació

- Patró de colors correcte a la pantalla.
- Cara de Parker a **~16 fps** reals per SPI.
- Sense HDMI ni escriptori: el sistema arrenca en mode `offscreen`.

## Lliçó

> **Un bus que respon no vol dir que el dispositiu estigui configurat.**

En un projecte encastat, la frontera entre «no hi ha maquinari» i «el maquinari
hi és però no està inicialitzat» no es veu mirant el cable. Cal una prova que
aïlli cada capa: fitxer → permisos → escriptura → controlador → píxel.

## Què quedava pendent

La pantalla va patir més endavant episodis de **congelació** i d'ulls que
s'allargaven. Aquests no eren el mateix error: van coincidir amb **dues
instàncies** de Parker competint pel SPI i amb el motor d'animació acumulant desviació en els ulls.
La lliçó operativa és a [[TREC/errades/Dues instancies i el micro]].
