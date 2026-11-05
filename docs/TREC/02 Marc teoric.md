---
tema: TREC
bloc: 2
estat: esborrany
---
# 02 · Marc teòric

> **Funció d'aquesta nota.** Donar el vocabulari i el context que cal abans de
> veure codi. No ha de ser més llarg que el marc pràctic: la guia del centre ho
> diu explícitament. Els detalls de cada terme són a [[conceptos]]; aquí hi ha el
> fil argumental i cada concepte connectat amb el lloc del pràctic on s'usa.
> Si un apartat no ajuda a entendre una decisió del pràctic, sobra.

## Com llegir aquest bloc

Cada concepte segueix el mateix patró:

1. **Què és**, en una frase.
2. **Un exemple quotidià**, sense ordinadors.
3. **En Parker**, amb el nom real del mòdul, la mesura o la decisió.

Això evita definir paraules i no saber per a què serveixen. Cada apartat acaba
amb un enllaç al punt del [[TREC/03 Marc practic|marc pràctic]] on s'aplica.

### Mapa teoria → pràctica

| Apartat | Què explica | On s'aplica |
|---|---|---|
| **2.1** | Neurona, capes, entrenament, token, atenció, predicció, mida del model i TTFT | 3.4 Cervell i 3.9 Resultats |
| **2.2** | Embeddings, RAG, Chroma, top-k i llindar | 3.5 Memòria |
| **2.3** | So digital, STT, TTS, VAD i suma de latències | 3.3 Oïda i veu |
| **2.4** | Client-servidor, API, HTTP/JSON, claus, 429 i fallback | 3.4 Doble cervell |
| **2.5** | SoC, CPU/GPU/NPU, RAM, SPI/GPIO, calor | 3.2 Maquinari i pantalla |
| **2.6** | BMO/Baymax, privacitat i cost | 3.6 Personalitat i 3.9 Discussió |
| **2.7** | Què no va aquí i per què | 3.1–3.11 |

---

## 2.1 La xarxa neuronal: de la neurona al text

### 2.1.1 La neurona artificial

**Què és.** Una neurona artificial rep uns números, els multiplica per uns pesos
(la importància de cada número), ho suma i converteix el total en una resposta
entre 0 i 1.

**Exemple.** Per decidir si vas d'excursió mires el temps (0,8 a favor), els
deures pendents (0,2 en contra) i les ganes (0,5 a favor). Amb els pesos
adequadament triats, la suma dona 0,83: més a prop del sí que del no.

**En Parker.** No hi ha una sola neurona decidint res: el model en té milers de
milions. La idea és la mateixa, però repartida en capes i en pesos que ja venen
entrenats. El codi de Parker no entrena aquestes neurones; les fa servir.

### 2.1.2 La codificació de les dades

**Què és.** Les neurones només entenen números, així que qualsevol entrada
(text, imatge, so) s'ha de traduir primer a números.

**Exemple.** Una foto és un mosaic de píxels; cada píxel té tres números (vermell,
verd i blau) entre 0 i 255. Un so és una llista de valors de pressió d'aire
mesurats moltes vegades per segon.

**En Parker.** El text es converteix en *tokens*; l'àudio del micròfon, en mostres
PCM a 16 kHz; la cara no és una imatge sinó una escena de formes que Qt converteix
en píxels per a la pantalla.

### 2.1.3 Les capes

**Què és.** Les neurones s'organitzen en capes: una d'entrada, diverses d'ocultes
i una de sortida. Cada capa combina el que ha après l'anterior.

**Exemple.** En un diari, els reporters recullen dades sense interpretar-les, els
redactors les converteixen en notícies i el director decideix el titular. Ningú
no fa la feina de l'altre.

**En Parker.** Les primeres capes detecten patrons molt simples; les últimes,
significat. Per això el model pot respondre sobre coses que no ha vist mai
exactament: no busca una frase guardada, sinó que construeix una resposta amb
patrons.

