"""
agent/rag/loader.py

Lê o documento escolhido para o Challenge (PDF ou CSV) e devolve uma lista
de Document do LangChain, prontos para serem divididos em chunks e
indexados no vetor store.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from langchain_core.documents import Document

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

# raiz do projeto = três pastas acima deste arquivo (agent/rag/ -> raiz)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


def _carregar_pdf(caminho: Path) -> list[Document]:
    if PdfReader is None:
        raise ImportError("Instale a dependência 'pypdf' para ler arquivos PDF.")

    leitor = PdfReader(str(caminho))
    documentos: list[Document] = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        documentos.append(
            Document(
                page_content=texto if texto else f"[página {numero} sem texto extraível]",
                metadata={"fonte": caminho.name, "pagina": numero, "tem_texto": bool(texto)},
            )
        )
    return documentos


def _carregar_csv(caminho: Path) -> list[Document]:
    df = pd.read_csv(caminho)
    documentos: list[Document] = []
    for indice, linha in df.iterrows():
        texto = "\n".join(f"{coluna}: {valor}" for coluna, valor in linha.items())
        documentos.append(
            Document(
                page_content=texto,
                metadata={"fonte": caminho.name, "linha": int(indice)},
            )
        )
    return documentos


def carregar_documento(nome_arquivo: str | None = None) -> list[Document]:
    """
    Carrega documentos da pasta data/.

    Se nome_arquivo for informado, carrega apenas esse arquivo.
    Caso contrário, carrega todos os .pdf e .csv encontrados na pasta.
    """
    if nome_arquivo:
        caminho = DATA_DIR / nome_arquivo
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
        return _carregar_por_sufixo(caminho)

    candidatos = sorted(DATA_DIR.glob("*.pdf")) + sorted(DATA_DIR.glob("*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum arquivo .pdf ou .csv encontrado em {DATA_DIR}."
        )
    documentos: list[Document] = []
    for caminho in candidatos:
        documentos.extend(_carregar_por_sufixo(caminho))
    return documentos


def _carregar_por_sufixo(caminho: Path) -> list[Document]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        return _carregar_pdf(caminho)
    elif sufixo == ".csv":
        return _carregar_csv(caminho)
    raise ValueError(f"Formato não suportado: {caminho.suffix}")
