# Copias de seguridad: qué hay en cada una

> **Regla de oro:** las copias viven **solo en este PC** (`backups/`). En la
> Orange Pi no se respalda: su tarjeta es para los recuerdos de Parker. Si se
> intenta allí, `tools/respaldo.py` se niega (detecta `RK3588S OPi 5 Pro`).

Cada carpeta es una copia **completa** del código de ese momento (no un parche).
Restaurar = copiar su contenido encima del proyecto.

```bash
# Copia nueva, con la fecha y una etiqueta
python tools/respaldo.py "antes-de-algo"

# Copia nueva incluyendo los recuerdos de la placa (parker.db + estado)
python tools/respaldo.py --con-recuerdos

# Restaurar una copia concreta
cp -r backups/2026-10-25_1746_antes-cerebro-doble/{parker.py,config.yaml,modulos,tests,tools,docs} .
```

Qué lleva cada copia:

| Fichero | Qué es |
|---|---|
| `parker.py` | programa principal (UI, escucha, boca, autonomía) |
| `config.yaml` | toda la configuración (cerebro, voz, escucha, pantalla, personalidad) |
| `modulos/` | cerebro, personalidad, memoria, escucha, voz, cara y pantalla |
| `tests/` | pruebas que deben pasar antes y después de tocar algo |
| `tools/` | scripts de diagnóstico, medición, respaldo y arranque |
| `docs/` | documentación |
| `INS.txt`, `README.md`, `requirements.txt` | notas y dependencias |
| `placa/` | **solo con `--con-recuerdos`**: `parker.db` (Chroma) y `parker.estado.json` |
| `LEEME.txt` | fecha, versión, motor del cerebro y nombres de variables `.env` |
| `MANIFIESTO.txt` | `sha256` + tamaño de cada fichero (para comparar copias) |

**No** se copian: `venv/` (se rehace con `pip install -r requirements.txt`), los
**valores** de `.env` (nunca se escriben en una copia; sí sus nombres en el
`LEEME.txt`) ni `assets/` (61 MB de voces, fijos desde el 4/10).

---

## Índice, en orden

### 1. `2026-10-17_1345` — punto de partida
Primera copia completa de la v5: cerebro **online con Groq** (`openai/gpt-oss-120b`),
voz Piper, cara Disney y escucha con Whisper. Sin `tests/test_rendimiento.py`
todavía. Es el «estado original» al que volver si algo se tuerce de raíz.

### 2. `2026-10-17_1416_latencia-optimizada` — primeras medidas
Cambian `cerebro.py`, `escucha.py`, `memoria.py`, `personalidad.py`, `parker.py`
y `config.yaml`. Nace **`tests/test_rendimiento.py`** (guardas de `num_ctx`,
`max_tokens`, umbral de memoria) y se ajustan los tests de personalidad y
pipeline para vigilarlo.

### 3. `2026-10-17_1504_latencia-cache-prefijo` — caché de prefijo
El cambio grande: separar **identidad (estática)** de **ánimo/fecha (volátil)**
para que Ollama pueda reutilizar el prefijo. Toca `cerebro.py`, `parker.py`,
`personalidad.py`, `memoria.py` y la documentación (`arquitectura`, `placa`,
`rendimiento`); el test de rendimiento gana las comprobaciones del prefijo.

### 4. `2026-10-17_1515_parker-db` — solo los recuerdos
No hay código: es un `parker.db.tgz` (Chroma comprimido). Existe aparte porque
los recuerdos **no están en git** y se perdían en las pruebas de esa tarde.

### 5. `2026-10-17_1527_autostart-y-documentacion` — arranque solo
Mismos ficheros de código que la copia 1 y documentación nueva: cómo arranca
Parker al encender (`tools/arrancar.sh` con `@reboot`), lock de instancia única
y rotación del log.

### 6. `2026-10-17_1559_identidad-vinculo-voz` — quién es y cuánto te quiere
Cambian `cerebro.py`, `personalidad.py`, **`voz.py`** y `parker.py`: identidad
propia de Parker, vínculo que crece con los días y la voz con `velocidad` y
`volumen` (en vez de tocar el audio). Nace `tests/test_voz.py`.

### 7. `2026-10-17_1805_antes-frases-termica-rkllm` — antes de tocar el habla
Punto de guardado antes de las frases prefabricadas, la lectura de sensores
térmicos y la prueba de RKLLM. Añade `tests/test_conversacion.py` y toca
`config.yaml`, `cerebro.py`, `personalidad.py`, `parker.py` y `docs/`.

