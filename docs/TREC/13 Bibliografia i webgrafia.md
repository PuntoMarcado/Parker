---
tema: TREC
bloc: 7
estat: viu
---
# 13 · Bibliografia i webgrafia

> **Què demana la guia.** Cada font ha de tenir la **ressenya completa** i un
> **comentari** de quina informació s'ha utilitzat. No s'hi han d'incloure
> documents consultats que no hagin servit. Ordre alfabètic i un sol sistema de
> citació.

**Sistema adoptat:** autor o entitat + any + títol + suport + disponibilitat +
data de consulta. Les obres impreses, sense URL.

**Data de consulta general:** 31 d'octubre de 2026.

---

## 1. Guies i documents del centre

**CENTRE EDUCATIU. *Guia del Treball de Recerca (2025-27)* [document intern].
Curs 2025-27.**

> És la norma que fixa l'estructura de la memòria, les normes de presentació, els
> percentatges d'avaluació (seguiment 30 %, dossier 30 %, oral 40 %) i la
> rúbrica. S'ha fet servir per a [[TREC/09 Redaccio de la memoria]] i
> [[TREC/11 Checklist TREC]].

**TURULL RUBINAT, Max; PONS I SERRA, Amadeu; ROCA ACEDO, Berta; SATORRAS
FIORETTI, Rosa M.; VALLÈS ELIZALDE, Àgueda. *Guia pràctica per fer un bon treball
de recerca (TR) a batxillerat. #20 consells essencials* [en línia]. Barcelona:
Institut de Ciències de l'Educació (ICE), Universitat de Barcelona, 2017.
Disponible a: http://hdl.handle.net/2445/114030 [Consulta: 31 octubre 2026].**

> Aporta el checklist final, les pautes de planificació, la diferència entre
> marc teòric i pràctic i les normes de cites. S'ha fet servir per al calendari,
> la redacció i la defensa.

**TREC - Full 1. *Pressupost Project 1: tot en local* [document intern]. 2026.**

> Full de càlcul del material: placa, pantalla, microSD, font, altaveu, carcassa
> i cables. Total: **275,52 €**. És la font de la taula de material de
> [[TREC/03 Marc practic]] §3.1.5.

---

## 2. Intel·ligència artificial i memòria

**HU, Edward J.; SHEN, Yelong; WALLIS, Phillip; ALLEN-ZHU, Zeyuan; LI, Yuanzhi;
WANG, Shean; WANG, Lu; CHEN, Weizhu. *LoRA: Low-Rank Adaptation of Large Language
Models* [en línia]. 2021. arXiv:2106.09685.**

> Explica per què un LoRA pot canviar l'estil d'un model sense reentrenar-lo
> sencer. S'ha fet servir per valorar la línia de personalitat de
> [[lora_voz]] i [[TREC/07 Conclusions]] §6.

**LEWIS, Patrick; et al. *Retrieval-Augmented Generation for Knowledge-Intensive
NLP Tasks* [en línia]. 2020. arXiv:2005.11401.**

> Defineix el esquema retrieval → augment → generation que s'explica al marc
> teòric i que implementa `modulos/memoria.py`.

**DETTMERS, Tim; PAGNONI, Artidoro; HOLTZMAN, Ari; ZETTLEMOYER, Luke. *QLoRA:
Efficient Finetuning of Quantized LLMs* [en línia]. 2023. arXiv:2305.14314.**

> Referència per a un futur entrenament en GPU de consum o al núvol. No s'ha
> aplicat encara; és una línia futura, no un resultat.

**QWEN TEAM. *Qwen2.5 Technical Report* [en línia]. 2024. arXiv:2412.15115.
Disponible també a: https://github.com/QwenLM/Qwen2.5 [Consulta: 31 octubre
2026].**

> Fitxa tècnica dels models `qwen2.5:1.5b` i `qwen2.5:3b` usats en local. S'ha
> fet servir per explicar mida, context i limits, no per justificar la tria: la
> tria es va fer amb mesures pròpies.

**OPENAI. *gpt-oss* [en línia]. GitHub, 2025. Disponible a:
https://github.com/openai/gpt-oss [Consulta: 31 octubre 2026].**

> Repositori dels models oberts `gpt-oss-20b` i `gpt-oss-120b`, els que donen la
> latència de 0,56-0,58 s al núvol. S'ha fet servir per a la comparativa de
> [[TREC/05 Resultats]] §3.

**SENTENCE-TRANSFORMERS. *paraphrase-multilingual-MiniLM-L12-v2* [en línia].
Hugging Face. Disponible a:
https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
[Consulta: 31 octubre 2026].**

> Fitxa del model d'*embeddings* multilingüe de 384 dimensions. És el que
> converteix els records en vectors; la seva mida explica el límit de precisió
> documentat a [[TREC/05 Resultats]] §5.

**CHROMADB. *Chroma Docs* [en línia]. Disponible a:
https://docs.trychroma.com [Consulta: 31 octubre 2026].**

> Documentació de la base vectorial local: col·leccions, metadades, consultes i
> persistència. S'ha fet servir per a `modulos/memoria.py` i per a les proves
> d'escala.

---

## 3. Veu i àudio

**RADFORD, Alec; KIM, Jong Wook; XU, Tao; BROCKMAN, Greg; MCLEAVEY, Christine;
SUTSKEVER, Ilya. *Robust Speech Recognition via Large-Scale Weak Supervision*
[en línia]. 2022. arXiv:2212.04356.**

> Article de Whisper. Explica per què el model gran transmet bé i per què el
> `base` pot fallar amb noms propis; dona context a la taula de STT.

