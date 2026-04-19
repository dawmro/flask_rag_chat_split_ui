import rag_pipeline
import pytest


@pytest.fixture(autouse=True)
def reset_rag_state():
    """
    Ensure every test starts with a clean pipeline state.
    """
    rag_pipeline.reset_state()
    yield
    rag_pipeline.reset_state()


def test_process_prompt_without_document_raises():
    """
    process_prompt should reject queries before any document is loaded.
    """
    with pytest.raises(RuntimeError) as exc_info:
        rag_pipeline.process_prompt("Hello")

    assert "No document loaded" in str(exc_info.value)


def test_process_prompt_with_blank_input_raises():
    """
    process_prompt should reject empty or whitespace-only prompts.
    """
    class DummyChain:
        def invoke(self, payload):
            return {"result": "should not be called"}

    rag_pipeline.conversation_retrieval_chain = DummyChain()

    with pytest.raises(ValueError) as exc_info:
        rag_pipeline.process_prompt(" ")

    assert "Prompt cannot be empty" in str(exc_info.value)


def test_process_prompt_returns_answer_and_updates_history():
    """
    process_prompt should:
    - call the retrieval chain with the expected question payload
    - return the answer text
    - append the exchange to chat_history
    """
    class DummyChain:
        def invoke(self, payload):
            assert payload == {"question": "test question"}
            return {"result": "dummy answer"}

    rag_pipeline.conversation_retrieval_chain = DummyChain()
    rag_pipeline.chat_history = []

    answer = rag_pipeline.process_prompt("test question")

    assert answer == "dummy answer"
    assert rag_pipeline.chat_history == [("test question", "dummy answer")]


def test_process_prompt_returns_fallback_when_result_is_empty():
    """
    If the chain returns an empty result, process_prompt should return
    the user-facing fallback answer.
    """
    class DummyChain:
        def invoke(self, payload):
            return {"result": " "}

    rag_pipeline.conversation_retrieval_chain = DummyChain()

    answer = rag_pipeline.process_prompt("question")

    assert answer == "I could not find a grounded answer in the uploaded PDF."
    assert rag_pipeline.chat_history == [
        ("question", "I could not find a grounded answer in the uploaded PDF.")
    ]


def test_process_document_raises_for_missing_file():
    """
    process_document should fail fast if the PDF path does not exist.
    """
    with pytest.raises(FileNotFoundError) as exc_info:
        rag_pipeline.process_document("missing.pdf")

    assert "Document not found" in str(exc_info.value)


def test_process_document_raises_for_empty_loaded_document(monkeypatch):
    """
    process_document should reject PDFs that load but contain no readable content.
    """
    monkeypatch.setattr(rag_pipeline.os.path, "isfile", lambda _: True)

    class DummyLoader:
        def __init__(self, path):
            self.path = path

        def load(self):
            return []

    monkeypatch.setattr(rag_pipeline, "PyPDFLoader", DummyLoader)

    with pytest.raises(ValueError) as exc_info:
        rag_pipeline.process_document("fake.pdf")

    assert "No readable content found" in str(exc_info.value)


def test_process_document_creates_chain_and_resets_history(monkeypatch):
    """
    process_document should:
    - validate the file path
    - load the PDF
    - split documents into chunks
    - create a Chroma vector store
    - build a RetrievalQA chain
    - reset chat history
    - store current_document_path
    """
    monkeypatch.setattr(rag_pipeline.os.path, "isfile", lambda _: True)

    class DummyLoader:
        def __init__(self, path):
            self.path = path

        def load(self):
            assert self.path == "fake.pdf"
            return ["fake_document"]

    class DummySplitter:
        def __init__(self, chunk_size, chunk_overlap):
            assert chunk_size == rag_pipeline.CHUNK_SIZE
            assert chunk_overlap == rag_pipeline.CHUNK_OVERLAP

        def split_documents(self, documents):
            assert documents == ["fake_document"]
            return ["chunk1", "chunk2"]

    class DummyDB:
        def persist(self):
            return None

        def as_retriever(self, search_type=None, search_kwargs=None):
            assert search_type == "mmr"
            assert search_kwargs == {
                "k": rag_pipeline.RETRIEVER_K,
                "lambda_mult": 0.25,
            }
            return "dummy_retriever"

    def dummy_from_documents(documents, embedding=None, persist_directory=None):
        assert documents == ["chunk1", "chunk2"]
        assert embedding is rag_pipeline.embeddings
        assert persist_directory == rag_pipeline.CHROMA_DB_DIR
        return DummyDB()

    def dummy_from_chain_type(llm=None, chain_type=None, retriever=None, **kwargs):
        assert llm is rag_pipeline.llm
        assert chain_type == "stuff"
        assert retriever == "dummy_retriever"
        assert kwargs["return_source_documents"] is False
        assert kwargs["input_key"] == "question"
        return "dummy_chain"

    clear_called = {"value": False}

    def dummy_clear_vector_store():
        clear_called["value"] = True

    rag_pipeline.chat_history = [("old question", "old answer")]

    monkeypatch.setattr(rag_pipeline, "PyPDFLoader", DummyLoader)
    monkeypatch.setattr(rag_pipeline, "RecursiveCharacterTextSplitter", DummySplitter)
    monkeypatch.setattr(rag_pipeline.Chroma, "from_documents", dummy_from_documents)
    monkeypatch.setattr(rag_pipeline.RetrievalQA, "from_chain_type", dummy_from_chain_type)
    monkeypatch.setattr(rag_pipeline, "_clear_vector_store", dummy_clear_vector_store)

    rag_pipeline.process_document("fake.pdf")

    assert clear_called["value"] is True
    assert rag_pipeline.conversation_retrieval_chain == "dummy_chain"
    assert rag_pipeline.current_document_path == "fake.pdf"
    assert rag_pipeline.chat_history == []