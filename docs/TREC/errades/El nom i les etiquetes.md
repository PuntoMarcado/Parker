---
tema: TREC
bloc: 5
estat: resolt
---
# El nom del personatge i les etiquetes

[[TREC/06 Errades i solucions]] · [[arquitectura]] · [[TREC/03 Marc practic]]

Aquest cas és el millor exemple de com **una paraula tècnica es converteix en un
tret de personalitat** si no es controla la frontera.

## Part A · «Dipper» / «Piper»

### Símptoma

Parker va saludar l'usuari amb un nom estrany:

```
[Parker -> Voz] ¡Oh! Claro, eres tú, Piper.
```

L'usuari ho va descriure com «em diu Dipper o una cosa així». El nom no venia de
la memòria ni de l'usuari: venia del **prompt**.

### Causa

La identitat contenia una instrucció contra els farcits:

```
No escribas rellenos como "mmm": Piper los deletrea.
```

El model de 3B va interpretar «Piper» com un **nom propi** i el va assignar a la
persona. A més, un cop inventat, el nom es desava a l'historial i es reforçava
torn a torn.

### Arreglo

Tres defenses, totes necessàries:

1. **Treure «Piper» del prompt.** La frase passa a «la veu els deletreja». Hi ha
   un test que falla si la paraula torna a aparèixer a la identitat.
2. **Corregir vocatius.** `corregir_nombre()` substitueix noms aliens després
   d'un salutació o de «tú,»: «¡Hola, Piper!» → «¡Hola, Alan!».
3. **Sanejar abans de l'historial.** La correcció s'aplica a `cerebro` **abans**
   de desar el torn. Si no, el nom dolent es converteix en context i el model el
   repeteix amb més força.

### Verificació

- El test d'identitat falla si apareix «Piper».
- Un torn amb «Hola, Piper» es converteix en «Hola, Alan» abans de la veu.
- L'historial no conté el nom inventat.

## Part B · Les etiquetes llegides en veu alta

### Símptoma

La veu llegia coses que no són diàleg:

- `cara:bien`
- `<|channel|>`
- entitats HTML (`&amp;`)
- valles de codi i JSON
- accents trencats: «Â¿QuÃ©» en lloc de «¿Qué»

### Causes

1. **Codificació.** El *stream* SSE es llegia en ISO-8859-1; els accents
   arribaven dobles a la síntesi. Es va passar a **UTF-8** (v6.0.1).
2. **Marcatge del model.** Els tokens especials i les etiquetes internes no es
   filtraven abans de la veu.
3. **Fuita d'etiquetes de la cara.** El model o el codi emetien `cara:bien` com
   a text; la veu ho pronunciava.

### Arreglo

- Llegir l'SSE en **UTF-8**.
- Filtrar abans de sintetitzar: tokens `<|…|>`, entitats HTML, valles de codi,
  JSON i etiquetes `cara:`.
- No deixar que les etiquetes arribin al text que es desa a l'historial.
- Provar amb una frase que contingui accents, cometes i símbols.

### Verificació

- La frase «¿Qué tal?» sona correcta, sense «Â».
- `cara:bien` no es pronuncia.
- El text de la veu i el de l'historial coincideixen (sense marcatge).

## Per què les dues parts van juntes

Totes dues són **fuites de la capa de sistema cap a la capa de personatge**:

| Capa | Hauria de quedar-se | Si fuites… |
|---|---|---|
| Prompt | Instruccions internes | El model les recita o les converteix en noms |
| Marcatge | Metadades per al codi | La veu les llegeix |
| Etiquetes de cara | Senyals per a l'animació | Es barregen amb el diàleg |
| Historial | Només diàleg net | L'error es reforça |

## Lliçó

> **La frontera entre el sistema i el personatge s'ha de sanejar abans de
> parlar.**

No n'hi ha prou amb filtrar la sortida: cal filtrar **l'entrada** (el prompt),
**el mitjà** (la codificació) i **la memòria** (l'historial). Si una sola capa
queda oberta, el personatge acaba dient coses que no són seves.

## Rastre

- `modulos/cerebro.py` (`corregir_nombre`, filtres de marcatge)
- `modulos/voz.py` (neteja abans de sintetitzar)
- `config.yaml` (identitat)
- `tests/test_conversacion.py`, `tests/test_personalidad.py`
- `docs/rendimiento.md` §8
