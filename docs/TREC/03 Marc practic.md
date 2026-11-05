---
tema: TREC
bloc: 3
estat: complet
tipus: memoria
---
# 03 · Marc pràctic

> **Aquest capítol no és un manual de muntatge.** Explica com es va passar d'una idea a un prototip funcional, per què es van prendre les decisions, què es va mesurar i què va fallar. La construcció hi és present, però el que interessa al tribunal no és aprendre a repetir el cablejat: és entendre **per què** el sistema és com és i **com se sap** que funciona.

La narració segueix l'ordre real del projecte: primer el disseny, després les iteracions, finalment els resultats i la discussió. Les dades provenen de les mesures del prototip, no de promeses de rendiment. Quan una xifra és antiga però explica una decisió, es diu; quan no hi ha mesura, es marca com a observació o com a línia futura.

---

## 3.1 Disseny del sistema

### 3.1.1 La pregunta que ordena el disseny

Parker no va néixer com una col·lecció de components, sinó com una pregunta: **es pot construir un company de sobretaula que escolti, recordi i respongui per veu en menys de dos segons, amb un pressupost de maquinari inferior a 300 € i sense dependre completament d'internet?**

Aquesta pregunta imposa cinc requisits que no es poden separar:

| Codi | Requisit | Per què és una condició del projecte |
|---|---|---|
| **R1** | Escoltar veu humana en català o castellà, sense prémer cap botó | La conversa ha de començar amb la paraula, no amb una aplicació |
| **R2** | Recordar fets entre sessions | Un company que ho oblida tot és una demo, no una presència |
| **R3** | Respondre en menys de 2 s fins a la primera paraula | Per sota d'aquest llindar la conversa es percep com a fluida |
| **R4** | Continuar funcionant sense internet | El sistema ha de tenir un pla B real, no nominal |
| **R5** | Acompanyar amb una cara i un to, no només amb text | La interfície ha de fer llegible l'estat del sistema |

Si una millora no ajudava a un d'aquests cinc requisits, quedava fora. Això explica per què el prototip no té rodes, càmera, braç ni intel·ligència artificial general: no formaven part del problema que es volia demostrar. També explica per què la cara no és decoració: és la manera de fer visible quan Parker escolta, pensa o parla.

### 3.1.2 Arquitectura per capes

El sistema es va dissenyar com una pila de capes. Cada capa té una funció i una prova pròpia; si una falla, no s'ha de confondre amb les altres. Aquesta separació és la idea més útil del capítol, perquè la majoria d'errors del projecte no venien del model, sinó d'una capa inferior.

| Capa | Què fa | Decisió principal |
|---|---|---|
| **Energia** | Donar corrent estable | Font de 5 V i 3 A; el consum no és un detall |
| **Maquinari** | Placa, pantalla, micròfon i altaveu | Orange Pi 5 Pro de 8 GB, pantalla circular i àudio USB |
| **Sistema operatiu** | Parla amb el maquinari | Linux, amb els controladors de pantalla, GPIO i àudio |
| **Programari de Parker** | Decideix i coordina | Oïda, memòria, cervell, veu, cara, agenda i personalitat |
| **Serveis externs** | Allò que no és a la placa | Núvol per redactar, veu, temps i música, només si el mode ho permet |
| **Persona** | Qui usa el sistema | Veu, silenci, interrupcions i expectatives |

Aquesta taula és també una eina de diagnòstic. Quan la pantalla queda blanca, la primera pregunta no és «quin model he de canviar», sinó **en quina capa està la fallada**. Un símptoma visual pot venir de l'alimentació, del cable, del controlador de pantalla, del programari gràfic o de dues instàncies que es disputen el mateix bus.

### 3.1.3 El flux d'un torn

Un torn comença quan la persona parla i acaba quan Parker respon. Entremig passen etapes que no es veuen, però que expliquen la latència:

1. **Detecció de veu.** El sistema distingeix parla de soroll i obre un buffer. Es guarden uns 0,3 s previs per no perdre la primera síl·laba.
2. **Transcripció.** L'àudio es converteix en text, en local o al núvol.
3. **Ordres directes.** Algunes frases no necessiten un model: «baixa el volum», «posa una alarma» o «para». Si encaixen en un patró conegut, s'executen de seguida.
4. **Memòria.** Es busquen els records més rellevants i les dades exactes que poden ajudar a respondre.
5. **Prompt.** La identitat estable, l'estat d'ànim, la data, els records i l'historial recent es combinen en una instrucció.
6. **Cervell.** El model genera text en streaming: la primera frase pot començar a sonar mentre la resta encara s'està escrivint.
7. **Veu.** La primera frase es sintetitza; les següents s'encuen perquè no es trepitgin.
8. **Cara.** L'emoció de la resposta mou la boca, els ulls i les celles.
9. **Escriptura de memòria.** Es desa **només** el missatge de la persona, no la resposta del model. Això evita que Parker es recordi a si mateix com si fos l'usuari.

L'ordre no és casual. La memòria va abans del cervell perquè el model necessita el context; la veu pot començar abans que el model acabi perquè l'usuari no ha d'esperar tota la resposta; la cara no ha de bloquejar el fil d'àudio. Aquesta és la diferència entre un sistema que **sembla** ràpid i un sistema que **és** capaç de respondre mentre encara treballa.

### 3.1.4 El maquinari com a part del disseny

Parker no és un programa que després s'executa en un ordinador qualsevol. El maquinari és una part del disseny: decideix què es pot fer, quant triga i què falla quan el sistema es queda sense recursos. La placa, la pantalla, el micròfon, l'altaveu i l'alimentació no són accessoris; són les condicions materials del prototip.

Per això el projecte no va començar triant un component, sinó una matriu de requisits: 8 GB de RAM, arquitectura ARM64 amb Linux, GPIO i SPI, USB, alimentació de 5 V i un cost contingut. El compliment d'aquests requisits és el que es desenvolupa a l'apartat 3.2.

