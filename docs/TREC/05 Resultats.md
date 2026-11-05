---
tema: TREC
bloc: 4
estat: esborrany
---
# 05 · Resultats

> **Com llegir aquesta nota.** Cada taula ve d'un log o d'una eina concreta,
> amb la data i el lloc de mesura. No hi ha xifres «de màrqueting»: hi ha el que
> es va mesurar i el que no. La metodologia és a
> [[TREC/04 Metodologia i proves]]; el detall llarg, a [[rendimiento]].

## 1. El resultat principal, en una taula

Temps des que deixes de parlar fins que Parker **comença a sonar**:

| Data | Configuració | Temps | Què havia canviat |
|---|---|---:|---|
| 17/10 (abans) | `small` + `qwen2.5:3b` + Piper | **15-20 s** | Punt de partida |
| 17/10 (després) | `base` + `1.5b` + prompt retallat | **4,2-4,7 s** | Model, STT, prompt i silenci de tall |
| 24-25/10 | `3b` + núvol Groq + STT núvol | **~1,6 s** | Doble cervell i transcripció al núvol |
| 30/10 (PC) | `gpt-oss-20b` | **0,51-0,56 s** | Només el cervell, xarxa de fibra |
| 30/10 (placa, mode local) | `qwen2.5:3b` | **5,78-5,90 s** | Ordre d'agenda resolta sense LLM |

**La lectura honesta:** el pipeline complet va baixar un ordre de magnitud, però
no perquè el model local s'hagi tornat màgic. És perquè **la part lenta ja no
s'executa a la placa**. El mode local continua existint i continua trigant.

## 2. On es va anar el temps (17/10/2026)

| Etapa | Abans | Després | Com |
|---|---:|---:|---|
| Tall de silenci | 1,3 s fix | **0,6 s** | `silencio_corte_seg` |
| STT | 4,8-5,3 s (`small`) | **1,6-1,8 s** (`base` int8) | Model + *hotwords* |
| Recuperar records | 0,15-0,18 s | 0,15-0,18 s | No era el coll |
| Primer token | 6,5-7,8 s (`3b`) | **0,9-1,9 s** (`1.5b`) | Model + prompt + prefix cachetat |
| Primera frase | 7,5-9 s | **1,3-2,1 s** | Resposta curta |
| TTS primera frase | 0,7-1,4 s | **0,5-0,9 s** | Frase més curta |
| **Fins que sona** | **15-20 s** | **4,2-4,7 s** | — |

Aquesta taula és la que millor explica el mètode: **no hi ha una bala de plata**,
hi ha sis etapes on es pot retallar.

## 3. Cervell: local vs núvol

### 3.1 El sostre de la placa

Mesurat a l'Orange Pi 5 Pro amb `qwen2.5:3b`, prompt real i 6 torns:

| Mètrica | Valor |
|---|---:|
| TTFT p50 | **8,75 s** (mín. 3,99 / màx. 12,40) |
| Torn complet p50 | **13,45 s** |
| Generació | **9,3 tok/s** |

Amb aquesta llatència no es pot conversar. Aquí va néixer la decisió de la v6:
**canviar de lloc la generació**, no canviar de model.

### 3.2 El núvol

| Motor | Model | TTFT (PC) | Generació |
|---|---|---:|---:|
| Groq | `openai/gpt-oss-20b` | **0,56 s** | 742 tok/s |
| Groq | `openai/gpt-oss-120b` | 0,58 s | 415 tok/s |
| Groq | `qwen/qwen3.8-27b` | 0,71 s | 240 tok/s (un torn en blanc) |
| Local | `qwen2.5:3b` | 8,75 s | 9,3 tok/s |

A la ruta completa de Parker, a la placa:

```
[Latencia] TTFB p50 1,23s (min 0,97 / max 1,37) | turno total p50 1,29s
[Cerebro] Nube lista en 0,57s (openai/gpt-oss-20b)
```

### 3.3 El preescalfament del prefix

| | Primer token | Prefill | Tokens (cachetats) |
|---|---:|---:|---:|
| Sense preescalfar | 8,94 s | 8,90 s | 635 (353) |
| Preescalfat 0,5 s abans | **0,64 s** | 0,60 s | 635 (619) |