### 8. `2026-10-17_1847_antes-fecha-y-relleno` — antes de fecha y muletillas
Guarda el estado justo antes de resolver fecha/hora **sin LLM** y de filtrar
las frases de relleno («mmm»). Cambian `cerebro.py`, `personalidad.py`,
`parker.py` y los dos tests de conversación/personalidad.

### 9. `2026-10-24_1433_antes-mejoras-rocky` — antes de copiar a Rocky
Solo cambia `README.md` y aparecen **`docs/evolucion.md`** y
**`docs/plan_mejoras.md`**: el diseño de la evolución y el plan de mejoras
tomadas del otro robot. El código es el de la copia 8.

### 10. `2026-10-25_1746_antes-cerebro-doble` — **el último «todo local»**
Copia completa **antes** del cambio a cerebro doble, con recuerdos incluidos
(`placa/parker.db` + `parker.estado.json`, 169 interacciones y 18 documentos).
Estado: v5 sin marca de versión, cerebro `qwen2.5:3b` en la placa, `num_ctx`
2048, precalentado por turno activo. **Medido ese día en la placa: TTFB p50
8,75 s** (mín. 3,99 / máx. 12,40), turno completo p50 13,45 s, 9,3 tok/s.
Es la copia a la que volver para tener a Parker otra vez 100 % local.

### 11. A partir de aquí: v6 (cerebro doble)
Con la v6 el cerebro es **nube (primario) + local (respaldo)**; ver
[cerebro_doble.md](cerebro_doble.md). Las copias nuevas lo dirán en su
`LEEME.txt` (`Versión: v6.0.0-doble-cerebro` y la línea `Cerebro:`).

### 12. `2026-10-26_2152_antes-v6.4.0-dia-musica-bandit` — antes del día completo
Copia completa (64 ficheros) **antes** de la sesión de las 14 ideas. Es el
estado **v6.3.0** con la agenda ya probada en la placa y sin nada de lo nuevo:
sin `rutinas.py`, `apuntes.py`, `tiempo.py` ni `musica.py`; sin el titular corto
en las citas; sin el cambio automático de modelo de la nube. Si algo de la
v6.4.0 diera problemas, esta es la copia a la que volver para quedarse en la
agenda + cerebro doble, que es lo último verificado a fondo en la placa.

Qué cambió exactamente la v6.4.0 respecto a esta copia (todo en
[plan_mejoras.md](plan_mejoras.md) y [dia.md](dia.md)):

| Fichero | Cambio |
|---|---|
| `parker.py` | Rutinas, apuntes, tiempo y música en el reparto sin LLM; parte del día; hilo de música; `_apagar()` con despedida; bandit en la autonomía; vigilante del micrófono |
| `config.yaml` | Secciones nuevas `rutinas`, `apuntes`, `tiempo`, `musica`; `modelos_alternativos`; `escucha.rearmar_mic_seg`; `autonomia.recompensa_iniciativa_seg` |
| `modulos/agenda.py` | Titular corto (`_titulo`), prioridad de las órdenes sobre las consultas, muletillas y apóstrofos del STT |
| `modulos/apuntes.py` | Nuevo: notas, listas y contadores + `parece_contador()` |
| `modulos/rutinas.py` | Nuevo: dormir/despertar, silencio temporal, parte del día y apagado (con variantes de STT) |
| `modulos/tiempo.py` | Nuevo: Open-Meteo sin clave y la ciudad como variable por voz |
| `modulos/musica.py` | Nuevo: Deezer sin clave + decodificación en memoria con `ffmpeg` |
| `modulos/personalidad.py` | Bandit de iniciativa (5 brazos) y copia profunda del estado (dos instancias no se pisaban) |
| `modulos/cerebro.py` | `revisar_modelo_online()`: elige otro modelo si el proveedor retira el configurado |
| `modulos/cara_parker.py` | `dormirse()`, `despertarse()`, `despedida()` (se marcha de lado y se funde) y `reaparecer()` |
| `modulos/version.py` | v6.4.0 + los módulos nuevos en la huella de código |
| `tests/` | `test_dia`, `test_musica`, `test_bandit`, `test_modelos_nube` (nuevos) y ampliaciones en `test_agenda`, `test_cara`, `test_personalidad`, `test_pipeline`, `test_rutinas` |
| `tools/probar_dia.py` | Nuevo: prueba real en la placa (red, altavoz, medición con el micro y apagado en seco) |

