"""
agent/skill_builder.py

Conduz a conversa inicial com o colaborador para construir o arquivo
skill_<colaborador_id>.md — o perfil de aprendizagem que fica SEMPRE ativo
(injeção direta no prompt, sem passar por RAG/embeddings) nas interações
futuras do agente tutor.

Armazenamento:
- Durante a conversa: st.session_state (temporário, dura enquanto a sessão
  do Streamlit estiver aberta).
- Rascunho de segurança: skills/.drafts/<colaborador_id>.json — protege
  contra perda de progresso se a página recarregar no meio da conversa.
- Resultado final, persistente: skills/<colaborador_id>.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import streamlit as st

# raiz do projeto = duas pastas acima deste arquivo (agent/ -> raiz)
BASE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = BASE_DIR / "skills"
DRAFTS_DIR = SKILLS_DIR / ".drafts"


@dataclass
class Pergunta:
    chave: str
    texto: str


# Perguntas que compõem o perfil de aprendizagem.
# Fique à vontade para adicionar/remover perguntas conforme o que fizer
# mais sentido para o seu Challenge.
PERGUNTAS: list[Pergunta] = [
    Pergunta(
        "estilo",
        "Quando você precisa aprender algo novo, o que funciona melhor: "
        "exemplos práticos, explicação direta e resumida, ou analogias "
        "com coisas que você já conhece?",
    ),
    Pergunta(
        "formato",
        "Você prefere respostas curtas e objetivas, ou explicações mais "
        "completas, com contexto?",
    ),
    Pergunta(
        "conhecimento_previo",
        "Quais áreas ou temas da empresa você já domina bem hoje?",
    ),
    Pergunta(
        "dificuldades",
        "Existe algum tipo de conteúdo que costuma ser mais difícil pra "
        "você entender (ex: textos longos, termos técnicos, planilhas)?",
    ),
    Pergunta(
        "objetivo",
        "O que você quer priorizar aprender nas próximas semanas?",
    ),
]


def _skill_path(colaborador_id: str) -> Path:
    return SKILLS_DIR / f"{colaborador_id}.md"


def _draft_path(colaborador_id: str) -> Path:
    return DRAFTS_DIR / f"{colaborador_id}.json"


def skill_existe(colaborador_id: str) -> bool:
    """Verifica se o colaborador já tem uma skill de aprendizagem salva."""
    return _skill_path(colaborador_id).exists()


def carregar_skill(colaborador_id: str) -> str:
    """Lê o conteúdo já persistido, para injeção direta no prompt do agente."""
    return _skill_path(colaborador_id).read_text(encoding="utf-8")


def _carregar_rascunho(colaborador_id: str) -> dict:
    caminho = _draft_path(colaborador_id)
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {}


def _salvar_rascunho(colaborador_id: str, respostas: dict) -> None:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    _draft_path(colaborador_id).write_text(
        json.dumps(respostas, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _gerar_markdown(colaborador_id: str, respostas: dict) -> str:
    return f"""# Perfil de aprendizagem — {colaborador_id}
_Gerado em {datetime.now():%Y-%m-%d %H:%M} • sempre injetado no prompt do agente_

## Como prefere aprender
{respostas.get("estilo", "").strip()}

## Formato de resposta preferido
{respostas.get("formato", "").strip()}

## Conhecimentos que já possui
{respostas.get("conhecimento_previo", "").strip()}

## Pontos de dificuldade
{respostas.get("dificuldades", "").strip()}

## Prioridade de aprendizado atual
{respostas.get("objetivo", "").strip()}
"""


def _finalizar(colaborador_id: str, respostas: dict) -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    conteudo = _gerar_markdown(colaborador_id, respostas)
    caminho = _skill_path(colaborador_id)
    caminho.write_text(conteudo, encoding="utf-8")

    # limpa o rascunho temporário, já não é mais necessário
    rascunho = _draft_path(colaborador_id)
    if rascunho.exists():
        rascunho.unlink()

    return caminho


def construir_skill(colaborador_id: str) -> Path | None:
    """
    Renderiza a conversa de construção da skill no Streamlit.

    Retorna o Path do skill.md quando a conversa termina e o arquivo é
    salvo, ou None enquanto a conversa ainda está em andamento (a função
    é chamada de novo a cada rerun do Streamlit).
    """
    estado_chave = f"skill_builder::{colaborador_id}"

    if estado_chave not in st.session_state:
        st.session_state[estado_chave] = {
            "passo": 0,
            # começa retomando um rascunho salvo, se existir
            "respostas": _carregar_rascunho(colaborador_id),
        }

    estado = st.session_state[estado_chave]
    passo = estado["passo"]
    respostas = estado["respostas"]

    st.subheader("Vamos entender como você aprende melhor")
    st.caption(
        "Isso leva menos de 2 minutos e fica salvo para sempre personalizar "
        "as respostas do agente daqui pra frente."
    )
    st.caption(
        "⚠️ As perguntas a seguir são apenas uma aproximação informal do seu "
        "estilo de aprendizagem — sem base científica rigorosa. Servem somente "
        "para personalizar o tom das respostas do agente."
    )

    # Reexibe o histórico da conversa até o passo atual
    for pergunta in PERGUNTAS[:passo]:
        with st.chat_message("assistant"):
            st.write(pergunta.texto)
        with st.chat_message("user"):
            st.write(respostas.get(pergunta.chave, ""))

    if passo < len(PERGUNTAS):
        pergunta_atual = PERGUNTAS[passo]
        with st.chat_message("assistant"):
            st.write(pergunta_atual.texto)

        resposta = st.chat_input("Sua resposta...")
        if resposta:
            respostas[pergunta_atual.chave] = resposta
            estado["passo"] += 1
            _salvar_rascunho(colaborador_id, respostas)
            st.rerun()
        return None

    # Todas as perguntas respondidas -> gera e persiste o skill.md
    caminho = _finalizar(colaborador_id, respostas)
    del st.session_state[estado_chave]

    st.success(
        f"Perfil de aprendizagem salvo em `{caminho}`. A partir de agora, "
        "o agente já vai usar isso em todas as suas respostas."
    )
    st.caption(
        "⚠️ Lembre-se: este perfil é uma aproximação informal, sem rigor científico. "
        "Você pode refazê-lo a qualquer momento pela barra lateral."
    )
    return caminho
