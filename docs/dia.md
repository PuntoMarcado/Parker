# El día de Parker: rutinas, apuntes, tiempo, música y apagado

> **Versión:** v6.5.0 (27/10/2026), que añade la escucha por encima de la música
> (ver §5). Todo lo de esta página se resuelve **sin LLM**: Parker reconoce la
> orden, la ejecuta y contesta con una frase corta en menos de 100 ms. Si algo de
> aquí no se reconoce, la frase sigue el camino normal (cerebro) y contesta como
> siempre.

Lo que hay aquí salió de una lista de ideas numerada que el dueño repasó el
26/10: rutinas del día (1), apuntes (2), titular corto en las citas (3),
apagado ordenado (4), el tiempo (5), cambio de modelo solo (6), vigilante del
micrófono (8), música por API (10) y el bandit de iniciativa (14).

---

## 1. Rutinas del día (dormir, despertar, callarse)

| Le dices | Qué pasa | Qué dice |
|---|---|---|
| «Parker, buenas noches» / «a dormir» / «me voy a la cama» | Se duerme: ojos cerrados, deja de tomar la iniciativa, no contesta charla | «Buenas noches. Descansa.» |
| «Parker, buenos días» / «despiértate» | Despierta y suelta **el parte del día** si hay algo apuntado | «Buenos días, Alan. Hoy tienes: …» |
| «Parker, cállate diez minutos» | Silencio temporal (vuelve solo y lo avisa) | «Vale, me callo diez minutos.» |
| «Parker, cállate» (a secas) | 10 minutos por defecto | «Vale, me callo un rato.» |
| «Parker, no hables más» | Silencio hasta que se lo levante la voz o se reinicie | «Vale, me callo hasta que me digas.» |

* **El parte del día** es a las `rutinas.hora_parte` (08:30 por defecto), una vez
  al día, y solo si hay algo en la agenda: citas del día y alarmas que aún no
  han sonado. Si no hay nada no lo dice (o sí, con `parte_si_vacio: true`).
  No lo inventa el modelo: es la agenda leída en voz alta.
* **Dormido o callado** solo se atienden órdenes del día («despiértate»,
  «apágate», «¿estás despierto?»). La charla se ignora a propósito y queda en
  el log: ni una llamada al modelo ni una frase de madrugada.

## 2. «Parker, apágate»: dejarlo todo listo para desenchufar

1. Se despide: «Me voy a dormir del todo. Hasta luego.»
2. La cara hace la **animación de despedida**: bosteza, se le cierran los ojos,
   se marcha hacia un lado encogiéndose y se funde a negro
   (`rutinas.despedida_seg`, 2,4 s).
3. Pide el apagado del sistema: `systemctl poweroff` (configurable en
   `rutinas.orden_apagado`; luego prueba `loginctl poweroff` y
   `shutdown -h now`).
4. **Ya no hay que hacer nada más que desconectar la corriente.** La placa se
   apaga sola y de forma limpia (systemd sincroniza la tarjeta), así que no hay
   riesgo de corromper los recuerdos por cortar a lo bruto. El LED rojo puede
   seguir encendido: eso es la fuente, no la placa trabajando.
5. Al volver a enchufarla arranca sola otra vez (`@reboot` →
   [inicio.md](inicio.md) §5), porque Parker termina con código 0 y `arrancar.sh`
   no lo reinicia.

> **Si no tiene permiso** para apagar, no se queda a oscuras: reaparece en
> pantalla, dice «No he podido apagar la placa: no tengo permiso. Sigo aquí.» y
> lo apunta en el log. Se comprueba sin apagar nada con
> `PARKER_APAGADO_SECO=1` (o `rutinas.apagado_seco: true`): hace toda la
> ceremonia y solo escribe el comando en el log.
>
> En la placa el permiso está dado por `logind`/polkit (verificado el 26/10:
> `pkcheck --action-id org.freedesktop.login1.power-off` responde autorizado).

## 2-bis. Borrar la memoria y reiniciar (v6.12.8)

