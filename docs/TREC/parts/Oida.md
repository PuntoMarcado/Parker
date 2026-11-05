---
tema: TREC
bloc: 3
part: oida
estat: viu
---
# Oïda (STT)

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[rendimiento]]

## 1. Què és

És la part que converteix **àudio en text**. Inclou el micròfon, la detecció de
veu (VAD), el motor de transcripció i les reparacions posteriors. Sense un bon
text d'entrada, el millor cervell respon a una altra cosa.

## 2. Què deia el document original

El document descrivia un **torn manual**:

> «Quan s'inicia el programa el bucle principal de Pygame detecta quan es prem la
> barra espaiadora. En aquest moment, el fil principal envia un senyal a la cua
> per canviar la cara d'en Parker a l'estat escoltant. Activa el micròfon de
> l'ordinador per enregistrar l'ona de veu. L'àudio es captura en format digital
> un arxiu temporal en format .wav.»

És a dir: **no hi havia detecció de veu**. Hi havia un botó, un senyal i un
fitxer temporal. Era un torn de laboratori, suficient per provar la cadena.

## 3. Evolució

| Moment | Què es va fer | Resultat |
|---|---|---|
| Prototip | Barra espaiadora + `.wav` | Control total, però no era conversa |
| Primera placa | VAD continu; tall de silenci 1,3 s → **0,6 s** | Es pot parlar sense tocar res |
| 17/10/2026 | Whisper `small` → **`base` int8** | 4,8-5,3 s → **1,6-2,0 s** |
| 17/10/2026 | *Hotwords* (`Parker`) i correcció de noms | Millor reconeixement del nom |
| 25/10/2026 | **v6.1: STT al núvol** (`whisper-large-v3-turbo`) | **0,68 s** i text exacte |
| 25/10/2026 | Reparació conversacional | «No t'he entès» en lloc de respondre a l'atzar |
| 30/10/2026 | **v6.8.1: micròfon USB tardà** | Espera fins a 25 s, refresca PortAudio i sona un chime |
| 30/10/2026 | Vigilant del micròfon | Si l'entrada queda en silenci absolut, rearma el flux |

## 4. Com funciona avui

1. El micròfon USB entra per PortAudio.
2. El VAD detecta veu i obre un buffer.
3. En detectar veu, es preescalfa el prefix del cervell (no competeix amb
   Whisper).
4. En acabar, talla després de **0,6 s** de silenci.
5. Transcriu:
   - **Núvol** (`whisper-large-v3-turbo`): ~0,68 s, text exacte.
   - **Local** (`faster-whisper base` int8): 1,6-2,0 s, més errors.
6. Aplica *hotwords*, correcció de noms i reparació si la frase no té sentit.

## 5. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| «Li parlo i no reacciona» en encendre | El micro USB apareix ~29 s després; PortAudio cacheja la llista | Esperar, refrescar i avisar amb un chime |
| Transcripció dolenta que Parker repetia | L'«eco» citava la transcripció crua | Exigir 4+ paraules i una marca personal |
| Sords durant la música | El micròfon sentia l'altaveu | *Ducking* i escolta amb la cançó |
| Un torn deixava Parker sord | `ocupado` no s'alliberava | Alliberar sempre |
| Soroll de fons convertit en veu | VAD massa sensible | Llindar i tall de 0,6 s |

## 6. Evidència

- [[rendimiento]] §2 i §10: taules de STT local vs núvol.
- [[placa]]: el cas del micro USB i el registre de la placa.
- `modulos/escucha.py`, `tests/test_escucha_nube.py`,
  `tools/prueba_stt.py`.

## 7. Relacions

Alimenta el **Cervell**; comparteix maquinari amb la **Veu** (el micròfon pot
sentir l'altaveu); el dispositiu i PortAudio són a la **placa**. El diagrama de
dades és al [[TREC/parts/00 Index de les parts]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança.
