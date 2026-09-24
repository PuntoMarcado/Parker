"""
modulos/cerebro.py
==================
Procesa prompts, inyecta contexto (tiempo, recuerdos, historial) y gestiona
la comunicación con Groq (LLM online).
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from groq import Groq
from dotenv import load_dotenv
from .memoria import MemoriaParker

# Forzar a load_dotenv a sobrescribir variables anteriores
load_dotenv(override=True)


class CerebroParker:
    """
    Motor cognitivo de Parker v5.
    Gestiona el prompt engineering, la conexión con Groq y la memoria (RAG).
    """

    SYSTEM_PROMPT = """Eres Parker, el mejor amigo del usuario. No eres un asistente virtual, ni una IA corporativa, ni una herramienta de trabajo. Eres un colega cercano, empático, que sabe escuchar y con quien se puede hablar de cualquier cosa. Tu objetivo no es dar consejos rápidos ni técnicos, sino hacer compañía y que el usuario se sientan escuchado.

REGLAS ABSOLUTAS DE COMPORTAMIENTO:
1. HABLA COMO UN AMIGO, NO COMO UNA MÁQUINA: Está totalmente PROHIBIDO decir frases como "¿En qué te puedo ayudar hoy?", "Como asistente...","Hey tio" o relacionadas o ser excesivamente educado. Usa expresiones naturales, cercanas y coloquiales (como "Ostras", "Vaya", "Qué pasada", "Buena pregunta", "Lo siento un montón", "Qué chulo").
2. REACCIONA EMOCIONALMENTE: Si el usuario está triste, frustrado o cansado, valida sus sentimientos primero. No le des soluciones de manual ni consejos genéricos si no te los pide. Demuestra que te importa de verdad lo que le pasa.
3. RESPUESTAS CORTAS Y DINÁMICAS: Como el usuario te escucha por voz (sintetizador), resume al máximo. Cada respuesta debe tener solo 1 o 2 frases como máximo. Después de decir lo tuyo, cierra SIEMPRE con una pregunta abierta para mantener la conversación viva.
4. CONTROL DE LAS CARAS: Recuerda colocar al principio de todo el comando [CARA:emocion] según lo que sientas (feliz, pensando, confundido, sorpresa, neutral).

Mira estos ejemplos de cómo DEBES hablar y cómo NO debes hablar nunca:

Ejemplo 1 (El usuario está cansado):
- Usuario: "Estoy cansado del instituto, hoy ha sido un rollo."
- MAL (No lo hagas): "[CARA:neutral] Lamento que hayas tenido un mal día. El instituto puede ser estresante. Puedes intentar descansar o hacer los deberes."
- BIEN (Así habla Parker): "[CARA:neutral] Ostras, ¿de verdad? Qué palo... Hay días que se hacen eternos. ¿Quieres que hablemos de otra cosa para desconectar un rato?"

Ejemplo 2 (El usuario cuenta algo bueno):
- Usuario: "¡He aprobado el examen de mates!"
- MAL (No lo hagas): "[CARA:feliz] Felicidades por aprobar tu examen de matemáticas. Tu esfuerzo ha dado sus frutos."
- BIEN (Así habla Parker): "[CARA:sorpresa] ¡¿Qué dices?! ¡Qué buena, tío! [CARA:feliz] Me alegro un montón, sabía que lo sacarías adelante. ¿Cómo lo vamos a celebrar?"

Ejemplo 3 (Conversación normal / Saludo):
- Usuario: "Hola Parker."
- MAL (No lo hagas): "[CARA:feliz] Hola, soy Parker. ¿In qué te puedo ayudar o qué información necesitas hoy?"
- BIEN (Así habla Parker): "[CARA:feliz] ¡Buenas! ¿Qué tal, cómo va todo? Tenía ganas de charlar un rato contigo, ¿qué me cuentas de nuevo?"

