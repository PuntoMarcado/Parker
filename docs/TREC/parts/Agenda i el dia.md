---
tema: TREC
bloc: 3
part: agenda-dia
estat: viu
---
# Agenda i el dia

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[agenda]] · [[dia]]

## 1. Què és

És el conjunt de funcions que fan que Parker **serveixi per a alguna cosa més que
conversar**: alarmes, temporitzadors, cites, rutines, apunts, temps i música.
Totes viuen en local i es poden controlar per veu, sense tocar el mòbil.

## 2. Què deia el document original

No hi era. El document original descrivia cervell, oïda, memòria i expressions;
l'agenda i el dia a dia van néixer després, quan la base ja funcionava. La idea
era apropar-se al **company de sobretaula** que fa la seva vida, no a un
assistent de tasques.

## 3. Evolució

| Moment | Què es va afegir | Resultat |
|---|---|---|
| 26/10/2026 | **v6.3: agenda** | Alarmes («a les 7:30»), temporitzadors («en 10 minuts») i cites («el dentista dijous a les 5») |
| 26/10/2026 | **v6.4: el dia** | «Bona nit», «bon dia», «calla 10 minuts», «apaga't» |
| 26/10/2026 | Apunts i comptadors | Notes, llistes i «litres de agua» per veu |
| 26/10/2026 | Temps i ciutat | Open-Meteo; «estem a Madrid» canvia la ciutat |
| 26/10/2026 | Música | Deezer, fragments de 30 s, volum propi |
| 27/10/2026 | **v6.5: música amb orelles** | *Ducking* per distingir la cançó de la veu |
| 30/10/2026 | **v6.9: reprogramació** | «Canvia la cita del dentista a les 6» mou la cita existent |
| 30/10/2026 | **v6.9.1: agenda robusta** | JSON truncat, entrades corruptes, dues alarmes → pregunta quina |

## 4. Com funciona avui

### Agenda

- **Alarmes:** hora concreta; avís amb campana i frase.
- **Temporitzadors:** «en 10 minuts», «d'aquí a mitja hora».
- **Cites:** data + hora + titular curt («cita dentista»).
- **Consulta:** «què tinc demà?», «què tinc aquesta setmana?».
- **Canvi i esborrat:** «canvia l'hora…», «borra l'alarma…», «borra totes les
  alarmes».
- **Fitxer:** `parker.agenda.json`, només a la placa.
- **Fil propi:** comprova cada segon; espera que Parker no estigui parlant.

### Rutines i apagada

- «Bona nit» / «bon dia» amb part del dia.
- «Calla 10 minuts».
- «Apaga't»: comiat, desada i apagada de la placa; després només cal
  desconnectar el cable.

### Apunts i comptadors

- «Apunta que…», «afegeix a la llista…», «quants litres porto?».
- Parker crea i esborra les seves pròpies variables sense tocar codi.

### Temps

- Open-Meteo, sense clau.
- Ciutat configurable per veu i confirmació amb la zona.

### Música

- Deezer per API, sense clau; fragments de 30 s amb `ffmpeg`.
- «Posa música», «para la música», «següent».
- Volum independent del de la veu; *ducking* mentre parla.

## 5. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| «Parker pone una alarma» desava «pone una» | La llista de soroll no cobria «pone» | Ampliar `_RUIDO_INICIAL` |
| «Canvia la cita» creava'n una altra | No hi havia pas de reprogramació | `_reprogramar()` abans de crear |
| «231 charlas» | Comptador per torn al prompt | Comptar converses i treure el número |
| No escoltava amb música | El micro sentia l'altaveu i el torn no s'alliberava | *Ducking* + alliberar sempre |
| El volum no canviava | Ordres que queien al LLM | Òrdres directes i percentatges exactes |
| L'agenda es corrompia | JSON sense tolerància | Càrrega robusta i escriptura atòmica |

## 6. Evidència

- [[agenda]]: comandaments, proves i límits.
- [[dia]]: rutines, apunts, temps, música i apagada.
- `tests/test_agenda.py` (10/10), `tests/test_acciones.py`,
  `tests/test_musica.py`, `tests/test_dia.py`, `tools/probar_agenda.py`.

## 7. Relacions

Els avisos sonen per la **Veu**; l'apagada és real al **Maquinari**; la
iniciativa no és una alarma (és de la **Personalitat**). El cas del comptador és
a [[TREC/errades/Comptador de converses i agenda]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança; el diagrama de dades és al [[TREC/parts/00 Index de les parts]].