| Le dices | Qué pasa |
|---|---|
| «Parker, borra tu memoria» / «borra la memoria» / «olvida todo» | **No borra todavía**: pregunta «¿Seguro?…». Si repites la orden en 60 s, vacía Chroma y limpia el historial de la sesión. Agenda, apuntes y personalidad no se tocan. |
| «Parker, reiníciate» / «reinicia el sistema» | Se despide, sale con código 75 y `arrancar.sh`/systemd lo vuelve a levantar en unos segundos. No borra memoria ni ajustes. |

El borrado también se puede hacer sin voz: `python tools/recuerdos.py --borrar`.
Antes de borrar conviene copiar `parker.db` al PC; la placa no guarda respaldos.

> **Probado en la placa el 01/11/2026 (v6.12.8):** «Parker, reiníciate» se oyó,
> se despidió y el supervisor la levantó con un PID nuevo (42828 → 43582) sin
> tocar memoria ni ajustes. El borrado real se hizo con
> `tools/recuerdos.py --borrar` (90 recuerdos → 0) y también por voz: se creó
> 1 recuerdo de prueba, la primera orden pidió confirmación y la segunda lo
> dejó en **0**.
>
> **Fallo corregido esa misma tarde:** el `initial_prompt` del STT llevaba
> preguntas entre «» y Whisper devolvía `¿qué día es hoy?».`; el filtro de eco
> exigía una comilla suelta y tiraba el turno entero, así que parecía sordo.
> Desde v6.12.7 una comilla suelta se limpia y solo se descarta el par «…»;
> desde v6.12.8 **no se envía ningún prompt** al STT (con audio poco claro la
> nube devolvía «Parker se escribe Parker.» y se procesaba como usuario). El
> nombre lo cubre `hotwords`. Comprobado con voz real: «Parker, ¿qué hora es?»
> → «Son las 8 y cuarenta y cinco de la noche».

## 3. Apuntes: notas, listas y contadores

Lo que **no tiene hora** (para eso está la [agenda](agenda.md)):

| Le dices | Qué hace |
|---|---|
| «Parker, apunta que compre leche» | Guarda la nota «compre leche» |
| «Parker, ¿qué tengo apuntado?» / «léeme las notas» | Lee las últimas notas |
| «Parker, borra la nota de la leche» / «borra todos los apuntes» | Borra por texto o todo |
| «Parker, apunta un litro de agua» | Suma 1 litro al contador de **agua** de hoy |
| «Parker, hoy he bebido dos litros de agua» | **Fija** el total de hoy en 2 |
| «Parker, ¿cuánta agua llevo hoy?» | «Hoy llevas un litro de agua» |
| «Parker, borra el contador de agua» | Borra el contador entero |

Cualquier cosa con cantidad + unidad + nombre crea su propio contador («apunta
tres cafés», «apunta cinco kilómetros», «apunta dos pastillas»): **el dueño
puede crear y borrar sus variables por voz**, sin que nadie toque el código.
Se guardan en `parker.apuntes.json` (solo en la placa); los días de contador de
más de `apuntes.dias_conservar` (60) se olvidan.

> **Lo que no puede** (y por qué): no se reescribe el programa. Cambiar
> `config.yaml` o el código desde dentro rompería la huella de versión —la que
> dice qué código corre en la placa— y un error de sintaxis lo dejaría sin
> arrancar. Para variables de verdad (el tiempo, la agenda, los contadores) ya
> tiene módulos con su propia persistencia; para cambiar el comportamiento hay
> que editar y desplegar, que es justo lo que mantiene esto previsible.

## 4. El tiempo y «dónde estoy»

* «¿Qué tiempo hace?» / «¿va a llover mañana?» / «¿cuántos grados hay?» →
  respuesta con las cifras reales de **Open-Meteo** (sin clave ni cuenta).
* «¿Dónde estás?» → «Vivo contigo, en Barcelona (España). El tiempo lo miro de
  ahí.»