### 2.1.4 L'entrenament

**Què és.** Els pesos comencen a l'atzar. Entrenar és ajustar-los milions de
vegades perquè la resposta s'apropi a la correcta.

**Exemple.** Afinar una guitarra amb milers de clavilles sense orella: gires una
mica, comproves, repeteixes. Cada correcció és petita per no desfer l'afinació
anterior.

**En Parker.** L'entrenament ja l'ha fet el creador del model (Qwen, Meta, etc.).
Parker només fa **inferència**: dona un text i rep una resposta. L'única excepció
prevista és un LoRA de personalitat, que avui està dissenyat però no entrenat
([[TREC/03 Marc practic]] §3.9.3).

El PDF actual explica quatre maneres d'entrenar. Totes quatre són formes
d'ajustar els pesos; canvien d'on surt la resposta correcta:

| Tipus | Com aprèn | Exemple | En Parker |
|---|---|---|---|
| **Supervisat** | Amb exemples etiquetats: la resposta correcta ja es coneix | Fotos de «gat» i «gos»; la xarxa compara i corregeix | No s'entrena aquí; és la base de molts classificadors |
| **No supervisat** | Sense etiquetes: la xarxa troba grups o patrons | Una caixa de Lego barrejada; el nen l'agrupa per forma o color | No s'entrena aquí; s'usa en models d'agrupament o de representació |
| **Autosupervisat** | El text mateix dona la resposta: s'amaga una paraula i es prediu | «El gat negre dorm plàcidament al…» → «sofà» | **És la base del LLM**: predir el següent token |
| **Per reforç** | Prova accions i rep una recompensa o un càstig | Un cotxe virtual que aprèn a no sortir de la pista | S'usa en l'alineament del model; Parker no l'entrena |

Per a Parker, la més important és l'autosupervisada: és la que converteix un text en un
joc de «predir el següent tros». L'aprenentatge per reforç explica per què els
models estan alineats per respondre d'una manera i no d'una altra, però no és una
cosa que el projecte faci en local.

### 2.1.5 Del text al token

**Què és.** Un **token** és la unitat mínima amb què treballa el model. No és una
paraula: pot ser una paraula curta, un tros de paraula, un accent o un signe.

**Exemple.** Un text és com una frase feta de peces de Lego. El model no veu
«Parker», veu una o dues peces que junta per construir el significat. En espanyol
solen ser 2-3 caràcters per token.

**En Parker.** El prompt sencer es mesura en tokens: identitat, regles, ànim, hora,
records i historial. Si el prompt creix, el model triga més a llegir-lo. Per això
`num_ctx` ha de ser prou gran (2048) i l'historial es limita a vuit missatges.

### 2.1.6 L'atenció i el transformer

**Què és.** L'**atenció** permet que cada paraula miri les altres i decideixi de
quina altra paraula depèn. El **transformer** és l'arquitectura que apila moltes
capes d'atenció.

**Exemple.** A «El gat va perseguir el ratolí perquè tenia gana», ¿qui tenia gana?
L'atenció relaciona «tenia gana» amb «gat» o «ratolí» segons el context. No és una
regla fixa: és una mesura de rellevància.

**En Parker.** Quan li dius «recordes el dentista?», el model no consulta una
agenda: mira el text del prompt i decideix quines paraules són rellevants. Si els
records són dolents o estan fora de context, la resposta també ho serà. L'ordre i
la qualitat del prompt importen tant com el model.

### 2.1.7 Predir el següent token

**Què és.** Un LLM no «pensa» una frase sencera: calcula quina peça de text és més
probable després de les anteriors, la tria, l'afegeix i repeteix.

**Exemple.** És com l'autocompletar del mòbil, però amb tot el context de la
conversa i amb milers de milions de textos al darrere. No sap què vol dir «veritat»;
sap què sol venir després.