La clau: llançar el preescalfament **en detectar veu**, no en transcriure, perquè
no competeixi amb Whisper. Això va eliminar els pics de 24 s que apareixien quan
les dues coses es trepitjaven.

## 4. Transcripció (STT)

| Motor | Temps | Text obtingut |
|---|---:|---|
| Local `small` | 4,76-5,33 s | «Oye Parker, hoy he tenido un día tranquilo…» |
| Local `base` int8 | 1,63-2,03 s | «Oye, parquear, hoy he tenido…» |
| **Núvol `whisper-large-v3-turbo`** | **0,68 s** | Text exacte |
| Local `tiny` | 1,01-1,33 s | Inintel·ligible |

La paradoxa és important: el model **més gran i més lent en abstracte** és el
més ràpid aquí, perquè corre en un servidor. A la placa, `base` és el compromís
del mode local.

## 5. Memòria: escala, llindar i fidelitat

### 5.1 Escala

Prova amb records sintètics del mateix estil que els reals, a la placa:

| Records | Indexar | Mida | Consulta p50 | Tema correcte (top-1 / top-3) |
|---:|---:|---:|---:|---:|
| 200 | 4,1 s | 0,9 MB | 147 ms | 85 % / 90 % |
| 1.000 | 21,0 s | 3,7 MB | 153 ms | **100 % / 100 %** |
| 3.000 | 63,7 s | 10,0 MB | 152 ms | **95 % / 95 %** |

- La **latència és plana**: ~150 ms, no creix amb el nombre de records.
- Indexar 3.000 costa 64 s, però és una feina d'una sola vegada.
- El que es perd en créixer és el **detall exacte** quan hi ha centenars de
  records gairebé iguals.

**Escala real:** la base tenia **52 records després de 205 converses** (~0,25 per
conversa). A aquest ritme, 1.000 records són anys.

### 5.2 El llindar no separa senyal de soroll

| | Senyal (el record hi és) | Soroll (no hi és) |
|---|---|---|
| 200 records | mitjana 0,621 / mín. 0,302 | màx. 0,724 |
| 1.000 records | mitjana 0,728 / mín. 0,625 | màx. 0,686 |
| 3.000 records | mitjana 0,759 / mín. 0,655 | màx. 0,724 |

**Se solapen.** No existeix un llindar que deixi fora tot el soroll sense tirar
records bons. Amb el 0,58 actual passen **12 records per consulta**; el top-3
s'omple de «pareguts».

### 5.3 El resultat que més importa explicar

8 preguntes curtes (com les de veu) sobre 12 fets distintius:

| Pregunta | Similitud | Entra? |
|---|---:|---|
| «¿qué lleva mi café?» | 0,874 | Sí |
| «¿cómo se llama mi dentista?» | 0,762 | Sí |
| «¿a qué soy alérgico?» | 0,744 | Sí |
| «¿con qué instrumento ensaya mi vecino?» | 0,718 | Per poc |
| «¿cómo se llama mi perro?» | 0,459 | **No** |
| «¿dónde veraneo?» | <0,459 | **No** |
| «¿qué estudié?» | 0,406 | **No** (era el top-1) |
| «¿cómo se llama mi hermano?» | 0,459 | **No** |

**4 de 8 fets desats no es recuperen.** No és un error de Chroma ni de la
base: és el límit d'un *embedding* petit amb frases de conversa i preguntes de
tres paraules. Per això al treball es parla de **memòria de tema**, no de memòria
de dades exactes.

### 5.4 Fidelitat: el núvol no inventa; el local, sí

12 fets a la memòria, 6 preguntes que hi són i 3 que no:

| Ajust | Encerts | Contaminació | Diu «no ho sé» | p50 |
|---|---:|---:|---:|---:|
| Núvol, top_k=3, 0,58 | 3/6 | **0** | **3/3** | 0,6 s |
| Núvol, top_k=3, 0,72 | 2/6 | **0** | **3/3** | 0,6 s |
| Núvol, top_k=8, 0,58 | 3/6 | **0** | **3/3** | 0,8 s |

