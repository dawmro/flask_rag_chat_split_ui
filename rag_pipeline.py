import logging
import os
import shutil
import uuid
from typing import Optional

from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")

LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b-instruct-q8_0")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
RETRIEVER_K = int(os.getenv("RAG_RETRIEVER_K", "6"))

logger.info("Initializing Ollama clients...")
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

    logger.info("Ollama clients initialized successfully")
except Exception:
    logger.exception("Failed to initialize Ollama clients")
    raise

conversation_retrieval_chain: Optional[RetrievalQA] = None
current_document_path: Optional[str] = None
chat_history = []


def reset_state() -> None:
    global conversation_retrieval_chain, current_document_path, chat_history
    conversation_retrieval_chain = None
    current_document_path = None
    chat_history = []


def _clear_vector_store() -> None:
    if os.path.isdir(CHROMA_DB_DIR):
        shutil.rmtree(CHROMA_DB_DIR)
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)


_clear_vector_store()


def process_document(document_path: str) -> None:
    global conversation_retrieval_chain, current_document_path, chat_history

    if not os.path.isfile(document_path):
        raise FileNotFoundError(f"Document not found: {document_path}")

    logger.info("Loading PDF document: %s", document_path)

    loader = PyPDFLoader(document_path)
    documents = loader.load()

    if not documents:
        raise ValueError("No readable content found in the PDF.")

    logger.info("Loaded %d document page(s)", len(documents))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    logger.info("Split document into %d chunk(s)", len(chunks))

    logger.info("Creating Chroma vector store...")
    persist_dir = os.path.join(CHROMA_DB_DIR, str(uuid.uuid4()))
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    db.persist()

    conversation_retrieval_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=db.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": RETRIEVER_K,
                "lambda_mult": 0.25,
            },
        ),
        return_source_documents=False,
        input_key="question",
    )

    current_document_path = document_path
    chat_history = []

    logger.info("RAG pipeline is ready for questions")


def process_prompt(prompt: str) -> str:
    global conversation_retrieval_chain, chat_history

    if conversation_retrieval_chain is None:
        raise RuntimeError("No document loaded. Upload and process a PDF first.")

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")

    logger.info("Processing user prompt: %s", prompt)

    result = conversation_retrieval_chain.invoke({
        "question": prompt,
    })

    answer = result.get("result", "").strip()

    if not answer:
        answer = "I could not find a grounded answer in the uploaded PDF."

    chat_history.append((prompt, answer))
    logger.info("Generated response successfully")

    return answer