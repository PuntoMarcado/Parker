---
tema: TREC
bloc: 7
estat: annex
tipus: annex
---
# 15 · Annex. Codi font complet

> **El codi no s'enganxa dins de la memòria.** El conjunt té més de 23.000
> línies i canvia amb el projecte; per això es publica al repositori i aquí se
> n'ofereix el mapa, la funció de cada fitxer i l'enllaç per obrir-lo des del
> mòbil o descarregar-lo sencer.

[[TREC/03 Marc practic]] · [[TREC/14 Annex. Muntatge i esquemes electrònics]] · [[TREC/08 Annex. Criteris de muntatge]]

## 1. Enllaç principal

- **Repositori:** <https://github.com/PuntoMarcado/Parker>
- **Codi en un sol fitxer ZIP:**
  <https://github.com/PuntoMarcado/Parker/archive/refs/heads/main.zip>
- **Annex de muntatge:** [[TREC/14 Annex. Muntatge i esquemes electrònics]]

La branca remota és **`main`**. Els enllaços d'aquest annex hi apunten
directament; si el repositori canvia de nom o de branca, cal actualitzar-los.

> **Accés des del mòbil.** El repositori és **privat**. Per obrir-lo cal iniciar
> sessió a GitHub amb un compte que hi tingui accés. Si s'ha de consultar des
> d'un dispositiu sense compte, cal fer el repositori públic o exportar els
> annexos; els enllaços no fan pública la documentació per si sols.

## 2. Per què el codi va a part

Incloure els scripts sencers dins del text trencaria el ritme de la memòria i
faria el document impossible de llegir. La solució és la mateixa que en un
projecte professional:

1. La memòria explica **què fa** el sistema i **per què**.
2. Aquest annex diu **on és** cada fitxer i **quina responsabilitat** té.
3. El repositori conserva el codi executable, la configuració i les proves.

No és una excusa per no llegir el codi: és una separació entre el relat i el
material de consulta.

## 3. Mapa general

