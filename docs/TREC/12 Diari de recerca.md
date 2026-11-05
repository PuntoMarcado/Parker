---
tema: TREC
bloc: 7
estat: viu
---
# 12 · Diari de recerca

> **Per què existeix.** La guia recomana portar un diari cronològic i adjuntar-lo
> als annexos: és la prova que el treball s'ha fet al llarg del temps i no la
> setmana abans. Aquesta cronologia s'ha reconstruït amb **evidències reals**
> (versions, logs, còpies i documents), no de memòria.

## 1. Com s'ha reconstruït

| Font | Què aporta |
|---|---|
| `modulos/version.py` | Data i descripció de cada versió |
| `docs/plan_mejoras.md` | Mesures, errors i decisions amb data |
| `docs/rendimiento.md` | Taules de latència i comparacions |
| `docs/historia.md` | Relat dels tres actes |
| `backups/` | Nom de cada còpia (data i etiqueta) |
| `docs/respaldos.md` | Índex del que hi ha a cada còpia |
| `docs/placa.md` §9 | Registre de la placa i lliçons |

**Nota honesta:** les dates d'agost i setembre són les del document original i
del prototip; no sempre hi ha hora exacta. On no hi ha evidència, es diu «sense
data documentada» en lloc d'inventar-la.

## 2. Cronologia

