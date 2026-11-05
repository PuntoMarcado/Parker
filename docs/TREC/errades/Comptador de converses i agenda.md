---
tema: TREC
bloc: 5
estat: resolt
---
# El comptador de converses i l'agenda

[[TREC/06 Errades i solucions]] · [[agenda]] · [[TREC/05 Resultats]]

## Símptoma

A «Parker, canvia l'hora del dentista de demà a les 6 de la tarda», Parker va
contestar, literalment:

```
[Parker -> Voz] 100% (desde hace 12 días, 231 charlas).
```

No era una al·lucinació del model. Era una línia del **prompt** copiada tal qual.

Dies abans, una altra alarma s'havia desat amb aquesta matèria:

```
[Escucha] Transcripción: 'Parker pone una alarma a las 7 de la tarde.'
[Agenda] Alarma puesta para hoy a las siete en punto de la tarde: pone una.
```

## Context

- `parker.estado.json` tenia `interacciones: 324` i `charlas: 232`.
- El mode del cervell era `local` (no `auto`), desat d'una prova anterior.
- La versió era la v6.8.1; l'agenda existia des de la v6.3.0.

## Causes (eren quatre)

1. **El comptador pujava per torn.** `registrar_interaccion()` sumava una
   «charla» per cada frase des del primer prototip. El número no representava
   converses.
2. **El número viatjava al prompt.** La línia de víncle deia
   «100 % (des de fa N dies, M converses)». El model la recitava perquè era
   l'única dada social que tenia.
3. **No hi havia reprogramació.** «Canvia l'hora» no tenia cap pas previ; queia
   al model, que només veia la fitxa i responia amb el bloc de víncle.
4. **La matèria de l'alarma era soroll.** `_RUIDO_INICIAL` cobria «pon», però
   no la variant «pone» que va produir el STT.

## Comprovació

- Es va llegir el JSON real de la placa: `charlas: 232`, `interacciones: 324`.
- Es va reproduir la frase amb el mateix estat i el mateix prompt.
- Es va veure que la línia sortia **des del prompt**, no des del model.
- Es va comprovar `parker.cerebro.json` = `{"modo": "local"}`.

## Arreglo

### v6.9.0

- `AgendaParker._reprogramar()` s'executa **abans** de crear. Reconeix «canvia
  l'hora / de les 7 a les 8», busca per tipus, matèria i hora antiga, i mou
  l'avís sense duplicar-lo.
- El prompt deixa de portar el número de converses.
- `charlas` compta **converses amb un buit de 45 min**, no torns.

### v6.9.1

- La línia del prompt passa a ser només una pauta de to:
  «Pauta de tracte (no la mencionis): …», sense `%`, dies ni comptador.
- En carregar estats antics, `charlas` es corregeix amb un **sostre honest**:
  2 converses/dia des del primer contacte. Amb el JSON real: **232 → 25**,
  víncle 75 %, 12,97 dies. Es marca `charlas_version: 2` per no repetir-ho.
- `_RUIDO_INICIAL` accepta `pone/pones/ponle/ponlo/ponla/programame/haz`.
  «Parker pone una alarma» ja no deixa matèria.
- Si hi ha dues alarmes o cites i la frase no diu quina, **pregunta** en lloc de
  moure'n una a l'atzar.
- L'agenda tolera JSON truncat, `[]`, `null`, entrades que no són objectes,
  dates no numèriques, `NaN`, infinits i dates fora de 2000-2100.
- L'ànim es desa amb escriptura **atòmica** (`.tmp` + `replace`).

## Verificació

```
tests/test_agenda.py ........ 10/10
tests/test_personalidad.py .. tots en verd
tests/test_cerebro_doble.py . 14/14
tests/test_conversacion.py .. tots en verd
```

Casos nous:

- «Parker pone una alarma a las 7» → matèria buida.
- «Canvia l'alarma de les 7 a les 8» → una sola alarma, 20:00, conserva matèria.
- Dues cites + «canvia la del dentista» → mou només la del dentista.
- Dues alarmes + «canvia l'alarma» → pregunta; no en mou cap.
- Estat amb 232 converses i 12,9 dies → 25 converses, 75 %, versió 2.
- Agenda amb 7 entrades corruptes → només carrega la vàlida.

A la placa, la cita va quedar de veritat el 31/10 a les 18:00, una sola, i
l'alarma va passar de les 19:00 a les 20:00 sense duplicat.

## Lliçó

> **Tot el que poses al prompt és codi executable. Si no vols que ho digui, no
> ho hi posis.**

I una segona: **un comptador no és una mesura social**. Contar torns i dir-ne
«converses» va produir una dada falsa que el model va repetir amb total
convicció. La solució no va ser filtrar la frase, sinó **corregir el significat**
de la dada.

## Rastre

- `modulos/agenda.py` (`_reprogramar`, `_RUIDO_INICIAL`)
- `modulos/personalidad.py` (`charlas`, `contexto_volatil`)
- `modulos/cerebro.py` (línia de víncle)
- `tests/test_agenda.py`, `tests/test_personalidad.py`
- `docs/plan_mejoras.md` §«231 charlas y una agenda que se deja cambiar»
