---
tema: TREC
bloc: 3
part: personalitat
estat: viu
---
# Personalitat

[[TREC/parts/00 Index de les parts]] · [[TREC/03 Marc practic]] · [[evolucion]]

## 1. Què és

És la capa que decideix **com parla, com es troba i quan pren la iniciativa**.
No és el cervell (que tria les paraules) ni la cara (que les expressa): és el que
fa que la mateixa resposta soni a Parker i no a un assistent genèric.

## 2. Què deia el document original

El document no tenia un apartat de personalitat. El referent era **BMO**:
un robot petit, ingenu i afectuós, que fa la seva vida i parla amb qui té a
prop. Més endavant es va afegir **Baymax** com a referent de manera: un company
que cuida i pregunta com estàs, sense to corporatiu.

A les converses del projecte es va concretar encara més:

- És **Parker**, no l'usuari.
- No té cos físic: és una **pantalla i una caixa** amb components.
- No ha de prometre accions que no pot fer (encendre llums, moure's).
- Ha de ser amigable, curiós i una mica ingenu, no un assistent que enumera.
- Ha de saber on és i què és, sense recitar-ho cada torn.

## 3. Evolució

| Moment | Què es va fer | Resultat |
|---|---|---|
| Prototip | Ficha bàsica i regles de to | Evitar «en què puc ajudar-te» |
| Primera placa | Ànim (energia, curiositat, afecte) i víncle | Parker canvia amb els dies |
| 26/10/2026 | **v6.4: bandit d'iniciativa** | Aprèn quan i de què parlar segons si li contestes |
| 27/10/2026 | **v6.6: fitxa que rota** | No repeteix sempre «la lluvia» o «silbar» |
| 27/10/2026 | **v6.8: gestos i silenci** | La cara acompanya l'estat d'ànim |
| 30/10/2026 | **v6.10.1: llavor concreta** | Les frases automàtiques tenen un motiu real |
| 30/10/2026 | **v6.10.2: frases amb sentit** | No inventa el motiu; el desa i l'explica |

## 4. Com funciona avui

- **Ficha:** gustos, records, manies i somnis, en rotació per conversa.
- **Ànim:** energia, curiositat i afecte; evoluciona amb el silenci i l'ús.
- **Víncle:** creix amb dies i converses; no es mostra com un percentatge.
- **Iniciativa:** cada 15 min de silenci, el bandit tria un braç:
  `contar`, `preguntar`, `proposar`, `eco` o `callar`.
- **Frases:** surten d'una llavor concreta (fitxa, hora, proposta o últim
  missatge), no d'una ordre oberta.
- **Meta-preguntes:** «¿qué has dicho?» es respon **sense LLM**, amb la frase i
  el motiu real, també després d'un reinici.
- **Regles:** no descriu accions físiques, no diu que xiula si no ha sonat el
  xiulet, no confon el seu nom amb el de l'usuari.

## 5. Què va fallar

| Símptoma | Causa | Arreglo |
|---|---|---|
| «Le gusta la lluvia» una i altra vegada | El prompt ensenyava sempre la primera entrada de la fitxa | Rotació per conversa |
| «Sueña con silbar» i no ho feia | El model convertia un desig en una acció | Xiulet real + regla de no prometre |
| «Creo que ordeno las palabras antes de decirlas» | Les manies es presentaven com a creences | Plantilla «quan ningú mira…» |
| «231 charlas» | El comptador viatjava al prompt | Treure'l; contar converses |
| «Eres tú, Piper/Dipper» | El prompt contenia «Piper» | Treure la paraula i corregir vocatius |
| Frases automàtiques incoherents | Instrucció oberta + eco de transcripcions dolentes | Llavor concreta, filtre d'eco i persistència |

## 6. Evidència

- [[evolucion]]: ànim, víncle, bandit i fitxa.
- [[plan_mejoras]] §v6.6, §v6.10.1, §v6.10.2.
- `modulos/personalidad.py`, `tests/test_personalidad.py` (18 blocs),
  `tests/test_bandit.py` (5/5).

## 7. Relacions

Modula el **Cervell** (to) i la **Cara** (ànim); no és la **Memòria** (fets) ni
l'**Agenda** (tasques). El cas de les frases automàtiques és a
[[TREC/errades/Frases automatiques]].

No s'enllaça lateralment amb cada part perquè el graf no confongui dependència
amb semblança; el diagrama de dades és al [[TREC/parts/00 Index de les parts]].