Quan el 429 de Groq va activar el respostal local, el `qwen2.5:3b` va dir que el
veí assajava amb un **piano** quan a la memòria hi havia **trompeta**, i va
trigar 5,0 s de mediana. La conclusió és clara: **la invenció ve del cervell, no
de la memòria**. Per això el núvol és el primari i el local és el respostal.

## 6. Veu

| Motor | Frase | Síntesi | Pèrdua de volum |
|---|---|---:|---:|
| Edge `es-ES-XimenaNeural` | 8,04 s | 1,84 s | Normalitzada a 0,51 |
| Edge `es-ES-XimenaNeural` | 7,32 s | 2,29 s | 0,51 |
| Piper `es_ES-davefx-medium` | 2,14 s | **0,36 s** | 0,55 |

Edge sembla «més lent», però el sintetitzador treballa **mentre sona** la frase
anterior. En una resposta de 2-3 frases només es paga sencer l'arrencada de la
primera. Si Edge falla, Piper respon en ~0,36 s i Parker no es queda mut.

## 7. Cara i comportament

- Pantalla GC9A01 a **~16 fps** reals per SPI, sense HDMI ni escriptori.
- **12 principis de l'animació de Disney** aplicats de manera selectiva (anticipació, esvaïment, *squash*, etc.).
- **Director de gestos**: micro-cellera, curiositat, mirar amunt, cabotada,
  sospir, estirament, badall, doble presa i somriure.
- Tres famílies segons el silenci: despert → sol (1,5 min) → avorrit (8 min).
- Iniciativa pròpia als **15 min** de silenci, amb la cara en «pensant» abans de
  parlar.
- Música: *ducking* per distingir la cançó de la veu humana.

Aquestes dades són **qualitatives**: no hi ha un qüestionari que demostri que la
cara «transmet». Es descriuen com a observació de disseny i es proposa mesurar-ho
en una línia futura.

## 8. Proves

| Suite | Resultat |
|---|---|
| `test_cerebro_doble.py` | 14/14 |
| `test_agenda.py` | 10/10 |
| `test_bandit.py` | 5/5 |
| `test_personalidad.py` | 18 blocs en verd |
| `test_pipeline.py`, `test_conversacion.py` | En verd |
| Total | **24 fitxers** de prova |

No és correcte dir «tots els tests passen» sense matisar: alguns necessiten
maquinari i s'executen a la placa; d'altres són offscreen al PC. El que sí que
és cert: **cada arreglo important té un cas nou** que el protegeix.

## 9. Què no s'ha aconseguit

| Objectiu | Estat | Per què |
|---|---|---|
| Cervell local ràpid i lúcid | **No** | 8,75 s de TTFT a la placa; el 3b entén però no corre |
| Memòria de dades exactes | **Parcial** | Recupera el tema; falla 4/8 preguntes curtes |
| Privacitat total per defecte | **No** | El mode híbrid envia text i àudio; hi ha interruptor |
| LoRA de personalitat entrenat | **No** | Dissenyat i amb dades; falta entrenament i avaluació |
| Estudi d'usuaris | **No** | Mostra d'un sol usuari |
| Carcassa i refrigeració definitives | **Parcial** | Proves d'encastat; la calor limita el 3b |

Aquesta taula és la que dona credibilitat a la resta: **el treball no ven el que
no té**.

## 10. Conclusió en tres frases

1. El pipeline pot començar a parlar en **~1,6 s** en una placa de 8 GB, però
   només si la generació es fa al núvol.
2. La memòria local és **suficient per al tema** i **insuficient per al detall**;
   el sistema ha de saber dir «no ho sé».
3. La part més valuable no és cap model, sinó el **mètode** que va permetre
   passar de 15-20 s a 1,6 s mesurant cada etapa i documentant cada error.

## 11. Notes relacionades

- [[TREC/04 Metodologia i proves]] — com s'han obtingut aquestes dades.
- [[TREC/03 Marc practic]] — què s'ha construït.
- [[TREC/07 Conclusions]] — què volen dir.
- [[TREC/09 Redaccio de la memoria]] — on van aquestes taules.
