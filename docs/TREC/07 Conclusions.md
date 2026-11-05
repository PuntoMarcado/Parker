---
tema: TREC
bloc: 6
estat: esborrany
---
# 07 · Conclusions

> **Què ha de contenir.** No repetir el treball: dir què s'ha demostrat, què no,
> per què, i què faria després. La guia demana explícitament **síntesi** i
> **sentit crític**, i que no s'hi posin valoracions buides («ha estat molt
> interessant»).

## 1. La resposta a la pregunta de recerca

> **Es pot construir un company conversacional de sobretaula, amb memòria local
> i veu natural, que respongui en menys de 2 segons i continuï funcionant sense
> internet, amb un pressupost de maquinari inferior a 300 €?**

**Sí, amb matisos.**

- **Sí** a la latència: el pipeline complet va arribar a **~1,6 s** fins a la
  primera paraula, en una placa de 8 GB i amb un pressupost de **275,52 €**.
- **Sí** a la continuïtat: sense internet, el cervell local respon i el sistema
  no s'atura.
- **Amb matisos** a la qualitat: la memòria recupera el **tema** (85-100 %), però
  no el **detall exacte** (4 de 8 preguntes curtes van fallar). El sistema ho ha
  de dir, no inventar-ho.
- **Amb matisos** a la privacitat: el mode híbrid envia text (i àudio, si el STT
  és al núvol) fora de casa. Hi ha un interruptor, però el valor per defecte no
  és «tot local».

La resposta honesta no és «ho hem aconseguit tot», sinó **«hem demostrat on és
el límit i com es gestiona»**.

## 2. Veredicte de les hipòtesis

| Hipòtesi | Veredicte | Evidència |
|---|---|---|
| **H1**: un sistema híbrid pot baixar de 2 s en una placa de 8 GB | **Acceptada** | 15-20 s → **~1,6 s**; TTFT de ruta completa p50 **1,23 s** |
| **H2**: Chroma local recupera el tema, però no dades exactes | **Parcialment acceptada** | Tema 85-100 %; 4/8 preguntes curtes no recuperen el fet |
| **H3**: el model local entén el context però inventa més que el núvol | **Acceptada** | Núvol: 0 contaminacions i 3/3 «no ho sé»; local: piano per trompeta |

H2 és la més interessant per al tribunal precisament perquè **no** és un sí
rotund. Un treball que només confirma les seves hipòtesis sol ser sospitós; un
que troba un límit i el mesura, no.

## 3. Objectius: què s'ha assolit

| Objectiu | Estat | Com es justifica |
|---|---|---|
| Integrar veu, cervell, memòria, cara i agenda | **Assolit** | Pipeline complet a la placa, amb 24 suites de prova |
| Reduir el temps fins a la primera paraula ≥ 70 % | **Assolit** | De 15-20 s a 1,6 s (> 90 %) |
| Mesurar l'abast de la memòria | **Assolit** | Escala 200-3.000 records; llindar; fidelitat |
| Doble cervell amb caiguda al local | **Assolit** | Mode auto/núvol/local, persistència i avisos |
| Documentar cada decisió amb evidència | **Assolit** | `version.py`, `plan_mejoras.md`, eines i tests |
| Cervell local ràpid i lúcid | **No assolit** | 8,75 s de TTFT; és el respostal, no el titular |
| Memòria de dades exactes | **No assolit** | Cal cerca híbrida o extracció de fets |
| LoRA de personalitat entrenat | **No assolit** | Dissenyat; falta entrenament i avaluació |
| Estudi amb usuaris | **No assolit** | Mostra d'un sol usuari |

## 4. Les tres lliçons tècniques

### 4.1 El coll d'ampolla no és el model, és el lloc

El model local no es va tornar ràpid: es va **treure la generació de la placa**.
Aquesta és la decisió que ho canvia tot. La mateixa idea es pot explicar com una
llei de disseny: **posa cada cost on no es noti**.

### 4.2 La memòria no és una base de dades

Chroma sap trobar **temes**, no fets exactes. Confondre-ho porta a prometre una
cosa que el sistema no pot complir. La solució no és un embedding més gran (no
hi cap), sinó:

- desar el fet, no la transcripció crua;
- ampliar la consulta amb el torn anterior;
- combinar cerca vectorial i lèxica;
- acceptar el top-1 si destaca sobre la cua, en lloc d'un llindar fix.

Cap d'aquestes quatre no s'ha implementat encara; són **línies futures**, no
resultats.

### 4.3 L'estat és part del sistema

Els errors més difícils no van ser de càlcul, sinó d'**estat**: un comptador
antic, un mode local desat, una frase espontània no persistida, dues instàncies
del procés. La lliçó: **tot allò que sobreviu a un reinici és una font de
veritat i, per tant, una font d'errors**.

## 5. Limitacions

1. **Mostra d'un sol usuari.** No es pot generalitzar sobre la qualitat de la
   conversa ni sobre l'acceptació.
2. **Privacitat per defecte.** El mode híbrid envia text i àudio. Cal declarar-ho
   i ensenyar l'interruptor.
3. **Temperatura.** El 3B baixa de freqüència cap als 75 °C; algunes mesures
   tenen rangs amples per això.
4. **Memòria de detall.** 4 de 8 preguntes curtes no recuperen el fet.
5. **Veu.** Edge TTS depèn de Microsoft; Piper és el respostal, amb menys
   naturalitat.
6. **LoRA no entrenat.** La personalitat es fa amb prompt; els pesos no s'han
   ajustat.
7. **Proves no exhaustives.** 24 suites cobreixen el comportament esperat, no
   totes les combinacions possibles.

## 6. Línies futures

Per ordre de relació amb els resultats:

| Línia | Per què | Què cal |
|---|---|---|
| **Memòria de fets** | Ataca el 4/8 | Extreure «fet + subjecte» en desar; cerca híbrida; marge en lloc de llindar |
| **Segona memòria de coneixement** | Permetre receptes, psicologia, manuals | Col·lecció `saberes` separada, top_k 2, llindar 0,72-0,75, etiqueta «dades llegides» |
| **LoRA de personalitat** | Consolidar el to BMO/Baymax sense prompt gegant | Dataset, QLoRA, avaluació base vs LoRA; GPU al núvol |
| **Refrigeració i carcassa** | Recuperar el 3B en calent | Disseny tèrmic, ventilació, proves de temperatura |
| **Estudi d'usuaris** | Saber si el company funciona fora del laboratori | Protocol amb 5-10 persones, qüestionari i tasques |
| **Mode cuina** | El pla 3 del document original | Dictat pas a pas, mans lliures, pausa i repetició |
| **Tancament net** | Acabat físic | ESC al muntatge final, apagada segura |

## 7. Opinió personal (breu)

Aquest treball m'ha canviat la manera de programar. Al principi buscava la
solució «bona»; ara busco **la mesura que diu si la solució és bona**. Moltes
idees que semblaven evidents van caure amb una taula: el model més gran no era
més ràpid, el llindar més alt no era més precís, la memòria més gran no era més
intel·ligent.

També m'ha ensenyat a distingir **una demo d'un producte**. Una demo ensenya el
millor torn; un producte ha de sobreviure al pitjor: el micro que no apareix, el
proveïdor que cau, l'estat que es corromp i la frase que no té sentit. La part
més valuable del projecte no és Parker quan funciona, sinó tot el que es va
documentar quan no ho feia.

## 8. Tancament

Parker no és una persona ni un robot general: és **un artefacte de sobretaula
que escolta, recorda i respon amb una cara**. Dins d'aquest límit, compleix la
seva promesa: està ahí, et parla i no et deixa incomunicat si falla internet.

El que queda per fer no és «més codi»: és **més comprensió** de la memòria, del
to i del cos. Aquest treball deixa el mapa i les eines per continuar.

## 9. Notes relacionades

- [[TREC/01 Pla de recerca]] — les hipòtesis que es tanquen aquí.
- [[TREC/05 Resultats]] — les dades que sostenen cada veredicte.
- [[TREC/06 Errades i solucions]] — el que va costar arribar-hi.
- [[TREC/09 Redaccio de la memoria]] — com es redacta aquesta conclusió.
