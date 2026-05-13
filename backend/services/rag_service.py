"""
rag_service.py

ChromaDB-based RAG for informational clinic queries.
Documents are embedded once at startup and stored persistently.

To manually ingest or re-ingest after editing any .txt file:
    python services/rag_service.py --ingest
"""

import os
import sys
import time
import logging
import shutil
from pathlib import Path

import chromadb
import numpy as np
from prometheus_client import Counter, Histogram
from sklearn.feature_extraction.text import HashingVectorizer

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "data" / "clinic_docs"
CHROMA_PERSIST = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "mediflow_clinic_docs"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
TOP_K = 3
EMBEDDING_DIMENSIONS = 384

PROM_RAG_QUERIES = Counter(
    "mediflow_rag_queries_total", "RAG query count", ["language"]
)
PROM_RAG_LATENCY = Histogram(
    "mediflow_rag_latency_seconds",
    "End-to-end RAG query latency",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 8.0]
)
PROM_RAG_EMPTY = Counter(
    "mediflow_rag_empty_results_total", "RAG queries returning no chunks"
)


class LocalHashEmbeddingFunction:
    """
    Deterministic local embeddings for the small clinic knowledge base.

    Chroma's default embedding function downloads a transformer model at
    runtime. That is brittle on free-tier hosts, CI, and locked-down Docker
    environments. This keeps RAG functional without external downloads.
    """

    def __init__(self) -> None:
        self._vectorizer = HashingVectorizer(
            n_features=EMBEDDING_DIMENSIONS,
            alternate_sign=False,
            norm="l2",
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True,
        )

    def name(self) -> str:
        return "mediflow-local-hashing-v1"

    def __call__(self, input):
        docs = [str(item or "") for item in input]
        vectors = self._vectorizer.transform(docs).astype(np.float32)
        return vectors.toarray().tolist()


def _get_embedding_fn():
    """
    Returns one embedding function consistently.
    CRITICAL: Do not change the embedding model after initial ingest
    without running --ingest again to rebuild the collection.
    """
    logger.info("RAG: using deterministic local hashing embeddings")
    return LocalHashEmbeddingFunction()