### 3.1.5 El pressupost: disseny i cost real

El pressupost del projecte no és una sola xifra. El full de disseny preveia **275,52 €**, amb una Raspberry Pi 5 com a base. El prototip final, amb Orange Pi 5 Pro, pantalla, targeta, caixa i accessoris, va costar **312,91 €**. La diferència és de **37,39 €**.

| Concepte | Pressupost de disseny | Cost real del prototip |
|---|---:|---:|
| Placa | Raspberry Pi 5 de 8 GB | Orange Pi 5 Pro de 8 GB |
| Pantalla | GC9A01 | GC9A01 |
| Emmagatzematge | microSD | microSD |
| Alimentació, àudio i cables | Inclosos | Inclosos |
| Caixa i suport | Parcials | Parcials |
| **Total** | **275,52 €** | **312,91 €** |

No és un sobrecost descontrolat: és el resultat de canviar la placa per una que complia millor els requisits i de comprar components que el disseny inicial no detallava. Al tribunal cal explicar-ho com una **decisió de disseny**, no com un error de càlcul. El que sí que és cert és que el projecte no va complir el sostre de 300 € del maquinari: el cost real el supera en 12,91 €. Aquesta és una limitació que s'ha de dir.


## 3.2 El maquinari: components, límits i verificació

> Aquest apartat explica el maquinari com una part del resultat, no com una llista de peces. No indica com cablejar-lo: explica per què cada element hi és, quina funció compleix i quins límits imposa al sistema.

### 3.2.1 Què havia de resoldre el maquinari

El maquinari havia de suportar cinc coses alhora: un model de llenguatge local, una transcripció de veu, una base de memòria, una interfície gràfica i una sortida d'àudio. Això descartava les plaques amb poca RAM i els ordinadors sense pins de connexió. També havia de poder estar encesa molta estona, dins d'una caixa petita i amb un consum raonable.

La llista de requisits era, doncs, una llista de decisions:

| Requisit | Per què condiciona el disseny |
|---|---|
| **8 GB de RAM** | El model local, la transcripció, la memòria i la interfície han de conviure sense fer swap |
| **ARM64 i Linux** | Permet executar les eines de veu, memòria i visió per ordinador que usa el projecte |
| **GPIO i SPI** | La pantalla circular no es connecta per HDMI; necessita un bus de baix nivell |
| **USB** | El micròfon i l'altaveu es poden canviar sense soldar res |
| **5 V i consum baix** | El dispositiu ha de poder estar engegat tota la tarda |
| **Cost contingut** | El pressupost de maquinari no havia de superar els 300 € |

Aquests requisits no són una preferència estètica. Si la placa no té prou RAM, el model local no cap; si no té SPI, la pantalla no es pot pintar sense HDMI; si no té USB, l'àudio queda lligat a un còdec intern que pot fallar. El maquinari és, per tant, el primer filtre del disseny.

### 3.2.2 La placa: per què una Orange Pi 5 Pro

La placa escollida és una **Orange Pi 5 Pro de 8 GB**, amb un processador RK3588S de vuit nuclis, arquitectura ARM64 i una NPU de 6 TOPS. La NPU no es va fer servir per al model principal, però formava part de la decisió per si més endavant es volia provar una acceleració específica.

| Candidata           |      RAM | GPIO/SPI | NPU    | Veredicte                                     |
| ------------------- | -------: | -------- | ------ | --------------------------------------------- |
| **Orange Pi 5 Pro** |     8 GB | Sí       | 6 TOPS | **Escollida**                                 |
| Raspberry Pi 5      |     8 GB | Sí       | No     | Alternativa inicial; menys nuclis i sense NPU |
| Radxa Rock 5B       |     8 GB | Sí       | 6 TOPS | Bona, però més cara i menys disponible        |
| Mini PC N100        |  8-16 GB | No       | No     | Descartat: sense pins i més consum            |
| Portàtil vell       | Variable | No       | No     | Descartat: no és encastable                   |

L'Orange Pi complia els sis requisits i oferia més nuclis i NPU que la Raspberry Pi prevista. **No es va triar per una prova de velocitat**: no s'ha mesurat la mateixa feina a totes les plaques. És una decisió per requisits, disponibilitat i preu, no una afirmació que sigui «la més ràpida». Aquesta distinció és important perquè el tribunal no pregunti per un benchmark que no existeix.

La Raspberry Pi 5 també hauria complert els requisits tècnics i té més comunitat. Es va descartar pel preu final i perquè l'Orange Pi oferia més nuclis i NPU en el moment de la compra. És una decisió de disseny, no un resultat experimental.

### 3.2.3 La pantalla: per què una GC9A01

La pantalla és una **GC9A01 d'1,28 polzades**, de 240×240 píxels, circular i amb interfície SPI. No és un monitor: és la cara del dispositiu. Aquesta diferència explica per què no es va triar una pantalla HDMI gran ni una OLED petita.

| Pantalla | Mida i resolució | Interfície | Per què no |
|---|---|---|---|
| **GC9A01** | 240×240, circular | SPI | **Escollida** |
| HDMI de 5" | 800×480, rectangular | HDMI i USB | Necessita controlador de vídeo i escriptori; massa gran |
| OLED de 0,96" | 128×64, rectangular | I2C | Massa petita i lenta per a una cara |
| TFT SPI de 2,8" | 320×240, rectangular | SPI | Rectangular, més pins i més consum |

La GC9A01 treballa a 3,3 V i s'alimenta per SPI. Això permet pintar-la **sense HDMI ni escriptori**: la placa renderitza la cara en memòria i envia els píxels pel bus. La contrapartida és que la inicialització és delicada i que el bus limita el refresc.

