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


# ---------------------------------------------------------------------
# process_prompt validation tests
# ---------------------------------------------------------------------

def test_process_prompt_without_document_raises():
    """
    Should reject queries before any document is loaded.
    """
    with pytest.raises(RuntimeError) as exc_info:
        rag_pipeline.process_prompt("Hello")

    assert "No documents loaded" in str(exc_info.value)


def test_process_prompt_with_blank_input_raises():
    """
    Should reject empty or whitespace-only prompts.
    """
    with pytest.raises(ValueError) as exc_info:
        rag_pipeline.process_prompt("   ")

    assert "Prompt cannot be empty" in str(exc_info.value)


# ---------------------------------------------------------------------
# process_prompt happy path
# ---------------------------------------------------------------------

def test_process_prompt_returns_answer_and_updates_history(monkeypatch):
    """
    Should:
    - call chain.invoke with correct payload
    - return structured dict response
    - update chat_history
    """

    class DummyChain:
        def invoke(self, payload):
            assert payload["question"] == "test question"
            assert "chat_history" in payload

            return {
                "answer": "dummy answer",
                "source_documents": []
            }

    monkeypatch.setattr(
        rag_pipeline,
        "_build_chain",
        lambda scope, doc_id: DummyChain()
    )

    rag_pipeline.loaded_documents["x"] = {"docId": "x"}
    rag_pipeline.active_doc_id = "x"
    rag_pipeline.chat_history = []

    result = rag_pipeline.process_prompt("test question")

    assert result["answer"] == "dummy answer"
    assert result["sources"] == []
    assert rag_pipeline.chat_history == [
        ("test question", "dummy answer")
    ]


def test_process_prompt_fallback_when_empty_answer(monkeypatch):
    """
    Should return fallback message if LLM returns empty answer.
    """

    class DummyChain:
        def invoke(self, payload):
            return {
                "answer": "   ",
                "source_documents": []
            }

    monkeypatch.setattr(
        rag_pipeline,
        "_build_chain",
        lambda scope, doc_id: DummyChain()
    )

    rag_pipeline.loaded_documents["x"] = {"docId": "x"}
    rag_pipeline.active_doc_id = "x"
    rag_pipeline.chat_history = []

    result = rag_pipeline.process_prompt("question")

    assert result["answer"] == "I could not find a grounded answer in the uploaded PDF(s)."
    assert result["sources"] == []


# ---------------------------------------------------------------------
# process_document tests
# ---------------------------------------------------------------------

def test_process_document_raises_for_missing_file():
    """
    Should fail fast if file does not exist.
    """
    with pytest.raises(FileNotFoundError) as exc_info:
        rag_pipeline.process_document("missing.pdf")

    assert "Document not found" in str(exc_info.value)


def test_process_document_raises_for_empty_pdf(monkeypatch):
    """
    Should reject PDFs that load but contain no pages.
    """

    monkeypatch.setattr(rag_pipeline.os.path, "isfile", lambda _: True)

    class DummyLoader:
        def __init__(self, path):
            pass

        def load(self):
            return []

    monkeypatch.setattr(rag_pipeline, "PyPDFLoader", DummyLoader)

    with pytest.raises(ValueError) as exc_info:
        rag_pipeline.process_document("fake.pdf")

    assert "No readable content found" in str(exc_info.value)


def test_process_document_success(monkeypatch):
    """
    Should:
    - load PDF
    - split into chunks
    - store metadata
    - set active_doc_id
    - update loaded_documents
    """

    monkeypatch.setattr(rag_pipeline.os.path, "isfile", lambda _: True)

    class DummyLoader:
        def __init__(self, *args, **kwargs):
            self.path = args[0] if args else None

        def load(self):
            return ["page1"]

    class DummySplitter:
        def __init__(self, chunk_size, chunk_overlap):
            assert chunk_size == rag_pipeline.CHUNK_SIZE
            assert chunk_overlap == rag_pipeline.CHUNK_OVERLAP

        def split_documents(self, docs):
            assert docs == ["page1"]

            # fake chunk objects with metadata
            class Chunk:
                def __init__(self):
                    self.metadata = {}

            c1 = Chunk()
            c2 = Chunk()
            return [c1, c2]

    class DummyDB:
        def add_documents(self, docs):
            assert len(docs) == 2

        def persist(self):
            pass

    def fake_get_vector_store():
        return DummyDB()

    monkeypatch.setattr(rag_pipeline, "PyPDFLoader", lambda path: DummyLoader(path))
    monkeypatch.setattr(rag_pipeline, "RecursiveCharacterTextSplitter", DummySplitter)
    monkeypatch.setattr(rag_pipeline, "_get_vector_store", fake_get_vector_store)

    result = rag_pipeline.process_document("fake.pdf")

    assert "docId" in result
    assert rag_pipeline.active_doc_id == result["docId"]
    assert len(rag_pipeline.loaded_documents) == 1


# ---------------------------------------------------------------------
# reset_state test
# ---------------------------------------------------------------------

def test_reset_state_clears_everything(monkeypatch):
    """
    reset_state should clear:
    - chat history
    - loaded documents
    - active doc
    """

    rag_pipeline.chat_history = [("a", "b")]
    rag_pipeline.loaded_documents = {"x": {}}
    rag_pipeline.active_doc_id = "x"

    monkeypatch.setattr(rag_pipeline, "_clear_vector_store", lambda: None)

    rag_pipeline.reset_state()

    assert rag_pipeline.chat_history == []
    assert rag_pipeline.loaded_documents == {}
    assert rag_pipeline.active_doc_id is None