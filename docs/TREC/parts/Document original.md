---
tema: TREC
bloc: 3
part: document
estat: tancat
---
# Document original

[[TREC/parts/00 Index de les parts]] · [[TREC/01 Pla de recerca]] · [[historia_original]] · [[historia]]

## 1. Què és

És el **text que el projecte tenia abans del codi**: el plantejament inicial, el
prototip al PC i les dues primeres actualitzacions del treball acadèmic. Es
conserva literal, en català, a `historia_original.md`, amb la redacció i
l'ortografia originals (inclosos els apartats que van quedar buits).

**Data de la segona actualització:** 11 d'agost de 2026.

## 2. Què hi ha dins

| Apartat | Contingut |
|---|---|
| 3.1 El cervell | Doble cervell Groq + Ollama; per què; simplificació a Groq; decisió de quedar-se només amb Ollama |
| 3.2 Reconeixement de veus | Barra espaiadora, senyal per la cua, `.wav` temporal |
| 3.3 Memòria | ChromaDB, RAG i el diari vectorial; segona actualització amb tres canvis |
| 3.4 Expressions | Imatges de BMO → pàgina web local → cara vectorial; intenció d'animar |
| 4. Disseny físic | Inversor, 250 €, decisió local vs satèl·lit |
| 5. Construcció | Prototip amb cervell, expressions i escolta; memòria pendent |
| 7. Limitacions | Pressupost de 250 €; tres plans (ampliar, pantalla al costat del PC, cuina) |

Les frases clau es poden citar directament; per exemple:

> «La creació de Parker va començar sense ordinador ni codi ni cap tecnologia, el
> primer que es va fer va ser estructurar de les funcions mínimes que hauria de
> tenir per considerar-se un projecte funcional.»

Aquesta frase és l'origen del [[TREC/01 Pla de recerca|pla de recerca]]: primer
les funcions, després el codi.

## 3. Com ha evolucionat el document

| Etapa | Què afegeix |
|---|---|
| Text inicial | Quatre peces mínimes; doble cervell; memòria; expressions; prototip; limitacions |
| 2a actualització (11/08/2026) | Memòria multilingüe i llindar flexible; tres llenguatges visuals; pressupost de 250 € i tres plans |
| `historia.md` (30/10/2026) | Uneix el text original amb les mesures reals, les dates i els enllaços al codi |
| Aquesta bóveda (31/10/2026) | Ordena el text per blocs, parts i evidències per al TREC |

El document original **no s'ha tocat**. Les correccions i les dades noves van a
`historia.md` i a les notes del TREC, no al text font.

## 4. Què es va conservar i què va canviar

| Idea del document | Què va passar de veritat | On és avui |
|---|---|---|
| Doble cervell Groq + Ollama | Es va descartar al paper; **va tornar a la v6.0** en mesurar 8,75 s | [[TREC/parts/Cervell]] |
| Només Ollama | Es va intentar; el límit era la placa | Mode `local` i respostal |
| `llama-3.3-70b-versatile` | El proveïdor rota models; cal no dependre'n | `gpt-oss-20b` + alternatius |
| Raspberry Pi | El dispositiu real és una **Orange Pi 5 Pro** | [[TREC/parts/Maquinari i desplegament]] |
| Pygame + barra espaiadora | Escolta contínua per VAD; PySide6 | [[TREC/parts/Oida]] |
| Imatges de BMO | Cara vectorial amb 12 principis i SPI | [[TREC/parts/cara/1 BMO (imatges)]] → [[TREC/parts/cara/4 Cara actual (Qt i SPI)]] |
| Memòria en anglès i llindar 75 % | MiniLM multilingüe, 0,58 i només missatge d'usuari | [[TREC/parts/Memoria]] |
| Memòria «pendent» | Implementada i en ús | `parker.db/` |
| 250 € i tres plans | Forma del pla 2, sense dependre del PC | [[TREC/03 Marc practic]] §3.1.5 |
| Asistent de cuina | No construït; sí la base per parlar-hi | Línia futura |

## 5. Per què és important per al TREC

1. **És la font de la Introducció**: motivació, idea i objectius no s'inventen;
   surten d'aquí.
2. **Permet distingir el pla del resultat**: la memòria no pot dir que el doble
   cervell «sempre va ser la idea» sense explicar que es va descartar i per què
   va tornar.
3. **Justifica la metodologia**: el text ja parlava de funcions mínimes, prototip
   i actualitzacions; el TREC hi afegeix la mesura.
4. **És una peça d'autoria**: el document és propi; copiar-lo literalment a la
   memòria també seria un problema, perquè el tribunal vol la redacció nova i
   l'anàlisi, no només la transcripció.

## 6. Evidència

- [[historia_original]]: text literal.
- [[historia]]: versió combinada amb dates, xifres i enllaços.
- [[TREC/09 Redaccio de la memoria]]: on va cada part del document.
- [[TREC/13 Bibliografia i webgrafia]]: com citar-lo.

## 7. Relacions

Els quatre apartats originals (cervell, oïda, memòria i cara) ja estan enllaçats
a la taula del punt 4; no es repeteixen aquí per no duplicar les mateixes
línies al graf. La jerarquia és [[TREC/parts/00 Index de les parts]] → aquesta
nota.
