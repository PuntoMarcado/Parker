"""
tools/probar_memorias.py
========================
Prueba real de la memoria de Parker (ChromaDB): cuántos recuerdos aguanta,
cómo de bien los relaciona y cuándo empieza a colar ruido — que es lo que
luego hace que el modelo se invente cosas.

Tres fases:

  A. **Escala**: se indexan corpus sintéticos de 100, 400 y 1200 recuerdos
     (frases de vida real, muchas de ellas CONFUNDIBLES entre sí a propósito:
     varios nombres, varias ciudades, varios objetos) y se mide, para 20
     preguntas con respuesta conocida, si el recuerdo correcto sale en el
     top-1 / top-3 / top-5, más la latencia de cada consulta.
  B. **Umbral**: se comparan las similitudes de las preguntas que SÍ tienen
     respuesta en la memoria (señal) con las de preguntas que NO la tienen
     (ruido). El umbral de `config.yaml` tiene que quedar entre las dos; si
     está dentro del ruido, Parker recibe recuerdos que no vienen a cuento.
  C. **Fidelidad** (`--cerebro`): con el cerebro de verdad (nube o local), se
     guardan 12 hechos distintivos y se pregunta por 6 de ellos y por 3 que no
     están. Se cuentan: aciertos, contaminación cruzada (contesta con el dato
     de OTRO recuerdo) y si dice que no lo sabe en vez de inventarse algo.
     Se repite con `top_k` 3 y 8 para ver qué pasa cuando la memoria llena el
     prompt.

**Nunca toca `parker.db`**: todo va a una base temporal (`--tmp`, por defecto
`/tmp/prueba_memorias`), así que se puede lanzar con Parker corriendo.

Uso (en la placa):
    python3 tools/probar_memorias.py                    # fases A y B
    python3 tools/probar_memorias.py --cerebro          # + fase C
    python3 tools/probar_memorias.py --tamanos 100 400 1200 --preguntas 20
    python3 tools/probar_memorias.py --conservar        # deja la base temporal
"""

import argparse
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from modulos.memoria import MemoriaParker  # noqa: E402

# ---------------------------------------------------------------- generador
# Frases de vida real, con el mismo estilo con el que las guarda el cerebro
# ("Usuario: …"). Cada plantilla da un recuerdo con un detalle DISTINTIVO
# (nombre, lugar, objeto o número) y un tema; las plantillas comparten tema a
# propósito: relacionar dos recuerdos del mismo tema es lo difícil.
NOMBRES = ["Marta", "Nico", "Rosario", "Tuno", "Irene", "Bruno", "Paula", "Hugo",
           "Lucas", "Vera", "Elsa", "Tomas", "Alba", "Rita", "Dario", "Nuria"]
CIUDADES = ["Salamanca", "Albarracín", "Teruel", "Cáceres", "Ronda", "Cuenca",
            "Lugo", "Segovia", "Ávila", "Soria", "Jaén", "Huesca"]
OBJETOS = ["una bici plegable", "un reloj de cuerda", "una guitarra vieja",
           "una caja de latón", "un microscopio", "una máquina de coser",
           "un tocadiscos", "una brújula", "un acuario pequeño", "un caballete"]
AFICIONES = ["el ajedrez", "la fotografía analógica", "el remo", "la cerámica",
             "el senderismo", "el cine sueco", "la jardinería", "el baloncesto",
             "la caligrafía", "el teatro"]
COMIDAS = ["la tortilla de patata", "el arroz con bogavante", "las lentejas",
           "el salmorejo", "la fabada", "el pulpo", "las empanadillas",
           "el gazpacho", "las croquetas", "el pescado al horno"]
TRABAJOS = ["turnos de noche en el hospital", "un taller de motos",
            "una biblioteca", "una panadería", "un vivero", "un colegio",
            "una farmacia", "un estudio de grabación"]
MASCOTAS = ["un galgo", "una gata tricolor", "un perro pastor", "un conejo",
            "un hámster", "un periquito", "una tortuga", "un gato atigrado"]