| Bloc | Fitxers | Línies aproximades | Enllaç |
|---|---:|---:|---|
| Nucli i arrencada | `parker.py` | 2.698 | [parker.py](https://github.com/PuntoMarcado/Parker/blob/main/parker.py) |
| Mòduls | 21 fitxers a `modulos/` | 10.582 | [modulos/](https://github.com/PuntoMarcado/Parker/tree/main/modulos) |
| Configuració | `config.yaml` | 448 | [config.yaml](https://github.com/PuntoMarcado/Parker/blob/main/config.yaml) |
| Dependències | `requirements.txt` | 20 | [requirements.txt](https://github.com/PuntoMarcado/Parker/blob/main/requirements.txt) |
| Proves | 31 fitxers a `tests/` | 6.282 | [tests/](https://github.com/PuntoMarcado/Parker/tree/main/tests) |
| Eines | 20 fitxers a `tools/` | 2.945 | [tools/](https://github.com/PuntoMarcado/Parker/tree/main/tools) |
| Entrenament | 11 fitxers a `training/` | 1.124 | [training/](https://github.com/PuntoMarcado/Parker/tree/main/training) |
| **Total** | **~80 fitxers** | **~23.300** | [Repositori](https://github.com/PuntoMarcado/Parker) |

El recompte és aproximat i pot variar amb el desenvolupament. La font de veritat
és el repositori, no aquesta taula.

## 4. Mòduls un per un

| Fitxer | Línies | Responsabilitat |
|---|---:|---|
| [`modulos/acciones.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/acciones.py) | 602 | Ordres directes sense LLM: volum, silenci i silbido |
| [`modulos/agenda.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/agenda.py) | 1.080 | Alarmes, temporitzadors i cites en local |
| [`modulos/apuntes.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/apuntes.py) | 356 | Notes, llistes i comptadors |
| [`modulos/barge_in.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/barge_in.py) | 75 | Cancel·lació del torn i represa |
| [`modulos/cara_parker.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/cara_parker.py) | 1.352 | Cara vectorial, motor de vida, gestos i lip-sync |
| [`modulos/cerebro.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/cerebro.py) | 1.623 | Cervell doble, streaming i etiquetes d'emoció |
| [`modulos/display_spidev.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/display_spidev.py) | 817 | Driver SPI/GPIO de la GC9A01 |
| [`modulos/escucha.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/escucha.py) | 425 | Transcripció amb dos backends |
| [`modulos/filtro_stt.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/filtro_stt.py) | 124 | Filtre d'al·lucinacions del STT |
| [`modulos/hechos.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/hechos.py) | 331 | Memòria de fets exactes |
| [`modulos/memoria.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/memoria.py) | 353 | Memòria vectorial i recuperació híbrida |
| [`modulos/musica.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/musica.py) | 490 | Música per API i detecció de veu sobre la cançó |
| [`modulos/personalidad.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/personalidad.py) | 1.210 | Identitat, ànim, víncle i iniciativa |
| [`modulos/prosodia.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/prosodia.py) | 194 | Ajust de la parla i del to |
| [`modulos/rutinas.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/rutinas.py) | 234 | Dormir, despertar, parts del dia i apagada |
| [`modulos/sonidos.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/sonidos.py) | 127 | Silbido, campana i xim |
| [`modulos/tiempo.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/tiempo.py) | 266 | Temps amb Open-Meteo |
| [`modulos/vad.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/vad.py) | 151 | Detecció d'activitat de veu |
| [`modulos/version.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/version.py) | 337 | Versió i empremta del codi |
| [`modulos/voz.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/voz.py) | 434 | Edge TTS i Piper |
| [`modulos/__init__.py`](https://github.com/PuntoMarcado/Parker/blob/main/modulos/__init__.py) | 1 | Paquet de mòduls |

## 5. Proves, eines i entrenament

| Directori | Què hi ha | Enllaç |
|---|---|---|
| `tests/` | 31 fitxers de prova: pipeline, memòria, veu, cara, agenda, música, rendiment i configuració | [tests/](https://github.com/PuntoMarcado/Parker/tree/main/tests) |
| `tools/` | Arrencada, diagnòstic, mesures de latència, proves de hardware i còpies | [tools/](https://github.com/PuntoMarcado/Parker/tree/main/tools) |
| `training/` | Pipeline del LoRA de personalitat: generar, preparar, entrenar, fusionar i avaluar | [training/](https://github.com/PuntoMarcado/Parker/tree/main/training) |

Els tests no formen part del dispositiu que veu l'usuari, però són la prova que
les afirmacions de la memòria no són només una demo manual.

## 6. Ordre de lectura recomanat

| Si vols entendre… | Comença per… | Després… |
|---|---|---|
| Com arrenca Parker | `parker.py` | `modulos/version.py` |
| Com pensa | `modulos/cerebro.py` | `modulos/personalidad.py` |
| Com recorda | `modulos/memoria.py` | `modulos/hechos.py` |
| Com sent | `modulos/escucha.py` | `modulos/vad.py`, `modulos/filtro_stt.py` |
| Com parla | `modulos/voz.py` | `modulos/prosodia.py` |
| Com mostra la cara | `modulos/cara_parker.py` | `modulos/display_spidev.py` |
| Com es munta | `config.yaml` | [[TREC/14 Annex. Muntatge i esquemes electrònics]] |

## 7. Configuració i secrets

`config.yaml` és part del codi publicat perquè conté els paràmetres que
expliquen el comportament: models, memòria, veu, pantalla, agenda i autonomia.
No conté cap clau secreta.

La clau de l'API viu a `.env`, que **no es publica**. El repositori tampoc no
inclou:

- models de veu o embeddings pesants (`.onnx`, carpetes de models);
- bases de dades de memòria (`parker.db`, SQLite derivat);
- còpies de seguretat (`backups/`);
- àudio temporal de proves;
- entorns virtuals (`venv/`, `env/`);
- el document `.docx` de la memòria.

Aquesta separació és deliberada: el codi ha de ser reproduïble sense exposar
credencials ni fitxers locals.

## 8. Com descarregar-lo al mòbil

1. Obre <https://github.com/PuntoMarcado/Parker>.
2. Toca **Code** i després **Download ZIP**.
3. Descomprimeix el fitxer al telèfon o comparteix-lo amb l'ordinador.
4. Per llegir només l'annex, obre directament el fitxer 14 des de la carpeta
   `docs/TREC/`.

## 9. Reproducció i límits

El codi està pensat per córrer en una **Orange Pi 5 Pro** amb Linux ARM64,
Python i les dependències de `requirements.txt`. En un PC sense SPI/GPIO, el
sistema pot arrencar sense pantalla física; ho indica el propi driver.

No n'hi ha prou amb descarregar el ZIP per tenir el robot muntat: calen els
models, el micròfon, l'altaveu, la pantalla i la configuració de la placa. Els
passos tècnics són a `docs/placa.md`; el muntatge, a l'annex 14.

## 10. Estat i autoria

- Branca publicada: `main`.
- Data de revisió d'aquest annex: 5 de novembre de 2026.
- Autoria del codi: projecte Parker, desenvolupat per a aquest TREC.
- El repositori no inclou una llicència oberta explícita; no es pot reutilitzar
  com si fos de domini públic sense autorització.

> **Nota de transparència.** Aquest annex no amaga els errors: els tests i les
> eines conserven les proves que van fallar i les que es van corregir. La
> memòria els explica; el repositori els deixa reproduir.
