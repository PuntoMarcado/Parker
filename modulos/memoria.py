"""
modulos/memoria.py
==================
Gestión de memoria a largo plazo mediante ChromaDB (RAG local).
"""

import os
import hashlib
import re
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


# Palabras que no aportan nada a una búsqueda léxica (BM25 las penaliza, pero
# un MATCH con 8 conectores devuelve media colección).
_STOPWORDS_FTS = {"el", "la", "los", "las", "un", "una", "unos", "unas",
                  "que", "por", "para", "con", "esto", "a", "de", "en",
                  "es", "mi", "mi", "yo", "tu", "tú", "del",
                  "al", "lo", "se", "sus", "y", "o", "u", "e"}


def formatear_recuerdos(recuerdos: List[Dict], max_caracteres: int = 0) -> str:
    """Recuerdos en el formato más corto posible para el prompt.

    Cada recuerdo se paga en CADA respuesta (el modelo lo reprocesa), así que
    aquí se tira lo que no aporta: el tipo, la similitud, la cabecera y los
    saltos de línea del par usuario/Parker. `max_caracteres` recorta los
    recuerdos largos (0 = sin recorte).
    """
    if not recuerdos:
        return ""
    lineas = []
    vistos = set()
    for rec in recuerdos:
        # Solo la parte del usuario ("Usuario: ..."): la respuesta de Parker
        # de aquel día no aporta para recordar a la persona y duplica tokens.
        # Se quita también el prefijo "Usuario:" y la fecha va en el formato.
        partes = []
        for parte in rec.get("texto", "").splitlines():
            parte = parte.strip()
            if not parte or parte.lower().startswith("parker:"):
                continue
            if parte.lower().startswith("usuario:"):
                parte = parte.split(":", 1)[1].strip()
            partes.append(parte)
        texto = " | ".join(partes)
        if max_caracteres and len(texto) > max_caracteres:
            texto = texto[:max_caracteres].rstrip() + "…"
        # La misma conversación puede guardarse dos veces (o recuperarse dos
        # veces): repetirla en el prompt cuesta tokens y no aporta nada.
        clave = " ".join(texto.split())
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        fecha = (rec.get("metadata") or {}).get("fecha", "")
        prefijo = f"[{len(lineas) + 1}] ({fecha}) " if fecha else f"[{len(lineas) + 1}] "
        lineas.append(f"{prefijo}{texto}")
    return "\n".join(lineas)


