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
import asyncio
import re
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
RAG_LLM_TIMEOUT_SECONDS = float(os.getenv("RAG_LLM_TIMEOUT_SECONDS", "8"))

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "bring", "can",
    "do", "does", "for", "from", "have", "how", "i", "in", "is", "it",
    "me", "my", "of", "on", "or", "our", "please", "should", "the",
    "there", "to", "what", "when", "where", "which", "who", "with", "you",
    "your",
}

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
PROM_RAG_FALLBACK = Counter(
    "mediflow_rag_fallback_total", "RAG fallback usage", ["reason"]
)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+|[\u0600-\u06FF]+", (text or "").lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lstrip("- ").strip())


def _limit_sentences(text: str, max_sentences: int) -> str:
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    pieces = [piece.strip() for piece in pieces if piece.strip()]
    return " ".join(pieces[:max_sentences]) if pieces else text.strip()


def _plain_text_answer(answer: str, mode: str) -> str:
    cleaned = re.sub(r"[*_`#>\[\]]", "", answer or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if mode == "voice":
        return _limit_sentences(cleaned, 2)
    return _limit_sentences(cleaned, 3)


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
        self._doc_chunks = None

    def _reset_persisted_store(self) -> None:
        """Drop only the local Chroma cache when persisted metadata is unusable."""
        self._client = None
        self._collection = None
        shutil.rmtree(CHROMA_PERSIST, ignore_errors=True)
        CHROMA_PERSIST.mkdir(parents=True, exist_ok=True)

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
            try:
                self._collection = self._client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=self._embed_fn,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as rebuild_exc:
                logger.warning(
                    "RAG: persisted Chroma store is incompatible, resetting cache: %s",
                    rebuild_exc,
                )
                self._reset_persisted_store()
                self._client = chromadb.PersistentClient(path=str(CHROMA_PERSIST))
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
        try:
            count = self._collection.count()
        except Exception as exc:
            logger.warning("RAG: collection count failed, rebuilding: %s", exc)
            self._reset_persisted_store()
            self._init_client()
            count = 0
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
            try:
                text = doc_file.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("RAG: skipping unreadable doc %s: %s", doc_file, exc)
                continue
            for chunk in _chunk_text(text, doc_file.stem):
                all_ids.append(chunk["id"])
                all_docs.append(chunk["text"])
                all_metas.append({"source": chunk["source"]})
            logger.info(f"RAG: chunked {doc_file.name}")

        if not all_ids:
            logger.error("RAG: no chunks produced from clinic documents")
            return 0

        # Batch upsert
        batch_size = 100
        for i in range(0, len(all_ids), batch_size):
            self._collection.add(
                ids=all_ids[i:i + batch_size],
                documents=all_docs[i:i + batch_size],
                metadatas=all_metas[i:i + batch_size],
            )

        logger.info(f"RAG: ingested {len(all_ids)} chunks from {len(doc_files)} files")
        self._doc_chunks = None
        return len(all_ids)

    def _load_document_chunks(self) -> list[dict]:
        """Load and cache text chunks directly from clinic docs for fallback retrieval."""
        cached = getattr(self, "_doc_chunks", None)
        if cached is not None:
            return cached

        chunks: list[dict] = []
        if not DOCS_DIR.exists():
            logger.error("RAG: DOCS_DIR not found for lexical fallback at %s", DOCS_DIR)
            self._doc_chunks = []
            return []

        for doc_file in sorted(DOCS_DIR.glob("*.txt")):
            try:
                text = doc_file.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("RAG: fallback skipped unreadable doc %s: %s", doc_file, exc)
                continue
            for chunk in _chunk_text(text, doc_file.stem):
                chunk["tokens"] = _tokens(chunk["text"])
                chunks.append(chunk)

        self._doc_chunks = chunks
        return chunks

    def _lexical_retrieve(self, user_question: str, limit: int = TOP_K) -> list[dict]:
        """Simple cached lexical retriever used when vector retrieval is empty or unavailable."""
        question_tokens = _tokens(user_question)
        if not question_tokens:
            return []

        text = user_question.lower()
        source_boosts = {
            "clinic_overview": ("hour", "timing", "open", "sunday", "emergency", "pharmacy", "parking", "language", "department"),
            "doctor_profiles": ("doctor", "dr", "fee", "qualification", "available", "specialist", "specialty", "dermatologist", "cardiologist"),
            "symptom_specialty_guide": ("symptom", "pain", "fever", "cough", "chest", "knee", "child", "doctor", "specialty", "see"),
            "policies": ("policy", "cancel", "reschedule", "walk", "record", "prescription", "photo", "attendant", "fee"),
            "visiting_guidelines": ("bring", "document", "cnic", "parking", "visitor", "attendant", "wheelchair", "accessibility"),
        }

        ranked = []
        for chunk in self._load_document_chunks():
            chunk_tokens = chunk.get("tokens") or _tokens(chunk.get("text", ""))
            overlap = len(question_tokens & chunk_tokens)
            if overlap == 0:
                continue
            score = float(overlap)
            chunk_text = chunk["text"].lower()
            for token in question_tokens:
                if token in chunk_text:
                    score += 0.25
            for source, keywords in source_boosts.items():
                if chunk["source"] == source and any(keyword in text for keyword in keywords):
                    score += 2.0
            ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in ranked[:limit]]

    def _retrieve_chunks(self, user_question: str) -> list[dict]:
        entries: list[dict] = []
        try:
            self._init_client()
            results = self._collection.query(
                query_texts=[user_question],
                n_results=max(TOP_K, 5),
            )
            docs = results.get("documents") or []
            metas = results.get("metadatas") or []
            documents = docs[0] if docs else []
            metadatas = metas[0] if metas else []
            for idx, doc in enumerate(documents):
                if not str(doc or "").strip():
                    continue
                meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
                entries.append({
                    "text": str(doc),
                    "source": str(meta.get("source") or "clinic_docs"),
                })
        except Exception as exc:
            PROM_RAG_FALLBACK.labels(reason="vector_error").inc()
            logger.warning("RAG: vector retrieval failed, using lexical fallback: %s", exc)

        lexical = self._lexical_retrieve(user_question, limit=max(TOP_K, 5))
        if not entries and lexical:
            PROM_RAG_FALLBACK.labels(reason="lexical_only").inc()
        elif lexical:
            PROM_RAG_FALLBACK.labels(reason="lexical_rerank").inc()

        seen = set()
        merged = []
        for entry in entries + lexical:
            key = (entry["source"], entry["text"][:120])
            if key in seen:
                continue
            seen.add(key)
            merged.append({"text": entry["text"], "source": entry["source"]})
        return merged[:max(TOP_K, 5)]

    def _extractive_answer(self, user_question: str, entries: list[dict], language: str, mode: str) -> str:
        question_tokens = _tokens(user_question)
        if not entries or not question_tokens:
            return self._fallback_message(language)

        candidates = []
        for entry in entries:
            source = entry["source"]
            for line in str(entry["text"]).splitlines():
                clean = _clean_line(line)
                if len(clean) < 5:
                    continue
                line_tokens = _tokens(clean)
                overlap = len(question_tokens & line_tokens)
                score = overlap
                lower_line = clean.lower()
                lower_question = user_question.lower()
                if any(word in lower_question for word in ("hour", "timing", "open")) and any(word in lower_line for word in ("opening hours", "sunday", "available")):
                    score += 4
                if any(word in lower_question for word in ("bring", "document", "cnic")) and any(word in lower_line for word in ("cnic", "b-form", "insurance", "medical reports", "prescriptions")):
                    score += 4
                if "parking" in lower_question and "parking" in lower_line:
                    score += 4
                if any(word in lower_question for word in ("fee", "cost", "charge")) and "fee" in lower_line:
                    score += 4
                if any(word in lower_question for word in ("cancel", "reschedule")) and any(word in lower_line for word in ("cancel", "reschedule", "2 hours")):
                    score += 4
                if score > 0:
                    candidates.append((score, source, clean))

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = []
        seen = set()
        for _, _, line in candidates:
            if line.lower() in seen:
                continue
            seen.add(line.lower())
            selected.append(line)
            if len(selected) >= (2 if mode == "voice" else 4):
                break

        if not selected:
            return self._fallback_message(language)

        answer = " ".join(selected)
        return _plain_text_answer(answer, mode)

    @staticmethod
    def _fallback_message(language: str) -> str:
        return (
            "I don't have that specific information. "
            "Please call 0800-MEDIFLOW."
        )

    async def query(
        self,
        user_question: str,
        language: str = "en",
        mode: str = "text",
        conversation_context: list[dict] | None = None,
    ) -> str:
        """
        Retrieve top-K relevant chunks and generate a grounded LLM answer.
        Returns the response string. Never raises — always returns something.
        """
        from services.llm_router import llm_router  # local import avoids circular

        t0 = time.time()
        PROM_RAG_QUERIES.labels(language=language).inc()

        entries = self._retrieve_chunks(user_question)

        if not entries:
            PROM_RAG_EMPTY.inc()
            PROM_RAG_LATENCY.observe(time.time() - t0)
            return self._fallback_message(language)

        context = "\n\n---\n\n".join(
            f"[From: {entry['source']}]\n{entry['text']}"
            for entry in entries
        )

        lang_instruction = (
            'Respond in Urdu (Arabic script) since the patient wrote in Urdu. '
            'Use natural, conversational Urdu. Do not mix in English words.'
            if language == 'ur'
            else 'Respond in English. Be warm and conversational.'
        )

        context_summary = ''
        if conversation_context:
            relevant_turns = [
                m for m in conversation_context
                if isinstance(m, dict)
                and m.get('role') in ('user', 'assistant')
                and 'content' in m
                and isinstance(m['content'], str)
            ][-4:]
            if relevant_turns:
                lines = []
                for m in relevant_turns:
                    speaker = 'Patient' if m['role'] == 'user' else 'Assistant'
                    content = m['content'][:120].replace('\n', ' ')
                    lines.append(f'{speaker}: {content}')
                context_summary = (
                    '\n\nRECENT CONVERSATION (use this for context only, '
                    'do not repeat it back):\n'
                    + '\n'.join(lines)
                    + '\n'
                )

        sources = [entry["source"] for entry in entries]
        top_source = sources[0] if sources else 'default'

        source_instructions = {
            'doctor_profiles': (
                'You are answering about a specific doctor. Include their specialty, '
                'what they treat, fee, and availability. Be warm and informative. '
                'Maximum 5 sentences.'
            ),
            'preparation_instructions': (
                'You are giving pre-appointment preparation instructions. '
                'Format your answer as a short numbered list of 3 to 5 practical steps. '
                'Be specific and friendly.'
            ),
            'symptom_specialty_guide': (
                'You are helping the patient find the right doctor. '
                'Name the recommended specialty and 1 or 2 specific doctors. '
                'Mention the fee. Offer to check available slots. '
                'Maximum 4 sentences.'
            ),
            'faqs': (
                'Give a direct, friendly answer. '
                'If a fee or time is mentioned in the context, include it. '
                'Maximum 3 sentences.'
            ),
            'policies': (
                'State the policy clearly and specifically. '
                'Include any fees or time windows mentioned in the context. '
                'Maximum 3 sentences.'
            ),
            'insurance_payments': (
                'Answer the insurance or payment question directly. '
                'List specific options from the context. '
                'Maximum 4 sentences.'
            ),
            'emergency_guidance': (
                'This is an emergency guidance question. '
                'Be clear, calm, and direct. '
                'If the symptom is a genuine emergency, say so clearly first '
                'and provide 1122 or the emergency line. '
                'Do not bury the emergency instruction.'
            ),
            'default': (
                'Be helpful, friendly, and specific to the patient question. '
                'Maximum 4 sentences.'
            ),
        }

        response_style = source_instructions.get(
            top_source,
            source_instructions['default']
        )

        if mode == "voice":
            response_style += " Respond in maximum 2 sentences. Do not use markdown or bullets."

        prompt = f"""You are MediFlow clinic assistant — a warm, knowledgeable
receptionist at a Pakistani medical clinic.

RULES:
- Answer ONLY using the CLINIC DOCUMENTS below.
- If the documents do not contain the answer, say:
  "I don't have that specific information. Please call 0800-MEDIFLOW."
- Never guess or make up fees, doctor names, or policies.
- Never mention that you are using documents or a knowledge base.
- {response_style}
- {lang_instruction}
{context_summary}
CLINIC DOCUMENTS:
{context}

PATIENT QUESTION: {user_question}

ANSWER:"""

        try:
            resp = await asyncio.wait_for(
                llm_router.call(
                    messages=[{"role": "user", "content": prompt}],
                    system="You are a helpful clinic information assistant. Return only the final patient-facing answer in plain text.",
                    task_type="urdu" if language == "ur" else "rag",
                ),
                timeout=RAG_LLM_TIMEOUT_SECONDS,
            )
            answer = resp.text if resp and resp.text else None
        except Exception as e:
            logger.error(f"RAG: LLM call failed: {e}")
            answer = None

        PROM_RAG_LATENCY.observe(time.time() - t0)

        if answer:
            answer = _plain_text_answer(answer, mode)
            lower_answer = answer.lower()
            if (
                "i don't have that specific information" not in lower_answer
                and "i do not have that specific information" not in lower_answer
                and "```" not in answer
                and not answer.lstrip().startswith(("{", "["))
            ):
                return answer
            PROM_RAG_FALLBACK.labels(reason="llm_unhelpful").inc()
        else:
            PROM_RAG_FALLBACK.labels(reason="llm_failure").inc()

        return self._extractive_answer(user_question, entries, language, mode)


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