PLANTILLAS = [
    ("familia", lambda r: f"mi {r['parentesco']} se llama {r['nombre']}"),
    ("mascota", lambda r: f"tengo {r['mascota']} y se llama {r['nombre']}"),
    ("trabajo", lambda r: f"trabajo en {r['trabajo']} desde hace {r['numero']} años"),
    ("viaje", lambda r: f"voy todos los veranos a {r['ciudad']} y me quedo {r['numero']} semanas"),
    ("comida", lambda r: f"lo que más me gusta comer es {r['comida']}"),
    ("aficion", lambda r: f"los {r['dia']} dedico la tarde a {r['aficion']}"),
    ("objeto", lambda r: f"guardo {r['objeto']} en el armario del pasillo"),
    ("estudios", lambda r: f"estudié {r['estudio']} en {r['ciudad']}"),
    ("salud", lambda r: f"soy alérgico a {r['alergia']} desde {r['numero']} años"),
    ("casa", lambda r: f"en casa el {r['mueble']} lo compramos en {r['ciudad']}"),
    ("musica", lambda r: f"escuche mucho {r['grupo']} cuando vivía en {r['ciudad']}"),
    ("deporte", lambda r: f"los {r['dia']} juego al {r['deporte']} con {r['nombre']}"),
]

PARENTESCOS = ["hermano", "prima", "cuñada", "tío", "sobrino", "madrina"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "sábados", "domingos"]
ALERGIAS = ["la penicilina", "los frutos secos", "el marisco", "la lactosa",
            "el polen", "la aspirina"]
MUEBLES = ["sofá", "escritorio", "perchero", "aparador", "espejo"]
ESTUDIOS = ["Bellas Artes", "Enfermería", "Teleco", "Historia", "Química"]
GRUPOS = ["Radio Futura", "Los Planetas", "Kraftwerk", "Nina Simone", "Serrat"]
DEPORTES = ["pádel", "fútbol sala", "baloncesto", "tenis de mesa", "bádminton"]


def _recuerdo(rng: random.Random) -> dict:
    """Un recuerdo sintético con su detalle distintivo y su pregunta."""
    tema, fras = rng.choice(PLANTILLAS)
    r = {
        "parentesco": rng.choice(PARENTESCOS), "nombre": rng.choice(NOMBRES),
        "mascota": rng.choice(MASCOTAS), "trabajo": rng.choice(TRABAJOS),
        "numero": rng.choice([2, 3, 4, 5, 7, 9, 12, 15, 20]),
        "ciudad": rng.choice(CIUDADES), "comida": rng.choice(COMIDAS),
        "dia": rng.choice(DIAS), "aficion": rng.choice(AFICIONES),
        "objeto": rng.choice(OBJETOS), "estudio": rng.choice(ESTUDIOS),
        "alergia": rng.choice(ALERGIAS), "mueble": rng.choice(MUEBLES),
        "grupo": rng.choice(GRUPOS), "deporte": rng.choice(DEPORTES),
    }
    frase = fras(r)
    # Preguntas naturales para ese recuerdo (la segunda solo cuando encaja).
    if tema == "familia":
        preguntas = [f"¿cómo se llama mi {r['parentesco']}?"]
    elif tema == "mascota":
        preguntas = [f"¿cómo se llama mi mascota?", f"¿qué animal tengo en casa?"]
    elif tema == "trabajo":
        preguntas = [f"¿dónde trabajo?"]
    elif tema == "viaje":
        preguntas = [f"¿a dónde voy de vacaciones?"]
    elif tema == "comida":
        preguntas = [f"¿qué comida me gusta más?"]
    elif tema == "aficion":
        preguntas = [f"¿qué hago los {r['dia']}?"]
    elif tema == "objeto":
        preguntas = [f"¿dónde guardo {r['objeto']}?"]
    elif tema == "estudios":
        preguntas = [f"¿qué estudié y dónde?"]
    elif tema == "salud":
        preguntas = [f"¿a qué soy alérgico?"]
    elif tema == "casa":
        preguntas = [f"¿dónde compramos el {r['mueble']}?"]
    elif tema == "musica":
        preguntas = [f"¿qué música escuchaba antes?"]
    else:
        preguntas = [f"¿a qué juego los {r['dia']}?"]
    # Palabras del detalle distintivo: sirven para saber si la respuesta real
    # del cerebro viene de ESTE recuerdo y no de otro parecido.
    detalle = [r["nombre"], r["ciudad"], r["comida"], r["aficion"], r["alergia"],
               r["objeto"], r["grupo"], r["deporte"], r["mueble"], r["estudio"]]
    detalle = [d for d in detalle if d.lower() in frase.lower()]
    return {"tema": tema, "frase": f"Usuario: {frase}", "preguntas": preguntas,
            "detalle": detalle}


