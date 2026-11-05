---
tema: TREC
bloc: 5
estat: resolt
---
# Frases automàtiques sense sentit

[[TREC/06 Errades i solucions]] · [[TREC/03 Marc practic]] · [[evolucion]]

## Símptoma

Quan Parker parlava pel seu compte (als 15 min de silenci), deia coses com:

- «Creo que ordeno las palabras antes de decirlas.»
- «Una de las cosas que me gustan: las listas: tengo una de cosas que empiezan
  por P…»
- «Me acuerdo de que me contaste: “dipre oscuro o algo”. ¿Sigue siendo así?»
  (quan la transcripció havia estat dolenta)

I si li preguntaves «què has dit?», la resposta **tampoc** tenia sentit: el model
s'inventava el motiu.

## Causes (eren quatre)

1. **Les manies es presentaven com a creences.** La plantilla deia «Crec que…» +
   una mania. «Crec que ordeno les paraules abans de dir-les» és una frase
   gramaticalment correcta i semànticament buida.
2. **Els gustos es tallaven malament.** Una entrada amb dos punts
   («Una de les coses que m'agraden: les llistes: …») produïa una enumeració
   sense fi.
3. **L'«eco» repetia la transcripció crua.** Si el STT havia entès malament,
   Parker ho citava com una confidència.
4. **La frase espontània no es desava.** `_ultima_iniciativa` vivia només en
   memòria; després d'un reinici no hi havia manera de saber què havia dit ni
   per què. El model omplia el buit.

## Comprovació

- Es va llegir el log de la placa: les frases noves no hi apareixien perquè
  l'última versió encara no s'havia desplegat.
- Es va reproduir la generació amb la fitxa i la instrucció oberta: el 3B
  responia amb «zumbidos», «lluvia» i metàfores.
- Es va simular un reinici i es va preguntar per la frase: el model va inventar
  una explicació plausible, però falsa.

## Arreglo

### v6.10.1 — una raó concreta

Les frases automàtiques ja no neixen d'una instrucció oberta. Surten d'una
**llavor concreta**:

| Braç | D'on surt la frase |
|---|---|
| `contar` | Una entrada de la fitxa (gust, record, mania) |
| `preguntar` | Una pregunta breu del banc |
| `proposar` | Una proposta del banc |
| `eco` | L'últim missatge de la persona, si és una confidència reconeixible |
| `callar` | No es diu res |

La fitxa es va netejar de gustos abstractes que alimentaven espirals. I si
pregunten per la frase, el model rep el **motiu real**, no l'ha d'improvisar.

### v6.10.2 — que la frase tingui sentit i es pugui explicar

- Les manies **no** es presenten com a creences: es diu «quan ningú mira…», no
  «crec que…».
- Els gustos es retallen abans de `:` o `;` i a 110 caràcters.
- L'«eco» exigeix **4+ paraules i una marca personal** (`me`, `mi`, `he`, `hoy`,
  `ayer`…); si no, cau en una pregunta petita.
- No es repeteix la mateixa frase dues vegades seguides.
- La **última frase espontània es desa a la fitxa** (no només en RAM). Després
  d'un reinici, Parker sap què va dir i per què.
- El reconeixement de «¿qué has dicho?», «¿a qué viene eso?», «¿por qué dices
  eso?» és més ampli i es respon **sense LLM**, de manera determinista.

## Verificació

`tests/test_personalidad.py` (18 blocs en verd) inclou:

- Frases de cada braç amb sentit.
- Un cas que simula un reinici i comprova que Parker explica la frase exacta.
- Cap repetició consecutiva.
- Cap eco d'una transcripció sense marca personal.
- La reparació («no tiene sentido») respon amb una frase curta, no amb una
  excusa llarga.

A la placa, amb la v6.10.2 desplegada:

```
contar    A veces repaso las palabras nuevas que aprendí.
          Me gustaría que mis recuerdos no se borren nunca.
preguntar ¿Qué tal ha ido el día?
proponer  ¿Te cuento algo y me cuentas algo tú?
eco       (transcripción mala) -> ¿Qué tal ha ido el día?
explica   Te contaba: «Una de las cosas que me gustan: las noches tranquilas».
          Me apetecía compartir algo mío contigo.
```

## Lliçó

> **Una frase espontània necessita una raó concreta; si no, és soroll amb veu
> de persona.**

I una segona, específica dels sistemes amb estat: **si el personatge ha de
poder explicar què ha dit, el «què» i el «per què» s'han de desar junts**. La
memòria del model no n'hi ha prou.

## Límit honest

Els bancs de preguntes i propostes són de quatre frases cada un; la varietat és
finita. I si es pregunta per una frase dita **abans** d'aquesta versió, no hi ha
registre: la consulta passa pel model. Les següents ja queden totes desades.

## Rastre

- `modulos/personalidad.py` (`semilla_iniciativa`, `_recorte_decible`, eco)
- `modulos/cerebro.py` (`hablar_proactivo`, `explicar_iniciativa`)
- `tests/test_personalidad.py`
- `docs/plan_mejoras.md` §v6.10.1 i §v6.10.2
- `modulos/version.py` (historial)