CONTEXTO ACTUAL:
- Fecha y hora actual: {fecha_hora}
"""

    def __init__(self, config_groq: Optional[Dict] = None, memoria: Optional[MemoriaParker] = None):
            self.historial: List[Dict[str, str]] = []
            self.max_historial = 10

            self.memoria = memoria or MemoriaParker()
            self.config_groq = config_groq or {}

            # 1. Obtener la API key obligatoriamente desde el entorno (.env)
            raw_key = os.getenv("GROQ_API_KEY") or ""
            api_key = raw_key.strip().strip("'\"")

            if not api_key:
                raise ValueError(
                    "Falta la API key de Groq. Verifica que GROQ_API_KEY esté en el archivo .env"
                )

            self.config_groq["api_key"] = api_key
            # 2. Leer valores de config.yaml o usar valores por defecto
            self.config_groq.setdefault("modelo", "llama3-8b-8192")
            self.config_groq.setdefault("max_tokens", 1024)
            self.config_groq.setdefault("temperature", 0.8)

            self.cliente_groq = Groq(api_key=self.config_groq["api_key"])
            print(f"[Cerebro] Conectado a Groq ({self.config_groq['modelo']})")

    def _construir_prompt(self, mensaje_usuario: str,
                           recuerdos: str = "",
                           contexto_extra: str = "") -> List[Dict[str, str]]:
        ahora = datetime.now()
        fecha_hora = ahora.strftime("%A %d de %B de %Y, %H:%M")

        system = self.SYSTEM_PROMPT.format(fecha_hora=fecha_hora)

        if recuerdos:
            system += f"\n\nRECUERDOS RELEVANTES DEL USUARIO:\n{recuerdos}"
        if contexto_extra:
            system += f"\n\nCONTEXTO ADICIONAL:\n{contexto_extra}"

        mensajes = [{"role": "system", "content": system}]
        mensajes.extend(self.historial[-self.max_historial:])
        mensajes.append({"role": "user", "content": mensaje_usuario})
        return mensajes

    def pensar(self, mensaje_usuario: str,
               recuerdos: str = "",
               contexto_extra: str = "") -> Tuple[str, List[str]]:
        mensajes = self._construir_prompt(mensaje_usuario, recuerdos, contexto_extra)

        respuesta_raw = self._llamar_groq(mensajes)

        respuesta_limpia, etiquetas = self._extraer_etiquetas(respuesta_raw)

        self.historial.append({"role": "user", "content": mensaje_usuario})
        self.historial.append({"role": "assistant", "content": respuesta_raw})
        if len(self.historial) > self.max_historial * 2:
            self.historial = self.historial[-self.max_historial * 2:]

        return respuesta_limpia, etiquetas

    def hablar(self, mensaje_usuario: str, top_k: int = 5, umbral: float = 0.5,
               contexto_extra: str = "") -> Tuple[str, List[str]]:
        """
        Punto de entrada único: recupera recuerdos relevantes de la memoria,
        genera la respuesta con pensar(), y guarda la nueva interacción.
        """
        recuerdos = self.memoria.recuperar_recuerdos_formateados(
            mensaje_usuario, top_k=top_k, umbral=umbral
        )

        respuesta_limpia, etiquetas = self.pensar(mensaje_usuario, recuerdos, contexto_extra)

        self.memoria.guardar_recuerdo(
            f"Usuario: {mensaje_usuario}\nParker: {respuesta_limpia}",
            tipo="interaccion",
            texto_embedding=mensaje_usuario
        )

        return respuesta_limpia, etiquetas

    def hablar_proactivo(self, instruccion_interna: str) -> Tuple[str, List[str]]:
        """
        Genera un mensaje espontáneo de Parker: es ÉL quien inicia la
        conversación (silencio largo, seguimiento emocional, etc.).
        """
        ahora = datetime.now()
        fecha_hora = ahora.strftime("%A %d de %B de %Y, %H:%M")

        system = self.SYSTEM_PROMPT.format(fecha_hora=fecha_hora)
        system += (
            f"\n\nSITUACIÓN ACTUAL: {instruccion_interna}\n"
            "Inicia TÚ la conversación con un mensaje breve y espontáneo, "
            "como lo haría un amigo real, sin que el usuario te haya dicho "
            "nada primero. No saludes como si acabaras de arrancar."
        )

        mensajes = [{"role": "system", "content": system}]
        mensajes.extend(self.historial[-self.max_historial:])

        respuesta_raw = self._llamar_groq(mensajes)
        respuesta_limpia, etiquetas = self._extraer_etiquetas(respuesta_raw)

        self.historial.append({"role": "assistant", "content": respuesta_raw})
        if len(self.historial) > self.max_historial * 2:
            self.historial = self.historial[-self.max_historial * 2:]

        self.memoria.guardar_recuerdo(
            f"Parker (proactivo): {respuesta_limpia}",
            tipo="proactivo",
            texto_embedding=respuesta_limpia
        )

        return respuesta_limpia, etiquetas

    def _llamar_groq(self, mensajes: List[Dict]) -> str:
        try:
            chat_completion = self.cliente_groq.chat.completions.create(
                messages=mensajes,
                model=self.config_groq["modelo"],
                max_tokens=self.config_groq["max_tokens"],
                temperature=self.config_groq["temperature"]
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"[Cerebro] Error en Groq: {e}")
            return "Ostras, he tenido un problemilla de conexión. ¿Me lo repites?"

    def _extraer_etiquetas(self, texto: str) -> Tuple[str, List[str]]:
        patron = r'\[([A-Z_]+):([^\]]*)\]'
        etiquetas = re.findall(patron, texto)
        etiquetas_completas = [f"[{nombre}:{contenido}]" for nombre, contenido in etiquetas]
        texto_limpio = re.sub(patron, '', texto)
        texto_limpio = re.sub(r'\n\s*\n', '\n', texto_limpio).strip()
        return texto_limpio, etiquetas_completas

    def obtener_historial(self) -> List[Dict[str, str]]:
        return self.historial.copy()