**En Parker.** Genera text token a token. `temperature` controla quant s'atreveix
a triar una opció poc probable (0,45 aquí); `max_tokens` limita la llargada. El
*streaming* permet rebre la primera frase i començar a parlar mentre la resta encara
s'està generant.

### 2.1.8 Mida i velocitat: per què cap en una placa

**Què és.** Els **paràmetres** són els pesos del model. Més paràmetres solen
significar més capacitat, però també més RAM i més càlcul. La **quantització**
guarda cada pes amb menys bits (4-8 en lloc de 16) perquè ocupi menys i vagi més
ràpid, a canvi de perdre una mica de precisió.

**Exemple.** Una enciclopèdia de milers de milions de números no cap en una
motxilla. Si guardes cada número amb menys decimals, el llibre és més prim: perds
detall, però te'l pots emportar.

**En Parker.** `qwen2.5:3b` té uns 3.000 milions de paràmetres i, en Q4, ocupa uns
2 GB dels 8 GB de la placa. L'1.5b és més ràpid, però entén menys el context. Quan
arriba el prompt, el model primer el llegeix (**prefill**) i després escriu la
resposta token a token: per això el primer tros de text tarda més que els següents.
Aquest temps s'anomena **TTFT** (*time to first token*).

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.4 explica el doble cervell amb
> les xifres, i §3.9 les resumeix.

### 2.1.9 Per què inventa

**Què és.** Com que el model prediu el que és plausible, no el que és cert, pot
omplir un buit amb una dada falsa però ben construïda. Això és una **al·lucinació**.

**Exemple.** Un alumne que no ha estudiat i respon amb molta seguretat: la frase
sona bé, però el contingut pot ser inventat. La seguretat no demostra coneixement.

**En Parker.** Ha passat amb el nom («Dipper» per «Piper») i amb un instrument
(piano per trompeta). La solució no és demanar-li «sigues sincer»: és donar-li
millor memòria, dir-li «si no ho saps, digues-ho» i filtrar el que entra al prompt.
El prompt és el seu món; si hi ha una etiqueta o un comptador, el pot recitar.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.4 explica com es construeix el
> prompt i per què el model local inventa més que el del núvol.

---

## 2.2 La memòria: RAG, embeddings i Chroma

### 2.2.1 Per què el model no recorda

**Què és.** Un LLM no té memòria entre peticions. Cada vegada que li parles comença
de zero; l'únic que recorda és el que hi ha dins del prompt d'aquella petició.

**Exemple.** És com una persona que cada matí oblida tot el que va passar ahir. Per
parlar-hi del dentista, cal ensenyar-li una fotografia o una nota cada vegada.

**En Parker.** La memòria no viu dins del model: viu a ChromaDB. Abans de generar,
Parker busca els records més semblants i els enganxa al prompt.

### 2.2.2 Embeddings i similitud

**Què és.** Un **embedding** converteix un text en un vector de números que
representa el seu significat. Dues frases que volen dir el mateix queden a prop,
encara que no comparteixin paraules. La **similitud coseno** mesura com s'assemblen.

**Exemple.** Imagina un mapa on cada idea és una ciutat. «Pasta» i «espagueti»
queden a prop; «pasta» i «dentista», lluny. No cal buscar la paraula exacta: es
busca la zona del mapa.

**En Parker.** `paraphrase-multilingual-MiniLM-L12-v2` converteix cada record en
384 números. La consulta no llegeix tots els records: busca els vectors més propers,
i per això el temps no creix amb la mida de la base.

### 2.2.3 RAG: retrieval, augment, generation

**Què és.** **RAG** (*Retrieval-Augmented Generation*) té tres passos: buscar
(*retrieval*), afegir els records al prompt (*augment*) i generar la resposta
(*generation*).

**Exemple.** Un examen amb llibre obert: primer busques la pàgina, després la poses
damunt la taula i finalment escrius la resposta. Si busques malament, la resposta
surt malament encara que el llibre sigui bo.