El fotograma té **240 × 240 × 2 = 115.200 bytes**. Amb el bus a 24 MHz, el temps teòric és d'uns 38 ms per fotograma, però el render, la CPU i el controlador fan que la mesura real sigui d'uns **16,4 fps**. La configuració es va deixar a **15 fps** per tenir marge i evitar cues. No és una pantalla de vídeo: és una cara, i la regularitat importa més que la velocitat màxima.

La inicialització es fa a **1 MHz** perquè és la part més fràgil: són escriptures molt curtes amb canvis de comanda i dades. Els fotogrames grans van a **24 MHz**. Aquesta diferència no és un caprici: primer cal assegurar que el controlador està configurat; després es pot augmentar la velocitat.

### 3.2.4 Arquitectura física i interfícies

La placa és el centre del sistema, però no ho fa tot. Cada component té una funció i una interfície diferent:

| Component              | Funció                                          | Interfície | Per què                                 |
| ---------------------- | ----------------------------------------------- | ---------- | --------------------------------------- |
| **Orange Pi 5 Pro**    | Executa el sistema i coordina les capes         | —          | És l'única peça que ho pot fer tot      |
| **GC9A01**             | Mostra la cara                                  | SPI i GPIO | Circular, petita i sense HDMI           |
| **Micròfon USB**       | Escolta la persona                              | USB        | Es pot canviar i no necessita soldadura |
| **Altaveu**            | Reprodueix la veu                               | Jack o USB | Mateixa lògica que el micròfon          |
| **microSD**            | Guarda el sistema, els models i els records     | —          | És l'emmagatzematge permanent           |
| **Font de 5 V / 3 A**  | Alimenta la placa i els perifèrics              | USB-C      | Ha de mantenir el voltatge sota càrrega |
| **Dissipador i caixa** | Controlen la temperatura i subjecten el conjunt | —          | La calor limita el rendiment            |

La pantalla no va connectada a HDMI: va al connector de pins de la placa. Això és el que permet un robot petit, sense monitor, amb la cara com a única sortida visual. El micròfon i l'altaveu van per USB o jack perquè el processador ja té controladors d'àudio i perquè es poden substituir sense tocar la placa.

La microSD és còmoda, però també és el punt feble: és més lenta que un disc sòlid i s'ha de cuidar. Els models, la memòria i les còpies no han de dependre d'escriure-hi constantment. Per això les còpies de seguretat es guarden al PC, no a la targeta del dispositiu.

### 3.2.5 Alimentació, àudio i calor

L'alimentació és la primera capa que cal assegurar. La placa necessita **5 V i 3 A**. Si la font és feble, la pantalla pot parpellejar, l'àudio pot cruixir, el USB pot desconnectar-se o la placa pot reiniciar-se sense avisar. No és un error de codi: és una condició física.

El micròfon USB té una altra limitació: pot trigar uns **29 s** a aparèixer després d'encendre. Si el programa obre l'àudio abans, es queda amb el dispositiu intern equivocat i pot donar silenci absolut. Per això el sistema espera, refresca la llista de dispositius i fa sonar un **xim** quan l'oïda està llesta. El xim no és decoració: és la interfície que diu «ja pots parlar».

La calor també forma part del maquinari. El RK3588S pot arribar a uns **75 °C** i, quan ho fa, baixa la freqüència per protegir-se. Llavors el model local va més lent, la cara pot perdre fotogrames i sembla que «Parker s'hagi tornat lent». La resposta és un dissipador, ventilació i no fer servir el model local més gran quan no cal.

La caixa és **parcial**. No hi ha un disseny CAD final ni una prova d'usuari de la forma. El prototip funciona, però no està acabat com a producte: la caixa ha de deixar entrar aire, subjectar la pantalla sense forçar el connector, protegir la targeta i no tapar l'antena. Aquesta és una limitació honesta del treball.

### 3.2.6 Què va fallar al maquinari

| Símptoma                                 | Causa física                              | Aprenentatge                                                         |
| ---------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------- |
| Pantalla blanca amb retroil·luminació    | Inicialització del controlador incompleta | Un bus que respon no és un dispositiu configurat                     |
| Pantalla negra després de moure un cable | Senyal de dades enviat a una entrada      | Una entrada no es converteix en sortida perquè el connector hi entri |
| Micròfon que no apareix                  | Enumeració USB tardana                    | El programari pot ser més ràpid que el maquinari                     |
| Pantalla que parpelleja amb el so        | Font insuficient o cable massa prim       | L'alimentació és la primera cosa a comprovar                         |
| Tot més lent després d'una estona        | El processador baixa freqüència per calor | El rendiment també és una qüestió tèrmica                            |
| Cara congelada                           | Dues instàncies competint pel bus         | Cal una sola instància i un llançador que ho garanteixi              |

La lliçó del bloc de maquinari és que **el hardware no és una capa passiva**. Una decisió de placa canvia la latència; una pantalla mal inicialitzada sembla un error de programari; un micròfon que arriba tard sembla un error de model. Separar les capes és el que permet diagnosticar sense endevinar.

### 3.2.7 Criteris de verificació del maquinari

| Bloc | Evidència que es va acceptar |
|---|---|
| Energia | La placa es manté estable amb la font de 5 V i 3 A |
| Arrencada | La placa arriba a l'aplicació sense monitor |
| Pantalla | Es veuen colors i la cara, no només retroil·luminació |
| Àudio | El micròfon transcriu i l'altaveu reprodueix |
| Temperatura | Després de 20 minuts, el sistema no entra en throttling |
| Caixa | La pantalla no rep pressió i l'antena queda lliure |

Aquests criteris no són un manual de muntatge: són les proves que permeten afirmar que el maquinari acompanya el relat del capítol. Si una d'aquestes evidències falla, el resultat corresponent s'ha de presentar com a limitació, no com a èxit.
---

## 3.3 Primera iteració: del paper al prototip

### 3.3.1 Una versió per validar el flux

