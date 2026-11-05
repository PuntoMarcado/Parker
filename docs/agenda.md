# La agenda de Parker: alarmas, temporizadores y citas

Desde la **v6.3.0 (26/10/2026)** Parker hace tres cosas útiles con el tiempo. Se
reconocen **sin pasar por el modelo** (como el volumen): contestan al instante,
no se inventan nada y no cuestan latencia. Cuando llega el momento, el aviso
**suena de verdad**: 2,5 s de campana por su altavoz (`despertador` en
`modulos/sonidos.py`) y después la frase.

Todo se guarda en **`parker.agenda.json`**, en la placa (el PC no se llena: ahí
solo van las copias). Los avisos de hace más de 30 días se olvidan solos.

| Quiero… | Le dices… |
|---|---|
| Un temporizador | «Parker, pon un temporizador de 10 minutos» · «avísame en media hora» · «recuérdame en 5 minutos **sacar la ropa**» · «en un minuto y medio» |
| Una alarma a una hora | «pon una alarma a las 7:30» · «despiértame a las siete y media» · «avísame a las 22:15» · «pon una alarma a las 7 de la tarde» |
| Apuntar una cita | «apunta que el viernes a las 5 tengo al dentista» · «recuérdame el 12 de noviembre a las 17:00 el médico» · «apunta el 3/12 la renovación del carnet» |
| Saber qué tiene | «¿qué tengo hoy?» · «¿qué tengo mañana?» · «¿qué tengo el viernes?» · «¿qué tengo esta semana?» · «¿qué alarmas tengo?» |
| Quitar algo | «borra el temporizador» · «cancela la cita del dentista» · «borra todas las alarmas» |

La frase larga que se guarda es la parte útil: `recuérdame en 5 minutos sacar la
ropa` avisa diciendo «¡Bip, bip! Han pasado cinco minutos. sacar la ropa.».

## Cómo interpreta lo que le dices

Son decisiones de diseño, no adivinanzas: están para que un fallo se note en la
confirmación (que dice el día y la hora **en palabras**) antes de que llegue el
aviso.

- **Alarma**: la **próxima** vez que sean esas horas. A las 16:00, «a las 7» es
  mañana a las 7:00 y lo contesta así («Alarma puesta para mañana a las siete»).
  «De la mañana», «de la tarde» y «de la noche» mandan sobre eso.
- **«A las 9 menos cuarto»** son las 8:45 y **«a las 7 y 50»** las 7:50: el
  acarreo se resuelve solo.
- **Cita**: una hora de 1 a 7 se entiende de la tarde (17:00) y de 8 a 11 de la
  mañana, porque es lo normal en una cita. Se oye en la confirmación.
- Una cita **sin hora** avisa a las 09:00 (`agenda.hora_citas`).
- Para apuntar una cita hace falta un verbo de apunte («apunta», «anota»,
  «recuérdame»): «el viernes tengo médico» a secas es charla, no una cita.
- **Repetir todavía no**: «despiértame todos los días a las 7» pone la próxima
  vez y la propia respuesta lo avisa («Solo lo pongo una vez; repetirlo cada día
  todavía no sé hacerlo»). Preferimos decirlo a prometerlo.
- **Silencio**: la campana suena aunque tengas la voz silenciada (un aviso se
  pide a propósito), pero no baja del 35 % (`agenda.volumen_minimo_aviso`) para
  que se oiga. La frase hablada sí respeta el volumen y el silencio.
- Si la placa estuvo apagada, al volver **recupera** los avisos que vencieron
  hace menos de `agenda.caducidad_horas` (12 h) y **descarta** los más viejos
  (un «sacar la ropa» de la semana pasada no tiene que sonar solo al encender).
- Los datos que Parker contesta aqui **no** se quedan en su contexto: la consulta
  es instantánea y no gasta un turno de cerebro.

## Comprobarlo de verdad en la placa

`tools/probar_agenda.py` hace la prueba que los tests no pueden hacer: medir con
**su propio micrófono** que la campana se oye por el altavoz. Con Parker parado
(el micro tiene que estar libre):

