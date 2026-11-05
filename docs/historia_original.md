# Historia original de Parker (documento del autor)

> **Qué es este documento.** Transcripción literal del texto que el autor del
> proyecto escribió antes de la etapa actual: el planteamiento inicial, el
> prototipo en el PC y las dos primeras actualizaciones del trabajo académico.
> Se ha respetado la redacción, la ortografía y los encabezados originales
> (incluidos los apartados que quedaron vacíos); solo se ha añadido este
> preámbulo.
>
> **Idioma.** El original está en catalán y así se conserva. La versión
> combinada con la etapa técnica —en español, con fechas, medidas y enlaces al
> código— está en [historia.md](historia.md).
>
> **Fecha.** El documento sitúa su segunda actualización, en el apartado del
> presupuesto, el **11 de agosto de 2026**.

---

3. MARC PRÀCTIC: PROGRAMACIÓ I PLANTEJAMENT DE LA CREACIÓ

La creació de Parker va començar sense ordinador ni codi ni cap tecnologia, el primer que es va fer va ser estructurar de les funcions mínimes que hauria de tenir per considerar-se un projecte funcional.

3.1. El cervell:

En la fase inicial de plantejament de Parker es va dissenyar un sistema de "doble cervell". D'una banda, Groq, un servei en línia que ofereix accés a models de llenguatge de gran escala amb un temps de resposta molt ràpid. De l'altra, Ollama, una eina que permet executar models de llenguatge de mida reduïda directament a l'ordinador, sense necessitat de connexió a internet; gràcies a aquest programa és possible fer córrer una intel·ligència artificial de mida reduïda, adaptada a les limitacions de processament del miniordinador (Raspberry Pi) previst per al dispositiu final.

La motivació d'aquest plantejament dual era evitar que Parker deixés l'usuari "incomunicat" en cas de no disposar de xarxa, ja que dependre sempre d'un servei extern posa en risc tant la disponibilitat del sistema com la privacitat de les converses, mentre que dependre sempre d'un model local poc potent podria alentir excessivament les respostes.

Durant el desenvolupament del prototip a l'ordinador personal, es va optar per simplificar temporalment aquesta arquitectura i treballar únicament amb Groq (concretament amb el model llama-3.3-70b-versatile). Degut a que ens permet centrar els esforços de programació en la resta de mòduls (memòria, veu, expressions) sense haver de gestionar dues vies d'execució en paral·lel. Un cop consolidada la resta del sistema, es preveu substituir Groq per Ollama de manera definitiva.

Un cop valorat amb més perspectiva, es va decidir descartar aquest doble cervell i quedar-se únicament amb Ollama com a solució definitiva. Encara que Groq ofereix respostes de més qualitat, aquest avantatge no compensa la complexitat afegida de mantenir dues vies d'execució en paral·lel ni els inconvenients associats a l'ús d'un servei en línia com són el cost i límits de tokens, dependència de connexió i dades sensibles viatjant a un tercer.

Es va tenir en compte que les converses de Parker no requereixen un raonament complex, sinó que es basen sobretot en la informació que el mateix usuari ha compartit prèviament i que queda emmagatzemada a la memòria de ChromaDB (apartat 3.3); per a aquest tipus d'interacció, un model reduït executat en local és suficient i, a més, garanteix que les dades no surtin mai del dispositiu.

3.2. Reconeixement de veus:

Quan s’inicia el programa el bucle principal de Pygame detecta quan es prem la barra espaiadora. En aquest moment, el fil principal envia un senyal a la cua per canviar la cara d'en Parker a l'estat escoltant. Activa el micròfon de l’ordinador per enregistrar l'ona de veu. L'àudio es captura en format digital un arxiu temporal en format .wav

3.3. Memoria:

Perquè Parker pugui tenir la capacitat de “recordar” es té plantejat implementar-li ChromaDB, una base de dades vectorial de codi obert que funciona de manera 100% local. Aquesta emmagatzemara els temes i experiències parlades amb l’usuari i les sabra identificar encara que hagi passat el temps, en paraules senzilles sera el seu diari on apunta els temes de conversa y experiències importants.

En lloc de desar les converses en un arxiu de text simple (on la IA hauria de llegir milers de línies cada vegada per buscar un record), ChromaDB utilitza un procés d'enginyeria de l'aprenentatge automàtic anomenat RAG (Retrieval-Augmented Generation o Generació Augmentada per Recuperació). Aquesta tecnologia es divideix en tres passos:

Recuperació (Retrieval): Cerca a la base de dades la informació més rellevant per a la conversa actual.
Augment (Augmented): Afegeix aquests records com a context extra (memòria a curt termini) al cervell de la IA.
Generació (Generation): La IA redacta una resposta tenint en compte tant el que li acabes de dir com el passat que ha recuperat.

Cada vegada que l'usuari revela una dada important (per exemple, “Avui em sento un poc trist”), el mòdul transforma aquest text en una cadena de números (un vector) que en representa el significat semàntic. Aquests vectors es guarden de manera permanent a l'arxiu de base de dades local