La primera versió no tenia la placa ni la cara. Era una prova de concepte en un ordinador: una finestra, un micròfon, una tecla per començar i acabar el torn i un model al núvol. L'objectiu no era impressionar, sinó comprovar que la cadena **veu → text → resposta → veu** es podia tancar sense que l'usuari hagués de tocar el teclat.

Aquesta versió va ensenyar tres coses:

- La transcripció i la generació es podien encadenar, però la latència era massa alta per a una conversa.
- El model responia bé quan la pregunta era clara, però no recordava res entre torns.
- La veu sintètica era el millor senyal per saber si el sistema havia acabat o s'havia penjat.

La primera iteració no es conserva com a producte; es conserva com a **evidència del problema**. Sense aquesta prova no s'hauria sabut que el coll d'ampolla no era la interfície, sinó la suma de transcripció, generació i síntesi.

### 3.3.2 Què va fallar

| Símptoma | Causa | Aprenentatge |
|---|---|---|
| La resposta arribava tard | Model local gran i transcripció lenta | Calia separar les etapes i mesurar-les |
| Parker oblidava el nom | No hi havia memòria entre sessions | La memòria és una part del sistema, no un extra |
| La veu sonava tallada | Se sintetitzava tota la resposta abans de reproduir-la | Calia començar per frases i fer streaming |
| L'usuari no sabia si escoltava | No hi havia cap indicador visual | La cara havia de comunicar estat |
| El torn no s'acabava mai | El tall de silenci era massa llarg | Calia un VAD i un temps màxim |

La lliçó principal va ser que **un prototip no es pot avaluar si no se sap quina etapa falla**. A partir d'aquí, cada iteració va incorporar una mesura i una prova, no només una funcionalitat.

---

## 3.4 Segona iteració: la placa i la latència

### 3.4.1 El coll d'ampolla no era el model

Quan el sistema es va passar a la placa, la conversa encara trigava **15-20 s** a començar a sonar. La temptació era canviar de model. La mesura va demostrar que el model era només una part del problema: hi havia transcripció lenta, un tall de silenci massa llarg, un prompt massa gran i una síntesi que esperava la resposta completa.

La primera optimització no va ser canviar el model, sinó **treure de la placa la part que la placa feia pitjor**. Es va reduir el tall de silenci, es va fer servir un model de transcripció més àgil, es va retallar el prompt i es va començar a parlar per frases. El resultat va baixar a **4,2-4,7 s**; encara no era suficient, però ja era una conversa possible.

### 3.4.2 Mesures per etapa

| Etapa                   | Abans (17/10) |                 Després (ruta híbrida) | Per què canvia                       |
| ----------------------- | ------------: | -------------------------------------: | ------------------------------------ |
| Tall de silenci         |         1,3 s |                              **0,6 s** | Menys espera sense tallar la paraula |
| Transcripció            |     4,8-5,3 s | **1,6-1,8 s** local / **0,68 s** núvol | Model i maquinari                    |
| Memòria                 |   0,15-0,18 s |                            **~0,15 s** | No era el coll                       |
| Primer token            |     6,5-7,8 s |                          **0,9-1,9 s** | Model, prompt i caché                |
| Primera frase           |       7,5-9 s |                          **1,3-2,1 s** | Resposta més curta                   |
| Veu de la primera frase |     0,7-1,4 s |                          **0,5-0,9 s** | Frase més curta                      |
| **Fins que sona**       |   **15-20 s** |                             **~1,6 s** | Totes les etapes                     |

La lectura honesta és que el pipeline complet va baixar un ordre de magnitud, però no perquè el model local s'hagués tornat màgic. És perquè **la part lenta ja no s'executava a la placa**. El mode local continua existint i continua trigant; la diferència és que ja no és l'única opció.

### 3.4.3 La pantalla: un bus que respon no és un dispositiu configurat

La GC9A01 va donar un dels errors més instructius del projecte. La retroil·luminació s'encenia, el bus SPI existia i les escriptures no donaven error, però la pantalla quedava blanca. La conclusió fàcil hauria estat «el cablejat està malament». No ho era.

La seqüència de proves va separar les capes:

- Un primer test va demostrar que els píxels es podien controlar: la pantalla parpellejava en blanc i negre.
- Un segon test va demostrar que els colors no es distingien: el panell acceptava dades, però la configuració de color era incorrecta.
- La causa era una **inicialització incompleta**: faltaven registres extendits, taules de gamma, la inversió i l'ordre de color correcte.
- La solució no va ser canviar el cable, sinó completar la configuració i validar-la amb un patró de colors abans de provar la cara.

La lliçó és que **un bus que respon no vol dir que el dispositiu estigui configurat**. En un sistema encastat, «no hi ha maquinari» i «el maquinari hi és però no està inicialitzat» es veuen igual des de fora. Cal una prova que separi fitxer, permisos, escriptura, controlador i píxel.

La pantalla va acabar funcionant a **16,4 fps** reals, amb fotogrames de **115.200 bytes** i una inicialització lenta a **1 MHz**; els fotogrames grans van a **24 MHz**. La configuració es va deixar a **15 fps** per tenir marge i evitar cues. No és una pantalla de vídeo: és una cara, i la regularitat importa més que la velocitat màxima.

### 3.4.4 Què va fallar

| Símptoma                                 | Capa         | Causa                                     | Resposta                                                             |
| ---------------------------------------- | ------------ | ----------------------------------------- | -------------------------------------------------------------------- |
| Pantalla blanca amb retroil·luminació    | Controlador  | Inicialització incompleta                 | Completar gamma, inversió i ordre de color                           |
| Pantalla negra després de moure un cable | Cablejat     | Senyal de dades enviat a una entrada      | Tornar el senyal al seu lloc; una entrada no és una sortida          |
| Micròfon que no apareixia                | Sistema      | El USB pot trigar uns 29 s a enumerar-se  | Esperar, refrescar la llista i avisar amb un xim                     |
| Tot més lent després d'una estona        | Maquinari    | El processador baixa frequència per calor | Dissipador, ventilació i no carregar el model local sense necessitat |
| Cara congelada                           | Concurrència | Dues instàncies competint pel mateix bus  | Una sola instància i un llançador que ho garanteixi                  |

