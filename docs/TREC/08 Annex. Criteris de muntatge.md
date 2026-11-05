---
tema: TREC
bloc: 7
estat: annex
tipus: annex
---
# 08 · Annex. Criteris de muntatge i verificació

> **Aquest annex no és una guia per muntar Parker.** És una traça de les condicions que es van comprovar per poder afirmar que el prototip funcionava. Les decisions i les mesures s'expliquen al [[TREC/03 Marc practic]]; aquí només es recull **què es va verificar** i **per què aquella comprovació era necessària**.

## 1. Per què calia separar les comprovacions

En un sistema encastat, un símptoma pot venir de capes molt diferents. Una pantalla blanca pot ser un cable, una inicialització incompleta, un permís del sistema o una concurrència entre dos processos. Per això la verificació no es va fer com una llista de passos, sinó com una seqüència de capes: **energia, maquinari, sistema, programa i persona**.

Cada capa havia de donar una evidència abans de passar a la següent. Si la placa no arrencava, no tenia sentit provar el model. Si la pantalla no responia, no tenia sentit culpar la cara. Aquesta disciplina va evitar hores de diagnòstic equivocat.

## 2. Criteris de verificació

| Bloc | Què es volia assegurar | Evidència que es va acceptar |
|---|---|---|
| **Energia** | La placa no es reiniciava ni perdia el so | Funcionament estable amb la font de 5 V i 3 A |
| **Arrencada** | El sistema arribava a l'aplicació sense monitor | La cara apareixia i el sistema quedava escoltant |
| **Pantalla** | El controlador rebia ordres i píxels correctes | Patró de colors i cara visible a la pantalla circular |
| **Àudio** | El micròfon i l'altaveu eren els dispositius correctes | So audible i transcripció d'una frase real |
| **Memòria** | Els records es desaven i es podien recuperar | Un record conegut apareixia en una conversa posterior |
| **Cervell** | El núvol responia i el local podia substituir-lo | Resposta amb xarxa i continuïtat sense xarxa |
| **Veu** | La resposta es convertia en àudio sense tallar-se | Primera frase reproduïda i frases següents encuades |
| **Cara** | L'animació no es congelava ni deformava | Expressions i gestos durant una conversa llarga |
| **Agenda** | Les ordres deterministes no depenien del model | Alarma, cita i temporitzador creats i consultats |
| **Privacitat** | L'usuari podia triar el mode local | Resposta sense xarxa i sense enviar text al núvol |

Aquesta taula no és un protocol d'instal·lació: és el resum de les proves que sostenen les afirmacions del capítol pràctic. Si una fila no s'hagués comprovat, l'afirmació corresponent hauria de baixar de categoria i presentar-se com a observació o com a línia futura.

## 3. Els errors que van canviar el disseny

Algunes comprovacions no van confirmar el que s'esperava; van canviar el projecte:

- **La pantalla blanca** va demostrar que un bus pot respondre sense que el dispositiu estigui configurat. La solució no era canviar el cable, sinó completar la inicialització i validar el color.
- **El micròfon que arribava tard** va demostrar que el maquinari pot ser més lent que el programa. La solució va ser esperar, refrescar la llista de dispositius i avisar amb un xim.
- **Les dues instàncies** van demostrar que un error aparentment de codi podia ser una condició d'execució. La solució va ser garantir una sola instància.
- **El model local que inventava** va demostrar que la qualitat no es pot separar de la latència. La solució va ser un doble cervell amb una reserva honesta.
- **La memòria que fallava en preguntes curtes** va demostrar que recuperar un tema no és el mateix que recuperar un fet exacte. La solució va ser una memòria de fets i un índex textual, no prometre una memòria perfecta.

## 4. Què queda fora d'aquest annex

No s'inclouen instruccions de cablejat, ordres de terminal ni configuracions del sistema. Aquestes dades viuen a [[TREC/14 Annex. Muntatge i esquemes electrònics]], que és la guia tècnica. El tribunal ha de poder entendre **per què** es va verificar cada capa; el muntatge no forma part del relat principal.

La traçabilitat completa —quina versió, quina mesura i quina prova sostenen cada afirmació— es desenvolupa a [[TREC/04 Metodologia i proves]]. Els resultats, a [[TREC/05 Resultats]]. I les conclusions, a [[TREC/07 Conclusions]].