### 13. `2026-10-27_1846_antes-v6.5.0-musica-escucha` — antes de la música con orejas
Copia completa (72 ficheros) **antes** del arreglo de la escucha con música.
Es el estado **v6.4.0** tal y como quedó desplegado: el que ponía música pero
solo atendía órdenes de música mientras sonaba, y que se quedaba sordo si el
turno lo abría la propia canción.

Qué cambió la v6.5.0 respecto a esta copia ([dia.md](dia.md) §5):

| Fichero | Cambio |
|---|---|
| `parker.py` | El turno se suelta SIEMPRE (era lo que dejaba a Parker sordo); modo música con `OyenteMusica` (duck + comprobación) y pre-roll de 1,1 s; las órdenes de música van antes que las acciones; la ganancia suena en rampa |
| `config.yaml` | `musica.duck_factor` (0,15) y `musica.factor_disparo` (1,2); `escucha.pre_roll_musica_seg` (1,1) |
| `modulos/musica.py` | `duck`/`duck_factor`, `ganancia_objetivo()`, `ganancia(ganancia=)`, `procesar(sonando=)` («baja el volumen» con música sonando) y la clase `OyenteMusica` |
| `modulos/version.py` | v6.5.0-musica-escucha (musica.py entra en la huella de código) |
| `tests/test_musica.py` | 8/8: volumen con música sonando, el «duck» y el discriminador (canción sola 0 turnos / persona 10 de 10) |
| `tests/test_dia.py` | La charla con música ya no se traga el reparto; «baja el volumen» es la música |
| `tools/probar_musica_escucha.py` | Nuevo: prueba real en la placa (suena la canción por el altavoz y mide con el micrófono) |

### 14. `2026-10-27_1947_antes-v6.6.0-ficha-rotacion` — antes de la ficha que rota
Copia completa (72 ficheros) **antes** de que sus gustos y sueños dejen de ser
siempre los mismos. Es el estado **v6.5.0-musica-escucha** (la música con orejas)
con la identidad enseñando siempre la primera entrada de la ficha: «le gusta la
lluvia» y «sueña con silbar» en todos los turnos.

Qué cambió la v6.6.0 respecto a esta copia ([plan_mejoras.md](plan_mejoras.md)):

| Fichero | Cambio |
|---|---|
| `modulos/personalidad.py` | `rotacion()` y `_rotar_si_toca()`: un gusto y un sueño distintos por conversación (índice guardado en `parker.estado.json`); `_lista()` pasa de `items[:n]` a ventana circular; la regla de «no saques tus gustos» deja de nombrar «lluvia» y «zumbido»; `resumen_para_log()` dice qué ficha lleva |
| `config.yaml` | `personalidad.rotacion` (true) y `personalidad.rotacion_minutos` (45) |
| `modulos/version.py` | v6.6.0-ficha-rotacion |
| `tests/test_personalidad.py` | Caso nuevo: estable dentro de la charla, distinta entre charlas, apagable y persistente |

### 15. `2026-10-27_2036_v6.7.0-antes-de-desplegar` — el cerebro por voz
Copia completa (73 ficheros) del árbol con la **v6.7.0 ya escrita**, hecha justo
antes de desplegarla en la placa. Sirve de punto de vuelta si la verificación en
el dispositivo hubiera fallado. La v6.6.0 desplegada y verificada antes de esta
sesión vive en la copia 14 más los ficheros que cambiaron aquí (el resto del
árbol es el mismo).

Qué añade la v6.7.0 respecto a la copia 14 ([cerebro_doble.md](cerebro_doble.md)
§6-bis):

| Fichero | Cambio |
|---|---|
| `modulos/cerebro.py` | Modos `auto`/`nube`/`local` (`cambiar_modo`, `modo_actual`, `frase_modo`), persistencia en `parker.cerebro.json`, avisos hablados de caída/vuelta (una vez por caída, con el 429 aparte) y `_online_disponible()` respetando el modo |
| `modulos/acciones.py` | `interpretar_orden_cerebro()`: órdenes por voz sin LLM, con las tres redes (canónicas, «termina en el destino», parecido `difflib`) para los fallos del oído |
| `parker.py` | Cableado de la orden (antes de las acciones) y `_decir_avisos_cerebro()` en la autonomía |
| `config.yaml` | `online.modo_inicial`, `online.ruta_estado`, `online.avisar_por_voz` |
| `modulos/version.py` | v6.7.0-cerebro-por-voz |
| `tests/test_cerebro_doble.py` | 13/13 (modos, persistencia, avisos) |
| `tests/test_acciones.py` | 8/8 (frases por voz, mangles del oído y negativos) |
| `docs/cerebro_doble.md`, `docs/dia.md`, `docs/plan_mejoras.md` | El modo por voz, sus avisos y lo medido |
| `tools/probar_memorias.py` | Viene de la sesión anterior y entra en esta copia: prueba real de la memoria (escala, umbral y fidelidad del cerebro) sin tocar `parker.db` |

