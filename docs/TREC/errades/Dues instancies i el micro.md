---
tema: TREC
bloc: 5
estat: resolt
---
# Dues instàncies i un micro que arriba tard

[[TREC/06 Errades i solucions]] · [[placa]] · [[inicio]]

Aquest cas és la lliçó operativa més important del projecte: **dos símptomes
diferents que semblen el mateix**.

## Part A · Dues instàncies de Parker

### Símptoma

Després de reiniciar per desplegar una versió:

- la cara es congela o va a salts;
- el micròfon no respon;
- el log mostra:

```
No pude reservar DC (GPIO1_B0) … Device or resource busy
[Error Stream Audio] … Device unavailable
```

### Hipòtesi

Hi ha **més d'un procés** `parker.py` obert alhora. El llançador `arrancar.sh`
s'havia activat (cron `@reboot`, amb *lock* i reintent cada 5 s) i, a més, algú
havia arrencat Parker a mà per comprovar el desplegament.

### Comprovació

```bash
pgrep -af parker.py
```

Van aparèixer **dues línies** amb el mateix executable i el mateix directori.

### Causa

Els dos processos es barallen per:

- el **micròfon** (ALSA no permet dues captures del mateix dispositiu);
- el **SPI** (el pin `DC` no es pot reservar dues vegades);
- la **pantalla** (cada procés pinta el seu fotograma).

El resultat no és un error net, sinó una cara entretallada i un micro mut: sembla
un *bug* de programari i és una condició d'execució.

### Arreglo

1. **No arrencar Parker a mà** si ja hi ha el procés.
2. Per reiniciar: matar **el PID concret** i deixar que `arrancar.sh` el
   relanci, o reiniciar la placa.
3. El llançador comprova el *lock* i no engega una segona instància.
4. Mai `pkill -f parker.py`: el patró pot coincidir amb el propi shell i matar
   processos que no toca.

### Verificació

- `pgrep -af parker.py` mostra **una sola** línia.
- La cara no es congela i el micro torna.
- El log no repeteix `Device or resource busy`.

## Part B · El micro USB apareix 29 segons tard

### Símptoma

La placa s'acaba d'encendre. La cara ja hi és, però **li parles i no reacciona**.
Al cap d'una estona, sense tocar res, comença a funcionar.

### Hipòtesi

Parker obre l'àudio abans que el micro USB existeixi. PortAudio llegeix la llista
de dispositius **en importar** el mòdul i la deixa cachejada; si el micro encara
no hi és, es queda amb el còdec intern, que dona silenci absolut.

### Comprovació

Al log d'arrencada:

```
[Escucha] Dispositivo de entrada: … (códec interno)
[Escucha] Bucle continuo activo. Esperando voz humana...
```

I, en paral·lel, la llista del sistema:

```bash
arecord -l        # el micro USB no apareix fins ~29 s després
```

### Causa

Una cursa d'arrencada: **Parker és més ràpid que el maquinari**. No és que el
micro estigui trencat; és que el sistema operatiu triga a enumerar-lo.

### Arreglo (v6.8.1)

1. En el **primer intent**, esperar fins a **25 s** que aparegui el micro.
2. **Refrescar** la llista de PortAudio (no confiar en la caché d'importació).
3. Si s'ha de quedar amb el còdec intern, no obrir el bucle fins a tenir un
   dispositiu amb entrada real.
4. Sonar un **chime de dues notes** quan l'oïda està llesta: la cara apareix
   abans, i sense el so l'usuari no sap si pot parlar.

### Verificació

- En encendre, el chime sona quan el micro és a punt.
- La primera frase dita just després del chime es transcriu.
- El log indica el dispositiu correcte, no el còdec intern.

## Lliçó comuna

> **Abans de tocar codi: quants processos hi ha i des de quan existeix el
> dispositiu.**

Aquestes dues comprovacions (`pgrep`, `arecord -l`) haurien estalviat hores. Per
això són les dues primeres línies del protocol de diagnòstic de
[[TREC/04 Metodologia i proves]] §3.6.

## Per al TREC

Aquest cas és un bon exemple de **variable no controlada**: el mateix codi
funciona o falla segons l'estat del sistema. No es pot dir «Parker no escolta»
sense dir *quantes instàncies hi ha* i *quin dispositiu d'àudio té obert*.