* **La ciudad es una variable por voz:** «Parker, estamos en Madrid» la cambia,
  la confirma («Vale: desde ahora miro el tiempo de Madrid (España)») y la
  guarda en `parker.tiempo.json`, que manda sobre `config.yaml`.
* Si no hay internet lo dice claro («No he podido mirar el tiempo: ahora mismo
  no tengo internet») en vez de inventárselo.

## 5. Música por orden de voz

| Le dices | Qué hace |
|---|---|
| «Parker, pon música» | Pone el primer puesto de la lista de éxitos |
| «Parker, pon algo de Queen» | Busca y pone el primer resultado |
| «Parker, pon la canción Bohemian Rhapsody» | Busca por título |
| «Parker, sube/baja la música» | Volumen de la música (independiente del de la voz) |
| «Parker, sube/baja el volumen» (con música sonando) | Es la **música**: es lo que se está oyendo |
| «Parker, sube/baja el volumen de tu voz» | El de la voz, como siempre |
| «Parker, para la música» | Corta y vacía lo que quedara en cola |
| «Parker, ¿qué está sonando?» | «Suena X, de Y» |

* El servicio es **Deezer** (API pública, sin clave): devuelve un **adelanto de
  30 s**. Es lo que se puede poner hoy sin cuenta ni OAuth desde la placa; para
  canciones enteras haría falta Spotify/Apple (cuenta de pago) o YouTube.
* El adelanto se descarga y se **decodifica en memoria con `ffmpeg`** (mono
  22 kHz) y se suena por bloques de 0,25 s: se puede parar a media canción y el
  volumen se aplica al vuelo. No se escribe nada en la tarjeta.
* Encadena hasta `musica.temas_seguidos` (3) resultados de la misma búsqueda,
  para que no se corte a los 30 s.
* **Mientras suena, Parker te sigue oyendo** (v6.5.0). El problema era de
  física: el micrófono oye el altavoz, así que cualquier subida de nivel podía
  ser el estribillo o el dueño hablando. La solución se mide sola: **bajar la
  música un momento («duck», al 15 %) y mirar**. Lo que venía del altavoz baja
  con ella; una persona, no. Así que:
  * Algo sobresale del nivel de la canción → Parker baja la música y comprueba.
  * Si el nivel cae con la música → era la canción: la música vuelve y **no se
    abre ningún turno** (en el log: `[Música] Devuelvo la música…`).
  * Si el nivel sigue alto → eres tú: abre turno con un pre-roll de 1,1 s (tu
    frase empezó mientras sonaba la canción) y te atiende con la música baja.
  * El disparo no basta con superar el nivel medio de la canción: tiene que
    superar también su **máximo de los últimos segundos**, porque una canción no
    se supera a sí misma (su pasaje fuerte es su propio máximo) y una voz sí.
  * Medido en la placa el 27/10 con «Bohemian Rhapsody» (volumen 0,7): la
    canción provoca **2 comprobaciones en 24 s** (antes, 6), todas resueltas
    como «era la canción» y **0 turnos abiertos**.
  * Los umbrales: `musica.duck_factor` (cuánto baja), `musica.factor_disparo`
    (cuánto tiene que sobresalir) y `escucha.pre_roll_musica_seg`. Si la música
    se bajara sola en los pasajes fuertes, subir `factor_disparo`; si no te oye
    por encima, bajarlo.
* Que la canción sola no te robe el turno está probado con el micrófono real:
  `tools/probar_musica_escucha.py` (en la placa, con Parker parado) mide cuánto
  se oye la canción, cuánto baja con el «duck» y cuántas veces se equivoca.
* Si suena una alarma de la agenda, la música se corta para que se oiga la
  campana.

> **El fallo que arregló esto (27/10):** un turno nacido de la propia canción se
> ignoraba sin hablar y **sin soltar el turno** (`ocupado`): Parker dejaba de
> escuchar en cuanto empezaba la música, y seguía sordo después. Ahora el turno
> se suelta siempre, pase lo que pase, y la música vuelve a su volumen.

## 6. Si el proveedor retira el modelo (Groq y sus cambios)

