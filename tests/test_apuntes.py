"""
Pruebas de los apuntes (notas y contadores) sin LLM y sin reloj real.

El caso de referencia es el que pidió el dueño: contar los litros de agua que
bebe al día y poder preguntárselos.
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.apuntes import ApuntesParker, _unidad_hablada  # noqa: E402

AHORA = datetime(2026, 10, 26, 16, 0)


def _apuntes(tmp: str = None) -> ApuntesParker:
    return ApuntesParker(ruta_apuntes=tmp)


def test_notas():
    apuntes = _apuntes()
    assert apuntes.procesar("Parker, apunta que compre leche", AHORA) == \
        "Apuntado: compre leche."
    assert apuntes.procesar("anota llamar al fontanero", AHORA) == \
        "Apuntado: llamar al fontanero."
    leido = apuntes.procesar("¿qué tenía apuntado?", AHORA)
    assert "compre leche" in leido and "fontanero" in leido, leido
    assert apuntes.procesar("borra la nota de la leche", AHORA) == \
        "Borrado: compre leche."
    assert apuntes.procesar("borra los apuntes", AHORA) == \
        "Borrado: llamar al fontanero."
    assert apuntes.notas == []
    assert apuntes.procesar("¿qué tengo apuntado?", AHORA) == \
        "No tienes nada apuntado."

    # La charla normal no apunta nada.
    for frase in ("me gusta la leche", "hoy tengo mucho trabajo", "¿qué tal?",
                  "ayer fui al médico"):
        otro = _apuntes()
        assert otro.procesar(frase, AHORA) is None, frase
        assert otro.notas == [], frase
    print("[OK] notas: apuntar, leer y borrar sin tocar la charla")


def test_contador_de_agua():
    apuntes = _apuntes()
    respuesta = apuntes.procesar("apunta un litro de agua", AHORA)
    assert respuesta.startswith("Anotado: un litro de agua."), respuesta
    assert "Hoy llevas un litro de agua" in respuesta, respuesta

    assert "dos litros" in apuntes.procesar("apunta otro litro de agua", AHORA)
    assert apuntes.procesar("¿cuánta agua llevo hoy?", AHORA).startswith(
        "Hoy llevas dos litros de agua.")

    # Al final del día lo normal es fijar el total, no ir sumando.
    apuntes.procesar("hoy he bebido dos litros y medio de agua", AHORA)
    dicho = apuntes.procesar("¿cuántos litros de agua llevo?", AHORA)
    assert dicho.startswith("Hoy llevas dos litros y medio de agua."), dicho

    # Medio litro y «un litro y medio» se entienden.
    apuntes2 = _apuntes()
    assert "medio litro" in apuntes2.procesar("apunta medio litro de agua", AHORA)
    assert "litro y medio" in apuntes2.procesar(
        "apunta un litro y medio de agua", AHORA)

    # Cada día empieza de cero, y lo de ayer no se pierde.
    manana = AHORA + timedelta(days=1)
    assert "un litro" in apuntes2.procesar("apunta un litro de agua", manana)
    assert apuntes2.contadores["agua"]["dias"]["2026-10-26"] == 2.0
    assert apuntes2.contadores["agua"]["dias"]["2026-10-27"] == 1.0

    # Sin nada apuntado hoy se dice tal cual.
    apuntes3 = _apuntes()
    assert apuntes3.procesar("¿cuánta agua llevo hoy?", AHORA) == \
        "Todavía no llevo nada apuntado de agua."
    print("[OK] contador de agua: sumar, fijar el día, medio litro y días separados")


def test_otros_contadores_y_unidades():
    apuntes = _apuntes()
    apuntes.procesar("apunta un café", AHORA)
    apuntes.procesar("apunta otro café", AHORA)
    assert apuntes.procesar("¿cuántos cafés llevo hoy?", AHORA).startswith(
        "Hoy llevas dos cafes.")
    apuntes.procesar("apunta cinco kilómetros andando", AHORA)
    assert "cinco" in apuntes.procesar("¿cuántos kilómetros llevo?", AHORA)
    # El nombre manda: litros de agua y litros de leche son contadores distintos.
    apuntes.procesar("apunta dos litros de leche", AHORA)
    assert sorted(apuntes.contadores) == ["cafe", "kilometro", "leche"], \
        sorted(apuntes.contadores)
    assert apuntes.contadores["leche"]["dias"]["2026-10-26"] == 2.0
    assert _unidad_hablada(1, "litros") == "un litro"
    assert _unidad_hablada(0.5, "litros") == "medio litro"
    assert _unidad_hablada(1.5, "litros") == "un litro y medio"
    print("[OK] otros contadores (café, kilómetros, leche) y unidades habladas")


def test_persistencia():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "parker.apuntes.json")
        apuntes = _apuntes(ruta)
        apuntes.procesar("apunta un litro de agua", AHORA)
        apuntes.procesar("apunta que compre pan", AHORA)
        assert Path(ruta).exists()

        otro = ApuntesParker(ruta_apuntes=ruta)
        assert otro.contadores["agua"]["dias"]["2026-10-26"] == 1.0
        assert otro.notas[0]["texto"] == "compre pan"
        # Y contesta con lo guardado, sin volver a apuntar nada.
        assert "un litro" in otro.procesar("¿cuánta agua llevo?", AHORA)
    print("[OK] los apuntes y los contadores se guardan y se releen")


if __name__ == "__main__":
    test_notas()
    test_contador_de_agua()
    test_otros_contadores_y_unidades()
    test_persistencia()
    print("\nApuntes: 4/4 en verde.")