---

### 16. `2026-10-27_2128_v6.8.0-cara-con-vida-propia` — la cara con vida propia

| Fichero | Qué trae |
|---|---|
| `modulos/cara_parker.py` | Director de gestos en reposo: `FAMILIAS_GESTOS` (despierto/solo/aburrido por silencio), `set_silencio()`, `familia_gestos()`, `gesto()`, `_gesto_aleatorio()`, `_pose_base()`, `_volver_al_frente()` y los gestos nuevos `micro_ceja`, `curiosear`, `mirar_arriba`, `cabecear`, `estiron`, `suspirar`. Parpadeo que se espacia y se hace lento con el silencio, amplitudes del motor de vida subidas y `_gesto_timer` en `detener()`/`dormirse()` |
| `parker.py` | Señal `SenalesCara.silencio` → `ParkerWindow._recibir_silencio` → `face.set_silencio()`; el bucle de autonomía manda el silencio y la cara se pone en `pensando` antes de la charla propia (`_comprobar_autonomia`) |
| `config.yaml` | `autonomia.umbral_silencio_seg: 900` (15 min; antes 2700) |
| `modulos/version.py` | v6.8.0-cara-con-vida-propia |
| `tests/test_cara.py` | 6/6 (director: familias por silencio, catálogo existente, gestos con vuelta, ojos sin alargarse) |
| `tests/test_animacion.py` | 9/9 (el director se para dormido y vuelve al despertar) |
| `docs/arquitectura.md`, `docs/evolucion.md`, `docs/placa.md`, `docs/plan_mejoras.md`, `README.md` | El director de gestos, la cadencia nueva y el aviso de las dos instancias |

---

### 17. `2026-10-30_1230_v6.8.1-micro-listo` — el oído a tiempo

Copia completa (75 ficheros) con el arreglo del arranque: el micro USB aparece
~29 s después de encender la placa y PortAudio cacheaba la lista sin él.

| Fichero | Qué trae |
|---|---|
| `parker.py` | `_resolver_microfono(..., esperar_seg)` espera y refresca PortAudio; el primer intento espera 25 s y el chime de «micro listo» suena antes de abrir la entrada |
| `modulos/sonidos.py` | `micro_listo()`: dos notas ascendentes, 0,43 s, distinta de la campana de la agenda |
| `config.yaml` | `escucha.esperar_micro_seg: 25` y `aviso_micro_volumen: 0.35` |
| `modulos/version.py` | v6.8.1-micro-listo |
| `tests/test_microfono.py` | 2/2: el micro que aparece tarde se encuentra tras refrescar; si ya está, no espera |
| `tests/test_sonidos.py` | 4/4 (nuevo caso del chime) |
| `docs/placa.md`, `docs/historia.md`, `README.md` | El diagnóstico y la lección del 30/10 |

---

### 18. `2026-10-30_1255_v6.9.0-agenda-reprogramable` — la agenda se deja cambiar

Copia completa (76 ficheros) con la primera versión que reprograma citas y
alarmas existentes en vez de crear otra o contestar con la ficha del vínculo.

| Fichero | Qué trae |
|---|---|
| `modulos/agenda.py` | `_reprogramar()` antes de crear, búsqueda por tipo/materia/hora vieja y conservación del título |
| `modulos/personalidad.py` | `charlas` cuenta conversaciones con hueco de 45 min; el número sale del prompt |
| `modulos/cerebro.py` / `parker.py` | Filtro `quitar_fugas_prompt` para que la ficha no se diga en voz alta |
| `tests/test_agenda.py` | Casos de reprogramar cita y alarma sin duplicar |

---

### 19. `2026-10-30_1356_v6.9.1-charlas-agenda-segura` — 232 charlas, corregidas

Copia completa (77 ficheros) con el cierre del 30/10: migración del contador
inflado, pauta de trato sin cifras, agenda que pide cuál cambiar/borrar cuando
hay varias y carga tolerante a ficheros corruptos.