| Data | Fita | Evidència | Versió |
|---|---|---|---|
| **Agost 2026** | Es defineixen les quatre peces mínimes: cervell, oïda, memòria, cara. Es dissenya el doble cervell Groq + Ollama. | `docs/historia_original.md` | — |
| **11/08/2026** | Pressupost de 250 € i tres plans (augmentar pressupost, pantalla al costat del PC, assistent de cuina). | Document original, §7 | — |
| **Setembre-octubre 2026** | Prototip al PC: Pygame, barra espaiadora, Groq `llama-3.3-70b-versatile`, primeres cares de BMO. | `docs/historia.md` §3 | pre-v6 |
| **17/10/2026** | Primer pressupost de latència a la placa: **15-20 s → 4,2-4,7 s**. Es retallen silenci, STT, model, prompt i veu. | `docs/rendimiento.md` §2 | v5 |
| **17/10/2026** | Còpies de seguretat: `2026-10-17_1345` (punt de partida), `_1416_latencia-optimizada`, `_1504_latencia-cache-prefijo`. | `backups/`, `docs/respaldos.md` | v5 |
| **24/10/2026** | Es torna al **`qwen2.5:3b`** per criteri del propietari: «útil i que tardi» abans que «ràpid i ximple». `num_ctx: 2048`; TTFT p50 7,6 s. | `docs/rendimiento.md` §3.1 | pre-v6 |
| **24/10/2026** | Es descarta la NPU RKLLM: el guany no compensa la complexitat. Es corregeix el nom «Piper/Dipper» i el preescalfament del prefix. | `docs/rendimiento.md` §7-8 | pre-v6 |
| **25/10/2026** | **v6.0: doble cervell.** Núvol primari (`gpt-oss-20b`) + local de respostal. TTFT de ruta completa **1,23 s p50**. | `modulos/version.py` | v6.0.0 |
| **25/10/2026** | **v6.1: STT al núvol** (`whisper-large-v3-turbo`): 4,31 s → **0,68 s**. Reparació conversacional. | `docs/rendimiento.md` §10 | v6.1.0 |
| **25/10/2026** | **v6.2: òrdres directes sense LLM** (volum, silenci, xiulet) i regles contra accions físiques. | `modulos/version.py` | v6.2.0 / v6.2.1 |
| **26/10/2026** | **v6.3: agenda** (alarmes, temporitzadors, cites) amb avís real per l'altaveu. | `docs/agenda.md` | v6.3.0 |
| **26/10/2026** | **v6.4: el dia complet** — rutines, apunts, temps, música per API, bandit d'iniciativa, selecció automàtica de model. | `docs/dia.md` | v6.4.0 |
| **27/10/2026** | **v6.5: música amb orelles** — *ducking* per distingir la cançó de la veu; s'arregla el `ocupado` que deixava Parker sord. | `docs/plan_mejoras.md` | v6.5.0 |
| **27/10/2026** | **v6.6: fitxa que rota** — els gustos ja no es repeteixen cada torn; es protegeix el prefix cachetat. | `modulos/version.py` | v6.6.0 |
| **27/10/2026** | **v6.7: cervell per veu** — «ponte en local», «torna al núvol», avisos de caiguda; el mode sobreviu al reinici. | `docs/cerebro_doble.md` §6-bis | v6.7.0 |
| **27/10/2026** | **Mesura de memòria a fons**: 3.000 records = 10 MB i ~150 ms per consulta; 4 de 8 preguntes curtes no recuperen el fet. | `docs/plan_mejoras.md` §«La memoria, medida a fondo» | v6.7 |
| **27/10/2026** | **v6.8: cara amb vida** — director de gestos, tres famílies segons el silenci, iniciativa als 15 min. | `docs/arquitectura.md` §5 | v6.8.0 |
| **30/10/2026** | **v6.8.1: el micro arriba tard** — espera fins a 25 s, refresca PortAudio i sona un chime. | `docs/placa.md` | v6.8.1 |
| **30/10/2026** | **v6.9: comptador i agenda** — 232 «converses» → 25 converses; reprogramació de cites; tolerància a estats corruptes. | `docs/plan_mejoras.md` §«231 charlas» | v6.9.0 / v6.9.1 |
| **30/10/2026** | **v6.10: veu Edge** `es-ES-XimenaNeural` + Piper de respostal; normalització de volum. | `docs/rendimiento.md` §11 | v6.10.0 |
| **30/10/2026** | **v6.10.1: iniciativa amb llavor concreta**; **v6.10.2: frases amb sentit** i explicació sense LLM, també després de reiniciar. | `modulos/version.py` | v6.10.1 / v6.10.2 |
| **31/10/2026** | Es crea aquesta bòveda Obsidian: mapa, notes TREC, bitàcola d'errors i guia de redacció. S'hi afegeixen nou notes de parts i la matriu d'evolució. | Aquesta carpeta | v6.10.2 |
| **31/10/2026** | Es separen les quatre etapes de la cara en nodes propis (BMO, web, vectors, Qt/SPI) i es treuen els enllaços laterals de les parts perquè el graf mostri jerarquia, no una teranyina. | `TREC/parts/cara/`, [[TREC/parts/Cara]], [[TREC/Mapa de Parker.canvas]], `.obsidian/graph.json` | v6.10.2 |
| **01/11/2026** | **Reestructuració dels dos marcs**: teoria numerada 2.1–2.8 (token, atenció, TTFT, API, maquinari) i pràctica 3.1–3.11, amb errors i solucions a cada apartat i comparativa de placa i pantalla. | [[TREC/02 Marc teoric]], [[TREC/03 Marc practic]], [[TREC/parts/Maquinari i desplegament]] | v6.10.2 |
| **01/11/2026** | **v6.10.3: la cara no es congela** — candau d'instància única (`~/.parker.runtime.lock`), l'ordre «cambio el cerebro en local» ja es reconeix i un vigilant reinicia el panell GC9A01 si deixa de rebre fotogrames. Provat a la placa: 15 fps en repòs i 14–15 fps en un torn local; canvi local → automàtic per veu. | `docs/historia.md` §4.7, `modulos/display_spidev.py` | v6.10.3 |
| **01/11/2026** | **v6.12.6-v6.12.8: manteniment i fals eco** — «borra la memoria» (confirmació en 60 s) i «reiníciate» per veu; 90 records de prova esborrats amb `tools/recuerdos.py --borrar` i un record creat per veu es va borrar amb dues ordres (1 → 0). El prompt del STT incloïa preguntes entre «» i Whisper tornava `¿qué día es hoy?».`; el filtre ho descartava com a eco i Parker semblava sord. Es va treure el prompt del STT (també el neutre, que tornava `Parker se escribe Parker.`) i es neteja una comilla solta. Prova real: «Parker, ¿qué hora es?» → «Son las 8 y cuarenta y cinco de la noche»; reinici per veu 42828 → 43582. | `docs/dia.md` §2-bis, `tests/test_escucha.py`, `tests/test_escucha_nube.py`, `tests/test_rutinas.py`, `tests/test_pipeline.py` | v6.12.6 / v6.12.7 / v6.12.8 |
| **02/11/2026** | **Marc teòric simplificat**: s'elimina el bloc 2.2 (paràmetres, prefill, TTFT i comparació núvol/local) i el que és útil es fon dins de 2.1; la teoria passa a 2.1–2.7. Es treuen de la teoria les xifres que ja són al pràctic (STT/TTS, fps, pressupost) i la comparació de velocitat queda a §3.4. | [[TREC/02 Marc teoric]], [[TREC/03 Marc practic]], [[TREC/09 Redaccio de la memoria]] | v6.12.8 |
| **02/11/2026** | **Millores de memòria i suport emocional** — fets exactes en SQLite, memòria híbrida FTS5 + RRF, prosòdia i màquina d'estats d'ajuda (ESConv). TTFB p50 2,80 s amb i sense fets: l'objectiu <1 s queda pendent. | [[mejoras_noviembre2026]], `modulos/hechos.py`, `modulos/prosodia.py` | v6.12.16 |
| **02/11/2026** | **v6.12.17: turnos fantasma** — el VAD abría conversación con ruido de sala (rms 0,0015-0,0026) y Whisper lo convertía en «Gracias.» o «¡Suscríbete al canal!»; el eco del altavoz se colaba como «oído local, oído local». Se sube el mínimo de señal a 0,0035, se descartan los bloques repetidos y el eco reciente en el turno normal, y el monitor de barge-in aplica el mismo filtro. | [[mejoras_noviembre2026]], `parker.py`, `modulos/filtro_stt.py` | v6.12.17 |
| **02/11/2026** | **v6.12.18: modo local/online completo** — «modo local» y «modo online» ahora cambian cerebro, oído y voz; antes solo el cerebro y la voz seguía en Edge. El cambio parcial se pide con «cerebro local». | [[mejoras_noviembre2026]], `modulos/acciones.py`, `tests/test_acciones.py` | v6.12.18 |
| **02/11/2026** | **v6.12.19: blindaje de memoria** — `_borrar_memoria` y el turno usan `getattr` para `hechos`/`prosodia`; `test_pipeline` vuelve a verde. Auditoría de 30 tests: solo fallaba la limpieza de Chroma en Windows, corregida en `test_memoria_hibrida`. | [[mejoras_noviembre2026]], `parker.py`, `tests/test_memoria_hibrida.py` | v6.12.19 |

