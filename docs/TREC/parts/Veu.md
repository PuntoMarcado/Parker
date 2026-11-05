---
tema: TREC
bloc: 3
part: veu
estat: viu
---
# Veu (TTS)

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[rendimiento]]

## 1. Què és

És la part que converteix **text en àudio**. Inclou el motor de síntesi, la
normalització de volum, la reproducció i la seva relació amb la música. És la
diferència entre «Parker contesta» i «Parker et parla».

## 2. Què deia el document original

El document no fixa el motor de veu; descriu el reconeixement (l'«oïda») i deixa
la veu com una peça més del sistema. Al prototip es va integrar **Piper**, un
sintetitzador local petit i ràpid, que després quedaria com a respostal.

## 3. Evolució

| Moment | Què es va fer | Resultat |
|---|---|---|
| Prototip | Piper local | Veu intel·ligible, una mica metàl·lica |
| Primera placa | Primera frase sintetitzada mentre el model segueix generant | La veu no espera la resposta sencera |
| 25/10/2026 | **v6.2.0**: ordres directes de volum i silenci | «Baja el volumen» sense LLM |
| 25/10/2026 | **v6.2.1**: percentatges exactes | «Al 33 %» fixa 33; rang 1-100 |
| 30/10/2026 | **v6.10.0**: Edge TTS `es-ES-XimenaNeural` | Veu molt més natural |
| 30/10/2026 | Piper com a respostal automàtic | Si Edge falla o no hi ha xarxa, no es queda mut |
| 30/10/2026 | Normalització de volum | Edge i Piper al mateix nivell percebut |

## 4. Com funciona avui

- **Motor principal:** Edge TTS, veu `es-ES-XimenaNeural`, per internet.
- **Respostal:** Piper `es_ES-davefx-medium`, local.
- **Temps:** Edge tarda 1,8-2,3 s per frase de 8 s, però sintetitza la frase
  següent mentre sona l'actual; Piper tarda ~0,36 s.
- **Caiguda:** si Edge no contesta en **8 s**, falla o no hi ha xarxa, entra
  Piper; es reintenta Edge al cap de **60 s**.
- **Volum:** 1-100; veu i música tenen volums independents.
- **Música:** *ducking* perquè el micròfon distingeixi la cançó de la veu.
- **Neteja:** abans de sintetitzar s'eliminen tokens, entitats HTML, valles de
  codi, JSON i etiquetes `cara:`.

## 5. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| La veu llegia `cara:bien` o els tokens de canal | Marcatge del model | Filtre abans de sintetitzar |
| «Â¿QuÃ©» en lloc de «¿Qué» | SSE llegit en ISO-8859-1 | UTF-8 |
| El volum no canviava | Ordres que queien al LLM | Òrdres directes i rang 1-100 |
| Parker deia «Dipper» | No era la veu: era el prompt | Treure «Piper» de la identitat |
| Silenci en la segona frase | ALSA ocupada per Parker | Dos reintents de 150/300 ms |
| Música massa alta sobre la veu | Un sol volum per a tot | Volums separats i *ducking* |

## 6. Evidència

- [[rendimiento]] §11: taula Edge vs Piper.
- [[TREC/errades/El nom i les etiquetes]]: marcatge i accents.
- `modulos/voz.py`, `tests/test_voz.py`, `tests/test_voz_edge.py`.
- `config.yaml` → `voz`.

## 7. Relacions

Rep el text del **Cervell**; el lip-sync és amb la **Cara**; els avisos i la
música són de l'**Agenda i el dia**; l'àudio pot tornar a l'**Oïda**. El
diagrama de dades és al [[TREC/parts/00 Index de les parts]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança.
