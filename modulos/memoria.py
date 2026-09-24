"""
modulos/memoria.py
==================
Gestión de memoria a largo plazo mediante ChromaDB (RAG local).
"""

import os
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class MemoriaParker:
    def __init__(self, db_path: str = "./parker.db",
                 coleccion: str = "recuerdos_parker",
                 modelo_embeddings: str = "paraphrase-multilingual-MiniLM-L12-v2"):
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

    def _obtener_o_crear_coleccion(self):
        try:
            return self.cliente.get_collection(name=self.nombre_coleccion)
        except Exception:
            print(f"[Memoria] Creando nueva colección: {self.nombre_coleccion}")
            return self.cliente.create_collection(
                name=self.nombre_coleccion,
                metadata={"hnsw:space": "cosine"}
            )

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
        print(f"[Memoria] Recuerdo guardado: {doc_id[:8]}... | Tipo: {tipo}")
        return doc_id

    def recuperar_recuerdos(self, consulta: str, top_k: int = 5,
                             umbral: float = 0.5) -> List[Dict]:
        if self.coleccion.count() == 0:
            return []

        resultados = self.coleccion.query(
            query_embeddings=[self._generar_embedding(consulta)],
            n_results=min(top_k, self.coleccion.count()),
            include=["documents", "metadatas", "distances"]
        )

        recuerdos = []
        for i in range(len(resultados['ids'][0])):
            similitud = 1.0 - resultados['distances'][0][i]
            if similitud >= umbral:
                recuerdos.append({
                    "id": resultados['ids'][0][i],
                    "texto": resultados['documents'][0][i],
                    "metadata": resultados['metadatas'][0][i],
                    "similitud": round(similitud, 4)
                })

        recuerdos.sort(key=lambda x: x['similitud'], reverse=True)
        return recuerdos

    def recuperar_recuerdos_formateados(self, consulta: str, top_k: int = 5,
                                         umbral: float = 0.5) -> str:
        recuerdos = self.recuperar_recuerdos(consulta, top_k, umbral)
        if not recuerdos:
            return ""

        lineas = ["=== RECUERDOS RELEVANTES ==="]
        for i, rec in enumerate(recuerdos, 1):
            fecha = rec['metadata'].get('fecha', 'fecha_desconocida')
            tipo = rec['metadata'].get('tipo', 'general')
            lineas.append(f"[{i}] ({fecha} | {tipo} | sim:{rec['similitud']}) {rec['texto']}")
        return "\n".join(lineas)

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

    def eliminar_recuerdo(self, doc_id: str) -> bool:
        try:
            self.coleccion.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"[Memoria] Error al eliminar {doc_id}: {e}")
            return False