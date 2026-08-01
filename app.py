"""
app.py

Ponto de entrada do Streamlit. Roteia o colaborador entre os dois modos:

1) Construir a skill de aprendizagem (primeira vez que ele usa o agente)
2) Tirar dúvidas / aprender com o agente (RAG + skill sempre injetada)

Rode com:  streamlit run app.py
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import re
import streamlit as st

from agent.skill_builder import carregar_skill, construir_skill, skill_existe
from agent.orchestrator import responder

st.set_page_config(page_title="Agente Tutor", page_icon="🎓")
st.title("🎓 Agente Tutor do Colaborador")

colaborador_id = st.sidebar.text_input("Seu usuário (ex: nome.sobrenome)")

if not colaborador_id:
    st.info("Informe seu usuário na barra lateral para começar.")
    st.stop()

# Modo 1: primeira vez do colaborador -> construir a skill de aprendizagem
if not skill_existe(colaborador_id):
    resultado = construir_skill(colaborador_id)
    if resultado is None:
        st.stop()
    else:
        st.rerun()

# Modo 2: já tem skill salva -> mostra o perfil e libera o chat de dúvidas
with st.sidebar.expander("Seu perfil de aprendizagem"):
    st.markdown(carregar_skill(colaborador_id))

if st.sidebar.button("Refazer meu perfil de aprendizagem"):
    from agent.skill_builder import _skill_path  # uso interno, só para reset manual

    _skill_path(colaborador_id).unlink(missing_ok=True)
    st.rerun()

MODOS_LABELS = {
    "duvida": "🎯 Tirar dúvida",
    "aprender": "🌱 Aprender do zero",
    "aprofundar": "🔎 Aprofundar",
}

st.sidebar.markdown("---")
modo = st.sidebar.radio(
    "Como quer abordar a próxima pergunta?",
    options=list(MODOS_LABELS.keys()),
    format_func=lambda chave: MODOS_LABELS.get(chave, chave),
    key="modo_interacao",
    index=0,
)

st.markdown("<span style='color: gray; font-size: 1.1rem'>Tire dúvidas, aprenda algo novo ou aprofunde seus conhecimentos</span>", unsafe_allow_html=True)

if "historico" not in st.session_state:
    st.session_state.historico = []

for entrada in st.session_state.historico:
    with st.chat_message(entrada["autor"]):
        if entrada["autor"] == "user":
            st.caption(MODOS_LABELS.get(entrada["modo"], entrada["modo"]))
        st.write(entrada["mensagem"])

pergunta = st.chat_input("Digite sua pergunta...")

if pergunta:
    st.session_state.historico.append({"autor": "user", "mensagem": pergunta, "modo": modo})
    with st.chat_message("user"):
        st.caption(MODOS_LABELS[modo])
        st.write(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando os documentos..."):
            resultado = responder(colaborador_id, pergunta, modo=modo)
        resposta = re.sub(r'^#{1,6}\s+', '', resultado["resposta"], flags=re.MULTILINE)
        st.write(resposta)
        if resultado["fontes"]:
            with st.expander("📄 Trechos consultados"):
                for trecho in resultado["trechos"]:
                    m = trecho.metadata
                    fonte = m.get("fonte", "documento")
                    pagina = m.get("pagina")
                    label = f"{fonte}, p. {pagina}" if pagina else fonte
                    st.caption(label)
                    st.markdown(f"> {trecho.page_content}")
                    st.divider()
    st.session_state.historico.append({"autor": "assistant", "mensagem": resultado["resposta"], "modo": modo})
 