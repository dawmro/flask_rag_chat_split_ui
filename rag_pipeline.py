"""
rag_pipeline.py

Multi-document conversational RAG (Retrieval-Augmented Generation) pipeline.

This module provides the backend logic for a "Chat with PDF(s)" application.
It supports indexing multiple PDFs into a single Chroma vector store and
answering user questions using retrieval + an LLM.

Core features:
- Multi-document indexing into a shared Chroma collection.
- Two retrieval scopes:
    * "active": search only within the currently selected document
    * "all": search across all indexed documents
- Conversational memory via chat history.
- Source citations (docId, filename, page) for UI navigation.

Important notes:
- This module keeps state in global variables and is therefore intended for a
  single-process development deployment. In production, state should be stored
  per-user/session in a database or cache (Redis, Postgres, etc.).
"""

import logging
import os
import shutil
import uuid
from typing import Optional

from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")

CHROMA_COLLECTION_NAME = "pdf_kb"

LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b-instruct-q8_0")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
RETRIEVER_K = int(os.getenv("RAG_RETRIEVER_K", "6"))

MAX_HISTORY_TURNS = 12

# MMR configuration:
# - lambda_mult closer to 0 => more diversity
# - lambda_mult closer to 1 => more relevance
MMR_LAMBDA_MULT = 0.25

# ---------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question", "chat_history"],
    template="""
You are a helpful assistant answering questions about uploaded PDF documents.

Chat history:
{chat_history}

Use ONLY the context below to answer the question.
If the answer is not in the context, say:
"I could not find a grounded answer in the uploaded PDF(s)."

Context:
{context}

Question:
{question}

Answer:
""".strip(),
)

# ---------------------------------------------------------------------
# Model initialization
# ---------------------------------------------------------------------

logger.info(
    "Initializing Ollama clients (LLM=%s, EMB=%s, URL=%s)...",
    LLM_MODEL,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
)

try:
    llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
        top_p=0.9,
    )

    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )

except Exception:
    logger.exception("Failed to initialize Ollama clients")
    raise

# ---------------------------------------------------------------------
# In-memory application state (single-process only)
# ---------------------------------------------------------------------

# Conversation memory used by ConversationalRetrievalChain.
# Each entry is a tuple: (user_message, assistant_answer).
chat_history: list[tuple[str, str]] = []

# Registry of documents uploaded during this server process.
# This does NOT reflect what is stored in Chroma on disk.
loaded_documents: dict[str, dict] = {}

# Document ID currently treated as "active" for filtered queries.
active_doc_id: Optional[str] = None


def _delete_vector_store() -> None:
    """
    Hard delete the entire Chroma persistence directory.

    Intended usage:
        - Call once at application startup for development mode
          (ensures no stale vectors exist between runs).

    Do NOT use during runtime resets:
        - On Windows, Chroma may keep file handles open, which can cause
          WinError 32 permission errors when deleting directories.
    """
    if os.path.isdir(CHROMA_DB_DIR):
        shutil.rmtree(CHROMA_DB_DIR, ignore_errors=True)

    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
    logger.info("Startup cleanup: deleted '%s' directory", CHROMA_DB_DIR)


# Development behavior: wipe vector store each time server starts
_delete_vector_store()


def reset_state() -> None:
    """
    Reset all application state.

    This resets:
    - chat history (conversation memory)
    - in-memory document registry
    - active document selection
    - Chroma vector store content (collection deletion)

    This function is typically used by the /reset API endpoint.
    """
    global chat_history, loaded_documents, active_doc_id

    chat_history = []
    loaded_documents = {}
    active_doc_id = None

    _clear_vector_store()

    logger.info("Backend reset complete.")


def _clear_vector_store() -> None:
    """
    Clear the Chroma collection without deleting filesystem persistence.

    This is the correct runtime reset method because it avoids Windows file-lock
    errors (WinError 32) caused by attempting to remove DB files while they are open.
    """
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)

    try:
        db = _get_vector_store()
        db._client.delete_collection(CHROMA_COLLECTION_NAME)
        logger.info("Vector store cleared: deleted collection '%s'", CHROMA_COLLECTION_NAME)
    except Exception:
        # Collection may not exist yet (first run).
        logger.info("Vector store clear: collection '%s' did not exist", CHROMA_COLLECTION_NAME)

    # Ensure empty collection exists
    _get_vector_store()


def _get_vector_store() -> Chroma:
    """
    Return a persistent Chroma vector store instance.

    All indexed documents share a single Chroma collection. Filtering is handled
    using metadata keys stored per chunk:
        - doc_id: internal unique document identifier
        - filename: original PDF filename
        - page: PDF page index (0-based from PyPDFLoader)
    """
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)

    return Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings,
        collection_name=CHROMA_COLLECTION_NAME,
    )


def list_documents() -> list[dict]:
    """
    Return metadata for all currently loaded documents.

    Notes:
        - This is an in-memory registry.
        - It does not read from Chroma persistence.
        - If the server restarts, this registry resets even if Chroma data exists.
    """
    return list(loaded_documents.values())