**En Parker.** `modulos/memoria.py` consulta Chroma amb el missatge de l'usuari,
recupera 3 records (`top_k`) que superin 0,58 de similitud i els enganxa al prompt.
Si cap no arriba, no n'hauria d'inventar cap.

### 2.2.4 Memòria de tema vs memòria de fet exacte

**Què és.** La similitud semàntica troba **temes**, no fets exactes. «Quin és el
nom del meu gos?» pot assemblar-se a qualsevol conversa sobre animals i no
recuperar el nom concret.

**Exemple.** Una biblioteca ordenada per «ambient» et porta a la prestatgeria
d'animals, però no et diu quin gos és el teu. Per això cal un índex o una fitxa.

**En Parker.** Amb preguntes curtes sobre fets desats, una part important no es va
recuperar. No és un error de Chroma: és el límit d'un embedding petit amb frases de
conversa i preguntes de tres paraules. Per això Parker ha après a dir «no ho sé» i
per això la memòria de fets és una línia futura.

### 2.2.5 Una segona memòria de coneixement

**Què és.** Chroma pot tenir diverses **col·leccions** separades. Una pot guardar
records personals i una altra coneixement general (receptes, psicologia, manuals).
La consulta ha de decidir a quina col·lecció mirar.

**Exemple.** Un diari personal i un llibre de cuina no es guarden al mateix calaix.
Si busques una recepta, no vols que et surti una conversa de fa tres mesos.

**En Parker.** La segona memòria està **dissenyada, no implementada**. La idea és
una col·lecció `saberes` amb el seu propi llindar, etiquetada com a «dades
llegides» perquè no es barregi amb la memòria personal.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.5 dona les xifres d'escala,
> llindar i fidelitat.

---

## 2.3 La veu: com es converteix so en text i text en so

### 2.3.1 So digital: mostreig, PCM i WAV

**Què és.** Un so és una ona de pressió d'aire. Digitalitzar-lo és mesurar aquesta
pressió moltes vegades per segon. El **sample rate** és el nombre de mesures per
segon; **PCM** és el format de les mostres; **WAV** és un contenidor que les guarda.

**Exemple.** Una pel·lícula és una successió de fotos; un so digital és una
successió de «fotos» de la pressió de l'aire. A 16.000 mostres per segon, l'oïda
humana no nota els talls.

**En Parker.** Whisper treballa a 16 kHz mono. Piper genera a 22,05 kHz i per això
cal remostrejar. El micròfon USB pot trigar a aparèixer; el format no és el
problema, ho és el dispositiu.

### 2.3.2 STT: Whisper

**Què és.** **STT** (*Speech To Text*) converteix àudio en text. Whisper és un model
d'OpenAI; `faster-whisper` és la mateixa xarxa reimplementada per anar més ràpida en
CPU. Els models `tiny`, `base`, `small` etc. són mides diferents.

**Exemple.** Un taquígraf escolta i escriu. Un de molt ràpid pot escriure més de
pressa, però pot confondre paraules; un de més lent escolta millor. Cal triar.

**En Parker.** Hi ha un model local (`base`) i un de núvol
(`whisper-large-v3-turbo`). El local no depèn de la xarxa però comet més errors;
el del núvol encerta més i és més ràpid. Les xifres són a §3.3.

### 2.3.3 TTS: Piper i Edge

**Què és.** **TTS** (*Text To Speech*) converteix text en àudio. Piper és local,
petit i ràpid; Edge TTS és un servei de Microsoft, més natural però depèn de la
xarxa.

**Exemple.** Una veu sintètica pot sonar com un GPS (clara però freda) o com una
persona (natural però més lenta). Parker pot començar a parlar amb la segona i
canviar a la primera si falla.

**En Parker.** Edge `es-ES-XimenaNeural` és la principal; Piper
`es_ES-davefx-medium` és el respostal. La síntesi es fa per frases: mentre sona una,
se sintetitza la següent.

