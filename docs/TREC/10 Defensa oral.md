---
tema: TREC
bloc: 6
estat: esborrany
---
# 10 · Defensa oral

> **La guia ho diu clar:** el tribunal ja s'ha llegit la memòria; la defensa no
> ha de repetir el treball, sinó **demostrar que l'entens i que saps per què
> cada decisió és així**. Tens **20 minuts** d'exposició i **10 minuts** de
> preguntes.

## 1. Objectiu de la defensa

Que el tribunal surti dient tres coses:

1. **Aquest noi sap què ha construït** (no ha copiat un tutorial).
2. **Sap mesurar** i distingir una dada d'una opinió.
3. **Sap reconèixer els límits** sense que calgui arrencar-li'ls.

## 2. Guió de 20 minuts

| Temps | Bloc | Què dir | Suport |
|---|---|---|---|
| 0:00-2:00 | **Ganxo** | «No és un altaveu: ha de recordar, mirar i equivocar-se com un company.» Pregunta de recerca. | Diapositiva 1, foto del dispositiu |
| 2:00-4:00 | **Objectius i hipòtesi** | Les tres hipòtesis (H1 latència, H2 memòria, H3 fidelitat), en una frase cada una. | Diapositiva 2 |
| 4:00-7:00 | **Marc teòric mínim** | Només el que cal per entendre el resultat: LLM, TTFT, RAG, STT/TTS. | Diapositiva 3-4 |
| 7:00-10:00 | **Iteració 1 i 2** | Del paper a la placa; 15-20 s → 4,2-4,7 s; on es va retallar. | Diapositiva 5-6, gràfic |
| 10:00-13:00 | **Iteració 3** | El local no n'hi havia prou (8,75 s); doble cervell; 1,23 s de TTFT; què surt al núvol. | Diapositiva 7-8 |
| 13:00-16:00 | **Demo** | Tres ordres: conversa, memòria, agenda. Si falla: vídeo de reserva. | Placa + pantalla + vídeo |
| 16:00-18:00 | **Resultats i límits** | Memòria 85-100 % tema, 4/8 detall; el local inventa; privacitat. | Diapositiva 9-10 |
| 18:00-20:00 | **Conclusions** | Sí, amb matisos; què faries després; tancament. | Diapositiva 11 |

### Si vas just de temps

Retalla el marc teòric (4:00-7:00) a 90 segons i deixa 30 segons més per a la
demo. **No retallis les conclusions ni els límits**: és el que més es valora.

## 3. Diapositives (12-14)

1. **Portada:** títol, nom, tutor, curs.
2. **La pregunta:** una frase gran; res més.
3. **Hipòtesis:** taula de tres files.
4. **Arquitectura:** el diagrama de [[TREC/03 Marc practic]] §2.
5. **Latència abans/després:** gràfic de barres per etapa.
6. **El sostre de la placa:** 8,75 s de TTFT amb el 3B.
7. **Doble cervell:** núvol primari + local respostal.
8. **Memòria:** escala i el 4/8 de detall.
9. **Fidelitat:** núvol vs local (0 contaminacions vs piano per trompeta).
10. **Errors:** tres símptomes i les seves causes (comptador, micro, etiquetes).
11. **Què s'ha aconseguit / què no:** dues columnes.
12. **Línies futures:** memòria de fets, LoRA, refrigeració.
13. **Tancament:** una frase + gràcies.
14. **Reserva:** captures de log i taules per si pregunten.

**Regles de disseny:** fons clar o fosc consistent, text gran, poc text per
diapositiva, una idea per diapositiva, imatges i gràfics. No llegir les
diapositives: es canvien i després s'explica.

## 4. Demo en directe (3 minuts)

### Preparació (abans d'entrar)

- [ ] Placa alimentada amb 5 V / 3 A.
- [ ] Només hi ha **una** instància del programa en marxa.
- [ ] Log amb la versió i l'empremta correctes.
- [ ] Volum alt, micròfon a prop, soroll de fons baix.
- [ ] Una cita de prova creada i coneguda.
- [ ] **Vídeo de reserva** gravat (2 min) per si falla la xarxa o l'àudio.

### Guió

1. **Conversa:** «Parker, explica'm en dues frases què et fa especial.» → ha de
   respondre curt, sense enumerar.
2. **Memòria:** «Parker, recordes què et vaig dir del dentista?» → ha de
   recuperar la cita o dir que no ho sap; **no** ha d'inventar.
3. **Agenda:** «Parker, què tinc demà?» → llegeix la cita.
4. **Canvi de cervell:** «Parker, ponte en local.» → avisa i canvia; després
   «torna al núvol».

### Si falla

- **No et disculpis durant 30 segons.** Diu: «La xarxa de l'aula és el pitjor
  escenari possible; passo al vídeo que vaig gravar amb el mateix codi.»