def process_document(document_path: str) -> dict:
    """
    Load and index a PDF document into the shared Chroma vector store.

    Steps:
    - Load pages from PDF
    - Split pages into overlapping text chunks
    - Attach metadata (doc_id, filename) to each chunk
    - Store embeddings in Chroma

    Args:
        document_path: filesystem path to a PDF file.

    Returns:
        dict: document metadata stored in loaded_documents.
              Example:
              {
                  "docId": "...",
                  "filename": "...",
                  "path": "..."
              }

    Raises:
        FileNotFoundError: if document_path does not exist.
        ValueError: if PDF contains no readable content.
    """
    global active_doc_id

    if not os.path.isfile(document_path):
        raise FileNotFoundError(f"Document not found: {document_path}")

    filename = os.path.basename(document_path)
    doc_id = str(uuid.uuid4())

    logger.info("Indexing PDF '%s' (doc_id=%s)", filename, doc_id)

    loader = PyPDFLoader(document_path)
    documents = loader.load()

    if not documents:
        raise ValueError("No readable content found in the PDF.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)

    if not chunks:
        raise ValueError("Document could not be split into chunks.")

    # Add metadata used later for filtering and citations.
    for chunk in chunks:
        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["filename"] = filename

    db = _get_vector_store()
    db.add_documents(chunks)
    db.persist()

    loaded_documents[doc_id] = {
        "docId": doc_id,
        "filename": filename,
        "path": document_path,
    }

    # New document becomes the active document by default.
    active_doc_id = doc_id

    logger.info(
        "PDF indexed successfully: filename=%s, chunks=%d, doc_id=%s",
        filename,
        len(chunks),
        doc_id,
    )

    return loaded_documents[doc_id]


def _build_chain(scope: str, doc_id: Optional[str]) -> ConversationalRetrievalChain:
    """
    Construct a ConversationalRetrievalChain for a given query scope.

    Business logic:
    - If scope == "active", retriever is filtered to only the specified doc_id.
    - If scope == "all", retriever searches across the entire vector store.

    Args:
        scope: Either "active" or "all".
        doc_id: Required if scope == "active". Ignored if scope == "all".

    Returns:
        A configured ConversationalRetrievalChain instance.
    """
    db = _get_vector_store()

    search_kwargs = {
        "k": RETRIEVER_K,
        "lambda_mult": MMR_LAMBDA_MULT,
    }

    if scope == "active":
        if not doc_id:
            raise ValueError("Missing docId for active scope.")
        search_kwargs["filter"] = {"doc_id": doc_id}

    retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs=search_kwargs,
    )

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": QA_PROMPT},
    )


def process_prompt(prompt: str, scope: str = "active", doc_id: Optional[str] = None) -> dict:
    """
    Answer a user question using conversational RAG.

    This function:
    - validates prompt and scope
    - selects doc_id if scope is active
    - performs retrieval + generation using LangChain conversational RAG
    - extracts citations from retrieved documents
    - updates chat_history memory

    Args:
        prompt: The user query.
        scope: "active" or "all".
        doc_id: Document ID used for filtering if scope == "active".

    Returns:
        dict:
            {
                "answer": "<final response text>",
                "sources": [
                    {"docId": "...", "filename": "...", "page": 1},
                    ...
                ]
            }

    Raises:
        ValueError: for invalid prompt/scope.
        RuntimeError: if no documents are indexed or no active doc is selected.
    """
    global chat_history, active_doc_id

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")

    if not loaded_documents:
        raise RuntimeError("No documents loaded. Upload a PDF first.")

    if scope not in ("active", "all"):
        raise ValueError("Scope must be 'active' or 'all'.")

    if scope == "active":
        doc_id = doc_id or active_doc_id
        if not doc_id:
            raise RuntimeError("No active document selected.")

    logger.info("Processing prompt (scope=%s, doc_id=%s): %s", scope, doc_id, prompt)

    chain = _build_chain(scope=scope, doc_id=doc_id)

    result = chain.invoke({
        "question": prompt,
        "chat_history": chat_history,
    })

    answer = (result.get("answer") or "").strip()
    if not answer:
        answer = "I could not find a grounded answer in the uploaded PDF(s)."

    # Extract sources (citations) from retrieved chunks
    source_docs = result.get("source_documents") or []

    sources = []
    for d in source_docs:
        meta = d.metadata or {}
        sources.append({
            "docId": meta.get("doc_id"),
            "filename": meta.get("filename"),
            "page": (meta.get("page", 0) or 0) + 1,  # convert to 1-indexed for UI
        })

    # Deduplicate sources while preserving order (prevents repeated citations)
    seen = set()
    unique_sources = []
    for s in sources:
        key = (s.get("docId"), s.get("page"))
        if key not in seen:
            seen.add(key)
            unique_sources.append(s)

    # Update conversational memory
    chat_history.append((prompt, answer))
    chat_history[:] = chat_history[-MAX_HISTORY_TURNS:]

    return {
        "answer": answer,
        "sources": unique_sources[:RETRIEVER_K],
    }