```bash
ssh orangepi@192.168.1.130
for p in $(pgrep -f 'arrancar\.sh'); do kill $p; done   # parar supervisor y Parker
cd ~/parker && QT_QPA_PLATFORM=offscreen ~/env/bin/python3 tools/probar_agenda.py --seg 8
~/parker/tools/arrancar.sh                              # volver a arrancarlo
```

Última ejecución (26/10, con el temporizador de 8 s):

```
[Prueba] «Parker, pon un temporizador de 8 segundos la lavadora» ->
         Temporizador de ocho segundos. Te aviso a las nueve y dos de la noche.
[Prueba] Silencio de fondo: RMS 0.00632
[Prueba] Campana reproducida en 2.57s de audio real
[Prueba] Durante la campana: RMS 0.12870 (20.4x el fondo)
[Prueba] Venció con +0.03s de desfase -> ¡Bip, bip! Han pasado ocho segundos. lavadora.
[Prueba] TODO BIEN: la campana se oye y el aviso salta a su hora.
```

Y en el log del Parker real, con un aviso venciendo mientras corre:

```
[Agenda] 2 avisos guardados («pon una alarma a las 7», «avísame en 10 minutos»)
[Agenda] AVISO (temporizador): ¡Bip, bip! Han pasado treinta y cinco segundos. doblar la ropa.
[Voz] Reproduccion finalizada
```

## Ajustes (en `config.yaml`, sección `agenda`)

```yaml
agenda:
  ruta_agenda: "./parker.agenda.json"
  hora_citas: "09:00"              # una cita sin hora avisa a esta hora
  intervalo_comprobacion_seg: 1.0  # cada cuánto mira si algún aviso venció
  caducidad_horas: 12              # un aviso más viejo no suena al volver
  volumen_minimo_aviso: 0.35       # la campana no baja de aquí
```

## Lo que aún NO hace (y sería el siguiente paso)

- **Repetir** alarmas (diaria, laborables, «todas las mañanas»).
- **Posponer** («cinco minutos más») y **parar** la alarma con la voz.
- **Notas y listas**: «apunta que compre leche», «¿qué tenía que comprar?».
- **Avisar con antelación**: «avísame 10 minutos antes de la cita».
- **Contar tiempo de conversación** (pomodoro: «avísame en 25 minutos de trabajo»).
- **Modo buenas noches**: no hablar hasta una hora concreta.

## Reprogramar por voz y no romperse (30/10/2026)

`agenda.procesar()` prueba `_reprogramar()` **antes** de crear. Reconoce:

- «cambia la hora del dentista de mañana a las 6 de la tarde» (fecha + hora);
- «cambia la cita del dentista a las 7» (conserva el día que ya tenía);
- «cambia la alarma de las 7 a las 8» (la primera hora identifica cuál es);
- «cambia la alarma a las 8» si solo hay una.

Si hay varias y la frase no dice cuál (ni materia ni hora vieja), **pregunta**
en vez de elegir al azar. Para borrar pasa lo mismo: «borra la alarma» con dos
puestas pregunta; «borra todas las alarmas» borra las dos.

La materia del aviso se conserva al mover la hora. El texto que se guarda es el
título corto (`cita dentista`, no la frase entera); la frase original queda en
`dicho` solo para revisarla. «Parker pone una alarma» ya no guarda «pone una»:
el limpiador reconoce también las variantes del STT (`pone`, `pones`, `ponle`…).

Robustez del fichero: un JSON truncado, un `[]`, un `null`, una entrada que no
sea objeto, un `ts` no numérico, `NaN`, `infinito` o una fecha fuera de
2000-2100 se descartan al cargar. La agenda arranca vacía o solo con lo válido;
nunca deja a Parker sin voz. El guardado es atómico (`.tmp` + `replace`).

Pruebas: `tests/test_agenda.py` **10/10** (incluye reprogramar cita/alarma,
ambiguas, corrupción y persistencia). En la placa (v6.9.0) la cita del dentista
pasó a 31/10 18:00 y la alarma de 19:00 a 20:00 con una sola entrada.
