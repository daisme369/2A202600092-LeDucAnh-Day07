"""
RAG CLI Chatbot - Gemini API + Recursive Chunking
===================================================
Interactive chatbot that reads documents from src/data, chunks them with
RecursiveChunker, embeds via Gemini embedding model, then retrieves top-3
nearest chunks with similarity scores before generating answers.
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from src.chunking import RecursiveChunker
from src.embeddings import GeminiEmbedder
from src.models import Document
from src.store import EmbeddingStore

# ---- Constants -------------------------------------------------------
DATA_DIR = Path(__file__).parent / "src" / "data"
ALLOWED_EXTENSIONS = {".md", ".txt"}
CHUNK_SIZE = 500
TOP_K = 3
MIN_CHUNK_CHARS = 120
LLM_MAX_RETRIES = 4
LLM_RETRY_BACKOFF_SECONDS = 2

# ---- ANSI colours for pretty CLI output ------------------------------
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_MAGENTA = "\033[95m"
C_DIM = "\033[2m"
C_BLUE = "\033[94m"


# ---- Document loading ------------------------------------------------
def load_documents_from_directory(data_dir: Path) -> list[Document]:
    """Recursively load all .md / .txt files from data_dir."""
    documents: list[Document] = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
            content = path.read_text(encoding="utf-8")
            documents.append(
                Document(
                    id=path.stem,
                    content=content,
                    metadata={
                        "source": str(path.relative_to(data_dir)),
                        "extension": path.suffix.lower(),
                    },
                )
            )
    return documents


# ---- Chunk documents -------------------------------------------------
def chunk_documents(
    docs: list[Document], chunk_size: int = CHUNK_SIZE
) -> list[Document]:
    """Split every document into smaller chunks using RecursiveChunker."""
    chunker = RecursiveChunker(chunk_size=chunk_size)
    chunked_docs: list[Document] = []

    for doc in docs:
        chunks = chunker.chunk(doc.content)
        for idx, chunk_text in enumerate(chunks):
            chunked_docs.append(
                Document(
                    id=f"{doc.id}__chunk_{idx}",
                    content=chunk_text,
                    metadata={
                        **doc.metadata,
                        "doc_id": doc.id,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                    },
                )
            )
    return chunked_docs


def _normalize_for_dedup(text: str) -> str:
    """Normalize text for exact dedup checks."""
    return re.sub(r"\s+", " ", text).strip().lower()


def optimize_chunks(
    docs: list[Document], min_chunk_chars: int = MIN_CHUNK_CHARS
) -> tuple[list[Document], dict[str, int]]:
    """Drop very short chunks and exact duplicate chunks to cut embedding calls."""
    optimized: list[Document] = []
    seen: set[str] = set()
    dropped_short = 0
    dropped_dup = 0

    for doc in docs:
        content = doc.content.strip()
        if len(content) < min_chunk_chars:
            dropped_short += 1
            continue

        normalized = _normalize_for_dedup(content)
        if normalized in seen:
            dropped_dup += 1
            continue

        seen.add(normalized)
        optimized.append(doc)

    stats = {
        "kept": len(optimized),
        "dropped_short": dropped_short,
        "dropped_duplicate": dropped_dup,
        "original": len(docs),
    }
    return optimized, stats


# ---- Gemini LLM helper ----------------------------------------------
def create_gemini_llm(api_key: str, model: str = "gemini-2.5-flash"):
    """Return a callable that sends a prompt to Gemini generative model."""
    from google import genai

    client = genai.Client(api_key=api_key)
    fallback_raw = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash").strip()
    fallback_models = [m.strip() for m in fallback_raw.split(",") if m.strip()]

    # Keep order while removing duplicates.
    model_candidates: list[str] = []
    for candidate in [model, *fallback_models]:
        if candidate not in model_candidates:
            model_candidates.append(candidate)

    def _is_transient_error(err_text: str) -> bool:
        transient_markers = (
            "503",
            "UNAVAILABLE",
            "429",
            "RESOURCE_EXHAUSTED",
            "500",
            "INTERNAL",
            "DEADLINE_EXCEEDED",
        )
        return any(marker in err_text for marker in transient_markers)

    def llm_fn(prompt: str) -> str:
        last_error: Exception | None = None

        for candidate_model in model_candidates:
            for attempt in range(LLM_MAX_RETRIES):
                try:
                    response = client.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    return response.text or ""
                except Exception as e:
                    err_text = str(e)
                    last_error = e
                    if not _is_transient_error(err_text):
                        raise

                    is_last_try = attempt == LLM_MAX_RETRIES - 1
                    if not is_last_try:
                        wait = LLM_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                        print(
                            f"\r  [LLM RETRY] {candidate_model} failed ({attempt + 1}/{LLM_MAX_RETRIES}), retry in {wait}s...",
                            end="",
                            flush=True,
                        )
                        time.sleep(wait)
            print(f"\r  [LLM FALLBACK] switching model from {candidate_model}...", end="", flush=True)

        raise RuntimeError(f"All LLM models failed. Last error: {last_error}")

    return llm_fn


# ---- Build RAG prompt ------------------------------------------------
def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    """Build a prompt that includes retrieved context chunks."""
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks, start=1):
        source = chunk["metadata"].get("source", "unknown")
        context_parts.append(
            f"[Chunk {i} | source: {source}]\n{chunk['content']}"
        )
    context_text = "\n\n---\n\n".join(context_parts)

    return (
        "You are a helpful assistant. Use ONLY the context below to answer "
        "the user's question. If the context does not contain enough "
        "information, say so.\n\n"
        f"### Context:\n{context_text}\n\n"
        f"### Question:\n{question}\n\n"
        "### Answer:"
    )


# ---- Pretty-print helpers -------------------------------------------
def print_banner() -> None:
    print(f"\n{C_CYAN}{C_BOLD}{'=' * 60}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}  [BOT]  RAG CLI Chatbot  -  Gemini + Recursive Chunking{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'=' * 60}{C_RESET}")


def print_retrieval_results(results: list[dict]) -> None:
    print(f"\n{C_YELLOW}{C_BOLD}  [RETRIEVAL] Top-{len(results)} Retrieved Chunks:{C_RESET}")
    print(f"{C_DIM}  {'-' * 56}{C_RESET}")
    for i, r in enumerate(results, start=1):
        score = r["score"]
        source = r["metadata"].get("source", "unknown")
        chunk_idx = r["metadata"].get("chunk_index", "?")
        total = r["metadata"].get("total_chunks", "?")
        preview = r["content"][:120].replace("\n", " ").strip()

        print(
            f"  {C_GREEN}{i}. score={score:.4f}{C_RESET}  "
            f"{C_MAGENTA}source={source}{C_RESET}  "
            f"{C_DIM}[chunk {chunk_idx}/{total}]{C_RESET}"
        )
        print(f"     {C_DIM}{preview}...{C_RESET}")
    print(f"{C_DIM}  {'-' * 56}{C_RESET}")


def print_answer(answer: str) -> None:
    print(f"\n{C_BLUE}{C_BOLD}  [ANSWER]:{C_RESET}")
    # Indent the answer for readability
    for line in answer.strip().splitlines():
        print(f"  {line}")
    print()


# ---- Main entry point ------------------------------------------------
def main() -> int:
    # Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    load_dotenv(override=False)

    # --- Validate API key ---
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set in .env - aborting.")
        return 1

    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()

    # --- Load documents ---
    print_banner()
    print(f"\n{C_DIM}  Loading documents from: {DATA_DIR}{C_RESET}")

    raw_docs = load_documents_from_directory(DATA_DIR)
    if not raw_docs:
        print(f"[ERROR] No .md/.txt files found in {DATA_DIR}")
        return 1

    print(f"  [OK] Loaded {C_BOLD}{len(raw_docs)}{C_RESET} documents:")
    for doc in raw_docs:
        print(f"     - {doc.metadata['source']}")

    # --- Chunk documents with RecursiveChunker ---
    print(f"\n{C_DIM}  Chunking with RecursiveChunker (chunk_size={CHUNK_SIZE})...{C_RESET}")
    chunked_docs = chunk_documents(raw_docs, chunk_size=CHUNK_SIZE)
    print(f"  [OK] Created {C_BOLD}{len(chunked_docs)}{C_RESET} chunks from {len(raw_docs)} documents")

    print(f"{C_DIM}  Optimizing chunks (min_chars={MIN_CHUNK_CHARS}, dedup=exact)...{C_RESET}")
    chunked_docs, prune_stats = optimize_chunks(chunked_docs, min_chunk_chars=MIN_CHUNK_CHARS)
    print(
        "  [OK] Kept "
        f"{C_BOLD}{prune_stats['kept']}{C_RESET}/{prune_stats['original']} chunks "
        f"(short={prune_stats['dropped_short']}, duplicate={prune_stats['dropped_duplicate']})"
    )

    # --- Initialize Gemini embedder ---
    print(f"\n{C_DIM}  Initializing Gemini embedder: {embedding_model}{C_RESET}")
    try:
        embedder = GeminiEmbedder(api_key=api_key, model_name=embedding_model)
    except Exception as e:
        print(f"[ERROR] Failed to initialize GeminiEmbedder: {e}")
        return 1

    # --- Build vector store ---
    total = len(chunked_docs)
    print(f"{C_DIM}  Building vector store (embedding {total} chunks in batches)...{C_RESET}")
    store = EmbeddingStore(collection_name="rag_chatbot_store", embedding_fn=embedder)

    store.add_documents(chunked_docs)

    print(f"  [OK] Vector store ready - {C_BOLD}{store.get_collection_size()}{C_RESET} chunks indexed")
    print(f"  [OK] Embedding backend: {C_BOLD}{embedder._backend_name}{C_RESET}")

    # --- Create Gemini LLM ---
    llm_model = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash").strip()
    print(f"{C_DIM}  Initializing Gemini LLM: {llm_model}{C_RESET}")
    llm_fn = create_gemini_llm(api_key=api_key, model=llm_model)

    # --- Interactive loop ---
    print(f"\n{C_CYAN}{'-' * 60}{C_RESET}")
    print(f"  Type your question and press Enter.")
    print(f"  Type {C_BOLD}'quit'{C_RESET} or {C_BOLD}'exit'{C_RESET} to stop.")
    print(f"{C_CYAN}{'-' * 60}{C_RESET}")

    while True:
        try:
            print()
            question = input(f"{C_CYAN}{C_BOLD}  [?] You: {C_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C_DIM}  Goodbye!{C_RESET}")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print(f"\n{C_DIM}  Goodbye!{C_RESET}")
            break

        # --- Retrieve ---
        results = store.search(question, top_k=TOP_K)
        print_retrieval_results(results)

        # --- Generate ---
        prompt = build_rag_prompt(question, results)
        try:
            answer = llm_fn(prompt)
        except Exception as e:
            answer = f"[Error calling Gemini API: {e}]"

        print_answer(answer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