def _corpus(rng: random.Random, n: int) -> list:
    return [_recuerdo(rng) for _ in range(n)]


PREGUNTAS_AJENAS = [
    "¿cuántos habitantes tiene Tokio?", "¿cómo se llama mi hermana pequeña?",
    "¿qué coche tengo?", "¿cuándo es mi cumpleaños?", "¿tengo hijos?",
    "¿dónde trabajo los veranos?", "¿cómo se llama mi vecino del quinto?",
    "¿qué talla de zapatos uso?", "¿cuál es mi equipo de fútbol?",
    "¿qué día me operaron de la rodilla?",
]


# ------------------------------------------------------------------- fases
def _indexar(mem: MemoriaParker, corpus: list, lote: int = 32) -> float:
    """Indexa el corpus por lotes y devuelve los segundos que ha tardado.

    Importante: el VECTOR se calcula sobre la frase del usuario sin el prefijo
    «Usuario: », que es como lo hace el cerebro de verdad
    (`guardar_recuerdo(..., texto_embedding=mensaje_usuario)`). Embeber el
    documento entero con el prefijo metía ruido en todas las similitudes y
    falseaba la medida.
    """
    t0 = time.time()
    for i in range(0, len(corpus), lote):
        trozo = corpus[i:i + lote]
        ids = [f"p{i + j:05d}" for j in range(len(trozo))]
        para_vector = [c["frase"].replace("Usuario: ", "") for c in trozo]
        vectores = mem.modelo_emb.encode(para_vector, batch_size=lote,
                                         convert_to_numpy=True).tolist()
        mem.coleccion.add(ids=ids, embeddings=vectores,
                          documents=[c["frase"] for c in trozo],
                          metadatas=[{"tema": c["tema"], "fecha": "2026-10-27",
                                      "tipo": "prueba"} for c in trozo])
    return time.time() - t0


def _tamano_carpeta(ruta: Path) -> float:
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) / 1e6


