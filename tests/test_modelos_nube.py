"""
tests/test_modelos_nube.py
==========================
Si el proveedor retira el modelo de la nube, Parker elige otro solo.

Pedido el 26/10/2026: «cada cierto tiempo Groq cambia sus modelos; si
desclasifica el que usamos, nos quedamos sin cerebro online». Sin salir a
internet (se sustituye `requests`), se comprueba:

  1. Si el modelo configurado sigue en la lista, no se cambia nada.
  2. Si ya no está, se usa el primero de `modelos_alternativos` que sí esté.
  3. Sin alternativos disponibles, se coge el primer modelo de TEXTO de la
     lista (nunca uno de voz o de transcripción).
  4. Si la consulta falla (sin red), no se toca nada ni se lanza error.
  5. `calentar()` hace esa revisión antes de gastar el primer turno.

Ejecutar:
    QT_QPA_PLATFORM=offscreen python tests/test_modelos_nube.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos import cerebro as C  # noqa: E402
from modulos.personalidad import PersonalidadParker  # noqa: E402


class MemoriaFalsa:
    def recuperar_recuerdos_formateados(self, *a, **k):
        return ""

    def guardar_recuerdo(self, *a, **k):
        pass


class RespuestaFalsa:
    def __init__(self, modelos=None, error=None):
        self._modelos = modelos or []
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return {"data": [{"id": m} for m in self._modelos]}


def _cerebro(modelo: str = "openai/gpt-oss-20b", alternativos=()) -> C.CerebroParker:
    cerebro = C.CerebroParker(
        config_llama={"modelo": "qwen2.5:3b", "historial_mensajes": 4},
        memoria=MemoriaFalsa(),
        personalidad=PersonalidadParker({"guardar_estado": False}),
        config_online={"activo": True, "modelo": modelo,
                       "modelos_alternativos": list(alternativos),
                       "reintento_seg": 60},
    )
    cerebro.online_api_key = "clave-de-prueba"
    return cerebro


class _SinRed:
    """`requests` de mentira: la lista de modelos que dice el proveedor."""

    def __init__(self, modelos=(), error=None, al_publicar=None):
        self.modelos = list(modelos)
        self.error = error
        self.al_publicar = al_publicar
        self._original_get = C.requests.get
        self._original_post = C.requests.post

    def __enter__(self):
        def get(_url, **k):
            if self.error:
                raise self.error
            return RespuestaFalsa(self.modelos)

        def post(url, json=None, **k):
            if self.al_publicar:
                self.al_publicar(url, json)
            return RespuestaFalsa(["ok"])

        C.requests.get = get
        C.requests.post = post
        return self

    def __exit__(self, *exc):
        C.requests.get = self._original_get
        C.requests.post = self._original_post
        return False


def test_modelo_presente_no_cambia():
    cerebro = _cerebro(alternativos=["openai/gpt-oss-120b"])
    with _SinRed(["openai/gpt-oss-20b", "openai/gpt-oss-120b"]):
        assert cerebro.revisar_modelo_online() is None
    assert cerebro.online_modelo == "openai/gpt-oss-20b", cerebro.online_modelo
    print("[OK] si el modelo sigue en el proveedor, no se toca nada")


def test_cambio_a_un_alternativo():
    cerebro = _cerebro(alternativos=["llama-3.3-70b-versatile",
                                    "openai/gpt-oss-120b"])
    with _SinRed(["openai/gpt-oss-120b", "llama-3.3-70b-versatile",
                  "whisper-large-v3"]):
        elegido = cerebro.revisar_modelo_online()
    assert elegido == "llama-3.3-70b-versatile", elegido
    assert cerebro.online_modelo == "llama-3.3-70b-versatile"
    assert cerebro.estado_cerebro()["modelo"] == "llama-3.3-70b-versatile"
    print("[OK] si retiran el modelo, pasa al primero de los alternativos")


def test_sin_alternativos_elige_un_modelo_de_texto():
    cerebro = _cerebro(alternativos=["modelo-que-ya-no-existe"])
    with _SinRed(["whisper-large-v3-turbo", "openai/gpt-oss-120b",
                  "whisper-large-v3"]):
        elegido = cerebro.revisar_modelo_online()
    assert elegido == "openai/gpt-oss-120b", elegido
    print("[OK] sin alternativos coge el primer modelo de texto (no voz)")


def test_sin_red_no_toca_nada():
    cerebro = _cerebro(alternativos=["openai/gpt-oss-120b"])
    with _SinRed(error=RuntimeError("sin internet")):
        assert cerebro.revisar_modelo_online() is None
    assert cerebro.online_modelo == "openai/gpt-oss-20b"
    print("[OK] sin red no cambia nada y no se lanza error")


def test_calentar_revisa_el_modelo_antes_del_turno():
    cerebro = _cerebro(alternativos=["openai/gpt-oss-120b"])
    publicados = []

    def al_publicar(url, json):
        publicados.append((url, (json or {}).get("model")))

    with _SinRed(["openai/gpt-oss-120b"], al_publicar=al_publicar):
        cerebro.calentar()
    assert publicados, publicados
    assert all(modelo == "openai/gpt-oss-120b" for _, modelo in publicados), publicados
    assert all("/chat/completions" in url for url, _ in publicados), publicados
    print("[OK] calentar() revisa el modelo y ya usa el sustituto")


if __name__ == "__main__":
    test_modelo_presente_no_cambia()
    test_cambio_a_un_alternativo()
    test_sin_alternativos_elige_un_modelo_de_texto()
    test_sin_red_no_toca_nada()
    test_calentar_revisa_el_modelo_antes_del_turno()
    print("\nModelos de la nube: 5/5 en verde.")