---

## 3.5 Tercera iteració: el doble cervell

### 3.5.1 Per què el local no n'hi havia prou

Amb el model local de 3.000 milions de paràmetres, la placa va donar **8,75 s de TTFT** de mediana i **13,45 s de torn**. Amb aquesta latència no es pot mantenir una conversa: l'usuari ja ha canviat de tema quan Parker comença a respondre. El model d'1.500 milions era més ràpid, però incoherent; el de 2.000 milions actual és una mica més lent que el d'1.500 i molt més útil, però encara no és un company fluid.

La conclusió no va ser «el local no serveix», sinó **«el local no pot ser el titular en aquesta placa»**. Aquesta diferència és la que va portar al disseny híbrid.

|                | Núvol                      | Local                           |
| -------------- | -------------------------- | ------------------------------- |
| Motor          | Servei extern              | Ollama a la placa               |
| Model actual   | Qwen 3.8 de 27.000 milions | Qwen 3.5 local de 2.000 milions |
| Latència       | ~0,5-1,2 s de TTFT         | ~5,5 s de torn                  |
| Qualitat       | Més lúcida                 | Més fluixa; pot inventar        |
| Privacitat     | El text surt de la placa   | Tot queda a la placa            |
| Disponibilitat | Necessita xarxa i clau     | Sempre                          |

El disseny actual és:

- El **núvol redacta** perquè la placa no pot generar amb prou latència.
- El **local escolta, transcriu, recorda, parla i dona la cara**.
- Si el núvol falla, el local respon; Parker avisa una vegada i continua.
- Quan torna la xarxa, el sistema pot tornar al núvol segons el mode triat.

### 3.5.2 La caiguda no és nominal

Un sistema híbrid que només funciona quan el servei extern va bé no és híbrid: és un sistema vulnerable amb un pla B de paper. Per això es va provar la caiguda de manera deliberada, amb el servei tallat i amb un error de límit de peticions.

El resultat va ser que el local responia, però trigava uns **5,5 s** i la qualitat baixava. Parker avisava una vegada i continuava; no es quedava mut. Aquesta és la diferència entre una demo i un prototip: la demo ensenya el millor torn; el prototip ha de sobreviure al pitjor.

### 3.5.3 Privacitat: el que surt i el que no

El mode híbrid envia text i, segons la configuració, àudio a un servei extern. No és un sistema 100 % local per defecte. Això s'ha de dir sense embuts:

- La **veu** pot sortir de la placa si la transcripció es fa al núvol.
- El **text** de la conversa surt si el cervell és al núvol.
- La **memòria**, la cara, l'agenda i l'estat queden a la placa.
- Hi ha un **mode local** que ho manté tot a la placa, però és més lent i menys precís.

La privacitat no és un interruptor binari: és un compromís. El projecte no promet privacitat total per defecte; promet que l'usuari pot triar el mode i que el sistema ha de funcionar quan tria el local.

### 3.5.4 Què va fallar

| Símptoma                           | Causa                                          | Resposta                                                        |
| ---------------------------------- | ---------------------------------------------- | --------------------------------------------------------------- |
| El núvol retorna un error de límit | El servei limita les peticions                 | Resposta local, avís únic i reintent més tard                   |
| El model local inventa un detall   | Model petit i memòria poc concloent            | Núvol com a primari; dir «no ho sé» quan no hi ha prova         |
| Pics de 24 s                       | El preescalfament competia amb la transcripció | Precalentar quan es detecta veu, no quan s'acaba de transcriure |
| El model desapareix del servei     | El proveïdor canvia la llista                  | Triar un model alternatiu i tornar al local si cal              |
| La resposta sona amb noms tècnics  | El prompt conté noms de motors                 | Treure els noms del text que es llegeix                         |

---

## 3.6 Quarta iteració: memòria, oïda i veu

### 3.6.1 La memòria no és una base de dades exacta

Parker converteix cada missatge de l'usuari en un **embedding**: un vector de 384 números que representa el significat del text. Dos textos que parlen del mateix tema queden a prop encara que no comparteixin paraules. Aquesta és la base de la memòria de tema.

El funcionament és senzill d'explicar:

1. La persona diu una frase.
2. La frase es converteix en vector.
3. Es busquen els tres records més propers.
4. Els records s'afegeixen al prompt.
5. El model respon amb aquest context.

No és una base de dades exacta: és una **memòria de tema**. Si la pregunta és molt curta o el record és un detall aïllat, pot no recuperar-lo. Aquesta diferència és la que més vegades es confon en parlar d'intel·ligència artificial.

Després de **205 converses**, la memòria real tenia **52 records**, aproximadament **0,25 per conversa**. Amb aquest ritme, arribar a 1.000 records seria qüestió d'anys. Per això les proves d'escala es van fer amb bases temporals, no amb la memòria de l'usuari.

### 3.6.2 El que es va mesurar

| Nombre de records | Tema correcte | Comentari                                      |
| ----------------: | ------------: | ---------------------------------------------- |
|               200 |          85 % | La base petita encara és sorollosa             |
|             1.000 |         100 % | El millor resultat de la sèrie                 |
|             3.000 |          95 % | Més records també aporten més candidats falsos |

La consulta es manté al voltant de **150 ms** i no creix de manera apreciable amb la mida. Això no vol dir que la qualitat sigui perfecta: vol dir que l'operació és eficient.

El resultat que més importa explicar és el de les **vuit preguntes curtes sobre dotze fets distintius**. Quatre no es van recuperar:

| Pregunta                                 | Similitud | Entra?                           |
| ---------------------------------------- | --------: | -------------------------------- |
| «¿qué lleva mi café?»                    |     0,874 | Sí                               |
| «¿cómo se llama mi dentista?»            |     0,762 | Sí                               |
| «¿a qué soy alérgico?»                   |     0,744 | Sí                               |
| «¿con qué instrumento ensaya mi vecino?» |     0,718 | Per poc                          |
| «¿cómo se llama mi perro?»               |     0,459 | No                               |
| «¿dónde veraneo?»                        |    <0,459 | No                               |
| «¿qué estudié?»                          |     0,406 | No, tot i ser el primer candidat |
| «¿cómo se llama mi hermano?»             |     0,459 | No                               |

**Quatre de vuit fets guardats no es recuperen.** No és un error de Chroma ni de la base: és el límit d'un embedding petit amb frases de conversa i preguntes de tres paraules. Per això el projecte parla de **memòria de tema**, no de memòria de dades exactes, i per això ha afegit una taula de fets i un índex de text complet com a complement. La memòria de tema serveix per seguir una conversa; la memòria de detall necessita una altra eina.

Les preguntes es van formular en castellà perquè és la llengua amb què es va configurar el model i es van recollir els registres. El que s'avalua és la recuperació, no la llengua.

### 3.6.3 La veu: dos motors amb papers diferents

La veu també es va dissenyar amb un primari i una reserva:

| Motor    | Veu                      |                    Latència | Quan entra           |
| -------- | ------------------------ | --------------------------: | -------------------- |
| Edge TTS | Veu neuronal en castellà | 1,8-2,3 s per frase de ~8 s | Principal, amb xarxa |
| Piper    | Veu local                |        **0,36 s** per frase | Reserva local        |

Edge sembla més lent, però sintetitza la frase següent **mentre sona** l'actual. En una resposta de dues o tres frases només es paga sencera la primera. Si Edge falla o triga més de 8 s, Piper entra sol; Edge es reintenta més tard. Aquesta és la mateixa lògica del doble cervell: **la qualitat no ha d'impedir que el sistema continuï**.

### 3.6.4 Què va fallar

| Símptoma | Causa | Resposta |
|---|---|---|
| Parker «oblidava» en català o castellà | Embedding gairebé monolingüe | Model multilingüe |
| No trobava el tema amb altres paraules | Llindar massa alt | Baixar el llindar i combinar cerca vectorial i textual |
| Es diluïa el significat | Es vectoritzava el torn sencer | Vectoritzar només el missatge de l'usuari |
| Quatre fets no es recuperaven | Embedding petit i preguntes curtes | Fets exactes i índex textual; no prometre-ho tot |
| El local deia «piano» per «trompeta» | Model petit | Núvol primari; dir «no ho sé» quan no hi ha prova |
| La veu llegia etiquetes | El marcatge arribava al sintetitzador | Filtrar abans de la veu i de l'historial |
| La segona frase quedava en silenci | El dispositiu d'àudio estava ocupat | Reintents i una cua de veu ordenada |

---

## 3.7 Cinquena iteració: cara, personalitat i dia a dia

### 3.7.1 La cara com a interfície

La cara va passar per quatre etapes: imatges fixes de BMO, una pàgina web amb ulls i boca separats, formes vectorials i, finalment, una escena animada amb motor de vida. La versió actual no és una imatge que canvia: és una **escena vectorial** que respira, parpelleja, mira i reacciona.

El que la fa viva:

- **Els dotze principis de l'animació de Disney** com a vocabulari de moviment: anticipació, estirament i compressió, posada en escena, acció directa i posa a posa, continuïtat i superposició, entrades i sortides suaus, arcs, acció secundària, ritme, exageració, dibuix sòlid i atractiu. El motor no els executa tots a cada gest: tria els que ajuden a fer llegible l'estat de la cara.
- **Respiració i flotació** contínues, amb sinusoides superposades.
- **Parpelleig asíncron** cada 2-5 s, amb doble parpelleig i petites variacions.
- **Director de gestos**: microllera, curiositat, mirar amunt, cabotada, sospir, estirament, badall, doble presa, somriure, assentir i negar.
- **Tres famílies segons el silenci**: despert, sol i avorrit.
- **Sincronització de la boca** amb l'àudio, a 110 ms.
- **Intro de 4,5 s**: desperta, mira als costats, badalla i mira al davant.

La cara té **vuit expressions** (neutral, feliç, trista, sorpresa, pensant, confós, escoltant i afecte) i **onze gestos**. El mode de demostració fa una passada de **38,1 s** amb tot el repertori. És una eina per ensenyar el treball, no una funció de la conversa normal.

La cara no és decoració: és el que fa que l'usuari sàpiga **quan** Parker escolta, pensa o parla sense mirar una pantalla de text. També fa que una espera d'1,6 s no sembli un bloqueig: la cara respira, parpelleja i mira.

### 3.7.2 Personalitat: el to i la iniciativa

La personalitat no és el cervell que tria les paraules ni la cara que les expressa. És la capa que decideix **com parla, com es troba i quan pren la iniciativa**. La identitat, els gustos, les manies i les muletilles són dades, no codi.

- **Ànim:** tres números (energia, curiositat i afecte) que pugen amb la conversa i baixen amb el silenci.
- **Víncle:** creix amb dies i converses; no es mostra com un percentatge.
- **Iniciativa:** cada 15 minuts de silenci, el sistema tria entre contar una cosa, preguntar, proposar, fer un eco o callar. Si l'usuari contesta, aquella opció guanya; si l'ignora, perd.
- **Frase espontània:** surt d'una entrada concreta de la fitxa, d'una hora, d'una proposta o de l'últim missatge. No és una ordre oberta al model.
- **Meta-preguntes:** «què has dit?» es respon sense model, amb la frase i el motiu real, també després d'un reinici.

Aquesta capa és la que converteix una resposta correcta en una resposta **amb to**. Un assistent pot dir «no ho sé»; Parker ha de dir-ho de manera que no talli la conversa.