## 3. Els tres actes, en una línia cada un

1. **El paper (agost):** quatre peces, doble cervell, memòria vectorial i un
   pressupost de 250 €. Cap línia de codi.
2. **El prototip (setembre-octubre):** Pygame, barra espaiadora, Groq i BMO.
   La primera Parker que parlava, recordava i posava cares.
3. **El dispositiu (17-31 octubre):** Orange Pi, pantalla SPI, mesura de
   latència, doble cervell, agenda, veu natural i cara viva.

## 4. Què s'ha après a cada fase

| Fase | Error o sorpresa | Aprenentatge |
|---|---|---|
| Paper | El pla de «només Ollama» no preveia la lentitud de la placa | Cal mesurar el maquinari abans de decidir l'arquitectura |
| Prototip | El model responia coses ràpides però poc útils | Velocitat sense context no és conversa |
| Primera placa | 15-20 s era inviable | Cal descompondre la latència per etapa |
| Cervell local | 8,75 s de TTFT; la calor empitjora | El límit és el maquinari, no el model |
| Doble cervell | La nube dona 1,23 s, però envia text | La privacitat és una decisió amb contrapartides |
| Memòria | 4/8 preguntes curtes fallen | Cal dir «no ho sé» i desar fets, no transcripcions |
| Cara i veu | Etiquetes llegides, noms inventats, micro tardà | La frontera sistema/personatge s'ha de sanejar |

## 5. Plantilla per continuar el diari

Cada sessió de treball hauria d'afegir una fila:

```
Data:
Què volia aconseguir:
Què he fet:
Què he mesurat (abans → després):
Què ha fallat:
Què he après:
Quina versió/empremta queda:
Següent pas:
```

Aquesta plantilla és la mateixa que es fa servir a
[[TREC/06 Errades i solucions]] §5. Si no es pot omplir «què he mesurat», la
sessió no ha produït coneixement, només codi.

## 6. Com s'adjunta a la memòria

- **Annex I:** aquesta cronologia, en paper.
- **Annex II:** logs representatius (arrencada, torn complet, error del micro).
- **Annex III:** taules de mesures completes.
- **Annex IV:** captures del prototip i del mapa d'Obsidian.

No cal adjuntar milers de línies de log: **tres o quatre que demostrin el punt**
valen més que un fitxer enorme sense comentar. La guia diu que els annexos són
opcionals, però el diari és «molt aconsellable».

## 7. Notes relacionades

- [[TREC/01 Pla de recerca]] — el pla que aquest diari segueix.
- [[TREC/05 Resultats]] — les xifres de cada fita.
- [[TREC/06 Errades i solucions]] — els errors de cada fase.
- [[TREC/08 Annex. Criteris de muntatge]] — criteris de muntatge i traçabilitat.