def _chunk_text(text: str, source: str) -> list[dict]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({
                "text": chunk,
                "source": source,
                "id": f"{source}_{idx}",
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
        idx += 1
    return chunks


class RAGService:
    def __init__(self):
        self._client = None
        self._collection = None
        self._embed_fn = None

    def _init_client(self) -> None:
        """Lazy-initialize ChromaDB client and embedding function."""
        if self._client is not None:
            return
        if self._embed_fn is None:
            self._embed_fn = _get_embedding_fn()

        CHROMA_PERSIST.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_PERSIST))
        try:
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:
            logger.warning(
                "RAG: existing collection could not be opened, rebuilding it: %s",
                exc,
            )
            try:
                self._client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            self._collection = self._client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"}
            )

    def ensure_collection_populated(self) -> None:
        """
        Called at FastAPI startup. Auto-ingests if the collection is empty.
        Safe to call multiple times.
        """
        self._init_client()
        count = self._collection.count()
        if count == 0:
            logger.info("RAG: collection empty, auto-ingesting clinic documents...")
            n = self.ingest_documents()
            logger.info("RAG: auto-ingest complete - %s chunks loaded", n)
        else:
            logger.info("RAG: collection ready with %s chunks", count)

    def ingest_documents(self) -> int:
        """
        Read all .txt files from clinic_docs, chunk and embed into ChromaDB.
        Clears existing collection first. Safe to run multiple times.
        Returns the number of chunks ingested.
        """
        self._init_client()
        # Clear existing collection
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = self._client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"}
        )

        all_ids, all_docs, all_metas = [], [], []

        if not DOCS_DIR.exists():
            logger.error(f"RAG: DOCS_DIR not found at {DOCS_DIR}")
            return 0

        doc_files = sorted(DOCS_DIR.glob("*.txt"))
        if not doc_files:
            logger.error(f"RAG: no .txt files found in {DOCS_DIR}")
            return 0

        for doc_file in doc_files:
            text = doc_file.read_text(encoding="utf-8")
            for chunk in _chunk_text(text, doc_file.stem):
                all_ids.append(chunk["id"])
                all_docs.append(chunk["text"])
                all_metas.append({"source": chunk["source"]})
            logger.info(f"RAG: chunked {doc_file.name}")

        # Batch upsert
        batch_size = 100
        for i in range(0, len(all_ids), batch_size):
            self._collection.add(
                ids=all_ids[i:i + batch_size],
                documents=all_docs[i:i + batch_size],
                metadatas=all_metas[i:i + batch_size],
            )

        logger.info(f"RAG: ingested {len(all_ids)} chunks from {len(doc_files)} files")
        return len(all_ids)

    async def query(self, user_question: str, language: str = "en", mode: str = "text") -> str:
        """
        Retrieve top-K relevant chunks and generate a grounded LLM answer.
        Returns the response string. Never raises — always returns something.
        """
        from services.llm_router import llm_router  # local import avoids circular

        t0 = time.time()
        PROM_RAG_QUERIES.labels(language=language).inc()

        self._init_client()

        # Retrieval
        try:
            results = self._collection.query(
                query_texts=[user_question],
                n_results=TOP_K,
            )
        except Exception as e:
            logger.error(f"RAG: ChromaDB query failed: {e}")
            return (
                "I do not have specific information about that. "
                "Please call the clinic at 0800-MEDIFLOW for details."
            )

        chunks = results["documents"][0] if results["documents"] else []
        sources = [m["source"] for m in results["metadatas"][0]] if results["metadatas"] else []

        if not chunks:
            PROM_RAG_EMPTY.inc()
            return (
                "I do not have specific information about that. "
                "Please call the clinic at 0800-MEDIFLOW for details."
            )

        context = "\n\n---\n\n".join(
            f"[From: {src}]\n{chunk}"
            for chunk, src in zip(chunks, sources)
        )

        lang_instruction = (
            "Respond in Urdu (Arabic script) since the patient wrote in Urdu."
            if language == "ur"
            else "Respond in English."
        )

        # Voice responses must be short for TTS latency budgets, with no markdown.
        if mode == "voice":
            sentence_constraint = "Respond in maximum 2 sentences. DO NOT use markdown, bullet points, or special formatting. Use plain conversational language."
        else:
            sentence_constraint = "Keep your response to 1 to 3 short sentences. Do not use markdown, bullet points, JSON, code blocks, or special formatting."

        prompt = f"""You are a professional MediFlow clinic assistant.
Your only source of information is the provided CONTEXT.
If the CONTEXT does not contain the exact answer, say: "I don't have that specific information. Please call 0800-MEDIFLOW."
Do not guess, invent policies, expose sources, mention chunks, or mention the retrieval system.
{sentence_constraint}
Be friendly, empathetic, and clear. Answer the patient's question directly first.
{lang_instruction}

--- CONTEXT ---
{context}
---------------

PATIENT QUESTION: {user_question}

ANSWER:"""

        try:
            resp = await llm_router.call(
                messages=[{"role": "user", "content": prompt}],
                system="You are a helpful clinic information assistant. Return only the final patient-facing answer in plain text.",
                task_type="urdu" if language == "ur" else "rag",
            )
            answer = resp.text if resp and resp.text else None
        except Exception as e:
            logger.error(f"RAG: LLM call failed: {e}")
            answer = None

        PROM_RAG_LATENCY.observe(time.time() - t0)

        return answer or (
            "I could not retrieve that information right now. "
            "Please call 0800-MEDIFLOW for assistance."
        )


# Singleton — import this everywhere
rag_service = RAGService()


if __name__ == "__main__":
    if "--ingest" in sys.argv:
        if "--reset" in sys.argv and CHROMA_PERSIST.exists():
            for child in CHROMA_PERSIST.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            print(f"Reset ChromaDB store at {CHROMA_PERSIST}")
        svc = RAGService()
        n = svc.ingest_documents()
        print(f"Ingested {n} chunks from {DOCS_DIR}")
    else:
        print("Usage: python services/rag_service.py --ingest [--reset]")