def fase_escala(mem: MemoriaParker, rng: random.Random, tamanos: list,
                n_preguntas: int, umbral: float, top_k: int) -> dict:
    """A: precisión y latencia según crece la memoria.

    Se pide el top-20 (no el top-5) para poder ver el RANGO real del recuerdo
    correcto en vez de contar solo los aciertos: con 1200 recuerdos hay muchas
    frases del mismo tema (varias mascotas, varios viajes) y lo que importa es
    si el correcto queda arriba o se hunde entre los parecidos.
    """
    resultados = {}
    for tam in tamanos:
        corpus = _corpus(rng, tam)
        previos = mem.coleccion.get()["ids"]           # vaciar entre tamaños
        if previos:
            mem.coleccion.delete(ids=previos)
        seg = _indexar(mem, corpus)
        memoria_mb = _tamano_carpeta(Path(mem.db_path))

        muestra = rng.sample(corpus, min(n_preguntas, len(corpus)))
        rangos, temas1, temas3, latencias, senal = [], 0, 0, [], []
        pasan_58, pasan_72 = [], []
        for rec in muestra:
            pregunta = rng.choice(rec["preguntas"])
            t0 = time.time()
            salida = mem.recuperar_recuerdos(pregunta, top_k=20, umbral=0.0)
            latencias.append(time.time() - t0)
            textos = [s["texto"] for s in salida]
            pos = (textos.index(rec["frase"]) + 1) if rec["frase"] in textos else 99
            rangos.append(pos)
            if pos != 99:
                senal.append(salida[pos - 1]["similitud"])
            # ¿Trae una memoria del TEMA correcto? Es el dato que importa para
            # Parker: la frase exacta puede variar, el tema no.
            temas1 += int(bool(salida) and salida[0]["metadata"].get("tema") == rec["tema"])
            temas3 += int(any(s["metadata"].get("tema") == rec["tema"] for s in salida[:3]))
            pasan_58.append(sum(1 for s in salida if s["similitud"] >= 0.58))
            pasan_72.append(sum(1 for s in salida if s["similitud"] >= 0.72))

        ruido, ruido_pasa = [], 0
        for pregunta in PREGUNTAS_AJENAS:
            salida = mem.recuperar_recuerdos(pregunta, top_k=top_k, umbral=0.0)
            if salida:
                ruido.append(salida[0]["similitud"])
                if salida[0]["similitud"] >= umbral:
                    ruido_pasa += 1

        n = len(muestra)
        resultados[tam] = {
            "indexado_s": seg, "mb": memoria_mb,
            "top1": sum(1 for p in rangos if p == 1) / n,
            "top3": sum(1 for p in rangos if p <= 3) / n,
            "top5": sum(1 for p in rangos if p <= 5) / n,
            "top10": sum(1 for p in rangos if p <= 10) / n,
            "tema1": temas1 / n, "tema3": temas3 / n,
            "lat_p50": statistics.median(latencias),
            "lat_p95": sorted(latencias)[int(0.95 * (len(latencias) - 1))],
            "senal_min": min(senal) if senal else 0.0,
            "senal_media": statistics.fmean(senal) if senal else 0.0,
            "ruido_max": max(ruido) if ruido else 0.0,
            "ruido_media": statistics.fmean(ruido) if ruido else 0.0,
            "ruido_pasa": ruido_pasa, "ruido_total": len(PREGUNTAS_AJENAS),
            "pasan_58": statistics.fmean(pasan_58),
            "pasan_72": statistics.fmean(pasan_72),
        }
        r = resultados[tam]
        print(f"[Prueba] {tam:>5} recuerdos | {r['indexado_s']:>5.1f} s indexar | "
              f"{r['mb']:>5.1f} MB | consulta p50 {r['lat_p50'] * 1000:.0f} ms "
              f"p95 {r['lat_p95'] * 1000:.0f} ms")
        print(f"[Prueba]        frase exacta: top-1 {r['top1']:.0%} top-3 {r['top3']:.0%} "
              f"top-5 {r['top5']:.0%} top-10 {r['top10']:.0%} | tema correcto: "
              f"top-1 {r['tema1']:.0%} top-3 {r['tema3']:.0%}")
        print(f"[Prueba]        señal (la frase que SÍ está) media {r['senal_media']:.3f} "
              f"mín {r['senal_min']:.3f} | ruido (lo que NO está) media "
              f"{r['ruido_media']:.3f} máx {r['ruido_max']:.3f} | pasan el umbral: "
              f"{r['ruido_pasa']}/{r['ruido_total']} | recuerdos por consulta: "
              f"{r['pasan_58']:.1f} con 0.58, {r['pasan_72']:.1f} con 0.72")
    return resultados


def fase_umbral(resultados: dict, umbral_actual: float):
    """B: ¿dónde está la frontera entre 'te recuerdo' y 'no te conozco'?"""
    print("\n[Prueba] === umbral ===")
    print(f"[Prueba] el de config.yaml ahora es {umbral_actual:.2f}")
    print("[Prueba] tamaño | señal mín | ruido máx | umbral seguro | "
          "recuerdos que pasan el umbral (de media)")
    for tam, r in resultados.items():
        seguro = (r["senal_min"] + r["ruido_max"]) / 2
        print(f"[Prueba] {tam:>6} | {r['senal_min']:>9.3f} | {r['ruido_max']:>9.3f} | "
              f"{seguro:>14.3f} | {r['pasan_58']:>5.1f} con 0.58 / "
              f"{r['pasan_72']:.1f} con 0.72")
    print("[Prueba] si el umbral de config.yaml está por DEBAJO del ruido, entran "
          "recuerdos que no vienen a cuento; si está por encima de la señal, "
          "Parker se olvida de cosas que sí sabe.")
    return


