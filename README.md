[![Python 3.10](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/downloads/)
[![Built with Ollama](https://img.shields.io/badge/Built%20with-Ollama-orange)](https://ollama.ai)
[![Powered by LangChain](https://img.shields.io/badge/Powered%20by-LangChain-green)](https://langchain.com)

# flask_rag_chat_split_ui

A Flask-based PDF chat application that lets a user upload a PDF, index it with a local Ollama-powered RAG pipeline, preview the PDF in the browser, and ask grounded questions about the uploaded document.

## Features

- PDF upload and preview
- One-document-at-a-time indexing
- Chroma vector store persistence
- Ollama-based embeddings and generation
- Split-screen chat interface
- Dark mode toggle
- Pytest unit coverage for RAG pipeline behavior

![alt text](https://github.com/dawmro/flask_rag_chat_split_ui/blob/main/main_page.png?raw=true)

## Requirements

- Python 3.10
- Ollama running locally
- A chat model, for example `llama3.1:8b-instruct-q8_0`
- An embedding model, for example `mxbai-embed-large`

## Environment variables

- `LLM_MODEL`
- `EMBEDDING_MODEL`
- `OLLAMA_BASE_URL`
- `RAG_CHUNK_SIZE`
- `RAG_CHUNK_OVERLAP`
- `RAG_RETRIEVER_K`


## 🛠 Quick Start
1. Clone repo
``` sh
git clone https://github.com/dawmro/flask_rag_chat_split_ui.git
```
2. Navigate into directory
``` sh
cd flask_rag_chat_split_ui
```
3. Create new virtual env:
``` sh
py -3.10 -m venv env
```
4. Activate your virtual env:
``` sh
env/Scripts/activate
```
5. Install requirements
```sh
pip install -r requirements.txt
```
6. Run Flask server
```sh
python server.py
```
7. Go into your browser and upload your PDF file
``` sh
http://127.0.0.1:8000
```


## Test

```sh
pytest -v
```