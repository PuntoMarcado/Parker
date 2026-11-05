---
tema: TREC
bloc: 7
estat: annex
tipus: annex
---
# 14 · Annex. Muntatge i esquemes electrònics

> **Guia tècnica del prototip.** El capítol [[TREC/03 Marc practic]] §3.2 explica
> per què es va triar cada component i quins límits té el maquinari. Aquí només
> hi ha el que no hi cap: peces, cablejat, ordre de muntatge i comprovació.

[[TREC/03 Marc practic]] · [[TREC/08 Annex. Criteris de muntatge]] · [[TREC/15 Annex. Codi font complet]]

## 1. Abast i seguretat

Cobreix l'Orange Pi 5 Pro, la pantalla GC9A01, el micròfon, l'altaveu,
l'alimentació, la microSD i la caixa. No cobreix la instal·lació del sistema
operatiu ni les dependències de Python: això és a `docs/placa.md`.

- Desconnecta l'alimentació abans de moure qualsevol cable.
- La pantalla i els senyals SPI treballen a **3,3 V**. No hi posis 5 V.
- La placa i la pantalla han de compartir **GND**.
- No forcis el connector de la pantalla ni tanquis la caixa amb cables pinçats.

> El mòdul no va per HDMI: va per SPI i necessita alimentació pròpia de 3,3 V,
> terra comuna i els senyals DC i RST.

## 2. Despiece

No hi ha PCB intermediària: la pantalla es connecta directament al header de
40 pins amb cables Dupont. És fàcil de modificar i també fàcil de deixar un
cable fluix.

| Núm. | Peça | Quantitat | Funció |
| ---: | --- | ---: | --- |
| 1 | **Orange Pi 5 Pro 8 GB** | 1 | Executa el sistema, el model local, la memòria i la interfície |
| 2 | **Pantalla GC9A01 1,28"** | 1 | Mostra la cara; 240×240, circular, SPI, 3,3 V |
| 3 | **microSD 64 GB A2** | 1 | Sistema, models i records; convé tenir-ne una còpia al PC |
| 4 | **Font USB-C 5 V / 3 A** | 1 | Alimenta la placa i els perifèrics |
| 5 | **Micròfon USB** | 1 | Capta la veu; pot trigar uns 29 s a enumerar-se |
| 6 | **Altaveu** | 1 | Reprodueix la veu; jack o USB |
| 7 | **Dissipador** | 1 | Evita que el SoC baixi de freqüència per calor |
| 8 | **Caixa** | 1 | Subjecta la pantalla i protegeix el conjunt; **parcial** |
| 9 | **Cables Dupont femella-femella** | 8 | Connexions pantalla-placa, uns 20 cm |
| 10 | **Separadors i cargols** | 4 | Subjecten la placa; material aïllant |

![Despiece orientatiu de Parker](annexos/despiece.svg)

*Figura 14.1. Despiece orientatiu. La caixa és parcial i no hi ha un CAD final:
el diagrama explica les peces, no serveix per fabricar una carcassa.*

No formen part del despiece la càmera, les rodes, el braç, els sensors de
proximitat ni una placa de distribució. Els models de veu (`.onnx`) es
descarreguen a part i no es consideren peces del projecte.

## 3. Esquema i cablejat