### 2.3.4 VAD: quan has acabat de parlar

**Què és.** El **VAD** (*Voice Activity Detection*) detecta si hi ha veu o silenci.
Serveix per obrir el torn quan comences i tancar-lo quan calles.

**Exemple.** Un walkie-talkie amb botó et obliga a prémer per parlar. Un VAD és com
un micròfon que s'obre sol i s'atura quan deixes de parlar.

**En Parker.** El tall és de 0,6 s de silenci: prou llarg per no tallar una frase i
prou curt per no fer esperar. El VAD també evita enviar silenci a transcriure.

### 2.3.5 La suma de latències

**Què és.** El temps total no és una sola etapa: és la suma del silenci de tall, la
transcripció, el primer token, la primera frase i la seva síntesi. Algunes etapes
es poden solapar.

**Exemple.** Una cursa de relleus: no importa només qui corre més, sinó quant es
tarda a passar el testimoni. Un equip pot tenir un corredor molt ràpid i perdre
perquè els canvis són lents.

**En Parker.** Al primer prototip se sumaven totes les etapes i la conversa no
arribava a temps. La millora no va ser una bala de plata: algunes coses es fan
mentre ja parla, i per això el que es percep és menor que el torn complet.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.3 i §3.9 donen les taules de
> latència i les proves amb música.

---

## 2.4 Client-servidor: com parla Parker amb el núvol

### 2.4.1 Client i servidor

**Què és.** Un **client** demana una cosa; un **servidor** la fa i respon. Parker és
el client; Groq és el servidor. La comunicació es fa per una **API**.

**Exemple.** En un restaurant, tu demanes del menú i el cambrer porta el plat. No
entres a la cuina ni necessites saber com funciona el forn. L'API és el menú i el
cambrer.

**En Parker.** `modulos/cerebro.py` envia el prompt a Groq i rep text. Si el
servidor no contesta, Parker no es queda mut: canvia al model local.

### 2.4.2 HTTP i JSON

**Què és.** **HTTP** és el protocol de les peticions web; **JSON** és el format de
dades amb claus i valors. Una petició porta una URL, unes capçaleres i un cos; la
resposta porta un codi d'estat i un cos.

