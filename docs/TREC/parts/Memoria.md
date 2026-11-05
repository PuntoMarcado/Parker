---
tema: TREC
bloc: 3
part: memoria
estat: viu amb límits
---
# Memòria

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[TREC/05 Resultats]]

## 1. Què és

És la part que permet que Parker **recordi entre sessions**. No és un historial
de xat: és una base vectorial local (ChromaDB) on es desen fets de la persona i
es consulten per significat, no per paraules exactes. El mecanisme es diu **RAG**:
recuperar → augmentar el prompt → generar.

## 2. Què deia el document original

El document la descrivia com «el seu diari»:

> «En lloc de desar les converses en un arxiu de text simple (on la IA hauria de
> llegir milers de línies cada vegada per buscar un record), ChromaDB utilitza
> un procés […] anomenat RAG.»

I la segona actualització va corregir tres coses que avui segueixen al codi:

| Problema | Canvi | Estat actual |
|---|---|---|
| El model d'embeddings era gairebé monolingüe | `paraphrase-multilingual-MiniLM-L12-v2` | En ús |
| El llindar del 75 % «oblidava» si es deia amb altres paraules | Baixar-lo al 50 % | Avui **0,58** |
| Es vectoritzava el torn sencer | Guardar **només** el missatge de la persona | En ús |

## 3. Evolució

| Moment | Què es va fer | Resultat |
|---|---|---|
| Prototip | Primera Chroma amb embeddings en anglès | Fallava en català/castellà |
| 2a actualització | MiniLM multilingüe, llindar flexible, només missatge d'usuari | Més precisió |
| Primera placa | `top_k: 3`, llindar 0,58, 140 caràcters per record | Consultes ~150 ms |
| 27/10/2026 | Prova d'escala 200/1.000/3.000 | Latència plana (~150 ms); tema 85-100 % |
| 27/10/2026 | Prova de fidelitat amb el cervell real | Núvol no contamina; local inventa |
| 27/10/2026 | Disseny de la segona memòria (`saberes`) | **No implementada**; només disseny |

## 4. Com funciona avui

- **Model:** `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions.
- **Base:** `parker.db/`, col·lecció `recuerdos_parker`.
- **Què es desa:** només el missatge de la persona, no la resposta del model.
- **Què es recupera:** `top_k: 3`, similitud mínima **0,58**, 140 caràcters.
- **Quan es consulta:** abans de generar, amb la frase actual.
- **Què no fa:** no guarda tota la conversa, no busca per paraula exacta i no
  garanteix un detall concret.

## 5. El límit que cal dir sense embuts

Amb 8 preguntes curtes sobre 12 fets guardats, **4 no es van recuperar**; una
d'elles era el top-1 però no passava el llindar. No és un error de Chroma: és el
límit d'un *embedding* petit amb preguntes de tres paraules.

| Mètrica | Resultat |
|---|---|
| Tema correcte amb 200 / 1.000 / 3.000 records | 85 % / 100 % / 95 % |
| Consulta p50 | ~150 ms (no creix) |
| Detall exacte en preguntes curtes | 4 de 8 fallades |
| Contaminació amb el núvol | 0 |
| «No ho sé» quan no hi és (núvol) | 3/3 |
| Al·lucinació del local quan falla el núvol | Sí («piano» per «trompeta») |

**Escala real:** 52 records després de 205 converses (~0,25 per conversa).

## 6. La segona memòria (disseny, no implementació)

Per a llibres de cuina, psicologia o manuals:

- Col·lecció **separada** `saberes`, mai barrejada amb `recuerdos_parker`.
- Fragments de ~400 caràcters, fets al PC i copiats a la placa.
- Consulta només per a preguntes de saber, `top_k: 2`, llindar 0,72-0,75.
- Bloc del prompt etiquetat: «Sabers (dades llegides, NO són records teus)».

Sense aquesta etiqueta, el model comença a explicar la recepta com una cosa que
va viure. Per això no s'ha activat encara: primer cal mesurar-la.

## 7. Evidència

- [[TREC/05 Resultats]] §5: taules d'escala, llindar i fidelitat.
- [[plan_mejoras]] §«La memoria, medida a fondo».
- `modulos/memoria.py`, `tools/probar_memorias.py`, `tests/test_pipeline.py`.

## 8. Relacions

El **Cervell** la consulta abans de generar. No és la **Personalitat** (ànim) ni
l'**Agenda** (tasques): és el diari de fets. El diagrama de dades és al
[[TREC/parts/00 Index de les parts]]; la línia futura, a [[TREC/07 Conclusions]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança.