- Posa el vídeo i **segueix explicant** el que es veu.
- Si la cara es congela: mira si hi ha dues instàncies; no reiniciïs a la
  lleugera. Si no es pot arreglar en 10 segons, continua sense demo.

## 5. Les xifres que has de saber de memòria

| Xifra | Valor |
|---|---|
| Temps inicial | 15-20 s |
| Temps final | ~1,6 s |
| TTFT ruta completa | 1,23 s p50 |
| TTFT local 3B | 8,75 s p50 |
| STT local `base` | 1,6-2,0 s |
| STT núvol | 0,68 s |
| Consulta memòria | ~150 ms |
| Records provats | 200 / 1.000 / 3.000 |
| Tema correcte | 85-100 % |
| Detall exacte | 4 de 8 fallades |
| Proves | 24 fitxers |
| Pressupost | 275,52 € |

No cal recitar-les totes: tria **quatre** (1,6 s, 8,75 s, 150 ms, 4/8) i deixa
la resta per a les preguntes.

## 6. Preguntes probables (i respostes curtes)

**1. Si el cervell és al núvol, això no és un robot?**
La placa fa l'oïda, la memòria, la veu, la cara i les funcions del dia; el núvol
només redacta la frase. Sense xarxa, el local respon. És un artefacte híbrid, i
ho dic obertament.

**2. Per què no uses un model més gran en local?**
Perquè el límit és la placa: el 3B ja triga 8,75 s i s'escalfa. Un 7B o 13B no
hi cap amb una latència usable. Ho vaig mesurar, no ho suposo.

**3. Això és intel·ligència artificial de veritat?**
És un sistema que integra models preexistents. La meva aportació és
l'arquitectura, la memòria, la selecció de context, la personalitat i el mètode
de mesura. No he entrenat el model.

**4. Què passa si es cau internet?**
Parker canvia al `qwen2.5:3b` local, avisa per veu una vegada i continua. Va més
lent (5,8-13 s segons el torn) i el STT empitjora, però no s'atura.

**5. La memòria no és perillosa? Guarda dades personals.**
Sí, i per això viu en local, les còpies es queden al PC i no es publiquen àudios.
El mode híbrid envia text a Groq; hi ha un interruptor perquè res surti
(`online.activo: false`).

**6. Per què falla 4 de 8 en memòria?**
Perquè un *embedding* petit amb preguntes de tres paraules dona similituds
solapades entre senyal i soroll. No és un error de Chroma; és el límit del model.
La solució és desar fets, cerca híbrida i marge, no un llindar més alt.

**7. Això ho pot fer servir una altra persona?**
Amb el codi i la guia, sí; cal una clau de Groq i una placa. La personalitat està
pensada per a un usuari, no per a multiusuari.

**8. Quant costa mantenir-ho?**
El maquinari, 275,52 €. El núvol, en el pla gratuït de Groq; no hi ha
subscripció. L'energia és la d'una placa de 5 V.

**9. Què faries amb sis mesos més?**
Memòria de fets (el 4/8), LoRA de personalitat, refrigeració perquè el 3B no
baixi de freqüència i un estudi amb 5-10 persones.

**10. Què és el que més t'ha costat?**
No va ser programar: va ser **saber què passava**. Els errors d'estat (dues
instàncies, mode local desat, comptador) semblaven al·lucinacions del model. Per
això ara mesuro abans de tocar.

## 7. Errors que cal evitar

- **Llegir les diapositives.** El tribunal ja sap llegir.
- **Culpar el model** de tot. Sovint era el prompt, l'estat o el maquinari.
- **Dir «funciona perfecte».** Tothom ha vist els límits a la memòria; si els
  amagues, perds credibilitat.
- **Disculpar-te massa** per la demo. Un imprevist explicat amb calma val més
  que una demo perfecta sense explicació.
- **Allargar-te.** Si et queden 30 segons, tanca amb la frase final; no compris
  una diapositiva nova.

## 8. Tancament (10 segons)

> «Parker no és un robot general ni una persona: és un objecte de sobretaula que
> escolta, recorda i respon amb una cara. Dins d'aquest límit, compleix la
> promesa: hi és, et parla i no et deixa incomunicat si falla internet. El que
> queda per fer no és més codi, sinó més comprensió de la memòria i del to.»

## 9. Assaig

- Grava't **una vegada** sencer i mira't sense so: mans, mirada, velocitat.
- Assaja **només** el ganxo i el tancament: és el que queda.
- Cronometra la demo per separat: no pot menjar-se les conclusions.
- Prepara la reserva: vídeo, captures de log i taules en paper.

## 10. Notes relacionades

- [[TREC/05 Resultats]] — les xifres que has de defensar.
- [[TREC/09 Redaccio de la memoria]] — el document que acompanya.
- [[TREC/06 Errades i solucions]] — els errors que et poden preguntar.
- [[TREC/11 Checklist TREC]] — la revisió final.