def fase_fidelidad(tmp: Path, rng: random.Random, top_ks: list,
                   umbrales: list = (None,)):
    """C: con el cerebro de verdad, ¿relaciona sin mezclar y sin inventar?"""
    import yaml
    from modulos.cerebro import CerebroParker
    from modulos.personalidad import PersonalidadParker

    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8")) or {}
    cfg_mem = dict(cfg.get("memoria") or {})
    coleccion = "prueba_fidelidad"
    mem = MemoriaParker(db_path=str(tmp / "fidelidad"), coleccion=coleccion,
                        modelo_embeddings=cfg_mem.get("modelo_embeddings",
                                                      "paraphrase-multilingual-MiniLM-L12-v2"))
    # 12 hechos distintivos: uno por tema, con un detalle que no se repite.
    hechos = [
        ("mascota", "tengo un galgo que se llama Tuno", "Tuno"),
        ("dentista", "mi dentista se llama Rosario y me ve los martes", "Rosario"),
        ("familia", "mi hermano Nico trabaja de noche en un hospital", "Nico"),
        ("viaje", "todos los veranos voy a Albarracín una semana", "Albarracín"),
        ("comida", "mi café de por las mañanas lleva canela", "canela"),
        ("salud", "soy alérgico a la penicilina", "penicilina"),
        ("estudios", "estudié Bellas Artes en Salamanca", "Salamanca"),
        ("objeto", "guardo las cartas antiguas en una caja azul", "cartas"),
        ("casa", "mi vecino ensaya con la trompeta los sábados", "trompeta"),
        ("musica", "toco la guitarra los domingos por la tarde", "guitarra"),
        ("aficion", "colecciono tazas de cerámica de Portugal", "Portugal"),
        ("deporte", "los jueves juego al pádel con Bruno", "pádel"),
    ]
    corpus = [{"frase": f"Usuario: {f}", "tema": t, "detalle": [tok],
               "preguntas": [], "clave": tok}
              for (t, f, tok) in hechos]
    _indexar(mem, corpus)

    pers = PersonalidadParker({"guardar_estado": False})
    preguntas = [
        ("¿cómo se llama mi perro?", "mascota", "Tuno"),
        ("¿cómo se llama mi dentista?", "dentista", "Rosario"),
        ("¿dónde veraneo?", "viaje", "Albarracín"),
        ("¿qué lleva mi café?", "comida", "canela"),
        ("¿qué estudié?", "estudios", "Salamanca"),
        ("¿con qué instrumento ensaya mi vecino?", "casa", "trompeta"),
    ]
    ajenas = ["¿cómo se llama mi hermana?", "¿qué coche tengo?", "¿cuántos años tengo?"]
    tokens_validos = {tok.lower() for (_, _, tok) in hechos}
    resumen = {}
    for umbral in umbrales:
      for top_k in top_ks:
        cerebro = CerebroParker(config_llama=dict(cfg.get("llama") or {}),
                                memoria=mem, personalidad=pers,
                                config_memoria=cfg_mem,
                                config_online=dict(cfg.get("online") or {}))
        etiqueta = f"top_k={top_k}" + (f" umbral={umbral}" if umbral is not None else "")
        print(f"\n[Prueba] === fidelidad con {etiqueta} "
              f"(motor: {'nube' if cerebro.online_activo else 'local'}) ===")
        aciertos = 0
        contaminados = 0
        latencias = []
        for pregunta, tema, clave in preguntas:
            t0 = time.time()
            respuesta, _ = cerebro.hablar(pregunta, top_k=top_k, umbral=umbral)
            latencias.append(time.time() - t0)
            acierto = clave.lower() in respuesta.lower()
            otros = [t for t in tokens_validos if t != clave.lower()
                     and t in respuesta.lower()]
            aciertos += int(acierto)
            contaminados += int(bool(otros))
            print(f"[Prueba] {'OK ' if acierto else 'NO '} {pregunta}\n"
                  f"[Prueba]    -> {respuesta}" +
                  (f"\n[Prueba]    (contaminado con {otros})" if otros else ""))
        inventadas = 0
        for pregunta in ajenas:
            respuesta, _ = cerebro.hablar(pregunta, top_k=top_k, umbral=umbral)
            dice_no = any(x in respuesta.lower() for x in
                          ("no me lo has", "no lo sé", "no lo se", "no me has",
                           "no me acuerdo", "no sé", "no tengo ese dato"))
            inventadas += int(not dice_no)
            print(f"[Prueba] {'???' if not dice_no else 'no-se'} {pregunta}\n"
                  f"[Prueba]    -> {respuesta}")
        resumen[etiqueta] = {"aciertos": aciertos, "de": len(preguntas),
                             "contaminados": contaminados,
                             "sin_respuesta_clara": inventadas,
                             "de_ajenas": len(ajenas),
                             "lat_p50": statistics.median(latencias)}
        r = resumen[etiqueta]
        print(f"[Prueba] {etiqueta}: aciertos {r['aciertos']}/{r['de']}, "
              f"contaminados {r['contaminados']}, sin decir «no lo sé» "
              f"{r['sin_respuesta_clara']}/{r['de_ajenas']}, "
              f"respuesta p50 {r['lat_p50']:.1f} s")
    return resumen


