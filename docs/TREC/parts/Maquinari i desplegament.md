---
tema: TREC
bloc: 3
part: maquinari
estat: viu
---
# Maquinari i desplegament

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[placa]] · [[TREC/08 Annex. Criteris de muntatge]]

## 1. Què és

És la part **física** i la que fa que el codi arribi a la placa sense errors:
placa, pantalla, micròfon, altaveu, alimentació, carcassa, instal·lació,
arrencada automàtica, versions i còpies.

## 2. Què deia el document original

El document preveia una **Raspberry Pi** i un pressupost de **250 €**, amb tres
plans:

1. Ampliar el pressupost.
2. Una pantalla petita al costat del monitor, amb el cervell al PC.
3. Un assistent de cuina que dicta la recepta.

El que es va construir s'assembla al **pla 2 en la forma** —un dispositiu petit
amb pantalla pròpia—, però **no depèn del PC**: la placa porta el seu cervell
local de respostal, la memòria i la veu.

## 3. Per què aquesta placa i no una altra

### 3.1 Requisits

| Requisit | Per què |
|---|---|
| **8 GB de RAM** | Model local de 3b, Whisper, Qt i Chroma han de conviure |
| **ARM64 i Linux** | Ollama, PySide6, `spidev` i `gpiod` hi han de córrer |
| **GPIO i SPI** | La pantalla circular no va per HDMI |
| **USB** | Micròfon i altaveu independents |
| **5 V i consum baix** | Ha de poder estar encesa tota la tarda |
| **Preu ≤ ~300 €** | És el sostre del projecte |

### 3.2 Candidates

Els preus són **orientatius** llevat del que surt del full de costes; varien segons
botiga, impostos i estoc. No s'ha fet un benchmark de la mateixa tasca a cada
placa: la decisió és per requisits, disponibilitat i preu.

| Candidata | CPU / RAM | NPU | GPIO/SPI | Consum | Preu orientatiu | Veredicte |
|---|---|---:|---|---|---|---|
| **Orange Pi 5 Pro 8 GB** | RK3588S: 4×A76 + 4×A55 / 8 GB | 6 TOPS | Sí | 5 V / 3 A | **238,84 €** amb font (factura) | **Escollida** |
| Raspberry Pi 5 8 GB | BCM2712: 4×A76 / 8 GB | No | Sí | 5 V / 5 A | ~90-110 € placa + font | Alternativa inicial; menys nuclis i sense NPU |
| Radxa Rock 5B 8 GB | RK3588: 8 nuclis / 8 GB | 6 TOPS | Sí | 5 V / 4 A | ~150-180 € | Bona, però més cara i menys disponible |
| Mini PC N100 | Intel N100 x86 / 8-16 GB | No | **No** | 10-25 W | ~200-300 € | Descartat: sense GPIO/SPI i més consum |
| Portàtil vell | x86 / variable | No | **No** | 15-45 W | ~0-200 € | Descartat: gran, sense pins i no encastable |

### 3.3 Per què va guanyar l'Orange Pi 5 Pro

- **Compleix els sis requisits**: 8 GB, ARM64, GPIO/SPI, USB, 5 V i preu dins del
  pressupost.
- **Més marge de CPU** que la Raspberry Pi 5 prevista: 8 nuclis (4 grans + 4
  petits) en lloc de 4, i NPU de 6 TOPS per si més endavant es vol provar RKLLM.
- **Disponibilitat en el moment de compra**: el paquet placa+font (238,84 €)
  entrava dins del pressupost de maquinari; el total amb pantalla, targeta i caixa
  puja a 312,91 € i cal explicar-lo. La Raspberry Pi 5 s'havia previst al document
  original, però el prototip final va canviar de placa.
- **És una placa, no un PC**: es pot deixar encesa, no fa soroll i cap en una caixa
  petita.

**Matís honest:** no s'ha mesurat la mateixa feina a la Raspberry Pi 5 i a
l'Orange Pi 5 Pro. No es pot afirmar «aquesta és la més ràpida»; es pot afirmar
«aquesta és la que millor compleix la matriu de requisits amb el pressupost i
l'estoc disponibles». La Raspberry Pi 5 també compliria els requisits tècnics i
té més comunitat; es descarta pel preu final i perquè l'Orange Pi oferia més
nuclis i NPU en el moment de compra, no per una mesura de rendiment.

## 4. Per què aquesta pantalla i no una altra

### 4.1 Candidates

| Pantalla | Mida / resolució | Interfície | Color | Preu orientatiu | Veredicte |
|---|---|---|---:|---|---|
| **GC9A01 1,28"** | 240×240, circular | SPI | Sí | **20,98 €** (factura) | **Escollida** |
| HDMI 5" | 800×480, rectangular | HDMI + USB | Sí | ~50-70 € | Necessita HDMI i escriptori; massa gran |
| OLED 0,96" | 128×64, rectangular | I2C | Monocroma | ~5-10 € | Massa petita i lenta per a una cara |
| TFT SPI 2,8" | 320×240, rectangular | SPI | Sí | ~15-25 € | Rectangular; més pins i més consum |

