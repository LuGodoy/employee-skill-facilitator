"""
agent/rag/vectorstore.py

Divide os documentos carregados em chunks, gera embeddings e cria/consulta
o vetor store (ChromaDB) usado na etapa de RAG.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PERSIST_DIR = BASE_DIR / "chroma_data"

# Embedding local, sem depender de chave de API — troque por
# OCIGenAIEmbeddings, OpenAIEmbeddings ou CohereEmbeddings se preferir
# usar o mesmo provedor do LLM.
_MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " "],
    )


def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=_MODELO_EMBEDDING)


def construir_vectorstore(documentos: list[Document]) -> Chroma:
    """Divide os documentos em chunks e (re)cria o índice no ChromaDB."""
    chunks = _splitter().split_documents(documentos)
    return Chroma.from_documents(
        documents=chunks,
        embedding=_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def carregar_vectorstore() -> Chroma:
    """Abre um índice já existente em disco, sem reprocessar os documentos."""
    return Chroma(
        embedding_function=_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def vectorstore_existe() -> bool:
    return PERSIST_DIR.exists() and any(PERSIST_DIR.iterdir())