![Esquema de connexions entre la GC9A01 i l'Orange Pi 5 Pro](annexos/esquema_connexions.svg)

*Figura 14.2. Connexions SPI/GPIO entre el mòdul GC9A01 i l'Orange Pi 5 Pro.
L'ordre dels terminals del dibuix és lògic; la posició física és la de la taula.*

| Mòdul | Senyal | Pin físic | GPIO / bus | Funció |
| --- | --- | ---: | --- | --- |
| **VCC** | Alimentació 3,3 V | **1** o **17** | — | Alimenta el mòdul |
| **GND** | Terra | **6** | — | Referència comuna |
| **DIN** | Dades SPI | **19** | `SPI0_MOSI_M2` / GPIO1_B2 | Envia píxels i ordres |
| **CLK** | Rellotge SPI | **23** | `SPI0_CLK_M2` / GPIO1_B3 | Marca el ritme de les dades |
| **CS** | Chip select | **24** | `SPI0_CS0_M2` / GPIO1_B4 | Activa el controlador |
| **DC** | Comanda / dades | **22** | GPIO1_B0 / `gpiochip1` línia 8 | Distingeix ordre de píxel |
| **RST** | Reset | **13** | GPIO4_B3 / `gpiochip4` línia 11 | Reinicia el controlador |
| **BL** | Retroil·luminació | **17** | — | 3,3 V = brillantor fixa |

> **Pin 17.** VCC i BL no poden anar tots dos al mateix pin. El més clar és
> **VCC a l'1 i BL al 17**. Si VCC va al 17, BL ha d'anar a un altre 3,3 V.

Regles que no s'han de trencar:

1. **VCC i BL a 3,3 V, mai a 5 V.**
2. **DIN al 19, no al 21.** El 21 és `MISO`, una entrada: no pot governar el mòdul.
3. **CS al 24, DC al 22 i RST al 13.** DC i RST no es poden intercanviar.
4. **Overlay actiu:** `spi0-m2-cs0-spidev`. Un altre overlay pot enviar les dades
   a uns altres pins i deixar la pantalla en blanc.

### 3.1 Configuració de referència

El driver llegeix noms de GPIO, no números de pin. Els valors que han de
coincidir amb `config.yaml` són:

| Paràmetre | Valor |
| --- | --- |
| `pantalla.spi_bus` / `spi_dispositivo` | `0` / `0` → `/dev/spidev0.0` |
| `pantalla.velocidad_hz` / `velocidad_init_hz` | `24000000` / `1000000` |
| `pantalla.dc_gpio` / `rst_gpio` | `GPIO1_B0` (22) / `GPIO4_B3` (13) |
| `pantalla.modo_spi` / `madctl` / `inversion` | `0` / `0x98` / `true` |

La inicialització va a **1 MHz** perquè són escriptures curtes amb canvis de
comanda i dades; els fotogrames grans van a **24 MHz**.

## 4. Muntatge

1. **Prepara.** Desconnecta la font, descarrega l'estàtica i separa placa,
   pantalla, cables i cargols. Comprova que el mòdul és una GC9A01 o equivalent
   amb connector de 8 pins.
2. **Fixa la placa.** Posa els separadors, munta el dissipador sense forçar-lo i
   deixa espai perquè surti l'aire.
3. **Cableja.** Identifica el pin 1, marca els vuit cables i connecta primer
   **GND** i després **VCC**; segueix la taula de la secció 3. Revisa que cap
   cable de 5 V arribi al mòdul.
4. **Subjecta la pantalla.** Presenta-la sense collar-la, deixa folgança al
   cable i evita que toqui components calents.
5. **Munta l'àudio.** Connecta el micròfon i l'altaveu, i separa'ls per reduir
   eco. Recorda que el micròfon USB pot trigar uns 29 s a aparèixer.
6. **Tanca la caixa.** Insereix la microSD fins que faci clic, deixa entrada i
   sortida d'aire i no tapis l'antena Wi-Fi.
7. **Primera encesa.** Connecta 5 V / 3 A, espera el xim d'àudio i comprova que
   apareix la cara. Si la pantalla és blanca, revisa BL, RST, DC, CS i la
   inicialització; si és negra, revisa VCC, GND i DIN.
8. **Abans de tancar.** Fes una conversa curta, deixa el sistema 20 minuts en
   repòs, comprova que només hi ha una instància i desa una còpia al PC.

## 5. Comprovació

| Comprovació | Resultat esperat | Senyal d'error |
| --- | --- | --- |
| Alimentació del mòdul | 3,3 V entre VCC i GND | 5 V o 0 V |
| Terra | Continuïtat entre GND del mòdul i de la placa | Terra flotant |
| Retroil·luminació | BL a 3,3 V | Pantalla completament negra |
| SPI | DIN 19, CLK 23, CS 24 | Blanc, negre o píxels esbiaixats |
| DC / RST | 22 / 13, segons la taula | El controlador no s'inicialitza |
| Arrencada | Cara visible sense HDMI | Cap imatge |
| Àudio | Micròfon i altaveu disponibles | Silenci o dispositiu equivocat |
| Estabilitat | 20 minuts sense reinicis ni throttling | Lentitud o cara congelada |

Si una comprovació falla, el diagnòstic per símptomes és a [[TREC/03 Marc practic]]
§3.2.6. Aquest annex no repeteix les causes: només fixa el cablejat correcte.

## 6. Relació i traçabilitat

- [[TREC/03 Marc practic]] §3.2: per què aquesta placa, aquesta pantalla i
  aquests límits.
- [[TREC/08 Annex. Criteris de muntatge]]: què es va verificar i per què.
- [[TREC/15 Annex. Codi font complet]]: scripts, configuració i proves.
- `docs/placa.md` §7, `modulos/display_spidev.py` i `config.yaml` → `pantalla`:
  referència tècnica completa.
- Repositori: <https://github.com/PuntoMarcado/Parker>
- Data de revisió: 5 de novembre de 2026.

> **Nota d'honestedat.** No s'ha fet una prova de consum amb instruments de
> laboratori ni una validació mecànica de la caixa. La caixa és un prototip
> funcional, no un producte acabat.
