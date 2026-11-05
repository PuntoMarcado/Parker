---
tema: TREC
bloc: 5
estat: esborrany
---
# 06 · Errades i solucions

> **Per què això és material de TREC i no un simple registre.** Cada error és una
> hipòtesi que es va poder comprovar. La taula mostra el cicle complet:
> **símptoma → causa → arreglo → versió → prova**. Les cinc notes enllaçades
> desenvolupen els casos que més ensenyen.

## 1. Taula mestra

| # | Símptoma | Causa real | Solució | Versió | Detall |
|---|---|---|---|---|---|
| 1 | La pantalla circular es queda en blanc | Seqüència d'inicialització SPI incompleta (faltaven taules de gamma i la inversió `0x21`) | Completar la init i validar amb patrons de color | pre-v6 | [[TREC/errades/Pantalla SPI en blanc]] |
| 2 | Dues veus, micro que no respon, `Device or resource busy` | Dues instàncies de `parker.py` competint pel micro i pel SPI | Lock al llançador; no arrencar a mà; reiniciar només matant el procés | operatiu | [[TREC/errades/Dues instancies i el micro]] |
| 3 | «Li parlo i no reacciona» en encendre | El micro USB apareix ~29 s després; PortAudio cacheja la llista i es queda amb el còdec intern | Esperar fins a 25 s, refrescar PortAudio i sonar un chime | v6.8.1 | [[TREC/errades/Dues instancies i el micro]] |
| 4 | Parker diu «Dipper» / un nom estrany | El prompt deia «Piper els deletreja» i el model ho va prendre com el nom de l'usuari | Treure «Piper» del prompt, corregir vocatius i sanejar abans de l'historial | 24/10 | [[TREC/errades/El nom i les etiquetes]] |
| 5 | La veu llegeix etiquetes (`cara:bien`), tokens de canal i accents rars | Marcatge del model i SSE llegit en ISO-8859-1 | UTF-8 + filtre de marcatge i etiquetes abans de sintetitzar | v6.0.1 i ajustos | [[TREC/errades/El nom i les etiquetes]] |
| 6 | «100 % (desde hace 12 días, 231 charlas)» | El comptador pujava per torn i el número viatjava al prompt | Comptar converses (buit de 45 min), treure el número del prompt i corregir estats antics | v6.9.0 / v6.9.1 | [[TREC/errades/Comptador de converses i agenda]] |
| 7 | «Parker pone una alarma» → matèria «pone una» | La llista de soroll inicial no cobria la variant «pone» | Ampliar `_RUIDO_INICIAL`; no deixar matèria si no n'hi ha | v6.9.1 | [[TREC/errades/Comptador de converses i agenda]] |
| 8 | «Canvia la cita del dentista» crea una cita nova | No hi havia pas de reprogramació; l'ordre anava al model | `_reprogramar()` abans de crear; buscar per tipus, matèria i hora | v6.9.0 | [[TREC/errades/Comptador de converses i agenda]] |
| 9 | Frases automàtiques sense sentit; en preguntar, una explicació incoherent | Plantilles que convertien manies en creences; «eco» de transcripcions dolentes; la frase no persistia | Semilla concreta, filtre d'eco, no repetir, desar l'última iniciativa i respondre sense LLM | v6.10.1 / v6.10.2 | [[TREC/errades/Frases automatiques]] |
| 10 | No escolta durant ni després de la música | Un torn nascut de la cançó no alliberava `ocupado` | Alliberar sempre; *ducking* per distingir cançó de veu | v6.5.0 | `plan_mejoras.md` §«La escucha con música» |
| 11 | El proveïdor retira el model i Parker es queda sense cervell | Model fix a `config.yaml` | Consultar `/models` i triar alternativa de la llista | v6.4.0 | [[dia]] §6 |
| 12 | Pics de 24 s de TTFT | El preescalfament competia amb Whisper | Preescalfar en detectar veu, no en transcriure | 24/10 | [[rendimiento]] §8 |
| 13 | El volum no canviava o tornava boig | Ordres amb `\b` que queien al LLM; percentatges no reconeguts | Òrdres directes sense LLM; rang 1-100; respostes amb el valor real | v6.2.0 / v6.2.1 | `plan_mejoras.md` §«Corrección del volumen» |
| 14 | Promet accions físiques («t'apago el llum») o diu que xiula i no xiula | El model omplia buits; no hi havia xiulet real | Regla «no tens cos» + xiulet sintetitzat + proves | v6.2.0 | `plan_mejoras.md` |
| 15 | 4 de 8 records no es recuperen | Llindar fix i *embedding* petit; preguntes de 3 paraules | Documentat; top-k i marge pendents | límit | [[TREC/05 Resultats]] §5 |
| 16 | El 3b local inventa (piano per trompeta) | Model petit sense prou context, activat pel 429 | Núvol primari; local com a respostal; dir «no ho sé» | v6.0 | [[TREC/05 Resultats]] §5.4 |
| 17 | La cara es congela i l'ordre «cambio el cerebro en local» no fa res | El patró de veu només acceptava «cambia al cerebro local»; a més, dues instàncies podien competir pel SPI i el micro | Ampliar el patró; candau d'instància a `~/.parker.runtime.lock`; vigilant del panell i latit del fil gràfic | v6.10.3 | [[TREC/errades/Dues instancies i el micro]], `historia.md` §4.7 |
| 18 | Li parles i no reacciona; el log diu `Eco del prompt de sesgo; ignoro` | El `initial_prompt` incloïa preguntes entre «»; Whisper tornava `¿qué día es hoy?».` (només el tancament) i el filtre descartava el torn sencer. Amb un prompt neutre tornava `Parker se escribe Parker.` | Treure el prompt del STT; netejar una comilla solta; descartar només el parell «…» | v6.12.7 / v6.12.8 | `dia.md` §2-bis |
| 19 | Després de «Parker, para» la veu calla però no torna a escoltar | El `for delta` només mirava l'ordre quan arribava un token; si el model callava, el torn quedava bloquejat. Tancar el generador mentre el fil lector el llegia llançava `generator already executing` | Fil lector + cua amb espera de 0,2 s; `preparar_turno()`; descartar àudio del torn tallat | v6.12.10 | [[jarvis\|Mejoras Jarvis]] |
| 20 | Contesta a «Gracias por ver el video», «¡Suscríbete al canal!» o «¡Ah!» | Whisper al·lucina amb soroll o amb la cua de l'altaveu; no hi havia filtre | `verbose_json` + `modulos/filtro_stt.py`: frases conegudes, interjeccions, repeticions i senyals fortes (`no_speech`, logprob, compressió) | v6.12.11 / v6.12.13 | [[jarvis\|Mejoras Jarvis]] §5 |
| 21 | Després de parlar, el micro dóna `Device unavailable` | El monitor de barge-in podia seguir transcrivint la seva última finestra amb l'`InputStream` obert | Esperar fins a 5 s el monitor abans de reobrir el micro | v6.12.12 | [[jarvis\|Mejoras Jarvis]] §5 |

## 2. Els cinc casos que cal saber explicar

No tots els errors tenen la mateixa profunditat. Aquests cinc són els que millor
mostren com es treballa:

### 2.1 La pantalla no és «màgia»

[[TREC/errades/Pantalla SPI en blanc]] — Un error de **hardware i programari
alhora**: el controlador GC9A01 necessita una seqüència d'inicialització
concreta. Sense les taules de gamma i la inversió, la pantalla s'encén però no
mostra res. La lliçó: **un bus que respon no vol dir que el dispositiu estigui
configurat**.

### 2.2 Dues instàncies i un micro que arriba tard

[[TREC/errades/Dues instancies i el micro]] — Dos problemes diferents que es
confonen amb «Parker s'ha penjat». La lliçó: **abans de tocar codi, comprovar
quants processos hi ha i des de quan existeix el dispositiu d'àudio**.

### 2.3 Un comptador que es va convertir en diàleg

[[TREC/errades/Comptador de converses i agenda]] — El model no va al·lucinar: va
copiar el prompt. La lliçó: **tot el que poses al prompt és codi executable**;
si no vols que ho digui, no ho hi posis.

### 2.4 El nom i les etiquetes

[[TREC/errades/El nom i les etiquetes]] — Una paraula tècnica («Piper») va
acabar sent el nom de l'usuari; una etiqueta interna va acabar llegida en veu
alta. La lliçó: **la frontera entre el sistema i el personatge s'ha de sanejar
abans de parlar**.

### 2.5 Frases automàtiques amb sentit

[[TREC/errades/Frases automatiques]] — Les plantilles podien generar
«Creo que ordeno las palabras antes de decirlas»; el «eco» repetia
transcripcions dolentes. La lliçó: **una frase espontània necessita una raó
concreta** (l'hora, un record, una proposta), no una instrucció oberta.

## 3. Errors de disseny que no són bugs

Hi ha coses que no s'arreglen amb una línia i que, per tant, van a les
limitacions:

| Decisió | Per què no és un error | Conseqüència |
|---|---|---|
| Enviar text al núvol | És un intercanvi conscient per tenir ~1,6 s | Cal declarar-ho i oferir el mode local |
| Usar un *embedding* petit | Cap en 384 dimensions no separa millor en aquest maquinari | El detall exacte falla; el tema s'encerta |
| Mantenir el 3b local | Entén millor el context que l'1.5b | 8,75 s de TTFT; és el respostal, no el titular |
| No entrenar LoRA encara | Requereix dades, GPU i avaluació | La personalitat es fa amb prompt, no amb pesos |
| No descarregar Wikipedia | 10 GB a la targeta i cap millora de resposta | S'usa la consulta puntual, no un corpus enorme |

## 4. El que s'ha après sobre el procés

1. **Mesurar abans de tocar.** La sensació «va lent» pot ser el mode local
   activat, el micro equivocat o la temperatura; sense log, s'arregla el que no
   toca.
2. **Un canvi alhora.** Barrejar model, prompt i STT impedeix saber què ha
   funcionat.
3. **L'estat és una font d'errors.** `parker.estado.json`,
   `parker.cerebro.json` i `parker.agenda.json` sobreviuen als reinicis: un valor
   antic pot semblar una al·lucinació.
4. **El prompt és codi.** Un número, una paraula o una etiqueta poden sortir per
   la boca del personatge.
5. **Cada arreglo necessita una prova.** Sense test, el mateix error torna tres
   versions després.
6. **La versió i l'empremta no són decoració.** Permeten saber si el que corre a
   la placa és el que s'ha provat al PC.
7. **Les còpies, al PC.** La targeta de la placa és per als records, no per als
   *backups*.

## 5. Com es documenta un error (plantilla)

Per als annexos i el diari de recerca:

```
### Símptoma
Què es veu o es sent, amb la frase o el log literal.

### Context
Versió, mode (núvol/local), hora, estat de la placa, què s'havia canviat.

### Hipòtesi
Una sola causa probable, formulada de manera comprovable.

### Comprovació
Log, prova o instrument que confirma o descarta la hipòtesi.

### Arreglo
Què s'ha canviat, en quin fitxer i per què.

### Prova
Test o protocol que impedeix que torni.

### Lliçó
Què s'ha après i com afecta el disseny.
```

Aquesta plantilla és la mateixa que s'ha fet servir a les cinc notes
detallades. Si un error no es pot omplir fins al final, encara no s'ha
entès.