### 4.2 Per què la GC9A01

- **És rodona**, com la cara de BMO; no cal retallar una pantalla rectangular.
- **240×240** és suficient per a ulls, boca i gestos sense carregar un escriptori.
- **SPI** permet pintar-la des de la placa sense HDMI ni servidor gràfic.
- **3,3 V i 1,28"** encaixen en una caixa petita i consumeixen poc.
- **Preu**: 20,98 €, dins del pressupost.

El mòdul concret és el **Waveshare 1.28inch LCD Module**, amb controlador GC9A01.

**Contrapartida:** la seqüència d'inici és delicada i el bus SPI limita el refresc.
Mesurat a la placa: **16,4 fps** amb fotogrames de **115.200 bytes** a 24 MHz. No
és una pantalla de vídeo; és una cara, i 16 fps són suficients per parpellejar i
moure la boca.

## 5. Evolució

| Moment | Què es va fer | Resultat |
|---|---|---|
| Agost 2026 | Paper: Raspberry Pi 5 8 GB, 250 € | Pressupost i tres plans |
| Prototip | PC amb Pygame i barra espaiadora | Primera Parker funcional |
| Octubre 2026 | **Orange Pi 5 Pro 8 GB** (RK3588S) | Més potència que la Raspberry prevista |
| 17/10/2026 | Pantalla GC9A01 per SPI | Cara sense HDMI ni escriptori |
| 17/10/2026 | Micròfon USB + altaveu | Àudio real |
| 30/10/2026 | Cron + `tools/arrancar.sh` | Arrencada sola, amb *lock* d'una instància |
| 30/10/2026 | Versió i empremta del codi | Saber què corre a la placa |
| 30/10/2026 | Còpies només al PC | La targeta queda per als records |

## 6. Com funciona avui

| Peça | Detall |
|---|---|
| Placa | Orange Pi 5 Pro, 8 GB, RK3588S (4×A76 + 4×A55) |
| Pantalla | GC9A01 240×240 per SPI0; DC `gpiochip1` línia 8; RST `gpiochip4` línia 11 |
| Àudio | Micròfon USB i altaveu; PortAudio |
| Alimentació | USB-C 5 V / 3 A |
| Targeta | microSD 64 GB A2 |
| Projecte | `/home/orangepi/parker` |
| Entorn | `/home/orangepi/env` (venv) |
| Arrencada | cron `@reboot` → `tools/arrancar.sh` |
| Log | `~/parker.log` |

### Regles que no s'han de trencar

1. **Una sola instància.** Dues es barallen pel micròfon i pel SPI.
2. **No arrencar a mà** si ja hi ha el procés; matar el PID i deixar que el
   llançador el relanci.
3. **No copiar el `venv` del PC**: les rodes binàries són d'una altra
   arquitectura.
4. **Comprovar la versió i l'empremta** al log després de desplegar.
5. **Les còpies, al PC**. `tools/respaldo.py` es nega a executar-se a la placa.

## 7. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| Pantalla en blanc | Seqüència d'inici del GC9A01 incompleta | Gamma + inversió `0x21` |
| Pantalla negra en moure un cable | El DIN va passar del pin 19 al 21 (MISO) | Tornar el DIN al 19; loopback a part |
| Micro que no respon en encendre | El USB apareix ~29 s després; PortAudio cacheja | Esperar, refrescar i sonar un chime |
| Cara congelada | Dues instàncies competint | Lock i una sola instància |
| Va lent | El 3B s'escalfa i baixa de freqüència | Ventilació; el local és respostal |
| Es perdia el fil de què corria | Dates de fitxers | Versió + empremta al log |
| Còpies a la targeta | Costum antic | Respaldo només al PC |

## 8. Evidència

- [[placa]]: instal·lació, SPI, registre i lliçons.
- [[TREC/08 Annex. Criteris de muntatge]]: criteris de verificació del muntatge.
- [[respaldos]]: què hi ha a cada còpia.
- `modulos/version.py`, `tools/arrancar.sh`, `tools/parker.service`
  (alternativa systemd, no usada), `docs/TREC - Full 1.pdf` (pressupost).
- `docs/TREC - costes.pdf`: 238,84 € placa amb font, 20,98 € pantalla,
  312,91 € total.

## 9. Relacions

Sustenta les quatre parts que toquen el maquinari: la **Cara** (pantalla SPI),
l'**Oïda** (micròfon USB), la **Veu** (altaveu) i el **Cervell** (model local).
El diagrama de dades és al [[TREC/parts/00 Index de les parts]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança.
