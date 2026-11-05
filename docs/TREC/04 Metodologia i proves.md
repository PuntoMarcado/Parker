---
tema: TREC
bloc: 4
estat: complet
tipus: memoria
---
# 04 · Metodologia i proves

> **Aquesta nota explica com se sap que el prototip funciona.** No és un recull d'ordres per reproduir-lo: és la descripció del mètode, dels instruments i de les condicions que fan que una mesura sigui comparable. El tribunal no ha de veure un vídeo i creure's una afirmació; ha de veure quina prova la sosté i quins límits té.

## 1. Tipus de recerca

El treball és un **projecte tecnològic amb mètode experimental**. Es construeix un artefacte i es compara el seu comportament abans i després d'una intervenció. No es busca una llei general sobre la intel·ligència artificial, sinó demostrar que **aquest** disseny compleix uns requisits en **aquest** maquinari.

Per això cada afirmació important ha de tenir una d'aquestes tres formes:

| Forma | Exemple |
|---|---|
| **Mesura** | «El TTFT de la ruta completa va ser 1,23 s de mediana.» |
| **Comparació controlada** | «Amb el mateix prompt i la mateixa placa, el model de 3B va trigar 8,75 s i el d'1,5B va ser més ràpid però menys coherent.» |
| **Limitació declarada** | «Amb 3.000 records, el tema s'encerta al 95 %, però el detall exacte no.» |

No val com a evidència «es nota més ràpid», «queda molt bé» o un vídeo sense registre. Una opinió pot ser una conclusió personal, però no pot substituir una mesura.

## 2. Disciplina d'iteració

Cada canvi del projecte segueix el mateix ordre:

1. **Reproduir el problema.** Cal un símptoma concret, no una impressió.
2. **Formular una sola hipòtesi.** «Va lent perquè el model és gran» és una hipòtesi; «va lent perquè el model, el prompt i la transcripció van malament» no ho és.
3. **Canviar una cosa.** Si es canvia el model i el prompt alhora i millora, no se sap quina de les dues ha funcionat.
4. **Mesurar.** Mateix prompt, mateixa placa, mateix nombre de torns i, si és possible, mateixa temperatura.
5. **Comprovar que no s'ha romput res.** La millora d'una part no pot justificar la caiguda d'una altra.
6. **Documentar.** Versió, causa, mesura i lliçó.

Aquesta disciplina va evitar un error important. En un moment es va tornar al model de 3B i es va ampliar el context; la millora no venia del model, sinó que el sistema estava retallant el prompt perquè no hi cabia. Sense separar les variables, s'hauria atribuït al model un canvi que era de configuració.

## 3. Instruments

### 3.1 Registres de latència

Cada torn deixa un registre amb les etapes principals:

- **Transcripció:** del final de la veu al text.
- **Primer token:** del text al primer tros de resposta.
- **Primera frase:** del primer token a l'àudio llest.
- **Torn complet:** de deixar de parlar a l'inici de la resposta.

Aquests registres són la font primària de les taules de resultats. No s'han inventat després: s'han llegit dels torns reals i s'han resumit amb medianes, mínims i màxims.

### 3.2 Banc del cervell

Per comparar models es va fer servir un banc de proves amb el prompt real de Parker. El banc permetia:

- Mesurar només la latència o només el context.
- Provar un model alternatiu sense canviar la configuració habitual.
- Forçar la ruta local per comparar-la amb la del núvol.
- Fer entre sis i deu torns per no dependre d'un sol resultat.

El banc dona **mediana, mínim i màxim**, no només la mitjana. Aquesta decisió és important: un sol torn de 29 s pot arruïnar una mitjana i no representa l'experiència habitual. La mediana és més honesta amb la distribució real.

### 3.3 Comparació de models

Els models candidats es van provar amb els mateixos prompts i la mateixa màquina quan era possible. Es van comparar el temps fins al primer token, la velocitat de generació i la qualitat de la resposta. La comparació no pretenia ser exhaustiva: es van triar els candidats que cabien al maquinari i al temps disponible.

Aquesta és una limitació del treball. No s'ha fet un concurs universal de models; s'ha fet una tria raonada per a un prototip concret.

### 3.4 Proves de memòria

Les proves de memòria es van fer amb bases temporals, no amb la memòria real de l'usuari. Això és deliberat: una prova de 3.000 records no pot contaminar els records personals que ja existeixen.

Es van mesurar tres coses:

- **Escala:** si el tema correcte es recupera amb 200, 1.000 i 3.000 records.
- **Llindar:** si la similitud separa els records útils del soroll.
- **Fidelitat:** si el model diu «no ho sé» quan el record no hi és o si s'inventa una resposta.

La prova de fets exactes es va fer amb vuit preguntes curtes sobre dotze dades distintives. Quatre no es van recuperar. Aquest resultat no és un efecte secundari: és una de les conclusions parcials del treball.