class MemoriaParker:
    def __init__(self, db_path: str = "./parker.db",
                 coleccion: str = "recuerdos_parker",
                 modelo_embeddings: str = "paraphrase-multilingual-MiniLM-L12-v2",
                 ruta_fts: Optional[str] = None,
                 hibrida: bool = True):
        self.db_path = os.path.abspath(db_path)
        self.nombre_coleccion = coleccion

        self.cliente = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=False)
        )

        print(f"[Memoria] Cargando modelo de embeddings: {modelo_embeddings}")
        self.modelo_emb = SentenceTransformer(modelo_embeddings)
        if hasattr(self.modelo_emb, "get_embedding_dimension"):
            self.dimension = self.modelo_emb.get_embedding_dimension()
        else:
            self.dimension = self.modelo_emb.get_sentence_embedding_dimension()

        self.coleccion = self._obtener_o_crear_coleccion()
        print(f"[Memoria] Colección '{coleccion}' lista. Documentos: {self.coleccion.count()}")

        # --- Búsqueda HÍBRIDA (03/11/2026) --------------------------------
        # La semántica (Chroma) sola se pierde nombres propios y datos
        # exactos: la evaluación midió 4/8 fallos en preguntas cortas de hechos.
        # La parte léxica (FTS5/BM25, mismo documento y sin recorte) la
        # cubre; ambas listas se funden con Reciprocal Rank Fusion. Si FTS5
        # no está disponible, `hibrida` queda False y se sigue igual que antes
        # (semántica + umbral), sin romper nada.
        self.hibrida = bool(hibrida) and self._abrir_fts(ruta_fts)

    def _obtener_o_crear_coleccion(self):
        try:
            return self.cliente.get_collection(name=self.nombre_coleccion)
        except Exception:
            print(f"[Memoria] Creando nueva colección: {self.nombre_coleccion}")
            return self.cliente.create_collection(
                name=self.nombre_coleccion,
                metadata={"hnsw:space": "cosine"}
            )

    # ---------------------------------------------------------- índice FTS5
    def _abrir_fts(self, ruta_fts: Optional[str]) -> bool:
        """Abre el índice léxico (FTS5) al lado de Chroma y lo rellena si falta.

        Un fichero SQLite aparte: tocar el SQLite interno de Chroma sería
        jugar con muelles bajo tensión. Se rellena desde Chroma si el número
        de filas no cuadra (borrados fuera, fallos del insert...).
        """
        try:
            ruta = ruta_fts or (self.db_path.rstrip("/\\") + "_fts.sqlite")
            self._fts_ruta = ruta
            self._fts = sqlite3.connect(ruta, check_same_thread=False)
            self._fts.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS recuerdos USING fts5("
                "doc_id UNINDEXED, fecha, texto, "
                "tokenize='unicode61 remove_diacritics 2')" )
            self._fts.commit()
        except Exception as e:
            print(f"[Memoria] Búsqueda léxica (FTS5) no disponible: {e}")
            print(f"[Memoria] Sigo solo con semántica + umbral (como antes)")
            self._fts = None
            return False
        n_fts = int(self._fts.execute(
            "SELECT COUNT(*) FROM recuerdos").fetchone()[0])
        n_chroma = int(self.coleccion.count())
        if n_fts != n_chroma:
            datos = self.coleccion.get(include=["documents", "metadatas"])
            self._fts.execute("DELETE FROM recuerdos")
            filas = []
            for doc_id, texto, meta in zip(datos["ids"], datos["documents"],
                                           datos["metadatas"]):
                filas.append((doc_id,
                              (meta or {}).get("fecha", ""),
                              texto or ""))
            self._fts.executemany(
                "INSERT INTO recuerdos (doc_id, fecha, texto) VALUES (?, ?, ?)",
                filas)
            self._fts.commit()
            print(f"[Memoria] Índice léxico rellenado: {len(filas)} recuerdos")
        print(f"[Memoria] Búsqueda híbrida activa (semántica + léxica FTS5)")
        return True

    def _fts_buscar(self, consulta: str, k: int = 8) -> List[Dict]:
        """Búsqueda léxica: tokens de la consulta contra FTS5, ranking BM25.

        El matching es contra el texto normalizado por el tokenizer
        (`remove_diacritics 2`): sin tildes, a minúsculas.
        """
        if self._fts is None:
            return []
        tokens = re.findall(r"[\wáéíóúüñ]{3,}", (consulta or "").lower())
        tokens = [t for t in tokens if t not in _STOPWORDS_FTS][:8]
        if not tokens:
            return []
        consulta_fts = " OR ".join(tokens)
        try:
            filas = self._fts.execute(
                "SELECT doc_id, fecha, texto, bm25(recuerdos) AS puntuacion "
                "FROM recuerdos WHERE recuerdos MATCH ? "
                "ORDER BY puntuacion LIMIT ?",
                (consulta_fts, k)).fetchall()
        except Exception as e:
            # Token inválido, sobrecarga de sintaxis u otro detalle de FTS5:
            # sin léxico esta vez, no se cae nada.
            print(f"[Memoria] FTS5 no pudo buscar ({e}); solo semántica")
            return []
        return [{"doc_id": f[0], "texto": f[2], "rank": i}
                for i, f in enumerate(filas)]

    def _generar_id(self, texto: str, timestamp: str) -> str:
        return hashlib.md5(f"{texto}{timestamp}".encode('utf-8')).hexdigest()

    def _generar_embedding(self, texto: str) -> List[float]:
        return self.modelo_emb.encode(texto, convert_to_numpy=True).tolist()

    def guardar_recuerdo(self, texto: str, metadata: Optional[Dict] = None,
                          tipo: str = "interaccion",
                          texto_embedding: Optional[str] = None) -> str:
        """
        Args:
            texto: contenido completo que se guarda y se muestra (ej. "Usuario: X\\nParker: Y")
            texto_embedding: texto usado SOLO para generar el vector de búsqueda.
                Si no se pasa, se usa 'texto' (comportamiento anterior).
                Se recomienda pasar aquí solo el mensaje del usuario, para que las
                búsquedas futuras comparen "pregunta nueva" vs "pregunta vieja"
                y no se diluyan con la respuesta de Parker.
        """
        timestamp = datetime.now().isoformat()
        doc_id = self._generar_id(texto, timestamp)

        meta = {
            "timestamp": timestamp,
            "tipo": tipo,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M")
        }
        if metadata:
            meta.update(metadata)

        texto_para_vector = texto_embedding if texto_embedding is not None else texto

        self.coleccion.add(
            ids=[doc_id],
            embeddings=[self._generar_embedding(texto_para_vector)],
            documents=[texto],
            metadatas=[meta]
        )
        # El texto también entra en el índice léxico (la misma fuente debe
        # estar en las dos punta del ranking, o RRF daría ventaja injusta).
        if self._fts is not None:
            try:
                self._fts.execute(
                    "INSERT INTO recuerdos (doc_id, fecha, texto) VALUES (?, ?, ?)",
                    (doc_id, meta.get("fecha", ""), texto))
                self._fts.commit()
            except Exception as e:
                print(f"[Memoria] FTS5 no pudo indexar el recuerdo: {e}")
        print(f"[Memoria] Recuerdo guardado: {doc_id[:8]}... | Tipo: {tipo}")
        return doc_id

    def recuperar_recuerdos(self, consulta: str, top_k: int = 5,
                             umbral: float = 0.5) -> List[Dict]:
        """Recuerdos con ranking HÍBRIDO (semántica + léxica, fusión RRF).

        Con híbrida activa el `umbral` NO se aplica (los límites de similitud
        coseno no separan señal de ruido: solapamiento medido en la placa);
        el orden lo funde RRF sobre ambas listas. Sin FTS5 (o con híbrida
        sin activar), se respeta el comportamiento de siempre: sólo semántica
        + umbral.
        """
        if self.coleccion.count() == 0:
            return []

        n_semantica = max(top_k * 3, 8)
        resultados = self.coleccion.query(
            query_embeddings=[self._generar_embedding(consulta)],
            n_results=min(n_semantica, self.coleccion.count()),
            include=["documents", "metadatas", "distances"]
        )

        semantica: List[Dict] = []
        for i in range(len(resultados['ids'][0])):
            semantica.append({
                "id": resultados['ids'][0][i],
                "texto": resultados['documents'][0][i],
                "metadata": resultados['metadatas'][0][i],
                "similitud": round(1.0 - resultados['distances'][0][i], 4),
            })

        # --- Camino SIN híbrida: como siempre (umbral + orden semántico) ---
        if not self.hibrida:
            recuerdos = [r for r in semantica if r["similitud"] >= umbral]
            recuerdos.sort(key=lambda x: x['similitud'], reverse=True)
            return recuerdos[:top_k]

        # --- Camino híbrido: RRF sobre semántica + léxica ----------------
        lexica = self._fts_buscar(consulta, k=max(8, top_k * 2))
        puntuaciones: Dict[str, float] = {}
        for rank, fila in enumerate(lexica):
            puntuaciones[fila["doc_id"]] = puntuaciones.get(
                fila["doc_id"], 0.0) + 1.0 / (60.0 + rank + 1)
        for rank, fila in enumerate(semantica):
            puntuaciones[fila["id"]] = puntuaciones.get(
                fila["id"], 0.0) + 1.0 / (60.0 + rank + 1)

        por_id = {fila["id"]: fila for fila in semantica}
        faltan = [did for did in puntuaciones if did not in por_id]
        if faltan:
            try:
                datos = self.coleccion.get(ids=faltan,
                                           include=["documents", "metadatas"])
                for i, doc_id in enumerate(datos["ids"]):
                    por_id[doc_id] = {
                        "id": doc_id,
                        "texto": datos["documents"][i],
                        "metadata": datos["metadatas"][i],
                        "similitud": None,  # viene solo del ranking léxico
                    }
            except Exception as e:
                print(f"[Memoria] Faltaban textos léxicos ({e}): se descartan")

        orden = sorted(puntuaciones.items(),
                       key=lambda kv: (-kv[1], -(por_id[kv[0]]["similitud"] or 0.0)))
        recuerdos = []
        for doc_id, _puntuacion in orden[:top_k]:
            fila = por_id.get(doc_id)
            if fila:
                recuerdos.append(fila)
        if lexica and len(lexica) >= top_k:
            print(f"[Memoria] Híbrido: {len(semantica)} semánticos + "
                  f"{len(lexica)} léxicos -> top {top_k}")
        return recuerdos[:top_k]

    def recuperar_recuerdos_formateados(self, consulta: str, top_k: int = 5,
                                         umbral: float = 0.5,
                                         max_caracteres: int = 0) -> str:
        recuerdos = self.recuperar_recuerdos(consulta, top_k, umbral)
        return formatear_recuerdos(recuerdos, max_caracteres)

    def obtener_estadisticas(self) -> Dict:
        return {
            "total_documentos": self.coleccion.count(),
            "coleccion": self.nombre_coleccion,
            "db_path": self.db_path,
            "dimension_embeddings": self.dimension
        }

    def buscar_por_fecha(self, fecha: str) -> List[Dict]:
        resultados = self.coleccion.get(where={"fecha": fecha}, include=["documents", "metadatas"])
        return [{"id": resultados['ids'][i], "texto": resultados['documents'][i],
                 "metadata": resultados['metadatas'][i]} for i in range(len(resultados['ids']))]

    def borrar_todos(self) -> int:
        """Borra TODOS los recuerdos de esta colección y devuelve cuántos eran.

        Se usa en el modo de borrado por voz (con confirmación) y en
        `tools/recuerdos.py --borrar`. La colección se conserva: el modelo de
        embeddings ya está cargado y Parker puede seguir guardando después.
        """
        total = self.coleccion.count()
        if total:
            datos = self.coleccion.get(include=["metadatas"])
            ids = datos.get("ids") or []
            if ids:
                self.coleccion.delete(ids=ids)
        if self._fts is not None:
            try:
                self._fts.execute("DELETE FROM recuerdos")
                self._fts.commit()
            except Exception as e:
                print(f"[Memoria] No pude vaciar el índice léxico: {e}")
        return total

    def eliminar_recuerdo(self, doc_id: str) -> bool:
        try:
            self.coleccion.delete(ids=[doc_id])
            if self._fts is not None:
                try:
                    self._fts.execute("DELETE FROM recuerdos WHERE doc_id = ?",
                                      (doc_id,))
                    self._fts.commit()
                except Exception as e:
                    print(f"[Memoria] No pude borrar del índice léxico: {e}")
            return True
        except Exception as e:
            print(f"[Memoria] Error al eliminar {doc_id}: {e}")
            return False