**Exemple.** Enviar una carta: el sobre porta l'adreça i el remitent (capçaleres),
dins hi ha el full (cos) i et tornen un justificant de recepció (codi d'estat).

**En Parker.** La petició va a `/chat/completions` amb el model, els missatges i
`stream: true`. La resposta arriba a trossos, no de cop; per això cal llegir-la en
UTF-8 i netejar el marcatge abans de sintetitzar.

### 2.4.3 Claus, límits i errors 429

**Què és.** Una **API key** identifica el compte. Els proveïdors posen límits de
peticions o de tokens; si els passes, retornen **429** (*too many requests*). També
poden retirar un model.

**Exemple.** Un museu dona un nombre limitat d'entrades per hora. Si s'han esgotat,
no et deixen entrar; has d'esperar o anar a un altre museu.

**En Parker.** La clau viu a `.env`, no a `config.yaml`. Si Groq dona 429 o retira
el model, Parker prova els models alternatius i, si cal, cau al local.

### 2.4.4 Núvol o local: no hi ha una opció millor

**Què és.** Un servei al núvol i un model local no es diferencien només en la
velocitat: canvien la privacitat, el cost, la disponibilitat i la qualitat. Triar-ne
un és decidir quin d'aquests factors pesa més.

**Exemple.** Taxi o cotxe propi: el taxi no l'has de mantenir ni aparcar, però depèn
d'una altra persona i pagues per trajecte; el cotxe és teu i sempre hi és, però
l'has de conduir i mantenir.

**En Parker.** El text pot sortir de casa o quedar-s'hi. Quina de les dues bandes
s'usa, i per què, és una decisió del marc pràctic (§3.4): depèn de les mesures, no
d'una preferència.

### 2.4.5 Fallback i estat

**Què és.** Un **fallback** és un pla B automàtic. Perquè funcioni, el sistema ha de
detectar la fallada, canviar de camí i avisar l'usuari sense repetir l'avís a cada
torn.

**Exemple.** Un generador elèctric de reserva: no s'engega mentre hi ha corrent,
però si n'hi ha una fallada, entra sol i et deixa acabar la feina.

**En Parker.** El mode es desa i sobreviu al reinici. Si cau la xarxa, avisa **una
vegada** per veu i continua amb Ollama. Quan torna, pot tornar sol o quedar-se en
local segons el mode triat.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.4 explica el doble cervell i les
> proves de caiguda.

---

## 2.5 Maquinari encastat: per què una placa i no un PC

### 2.5.1 SoC, CPU, GPU i NPU

**Què és.** Un **SoC** (*System on a Chip*) és un xip que integra CPU, GPU, memòria i
perifèrics. La **CPU** fa càlcul general; la **GPU** fa moltes operacions en paral·lel;
la **NPU** està especialitzada en xarxes neuronals.

**Exemple.** Una cuina petita amb un xef (CPU), ajudants (GPU) i un especialista en
postres (NPU). El xef pot fer-ho tot, però l'especialista és més ràpid en el seu
plat. Els **TOPS** són la capacitat teòrica de l'especialista, no la velocitat real
del restaurant.

**En Parker.** L'Orange Pi 5 Pro té un RK3588S: 8 nuclis, GPU i NPU de 6 TOPS. El
model local corre en CPU; la NPU s'ha investigat però no s'ha adoptat perquè el
guany no compensa la complexitat (§3.9.5).

### 2.5.2 RAM i emmagatzematge

**Què és.** La **RAM** és la memòria de treball, ràpida i volàtil; l'**emmagatzematge**
(microSD, SSD) és permanent però més lent. El model s'ha de carregar a la RAM per
executar-se.

**Exemple.** Un escriptori (RAM) on poses els papers que estàs fent i un armari
(microSD) on els guardes. Si l'escriptori és petit, no hi caben tots els papers alhora.

**En Parker.** 8 GB de RAM perquè hi convisquin el model local, Whisper, Qt i Chroma.
La microSD guarda models i `parker.db`; és lenta per escriure-hi, i per això les
còpies no es fan a la placa.

### 2.5.3 GPIO, SPI i pantalla

**Què és.** **GPIO** són pins que es poden posar a 0 o 1 per controlar coses. **SPI**
és un bus sèrie ràpid per enviar dades a un perifèric, com una pantalla. El
controlador de la pantalla necessita pins de dades, rellotge, selecció de xip i dos
pins de control (DC i RST).

**Exemple.** És com enviar una imatge a una impressora: el cable USB porta les dades
(SPI), i dos botons li diuen «ara ve una ordre» (DC) i «reinicia» (RST).

**En Parker.** La GC9A01 de 240×240 va per SPI0. Si la seqüència d'inici és
incompleta, la pantalla s'il·lumina però queda blanca. El cablejat i el refresc
són al marc pràctic (§3.2).

### 2.5.4 Consum, calor i throttling

**Què és.** Un xip consumeix energia i genera calor. Si la temperatura puja massa,
el sistema baixa la freqüència (**throttling**) per protegir-se; llavors tot va més
lent.

**Exemple.** Un mòbil al sol s'escalfa i la pantalla baixa de brillantor o el joc
va a salts. No s'ha espatllat: s'està protegint.

**En Parker.** Alimentació 5 V / 3 A. El model de 3b pot escalfar la placa fins que
baixa de freqüència; per això la refrigeració és una línia futura, no un detall
estètic.

### 2.5.5 Per què una placa i no un PC

**Què és.** Un PC és més potent, però és gran, consumeix més i no té els pins de
GPIO/SPI que necessita la pantalla. Una placa encastada és petita, silenciosa i es
pot deixar encesa tot el dia.

**Exemple.** Un portàtil és millor per editar vídeo; un rellotge de paret és millor
per donar l'hora sense ocupar una taula. No competeixen: fan feines diferents.

**En Parker.** El PC serveix per desenvolupar i mesurar; la placa és el dispositiu
final. La comparació concreta de plaques i pantalles és al marc pràctic (§3.2),
perquè depèn del preu i de la disponibilitat del moment.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.2 justifica la placa i la
> pantalla amb una matriu de requisits, no amb una preferència.

---

## 2.6 Referents, privacitat i cost

### 2.6.1 BMO i Baymax

**Què és.** No són models de llenguatge ni tecnologies: són **referents de disseny
de personatge**. BMO aporta el to ingenu i afectuós; Baymax, la manera de cuidar
sense sonar corporatiu.

**Exemple.** Un amic que s'asseu amb tu no et diu «en què puc ajudar-te» cada cop
que et veu. Et pregunta com estàs i continua la conversa.

**En Parker.** Al prompt es tradueix en regles: no enumerar, no fingir un cos, no
prometre accions físiques, no fer servir el to d'assistent. La personalitat és una
capa que modula totes les respostes.

### 2.6.2 Privacitat: què surt i què no

**Què és.** Cal distingir el que es queda a la placa del que viatja. El mode híbrid
envia text (i àudio, si el STT és al núvol) a un tercer; el mode local no.

**Exemple.** Una carta pot quedar-se a casa o enviar-se per correu. El sobre no és
el problema; el contingut i el destinatari sí.

**En Parker.** Micròfon, VAD, Chroma, ànim, agenda, cara i veu queden a la placa.
El text del prompt surt per defecte; l'àudio també si el STT és automàtic. Hi ha
un interruptor (`online.activo: false`, `escucha.motor: local`) i ordres de veu
(«ponte en local»).

### 2.6.3 Cost

**Què és.** El cost no és només el maquinari: també hi ha electricitat, límits
gratuïts i temps de manteniment. Un servei gratuït pot canviar de condicions.

**Exemple.** Un cotxe barat pot sortir car si gasta molt o si les peces no es
troben. Mirar només el preu de compra enganya.

**En Parker.** El pressupost i el full de costes són al marc pràctic (§3.2), amb les
xifres. Groq, Open-Meteo i Deezer s'usen en plans gratuïts; el cost real és la
placa i el temps.

> **Al marc pràctic:** [[TREC/03 Marc practic]] §3.6 i §3.9.2 expliquen com es
> tradueix el to en regles i què queda fora de la privacitat per defecte.

---

## 2.7 Què queda fora del marc teòric

No va aquí:

- com es programa cada mòdul (això és [[TREC/03 Marc practic]]);
- les mesures concretes (això és [[TREC/05 Resultats]]);
- la cronologia (això és [[TREC/12 Diari de recerca]]);
- els errors i les seves solucions (això és [[TREC/06 Errades i solucions]]).

El marc teòric ha de respondre **per què aquestes tecnologies existeixen i quins
límits tenen**, no com s'ha fet el codi línia a línia. Si una explicació només té
sentit perquè Parker existeix, ja no és teoria: és pràctica.

### 2.7.1 Glossari de consulta ràpida

Els termes tècnics que apareixen al llarg del treball, amb una línia cada un, són a
[[conceptos]]. Aquesta nota no els repeteix tots: els explica en context i els
connecta amb el lloc del pràctic on s'usen.

### 2.7.2 Pont cap al marc pràctic

El pràctic comença on acaba aquesta nota: amb uns requisits (escoltar, recordar,
respondre en menys de 2 s, funcionar sense xarxa i tenir cara) i unes decisions
(placa, pantalla, models, memòria, veu). Cada decisió es justifica amb un concepte
d'aquest bloc i es mesura al [[TREC/05 Resultats|bloc de resultats]].