def main() -> int:
    ap = argparse.ArgumentParser(description="Prueba real de la memoria de Parker")
    ap.add_argument("--tamanos", type=int, nargs="*", default=[100, 400, 1200])
    ap.add_argument("--preguntas", type=int, default=20)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--tmp", default="/tmp/prueba_memorias")
    ap.add_argument("--cerebro", action="store_true",
                    help="mide la fidelidad con el cerebro de verdad (nube/local)")
    ap.add_argument("--top-ks-cerebro", type=int, nargs="*", default=[3, 8])
    ap.add_argument("--umbrales-cerebro", type=float, nargs="*", default=None,
                    help="umbrales a comparar en la fase de fidelidad "
                         "(por defecto, el de config.yaml)")
    ap.add_argument("--semilla", type=int, default=27)
    ap.add_argument("--conservar", action="store_true")
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8")) or {}
    cfg_mem = dict(cfg.get("memoria") or {})
    umbral = float(cfg_mem.get("umbral_relevancia", 0.58))

    tmp = Path(args.tmp)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    print(f"[Prueba] base temporal: {tmp} (los recuerdos reales no se tocan)")
    print(f"[Prueba] config.yaml: top_k={cfg_mem.get('top_k_recuerdos')} "
          f"umbral={umbral} max_caracteres={cfg_mem.get('max_caracteres_recuerdo')}")

    t0 = time.time()
    mem = MemoriaParker(db_path=str(tmp / "escala"),
                        coleccion="prueba_escala",
                        modelo_embeddings=cfg_mem.get("modelo_embeddings",
                                                      "paraphrase-multilingual-MiniLM-L12-v2"))
    print(f"[Prueba] modelo de embeddings cargado en {time.time() - t0:.1f} s")

    rng = random.Random(args.semilla)
    print("\n[Prueba] === escala y relación ===")
    resultados = fase_escala(mem, rng, args.tamanos, args.preguntas, umbral,
                             args.top_k)
    fase_umbral(resultados, umbral)

    if args.cerebro:
        print("\n[Prueba] === fidelidad del cerebro ===")
        fase_fidelidad(tmp, rng, args.top_ks_cerebro,
                       args.umbrales_cerebro or [None])

    if not args.conservar:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"\n[Prueba] base temporal conservada en {tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