| Fichero | Qué trae |
|---|---|
| `modulos/personalidad.py` | `CHARLAS_VERSION = 2`, `_migrar_charlas()` (techo 2/día), `_sanear_estado()`, guardado atómico y `vinculo_para_prompt()` sin `%`/días/charlas |
| `modulos/agenda.py` | Variantes del STT (`pone`, `pones`, `ponle`…), confirmación si hay varias, carga tolerante a `NaN`/`inf`/JSON truncado, sin `@staticmethod` duplicado |
| `modulos/cerebro.py` | `quitar_fugas_prompt` reconoce también `Pauta de trato:` y `Trato:` |
| `tests/test_agenda.py` | 10/10 (payload «pone una», ambiguas, corrupción) |
| `tests/test_personalidad.py` | Migración 232 -> 25, pauta sin cifras, estado saneado |
| `tests/test_cerebro_doble.py` | 14/14 (fugas nuevas) |
| `tests/test_conversacion.py` | Dos turnos seguidos son una conversación |
| `modulos/version.py` | v6.9.1-charlas-reales-agenda-segura |
| `docs/plan_mejoras.md`, `docs/agenda.md`, `docs/rendimiento.md`, `docs/investigacion_oct2026.md` | Diagnóstico, pruebas, medidas y research |

---

### 20. `2026-10-30_2038_v6.10.0-voz-edge` — Ximena y respaldo Piper

Copia completa (79 ficheros) con la voz de Edge TTS y el despliegue en la placa
hecho el 30/10 por la tarde. Incluye también el estado de la placa antes del
despliegue en `backups/2026-10-30_2015_placa-antes-v6.9.1/` (código y datos).

| Fichero | Qué trae |
|---|---|
| `modulos/voz.py` | `motor="edge"`, `es-ES-XimenaNeural`, MP3→PCM con ffmpeg, normalización, respaldo Piper con enfriamiento y reintentos de ALSA |
| `parker.py` / `config.yaml` | Paso de los parámetros de voz; `voz.motor: edge`; `edge_timeout_seg` y `edge_reintento_seg` |
| `modulos/version.py` | v6.10.0-voz-edge-ximena; `modulos/voz.py` en la huella |
| `tests/test_voz_edge.py` | Selección Edge, respaldo, enfriamiento y ritmo (sin red) |
| `docs/lora_voz.md` | LoRA de personalidad vs. LoRA de voz, ruta práctica |
| `docs/plan_mejoras.md`, `docs/rendimiento.md`, `README.md` | Cambio, medidas y estado |

**Antes de esta copia** hay dos snapshots del mismo día:
`2026-10-30_2012_pre-despliegue-v6.9.1` (PC) y
`2026-10-30_2015_placa-antes-v6.9.1` (código y datos de la placa).

La copia **`2026-10-30_2049_v6.10.0-final`** es la misma versión con la
documentación de las pruebas de modelos ya incluida (79 ficheros).

---

### 21. `2026-10-30_2108_v6.10.0-lora-pipeline` — tubería LoRA de actitud

Copia completa (92 ficheros) con la programación del LoRA de personalidad y la
documentación de la línea base. No incluye modelos ni adaptadores entrenados
(todavía no existen); sí incluye semilla, scripts, evaluación base y README.

| Fichero | Qué trae |
|---|---|
| `training/persona_sistema.txt` | System prompt compacto para entrenar |
| `training/datos/semilla.jsonl` | 28 diálogos escritos a mano |
| `training/preparar_dataset.py` | Limpieza de logs, validación, deduplicación y split 25/3 |
| `training/generar_dataset.py` | Ampliación sintética con Groq (probada 2/2 en la placa) |
| `training/entrenar_lora.py` | QLoRA 4 bits para Qwen2.5-3B |
| `training/fusionar_lora.py` / `exportar_ollama.sh` | Fusión, GGUF, cuantización y `ollama create` |
| `training/evaluar_lora.py` / `evaluacion_base.md` | Comparativa base vs LoRA; línea base real del 3B |
| `training/README.md` | Requisitos, pasos y límites (no hay GPU en este PC) |

---

## Cómo saber qué copia es cuál sin abrir ficheros

```bash
# Versión y motor de cada copia
grep -H "Version\|Cerebro" backups/*/LEEME.txt

# ¿Qué cambió entre dos copias? (nombres de ficheros)
diff -rq backups/2026-10-25_1746_antes-cerebro-doble backups/<otra> | grep -v LEEME

# ¿Este fichero es igual al de la copia?
sha256sum parker.py; grep " parker.py$" backups/2026-10-25_1746_antes-cerebro-doble/MANIFIESTO.txt
```
