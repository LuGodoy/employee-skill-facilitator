"""
agent/orchestrator.py

Monta o agente tutor: injeta o skill.md do colaborador (sempre ativo,
sem passar por embeddings) + os trechos recuperados via RAG (ChromaDB)
no prompt, e chama o LLM para gerar a resposta final.
"""

from __future__ import annotations

import os

from langchain_core.prompts import ChatPromptTemplate

from agent.rag.loader import carregar_documento
from agent.rag.vectorstore import (
    carregar_vectorstore,
    construir_vectorstore,
    vectorstore_existe,
)
from agent.skill_builder import carregar_skill, skill_existe

INSTRUCOES_MODO = {
    "duvida": "Resposta curta e direta, apenas o essencial para responder a pergunta.",
    "aprender": "Resposta completa com contexto suficiente para entender o assunto do zero.",
    "aprofundar": "Resposta detalhada cobrindo trade-offs, limitações e implicações práticas.",
}

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("human",
         "Você é um agente tutor que ajuda um colaborador a aprender sobre a empresa "
         "com base nos documentos internos.\n\n"
         "Perfil de aprendizagem do colaborador (siga sempre este estilo):\n{skill}\n\n"
         "Instrução de modo:\n{instrucao_modo}\n\n"
         "Trechos dos documentos da empresa:\n{contexto}\n\n"
         "Pergunta do colaborador: {pergunta}\n\n"
         "Responda com base apenas nos trechos acima. Se a informação não estiver neles, "
         "diga que não encontrou — não invente."),
    ]
)

SKILL_PADRAO = (
    "Nenhum perfil de aprendizagem definido ainda — responda de forma "
    "clara e didática, sem assumir nível técnico prévio."
)


def obter_ou_criar_vectorstore():
    """Reaproveita o índice já existente, ou processa o documento pela primeira vez."""
    if vectorstore_existe():
        return carregar_vectorstore()
    documentos = carregar_documento()
    return construir_vectorstore(documentos)


def _formatar_contexto(trechos) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in trechos)

def _extrair_fontes(trechos) -> list[str]:
    vistas: set[str] = set()
    fontes: list[str] = []
    for doc in trechos:
        m = doc.metadata
        if not m.get("tem_texto", True):
            continue
        if "pagina" in m:
            ref = f"{m['fonte']}, p. {m['pagina']}"
        elif "linha" in m:
            ref = f"{m['fonte']}, linha {m['linha']}"
        else:
            ref = m.get("fonte", "documento")
        if ref not in vistas:
            vistas.add(ref)
            fontes.append(ref)
    return fontes

def get_llm():
    """
    Retorna o LLM usado para gerar as respostas.

    Configurado por padrão para a API de IA generativa da Oracle (OCI),
    lendo as credenciais de variáveis de ambiente (ver .env.example).

    Para trocar de provedor, troque só esta função — o resto do arquivo
    não muda. Alternativas com a mesma interface do LangChain:
        from langchain_openai import ChatOpenAI
        from langchain_cohere import ChatCohere
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_anthropic import ChatAnthropic
    """
    from langchain_cohere import ChatCohere

    return ChatCohere(
        model=os.environ.get("COHERE_MODEL", "command-r"),
        cohere_api_key=os.environ["COHERE_API_KEY"],
        temperature=0.3,
        max_tokens=800,
    )


def responder(colaborador_id: str, pergunta: str, k: int = 4, modo: str = "duvida") -> dict:
    """Gera a resposta do agente tutor para uma pergunta do colaborador."""
    skill = carregar_skill(colaborador_id) if skill_existe(colaborador_id) else SKILL_PADRAO
    instrucao_modo = INSTRUCOES_MODO.get(modo, INSTRUCOES_MODO["duvida"])

    vectorstore = obter_ou_criar_vectorstore()
    trechos = vectorstore.similarity_search(pergunta, k=k)
    contexto = _formatar_contexto(trechos)
    fontes = _extrair_fontes(trechos)

    cadeia = PROMPT | get_llm()
    resultado = cadeia.invoke({"skill": skill, "instrucao_modo": instrucao_modo, "contexto": contexto, "pergunta": pergunta})
    resposta = resultado.content if hasattr(resultado, "content") else str(resultado)
    return {"resposta": resposta, "fontes": fontes, "trechos": trechos}