### 3.7.3 Agenda, notes, rutines i música

Les ordres directes van primer per una raó de disseny: «baixa el volum» no necessita un model. Si passa pel model, pot arribar tard, inventar-se el valor o barrejar-se amb la música. Per això les accions deterministes es resolen abans de la conversa.

El sistema fa:

- **Alarmes** a una hora concreta, amb campana i frase.
- **Temporitzadors**, per exemple «d'aquí a deu minuts».
- **Cites** amb data, hora i un titular curt; es poden reprogramar.
- **Rutines** com «bona nit», «bon dia», «calla deu minuts» o «apaga't».
- **Apunts**, llistes i comptadors.
- **Temps** amb Open-Meteo, sense clau.
- **Música** amb Deezer i fragments de 30 s; a la configuració actual està desactivada mentre s'estabilitza l'àudio.

### 3.7.4 Què va fallar

| Símptoma | Causa | Resposta |
|---|---|---|
| La cara es congelava | Dues instàncies o massa fotogrames | Una sola instància i 15 fps |
| Els ulls s'allargaven | El motor acumulava desplaçament | Tornar a la pose base i limitar el moviment |
| «231 xerrades» | Un comptador antic viatjava al prompt | Comptar converses, no torns, i treure el número del text |
| Parker deia «Piper» | El nom del motor era al prompt | Treure el nom i sanejar el vocatiu |
| Una alarma es deia «pose una» | El soroll inicial no cobria aquella variant | Ampliar el reconeixement i afegir una prova |
| La demo no sortia | L'ordre no encaixava | Reconèixer la frase i provar-la per veu |
| La cara no responia durant la demo | La demo bloquejava les expressions normals | Limitar la demo i documentar-ho com a limitació |

---

## 3.8 Estabilització i proves

### 3.8.1 Una sola instància

Dues còpies del programa semblen un error de programari, però són una **condició d'execució**: les dues volen el mateix micròfon, el mateix bus de pantalla i els mateixos pins. El resultat és una cara congelada, un micròfon mut i un registre ple d'errors de dispositiu ocupat.

La solució no és filtrar el símptoma, sinó **no arrencar una segona instància**. El llançador té un bloqueig i comprova que no hi hagi cap procés anterior. Aquesta és una lliçó de disseny: alguns errors que semblen del codi són, en realitat, condicions del sistema.

### 3.8.2 L'arrencada també és part de la interfície

El micròfon USB pot trigar uns **29 s** a aparèixer després d'encendre. Si el programa obre l'àudio abans, es queda amb el dispositiu intern equivocat i pot donar silenci absolut. Per això el sistema espera, refresca la llista de dispositius i fa sonar un **xim de dues notes** quan l'oïda està llesta.

El xim no és decoració: és la interfície que diu «ja pots parlar». Sense ell, l'usuari no sap si Parker està engegat, si el micròfon ha arribat o si el programa s'ha penjat. Aquesta és una de les decisions més petites i més útils del projecte.

### 3.8.3 Proves

El projecte té **24 fitxers de prova**. No tots es poden executar en qualsevol màquina: alguns necessiten la placa, la pantalla o el micròfon; d'altres es poden fer en un ordinador sense maquinari.

| Àrea                | Què es prova                                  | Resultat                             |
| ------------------- | --------------------------------------------- | ------------------------------------ |
| Cervell doble       | Caiguda al local, model alternatiu, streaming | 14/14                                |
| Agenda              | Alarmes, cites, reprogramació                 | 10/10                                |
| Personalitat        | Ànim, víncle, iniciativa                      | 18 blocs en verd                     |
| Accions             | Ordres directes sense model                   | 10/10                                |
| Animació            | Expressions, gestos i demo                    | 8 expressions + 11 gestos            |
| Pipeline i conversa | Flux complet i etiquetes                      | En verd                              |
| Total               | 24 fitxers                                    | Cobertura de les funcions principals |

No és correcte dir «tots els tests passen» sense matisar: alguns depenen de maquinari i s'executen a la placa; d'altres són simulacions al PC. El que sí que és cert és que **cada arreglo important té un cas nou** que el protegeix. Això converteix un error en coneixement.

### 3.8.4 Què va fallar

| Símptoma | Causa | Resposta |
|---|---|---|
| El sistema es quedava sord | Un bloqueig no s'alliberava després d'un error | Alliberar sempre i provar el camí d'error |
| L'agenda es corrompia | Escriptura no atòmica | Càrrega robusta i còpia de seguretat |
| La versió del PC i la de la placa no coincidien | S'havia copiat una part del projecte | Comprovar versió i empremta a l'arrencada |
| Un canvi arreglava una cosa i en trencava una altra | No hi havia prova de regressió | Afegir un cas per cada arreglo |
| El registre es perdia en reiniciar | Es reiniciava abans de copiar-lo | Llegir i desar l'evidència abans de reiniciar |

---

## 3.9 Resultats

### 3.9.1 Latència

| Data               | Configuració                                      |     Temps fins que sona |
| ------------------ | ------------------------------------------------- | ----------------------: |
| 17/10, abans       | Transcripció small, model local de 3B i veu Piper |             **15-20 s** |
| 17/10, després     | Transcripció base, model d'1,5B i prompt retallat |           **4,2-4,7 s** |
| 24-25/10           | Model de 3B, núvol i transcripció al núvol        |              **~1,6 s** |
| 30/10, PC          | gpt-oss-20b                                       | **0,51-0,56 s** de TTFT |
| 30/10, placa local | Qwen 2.5 de 3B                                    |         **5,78-5,90 s** |

La ruta completa va arribar a un **TTFT de 1,23 s de mediana** i un inici de resposta de **1,29 s**. Aquesta segona xifra mesura l'inici de la resposta, no la durada de tota la locució. La diferència entre 15-20 s i 1,6 s és el resultat principal del treball, però no s'ha d'atribuir al model: és el resultat de **treure la part lenta de la placa** i de retallar cada etapa.

