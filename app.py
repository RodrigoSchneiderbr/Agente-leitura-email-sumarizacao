import streamlit as st
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import os
import re
import json
from dotenv import load_dotenv

# Importações do LangGraph e LangChain
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Carrega as credenciais
load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")

# Define o endereço do Ollama automaticamente (Docker ou Local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

CATEGORIAS = ["Trabalho", "Pessoal", "Finanças/Boletos", "Promoções", "Newsletters", "Outros"]

def limpar_html(texto_html):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(texto_html))

# =====================================================================
#                      CRIANDO O AGENTE COM LANGGRAPH
# =====================================================================

class EmailState(TypedDict):
    remetente: str
    assunto: str
    corpo: str
    categoria: str
    resumo: str

# Inicializamos o LLM apontando para a URL dinâmica
llm = ChatOllama(
    model="llama3", 
    format="json", 
    temperature=0,
    base_url=OLLAMA_BASE_URL
)

def no_categorizador(state: EmailState):
    prompt = f"""
    Analise o e-mail abaixo e classifique-o em UMA destas opções: {', '.join(CATEGORIAS)}.
    
    De: {state['remetente']}
    Assunto: {state['assunto']}
    Corpo: {state['corpo'][:1000]}
    
    Responda APENAS em JSON no formato: {{"categoria": "NomeDaCategoria"}}
    """
    resposta = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        dados = json.loads(resposta.content)
        categoria = dados.get("categoria", "Outros")
        if categoria not in CATEGORIAS:
            categoria = "Outros"
    except:
        categoria = "Outros"
        
    return {"categoria": categoria}

def no_resumo_financas(state: EmailState):
    prompt = f"""
    Você é um especialista financeiro. Resuma o e-mail em até 2 linhas.
    SE houver valores financeiros (R$) ou datas de vencimento, DESTAQUE-OS no início do resumo.
    
    Assunto: {state['assunto']}
    Corpo: {state['corpo'][:1500]}
    
    Responda em JSON: {{"resumo": "Seu resumo aqui"}}
    """
    resposta = llm.invoke([HumanMessage(content=prompt)])
    try:
        resumo = json.loads(resposta.content).get("resumo", "Sem resumo.")
    except:
        resumo = "Erro ao resumir."
    return {"resumo": resumo}

def no_resumo_trabalho(state: EmailState):
    prompt = f"""
    Você é um assistente executivo. Resuma o e-mail de trabalho em até 2 linhas.
    SE houver tarefas para fazer ou prazos (ações), liste-os no resumo.
    
    Assunto: {state['assunto']}
    Corpo: {state['corpo'][:1500]}
    
    Responda em JSON: {{"resumo": "Seu resumo aqui"}}
    """
    resposta = llm.invoke([HumanMessage(content=prompt)])
    try:
        resumo = json.loads(resposta.content).get("resumo", "Sem resumo.")
    except:
        resumo = "Erro ao resumir."
    return {"resumo": resumo}

def no_resumo_geral(state: EmailState):
    prompt = f"""
    Resuma o e-mail abaixo em até 2 linhas.
    
    Assunto: {state['assunto']}
    Corpo: {state['corpo'][:1500]}
    
    Responda em JSON: {{"resumo": "Seu resumo aqui"}}
    """
    resposta = llm.invoke([HumanMessage(content=prompt)])
    try:
        resumo = json.loads(resposta.content).get("resumo", "Sem resumo.")
    except:
        resumo = "Erro ao resumir."
    return {"resumo": resumo}

def decidir_proximo_passo(state: EmailState):
    cat = state["categoria"]
    if cat == "Finanças/Boletos":
        return "resumir_financas"
    elif cat == "Trabalho":
        return "resumir_trabalho"
    else:
        return "resumir_geral"

# MONTANDO O GRAFO
workflow = StateGraph(EmailState)
workflow.add_node("categorizador", no_categorizador)
workflow.add_node("resumir_financas", no_resumo_financas)
workflow.add_node("resumir_trabalho", no_resumo_trabalho)
workflow.add_node("resumir_geral", no_resumo_geral)