«Cada cierto tiempo Groq cambia sus modelos» (el dueño lo vivió en sus
primeros prototipos). Ahora, al arrancar, Parker pregunta la lista real
(`/models`) y, si el suyo ya no está, pasa al primero de
`online.modelos_alternativos` que siga existiendo; si ninguno está, coge el
primer modelo **de texto** de la lista (nunca uno de voz o transcripción). Lo
avisa en el log con el nombre exacto para dejarlo fijo en `config.yaml`:

```
[Cerebro] «openai/gpt-oss-20b» ya no está en el proveedor; uso
          «openai/gpt-oss-120b». Apúntalo en config.yaml (online.modelo)…
```

## 6-bis. Cambiar de cerebro por voz (nube ↔ local)

| Le dices | Qué pasa | Qué contesta |
|---|---|---|
| «Parker, ponte en local» | Piensa con el cerebro de casa: no intenta internet ni una vez | «Vale, me pongo en local: pienso con qwen2.5:3b aquí dentro…» |
| «Parker, vuelve a la nube» | Vuelve al de internet (y el de casa queda de respaldo) | «Vale, tiro de internet. Si no me llega, te lo digo…» |
| «Parker, modo automático» | Internet mientras haya; el de casa cuando falle | «Vale, en automático…» |
| «Parker, ¿qué cerebro usas?» | Lo dice: modo, modelo y con qué oído te escucha | «Estoy con el de internet (gpt-oss-20b)…» |

* Lo elegido **se recuerda** entre reinicios (`parker.cerebro.json`): si lo dejas
  en local porque el internet va mal, no vuelve a la nube solo.
* Si la nube falla, lo **avisa en voz alta** una vez: «Me he quedado sin
  internet, así que sigo con el cerebro de casa…». También avisa si el
  proveedor frena por pedir demasiado seguido y cuando vuelve. Se silencia con
  `online.avisar_por_voz: false`.
* El oído destroza estas frases cortas («Ponte en local» llegó como «Ponte en lo
  caldo»), así que el reconocedor acepta también frases cortas que terminan en
  «local»/«nube» y parecidos razonables. Detalle: [cerebro_doble.md](cerebro_doble.md) §6-bis.

## 7. Vigilante del micrófono

El fallo real que se vio en la placa no es un error del micro, es que se queda
**entregando silencio** (USB a medio conectar, índice de ALSA cambiado tras un
reinicio): Parker parece sordo y no hay excepción que lo delate. Si el ruido de
fondo se queda por debajo de 0,0005 durante `escucha.rearmar_mic_seg` (90 s),
cierra el flujo, vuelve a buscar el micrófono por nombre y lo abre otra vez:

```
[Escucha] Entrada de audio muerta (0.00012) durante 90s: rearmo el micrófono (rearme nº 1).
```

## 8. Bandit de iniciativa: aprender cuándo hablar

Hasta ahora Parker elegía al azar qué decir cuando llevaba mucho rato callado.
Desde la v6.4.0 trata cada familia de iniciativa como un brazo de un
**bandit** (Thompson sampling con un Beta(1,1) por brazo, sin dependencias):

| Brazo | Qué hace |
|---|---|
| `contar` | Cuenta algo suyo mientras no hablabais |
| `preguntar` | Pregunta por algo concreto y pequeño del día |
| `proponer` | Propone algo sencillo para hacer juntos |
| `eco` | Menciona algo que le contaste hace días |
| `callar` | **No dice nada**: un gesto y ya |

La recompensa la da el uso real, sin gastar un token: **+1** si contestas en
menos de 120 s, **0** si contestas tarde, **−0,3** si nadie contesta en 30
minutos y **−1** si te quejas («cállate», «ahora no»). En `callar` es al revés:
no haber molestado cuenta como acierto. Los contadores se guardan en
`parker.estado.json` y el log enseña qué ha aprendido:

```
[Bandit] bandit: callar 6/2, contar 3/1, eco 4/1, preguntar 9/1, proponer 2/1
[Bandit] preguntar: +1.0 respuesta en 12s (exitos=10.0 fracasos=1.0)
```