### 3.9.2 Memòria i qualitat

| Mètrica                                       | Resultat                               |
| --------------------------------------------- | -------------------------------------- |
| Tema correcte amb 200 / 1.000 / 3.000 records | 85 % / 100 % / 95 %                    |
| Consulta de mediana                           | ~150 ms, sense créixer amb la base     |
| Detall exacte en preguntes curtes             | **4 de 8 fallades**                    |
| Contaminació de records amb el núvol          | 0                                      |
| «No ho sé» quan no hi ha record, al núvol     | 3/3                                    |
| Al·lucinació local quan falla el núvol        | Sí, per exemple «piano» per «trompeta» |

La memòria és útil per seguir una conversa, però no és una agenda de dades exactes. Aquesta és la conclusió parcial més important del capítol.

### 3.9.3 STT, veu i cara

- La transcripció al núvol va donar **0,68 s**; la local, **1,6-2,0 s**.
- La veu d'Edge va trigar **1,8-2,3 s** per frase, però es va solapar amb la síntesi següent; Piper va trigar **0,36 s** i va quedar com a reserva.
- La cara va funcionar a **16,4 fps** reals, amb **15 fps** configurats.
- La demo completa va durar **38,1 s** i va mostrar **8 expressions i 11 gestos**.

### 3.9.4 Què no s'ha aconseguit

| Objectiu                            | Estat       | Per què                                                  |
| ----------------------------------- | ----------- | -------------------------------------------------------- |
| Cervell local ràpid i lúcid         | **No**      | 8,75 s de TTFT al model de 3B; el de 2B és reserva       |
| Memòria de dades exactes            | **Parcial** | Recupera el tema, però falla 4 de 8 preguntes curtes     |
| Privacitat total per defecte        | **No**      | El mode híbrid envia text i, segons el mode, àudio       |
| LoRA de personalitat entrenat       | **No**      | Està dissenyat, però no entrenat ni avaluat              |
| Estudi d'usuaris                    | **No**      | La mostra és el propi autor                              |
| Carcassa i refrigeració definitives | **Parcial** | Hi ha proves d'encastat, però la calor continua limitant |

Aquesta taula és la que dona credibilitat a la resta: **el treball no ven el que no té**.

---

## 3.10 Discussió

### 3.10.1 Què volen dir els números

El resultat de latència no diu que el prototip sigui més ràpid que un assistent comercial. Diu que, **en aquesta placa, amb aquesta arquitectura i aquest prompt**, el temps fins a la primera paraula va baixar de 15-20 s a aproximadament 1,6 s. La comparació és abans-després, no amb un producte del mercat.

La memòria no diu que Parker «recordi com una persona». Diu que recupera el tema en la majoria de casos i que falla en dades exactes quan la pregunta és molt curta. Aquesta és una conclusió més petita i més honesta que «té memòria perfecta».

La cara no és una prova de qualitat conversacional. És una prova que la interfície pot comunicar estat i reduir la sensació d'espera. Per mesurar si això ajuda de veritat caldria un estudi d'usuaris que el projecte no ha fet.

### 3.10.2 Comparació amb l'estat de l'art

El projecte no competeix amb un assistent comercial en qualitat de llenguatge ni en nombre de funcions. Competeix en **integritat del sistema**: un dispositiu petit, amb maquinari limitat, que integra veu, memòria, cara, agenda i doble cervell en un sol flux.

La comparació honesta és amb un prototip propi anterior, no amb un producte d'una gran empresa. L'aportació és l'arquitectura d'integració, la mesura de la latència, el disseny del doble cervell, la selecció i el format dels records, la personalitat, la cara i la capa d'ordres directes. La resta són llibreries i models oberts que es reconeixen a la bibliografia.

### 3.10.3 Ètica i privacitat

El projecte tracta converses personals i estats d'ànim. Per això:

- Les converses són del propi autor; no es publiquen àudios ni noms de tercers.
- La memòria pot contenir dades sensibles; les còpies es guarden al PC, no a la placa, i no es pugen a un repositori públic.
- Els serveis externs reben només el que necessiten. Cal declarar-ho i explicar com desactivar-los.
- El mode local existeix, però no és el mode per defecte. Aquesta és una limitació de privacitat que s'ha de dir.

### 3.10.4 Línies futures

- **Memòria de fets:** consolidar la taula de fets i mesurar-la amb més preguntes; no prometre recuperació perfecta.
- **Carcassa:** tancar un disseny amb ventilació, suport de pantalla i accés als ports.
- **Refrigeració:** comparar dissipador passiu i actiu amb temperatura i latència, no amb impressions.
- **NPU:** provar l'accelerador amb una mesura reproduïble; no adoptar-lo per moda.
- **Estudi d'usuaris:** gravar sessions reals i mesurar si la cara i el to ajuden, no només si el text és correcte.
- **Mode local:** reduir el TTFT o acceptar que és una reserva; no vendre'l com a equivalent al núvol.

---

## 3.11 Síntesi del capítol

El marc pràctic explica com una idea es va convertir en un prototip i com el prototip es va corregir amb mesures. La primera versió va demostrar que el flux era possible; la segona va demostrar que la placa era el límit; la tercera va separar el cervell del dispositiu; la quarta va afegir memòria i veu; la cinquena va donar cara, personalitat i vida quotidiana.

El resultat no és un producte acabat. És un sistema que **funciona en condicions reals**, que **declara els seus límits** i que **documenta com els ha gestionat**. Aquesta és la contribució que es pot defensar davant del tribunal: no haver aconseguit-ho tot, sinó haver demostrat què es pot aconseguir amb aquest maquinari, aquest pressupost i aquest mètode.

Els resultats detallats són a [[TREC/05 Resultats]]; les conclusions i les línies futures, a [[TREC/07 Conclusions]].