Quan l'usuari torna a parlar, el sistema cerca a la base de dades quins records del passat s'assemblen matemàticament a la conversa actual. Si l'usuari diu “No sé què menjar avui” ChromaDB recupera el vector d’un altre moment que li haguessis dit “Estic a dieta i sempre haig de menjar pasta i carn” i l'injecta al "cervell" de la IA abans que aquesta generi la resposta. Així, en Parker podria contestar de manera personalitzada: “Has de menjar carn i pasta, ets a dieta”.

2na Actualització

Ens hem adonat que el sistema de memòria que estàvem utilitzant ens estava donant problemes degut a que estava configurat per conversacions i informació en anglès. En aquest moment estem actualitzant la memòria per adaptar-la completament al nostre entorn i solucionar els errors de pèrdua d'informació aplicant tres canvis estructurals:

Canvi al model d'embeddings multilingüe: El "traductor matemàtic" original de chroma db estava entrenat sobretot en anglès, el que generava una tendència i impedia que Parker reconegués bé la similitud de frases en català o castellà. S'ha substituït pel model paraphrase-multilingual-MiniLM-L12-v2, el qual entén la semàntica en més de 50 idiomes de forma nativa i s'executa ràpidament en local.

Ajustament del llindar de similitud (Threshold): Inicialment, el sistema exigia una similitud matemàtica molt alta (del 75%) per considerar que un record era rellevant. Això feia que Parker "oblidés" coses si l'usuari feia servir paraules lleugerament diferents. S'ha reduït aquest llindar a un 50%, permetent que la base de dades sigui més flexible i rescati records associats correctament. En fase de prova.

Aïllament del missatge per a la vectorització: Abans es guardava i es convertia a números el torn complet (el que deia l'usuari més la resposta d'en Parker junts). Això diluïa el significat real del que sentia l'usuari. Ara, el codi s'ha modificat perquè només es transformi en vector el missatge exacte de la persona, garantint una cerca molt més precisa quan es consulti en el futur.

3.4. Expressions

En el moment de la presentació de la memòria d’aquest treball, s’estan utilitzant les expressions estàtiques d’un dels personatges esmentats a l'inici, en BMO. Durant la fase de desenvolupament, s’ha prioritzat de manera deliberada la implementació, optimització i arquitectura de les funcions lògiques del sistema (com ara el processament del llenguatge, la memòria i la integració de models d’IA locals) per sobre del disseny visual definitiu.

Per al disseny final es té la intenció de crear unes animacions perquè Parker tingui fluïdesa a la parla i a les seves expressions.

2na Actualització

Al llarg d’aquest projecte fins ara Parker ha tingut 3 maneres de llenguatge visual. Sent la primera, la abans comentada d’imatges del personatge BMO i la segona una pagina web en local que es connectava amb el codi de python que li enviava les instruccions, sent cada part de la cara, com el ulls i la boca, elements separats pero obtenir més expressions.

En aquest moment de la segona actualització la cara esta composta per vectores. Utilitzant-los de manera dinàmica per obtenir les diferents expressions per a la cara.

4. DISSENY FÍSIC DEL ROBOT ACOMPANYANT

2na Actualització

Gràcies a la col·laboració per part d’un inversor hem pogut augmentar els plantejaments per a la fabricació del dispositiu que portarà a Parker dins. Encara que en aquest moment també s'està decidint si funcionara tot de manera local o com un satèl·lit que rep les dades i les processa.

5. CONSTRUCCIÓ I PROGRAMACIÓ

En aquest moment del projecte s’ha creat un prototip de Parker. Al que se li han implementat millores com han sigut un millor cervell, diferents expressions facials, millor escolta. Juntament amb les altres millores es té pendent la implementació d’una memòria central. Aquesta permetra a Parker “recordar” coses que hagis dit o sentiments que hagi expressat la persona.

6. METODOLOGIA EXPERIMENTAL

7. LIMITACIONS DEL SISTEMA

2a Actualització

En aquest moment i gràcies a l’inversor tenim un pressupost de 250€. L'única limitació en aquest moment és el preu i el processament del cervell de Parker.

A dia d’avui, 11 d’agost es tenen 3 plans per a progressar tenint en compte les limitacions del pressupost, aquest apartat també se li presentara a l’inversor per tenir en compte la seva opinió i poder escollir un dels 3 plantejaments.

En primer lloc tenim l’idea d’augmentar el pressupost.

En segon lloc, fer-ho com una pantalleta petita al costat del monitor de l’ordinador i que el cervell de la IA estigui a l’ordinador. Desavantatges d’aquest plan es que el temps de resposta dependrà de l’ordinador i la seva Ram.

En tercer lloc, transformar-ho en un assistent per a la cuina, tu li pases la recepta y et va dictant els ingredients, els passos i com fer cada cosa perquè tu no hagis de mirar la recepta cada cop.

8. CONCLUSIONS
