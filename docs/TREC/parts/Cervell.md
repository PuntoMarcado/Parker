---
tema: TREC
bloc: 3
part: cervell
estat: viu
---
# Cervell

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[cerebro_doble]]

## 1. Què és

És la part que **decideix què dir**. No és la personalitat (que decideix *com* i
*quan* dir-ho) ni la memòria (que aporta *què sap* de tu). El cervell rep un text
—la teva frase, l'ànim, tres records i l'historial recent— i genera una resposta
en streaming.

## 2. Què deia el document original

El document del 11/08/2026 dissenyava un **doble cervell**:

- **Groq** al núvol: ràpid, però depèn d'internet, del cost i dels límits.
- **Ollama** en local: sense xarxa i sense treure dades de casa, però lent en un
  miniordinador.

La motivació escrita era no deixar l'usuari «incomunicat» si fallava la xarxa.
Durant el prototip es va simplificar a **només Groq**, amb
`llama-3.3-70b-versatile`, per centrar-se en memòria, veu i expressions. Després
es va decidir **descartar el doble cervell i quedar-se només amb Ollama**, per
privacitat, cost i complexitat. El quart capítol no era al paper: quan es va
mesurar Ollama a la placa, el doble cervell va tornar.

## 3. Evolució

| Moment | Què es va fer | Per què | Resultat |
|---|---|---|---|
| Agost 2026 | Paper: Groq + Ollama | Disponibilitat i privacitat | Disseny |
| Prototip | Només Groq `llama-3.3-70b` | Simplificar mentre es construïa la resta | Funcionava, però depenia de la xarxa |
| 17/10/2026 | `qwen2.5:1.5b` local | Baixar la latència | 0,9-1,9 s de TTFT, però respostes curtes i fràgils |
| 24/10/2026 | Tornada al `qwen2.5:3b`; `num_ctx: 2048` | «Útil i que tardi» abans que «ràpid i ximple» | TTFT p50 **8,75 s** a la placa; el coll era la placa |
| 25/10/2026 | **v6.0: doble cervell** | La placa posa oïda, memòria, veu i cara; el núvol només redacta | Ruta completa **1,23 s p50**; núvol `gpt-oss-20b` |
| 27/10/2026 | **v6.7: canvi per veu** | Poder triar núvol/local sense tocar configuració | Mode persistit a `parker.cerebro.json` |
| 30/10/2026 | Model alternatiu automàtic | Els proveïdors retiren models | Consulta `/models` i tria de la llista |
| 30/10/2026 | **v6.9.1 / v6.10.2** | El prompt portava comptadors i frases que el model recitava | Prompt net; menys fugues |

## 4. Com funciona avui

- **Primari: núvol.** Groq amb `openai/gpt-oss-20b`. Només rep **text**:
  identitat, ànim, tres records retallats, vuit missatges d'historial i la
  pregunta.
- **Respostal: local.** Ollama amb `qwen2.5:3b`, `num_ctx: 2048`, 4 fils.
  Entén millor el context que l'1.5b, però triga 8-13 s.
- **Modes:** `auto` (núvol + respostal), `nube`, `local`. Es canvien per veu:
  «ponte en local», «torna al núvol», «mode automàtic».
- **Caiguda:** si no hi ha xarxa, si el proveïdor dona 429 o si el model ha
  desaparegut, respon el local. Parker avisa **una vegada** per caiguda.
- **Longitud:** `max_oraciones: 3` (el tall real), `max_tokens` 160 al núvol i
  100 al local. El prompt demana una o dues frases.
- **Temperatura:** 0,6 al núvol; 0,45 al local (restaurada el 24/10 perquè 0,35
  tornava les respostes rígides).

## 5. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| Pics de 24 s de TTFT | El preescalfament competia amb Whisper | Llançar-lo en **detectar veu**, no en transcriure |
| El 3B «es confonia» amb contexts llargs | `num_ctx: 1024` retallava el prompt | Pujar a 2048 |
| El model recitava «231 charlas» | El comptador viatjava al prompt | Treure el número; comptar converses |
| El 3B deia «piano» per «trompeta» | Model petit sense context suficient | Núvol primari; local com a respostal |
| El mode local sobrevivia al reinici | `parker.cerebro.json` desava l'última ordre | Comprovar el mode al log després de desplegar |
| El proveïdor va retirar el model | Model fix a `config.yaml` | Llista d'alternatius + `/models` |

## 6. Evidència

- [[rendimiento]] §3, §7, §8 i §9: taules de TTFT i comparació de models.
- [[cerebro_doble]]: arquitectura, modes, avisos i privacitat.
- `tests/test_cerebro_doble.py` (14/14) i `tests/test_pipeline.py`.
- `tools/eval_cerebro.py` i `tools/bakeoff.sh`.

## 7. Relacions

La seva entrada és l'**Oïda**; la sortida, la **Veu**; els records venen de la
**Memòria**; el to el posa la **Personalitat**; el model local corre a la
**placa**. El diagrama de dades és al [[TREC/parts/00 Index de les parts]].

Aquestes relacions no es converteixen en enllaços laterals perquè el graf no
dibuixi una teranyina de «sembla que hi va»: la jerarquia és índex → part, i les
dependències són al diagrama.