**SYSTRAN. *faster-whisper* [en línia]. GitHub. Disponible a:
https://github.com/SYSTRAN/faster-whisper [Consulta: 31 octubre 2026].**

> Implementació ràpida de Whisper amb quantització int8. És el motor local de
> `modulos/escucha.py`.

**RHASSPY. *Piper* [en línia]. GitHub. Disponible a:
https://github.com/rhasspy/piper [Consulta: 31 octubre 2026].**

> Sintetitzador local lleuger. S'ha fet servir com a veu de respostal i per
> comparar la latència (0,36 s per frase).

**RANY2. *edge-tts* [en línia]. GitHub. Disponible a:
https://github.com/rany2/edge-tts [Consulta: 31 octubre 2026].**

> Client no oficial de les veus neuronals de Microsoft Edge. Permet usar
> `es-ES-XimenaNeural` des de Python; no és un servei oficial de Microsoft.

**SNEAKERS4. *Silero VAD* [en línia]. GitHub. Disponible a:
https://github.com/snakers4/silero-vad [Consulta: 31 octubre 2026].**

> Detector d'activitat de veu que usa `faster-whisper`. És el que permet tallar
> el torn als 0,6 s de silenci.

---

## 4. Maquinari i sistema

**ROCKCHIP. *RK3588* [en línia]. Disponible a: https://www.rock-chips.com
[Consulta: 31 octubre 2026].**

> Fitxa del SoC de l'Orange Pi 5 Pro: nuclis A76/A55, NPU de 6 TOPS i suport de
> memòria. S'ha fet servir per explicar per què el model local va lent.

**AIROCKCHIP. *RKLLM* [en línia]. GitHub. Disponible a:
https://github.com/airockchip/rknn-llm [Consulta: 31 octubre 2026].**

> Eines per executar models a la NPU del RK3588. Es va valorar i es va descartar
> amb mesures pròpies; la referència queda per a una revisió futura.

**QT GROUP. *Qt for Python (PySide6)* [en línia]. Disponible a:
https://doc.qt.io/qtforpython-6/ [Consulta: 31 octubre 2026].**

> Documentació de la interfície gràfica i dels senyals que connecten la cara amb
> la resta del sistema.

**PYTHON-SOUNDDEVICE. *sounddevice* [en línia]. Disponible a:
https://python-sounddevice.readthedocs.io [Consulta: 31 octubre 2026].**

> Entrada i sortida d'àudio per PortAudio. És la peça que va fer visible el
> problema del micro USB que apareix tard.

---

## 5. Serveis

**GROQ. *GroqCloud Documentation* [en línia]. Disponible a:
https://console.groq.com/docs [Consulta: 31 octubre 2026].**

> API compatible amb OpenAI, llista de models i límits. S'ha fet servir per al
> cervell primari i per a la selecció automàtica si un model desapareix.

**OLLAMA. *Ollama* [en línia]. Disponible a: https://ollama.com [Consulta: 31
octubre 2026].**

> Execució local de models i API REST. És el cervell de respostal i el que fa
> possible el mode sense internet.

**OPEN-METEO. *Open-Meteo* [en línia]. Disponible a: https://open-meteo.com
[Consulta: 31 octubre 2026].**

> API meteorològica sense clau. S'ha fet servir per a les preguntes del temps i
> per canviar la ciutat per veu.

**DEEZER. *Deezer API* [en línia]. Disponible a: https://developers.deezer.com
[Consulta: 31 octubre 2026].**

> Cerca i previsualitzacions de 30 s. És la base del mòdul de música; les
> cançons no es descarreguen.

---

## 6. Eines de documentació

**OBSIDIAN. *Obsidian* [en línia]. Disponible a: https://obsidian.md [Consulta:
31 octubre 2026].**

> Aplicació que llegeix aquesta carpeta com a bòveda i genera el graf de notes.
> No és una dependència del projecte: si desapareix, els fitxers Markdown
> continuen sent llegibles.

**JSON CANVAS. *JSON Canvas* [en línia]. Disponible a: https://jsoncanvas.org
[Consulta: 31 octubre 2026].**

> Format obert del fitxer `TREC/Mapa de Parker.canvas`, el mapa visual
> arrossegable.

---

## 7. Referents de ficció

**PENNELTON WARD, Pendleton. *Adventure Time* [sèrie de televisió]. Cartoon
Network, 2010-2018.**

> Referent de to: un robot petit, ingenu i afectuós que viu la seva vida. No
> s'ha fet servir com a font tècnica, sinó com a criteri de disseny de
> personalitat.

**HALL, Don (dir.). *Big Hero 6* [pel·lícula]. Walt Disney Animation Studios,
2014.**

> Referent de manera: un company que cuida i pregunta com estàs, sense to
> d'assistent corporatiu.

---

## 8. Com citar aquestes fonts al text

- Primera menció: **(Turull et al., 2017)** o «segons la guia del centre».
- Cites textuals: entre cometes i amb pàgina si n'hi ha.
- Figures o taules preses d'una font: «Font: …» al peu.
- No barrejar sistemes (autor-any i nota al peu) en el mateix treball.

## 9. Què no s'ha d'incloure

- Documents consultats que no s'han usat.
- Wikis o blogs sense autoria quan hi ha la font original.
- Aquestes notes d'Obsidian com si fossin bibliografia: són **material de
  treball**, no una font externa.

> **Avís d'autoria:** les dades, taules i explicacions d'aquesta bòveda són una
> síntesi de material propi (codis, logs i mesures). La memòria s'ha de redactar
> amb paraules pròpies i citar les fonts externes que realment s'hagin
> consultat.