### 3.5 Proves de regressió

El projecte té **24 fitxers de prova**. No tots es poden executar en qualsevol màquina: alguns necessiten la placa, la pantalla o el micròfon; d'altres són simulacions en un ordinador.

Cada arreglo important afegeix un cas nou que reprodueix el símptoma. Per exemple, quan l'agenda va desar «pose una» com a matèria d'una alarma, es va afegir un cas que comprova que aquella frase no genera cap alarma. Això converteix un error en **coneixement**: la versió següent no pot tornar a caure-hi sense que la prova ho detecti.

### 3.6 Prova manual a la placa

Cap prova automàtica substitueix parlar-hi. El protocol manual és:

1. Comprovar que la versió i l'empremta del PC i de la placa coincideixen.
2. Dir una frase llarga, d'unes deu a quinze paraules, i esperar la resposta.
3. Provar una ordre directa, una pregunta de memòria i una ordre d'agenda.
4. Mirar la cara: no ha de quedar congelada ni amb els ulls deformats.
5. Si falla, llegir i desar el registre **abans** de reiniciar; el reinici esborra l'evidència.

La prova manual no és menys rigorosa que l'automàtica: és l'única que comprova la qualitat percebuda i la coherència del conjunt.

## 4. Protocol de mesura

Perquè dues xifres siguin comparables, cal controlar les condicions:

| Condició | Per què |
|---|---|
| Mateix prompt d'identitat | Canviar-lo canvia el prefill i el TTFT |
| Mateixa placa i mateixa temperatura | Els nuclis grans baixen de freqüència a partir d'uns 75 °C |
| Mateix model i mateixa quantització | El mateix model pot comportar-se diferent segons la compressió |
| Mateix nombre de torns | Un sol torn no és una mostra |
| Reportar mediana, mínim i màxim | La mitjana amaga la cua |
| Anotar versió i empremta | Sense això no se sap què s'ha mesurat |
| Un canvi per mesura | Aïlla la causa |

La temperatura és la variable no controlada més important. Quan el processador arriba a uns 75 °C, pot baixar la freqüència i el TTFT pot passar de 3,7 s a 10-12 s. Per això algunes taules tenen rangs amples i per això la refrigeració és una línia futura, no un detall estètic.

## 5. Validesa i límits

### El que la metodologia permet afirmar

- Que **en aquesta placa** i **amb aquest prompt** el pipeline va passar de 15-20 s a aproximadament 1,6 s.
- Que la memòria recupera el **tema** en el 85-100 % dels casos segons la mida de la base.
- Que el model local **al·lucina més** que el del núvol quan falla la memòria.
- Que els arreglos no trenquen les funcions cobertes per les 24 suites.

### El que no permet afirmar

- **No és un estudi d'usuaris.** La mostra és el propi autor; no es pot dir que «agrada a la gent».
- **No és una comparació exhaustiva de models.** S'han provat els candidats que cabien al maquinari i al temps disponible.
- **No és una mesura de laboratori.** La xarxa de casa i el soroll del menjador no són condicions controlades.
- **No tots els tests corren a la placa.** Alguns depenen de la interfície gràfica o de l'àudio i es queden al PC.

Aquestes limitacions no debiliten el treball: el fan **creïble**. Un TREC que diu «no ho sé» on no ho sap val més que un que ho inventa tot.

## 6. Ètica i privacitat

- **Consentiment:** les converses són del propi autor; no es publiquen àudios ni noms de tercers.
- **Dades sensibles:** la memòria pot contenir estats d'ànim. Les còpies es guarden al PC, no a la placa, i no es pugen a cap repositori públic.
- **Tercers:** els serveis de núvol, veu, música i temps reben només el que necessiten. Cal declarar-ho a la memòria i explicar com desactivar-los.
- **Autoria:** el codi és propi; les llibreries i models tenen les seves llicències, citades a [[TREC/13 Bibliografia i webgrafia]].

## 7. Traçabilitat: la regla de les tres proves

Per a cada afirmació important de la memòria, cal poder ensenyar:

1. **El codi** que ho fa.
2. **La mesura** que ho sosté.
3. **La prova** que ho protegeix.

Si falta una de les tres, l'afirmació es marca com a **línia futura** o com a **observació qualitativa**, no com a resultat. Aquesta regla és la que dona coherència a tot el treball i la que es pot explicar en trenta segons al tribunal.

## 8. Reproducció: què vol dir i què no

El projecte es pot reproduir, però no és un producte d'instal·lació automàtica. Reproduir-lo vol dir entendre les decisions, disposar del maquinari equivalent i acceptar que les xifres poden variar per la temperatura, la xarxa i la versió dels models.

La memòria no inclou un manual d'instal·lació perquè el tribunal no ha de muntar el robot: ha d'entendre per què es va muntar així. Les notes tècniques del projecte queden com a **annexos de consulta**, no com el cos del treball.