Diseño completo y por qué (evolución del personaje):
[evolucion.md](evolucion.md) §6.

## 9. Citas con titular corto

Antes se guardaba la frase entera («tengo cita con el dentista»). Ahora el
calendario guarda un **titular** de como mucho 6 palabras sin artículos ni
conectores, y es lo que se lee y lo que suena en el aviso:

| Dices | Se guarda | Lo que dice al preguntar |
|---|---|---|
| «apunta que el viernes a las 9 tengo cita con el dentista» | `cita dentista` | «El viernes 30 de octubre a las nueve en punto, cita dentista» |
| «recuérdame el 3/12 la renovación del carnet» | `renovacion carnet` | «El jueves 3 de diciembre a las nueve en punto, renovacion carnet» |

Lo que dijiste exacto se guarda aparte (`dicho`) por si hay que revisarlo, pero
no se dice nunca tal cual.

## 10. Probar todo esto sin micrófono

```bash
# En el PC (rápido, sin hardware):
QT_QPA_PLATFORM=offscreen python tests/test_dia.py     # rutinas, apuntes, tiempo, música
QT_QPA_PLATFORM=offscreen python tests/test_musica.py  # búsqueda, decodificación y volumen
QT_QPA_PLATFORM=offscreen python tests/test_bandit.py  # lo que aprende

# En la placa (red real: tiempo, Deezer y ffmpeg de verdad):
~/env/bin/python3 ~/parker/tools/probar_dia.py                  # módulos, con red
~/env/bin/python3 ~/parker/tools/probar_dia.py --sonar          # y suena (Parker parado,
                                                               # así el micro está libre)
~/env/bin/python3 ~/parker/tools/probar_dia.py --apagar-seco    # método real de apagado
~/env/bin/python3 ~/parker/tools/probar_dia.py --apagado        # + comprueba el permiso

# Y para probarlo POR VOZ, con Parker en marcha (lo dice su propio altavoz y
# su micrófono lo oye, como si lo dijeras tú):
~/env/bin/python3 ~/parker/tools/probar_dia.py --decir "Parker, ¿qué tiempo hace hoy?"
tail -n 40 ~/parker.log

# Escucha por encima de la música (con Parker PARADO, para tener el micro libre):
~/env/bin/python3 ~/parker/tools/probar_musica_escucha.py --seg 25
~/env/bin/python3 ~/parker/tools/probar_musica_escucha.py --seg 40 --hablar 10
```

Medido en la placa el 26/10/2026 con estas pruebas:

| Qué | Resultado |
|---|---|
| Tiempo real (Open-Meteo) | «En Barcelona, ahora hay quince grados y está casi despejado» |
| Música (Deezer + ffmpeg) | *Bohemian Rhapsody*, 30,0 s decodificados a 22 kHz y **10,6× el fondo** medido con el micro durante la reproducción |
| Apuntes por voz | «apunta un litro de agua a las 2 de la tarde» → contador de agua, sin crear alarma |
| Fecha por voz | «¿qué día es mañana?» → «Mañana será martes, 27 de octubre de 2026» |
| Apagado | `pkcheck` autorizado y `Parker._apagar()` completo en modo seco (despedida y animación incluidas) |
| Batería completa en la placa | **25/25** en verde (incluidos cara, animación y render) |

> **Nota del STT:** con la voz sintética de las pruebas, «apágate» llegó a
transcribirse como «apajate», y «un litro d'agua» con apóstrofo. Las dos cosas
están arregladas en el código (variantes de apagado en `rutinas.py` y arreglo
del apóstrofo en `_plano`), pero conviene saberlo: el STT en español se inventa
palabras cuando el audio es raro, y las órdenes críticas aguantan ya las
transcripciones reales observadas.

`tools/probar_dia.py` encadena los módulos reales (sin voz ni micrófono) y deja
el resultado en el log: es la forma de comprobar en la placa que el tiempo
llega, que Deezer responde, que `ffmpeg` decodifica y que el apagado está
autorizado.