workflow.set_entry_point("categorizador")
workflow.add_conditional_edges("categorizador", decidir_proximo_passo)
workflow.add_edge("resumir_financas", END)
workflow.add_edge("resumir_trabalho", END)
workflow.add_edge("resumir_geral", END)

agente_langgraph = workflow.compile()
# =====================================================================

def buscar_e_resumir_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            st.error("Não foi possível abrir a caixa de entrada (INBOX).")
            return None

        limite_tempo = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)
        ontem = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")

        status, mensagens = mail.search(None, f'(UNSEEN SINCE "{ontem}")')
        ids_emails = mensagens[0].split()

        if not ids_emails:
            mail.logout()
            return []

        emails_ultimas_6_horas = []
        for e_id in ids_emails:
            _, msg_data = mail.fetch(e_id, '(BODY[HEADER.FIELDS (DATE)])')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg_data_header = email.message_from_bytes(response_part[1])
                    data_email_str = msg_data_header.get("Date")
                    if data_email_str:
                        data_email = parsedate_to_datetime(data_email_str)
                        if data_email >= limite_tempo:
                            emails_ultimas_6_horas.append(e_id)

        resultados = []
        barra_progresso = st.progress(0)
        total_emails = len(emails_ultimas_6_horas)

        for indice, e_id in enumerate(emails_ultimas_6_horas):
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    assunto_encoded, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(assunto_encoded, bytes):
                        assunto = assunto_encoded.decode(encoding if encoding else "utf-8")
                    else:
                        assunto = assunto_encoded
                        
                    remetente = msg.get("From")
                    corpo = ""

                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                corpo = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        corpo = msg.get_payload(decode=True).decode(errors="ignore")

                    corpo_limpo = limpar_html(corpo)
                    
                    estado_inicial = {
                        "remetente": remetente,
                        "assunto": assunto,
                        "corpo": corpo_limpo,
                        "categoria": "",
                        "resumo": ""
                    }
                    
                    estado_final = agente_langgraph.invoke(estado_inicial)

                    resultados.append({
                        "remetente": remetente,
                        "assunto": assunto,
                        "categoria": estado_final["categoria"],
                        "resumo": estado_final["resumo"]
                    })
            
            barra_progresso.progress((indice + 1) / total_emails)

        mail.logout()
        return resultados

    except Exception as e:
        st.error(f"Erro ao acessar e-mails: {e}")
        return None

# ================= INTERFACE DO STREAMLIT =================
st.set_page_config(page_title="Agente de E-mail IA", page_icon="📧", layout="wide")

st.title("📬 Painel do Agente Avançado para Sumarização de E-mails (LangGraph)")
st.write("Verifique e leia os resumos dos e-mails das **últimas 6 horas**.")

if st.button("🔄 Ler e Resumir Caixa de Entrada"):
    with st.spinner('O Agente LangGraph está trabalhando...'):
        lista_emails = buscar_e_resumir_emails()
    
    if lista_emails is not None:
        qtd_novos = len(lista_emails)
        st.metric(label="E-mails Novos (Últimas 6h)", value=qtd_novos)
        
        if qtd_novos == 0:
            st.success("Tudo limpo nas últimas 6 horas! 🎉")
        else:
            st.success(f"A IA processou {qtd_novos} e-mails!")
            st.divider()
            
            emails_por_categoria = {}
            for email_processado in lista_emails:
                cat = email_processado["categoria"]
                if cat not in emails_por_categoria:
                    emails_por_categoria[cat] = []
                emails_por_categoria[cat].append(email_processado)

            abas = st.tabs(list(emails_por_categoria.keys()))
            
            for aba, nome_categoria in zip(abas, emails_por_categoria.keys()):
                with aba:
                    for em in emails_por_categoria[nome_categoria]:
                        with st.expander(f"✉️ {em['assunto']}"):
                            st.markdown(f"**De:** `{em['remetente']}`")
                            st.markdown(f"**Resumo da IA:** \n> {em['resumo']}")