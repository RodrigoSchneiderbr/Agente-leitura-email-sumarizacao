import streamlit as st
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.message import EmailMessage
import datetime
import os
import re
import json
from dotenv import load_dotenv

# Importações do LangGraph e LangChain
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from memoria_rag import salvar_email_no_rag, consultar_memoria

# =====================================================================
#                      CONFIGURAÇÕES INICIAIS
# =====================================================================
load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

CATEGORIAS = ["Trabalho", "Pessoal", "Finanças/Boletos", "Promoções", "Newsletters", "Outros"]

def limpar_html(texto_html):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(texto_html))

# =====================================================================
#                      AÇÕES ATIVAS DO AGENTE (IMAP)
# =====================================================================

def mover_email_para_pasta(mail, id_email, categoria):
    nome_pasta = f"IA_{categoria.replace('/', '_')}"
    try:
        mail.create(f'"{nome_pasta}"')
        status, _ = mail.copy(id_email, f'"{nome_pasta}"')
        if status == 'OK':
            mail.store(id_email, '+FLAGS', '\\Deleted')
            return True
    except Exception as e:
        print(f"Erro ao mover o e-mail {id_email}: {e}")
    return False

def criar_rascunho_imap(remetente, assunto_original, texto_rascunho):
    """Agora esta função abre a própria conexão para ser usada pelo LangGraph"""
    if not texto_rascunho or len(texto_rascunho) < 5:
        return False

    msg = EmailMessage()
    msg['Subject'] = f"Re: {assunto_original}"
    msg['To'] = remetente
    msg['From'] = EMAIL_ACCOUNT
    msg.set_content(texto_rascunho)

    pasta_rascunhos = "IA_Rascunhos"
    
    try:
        mail_temp = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail_temp.login(EMAIL_ACCOUNT, APP_PASSWORD)
        mail_temp.create(f'"{pasta_rascunhos}"')
        mail_temp.append(f'"{pasta_rascunhos}"', '\\Draft', None, msg.as_bytes())
        mail_temp.logout()
        return True
    except Exception as e:
        print(f"Erro ao salvar rascunho: {e}")
        return False

# =====================================================================
#                      CRIANDO O AGENTE COM LANGGRAPH
# =====================================================================

class EmailState(TypedDict):
    id_email: str
    remetente: str
    assunto: str
    corpo: str
    categoria: str
    resumo: str
    rascunho: str

llm = ChatOllama(model=OLLAMA_MODEL, format="json", temperature=0, base_url=OLLAMA_BASE_URL)

def no_categorizador(state: EmailState):
    prompt = f"""
    Analise o e-mail abaixo e classifique-o em UMA destas opções: {', '.join(CATEGORIAS)}.
    De: {state['remetente']} \nAssunto: {state['assunto']} \nCorpo: {state['corpo'][:1000]}
    Responda APENAS em JSON no formato: {{"categoria": "NomeDaCategoria"}}
    """
    try:
        resposta = llm.invoke([HumanMessage(content=prompt)])
        categoria = json.loads(resposta.content).get("categoria", "Outros")
        if categoria not in CATEGORIAS: categoria = "Outros"
    except:
        categoria = "Outros"
    return {"categoria": categoria}

def no_resumo_financas(state: EmailState):
    prompt = f"Resuma este e-mail financeiro em 2 linhas (destaque R$ e datas).\nAssunto: {state['assunto']}\nCorpo: {state['corpo'][:1500]}\nResponda em JSON: {{\"resumo\": \"...\"}}"
    try:
        resumo = json.loads(llm.invoke([HumanMessage(content=prompt)]).content).get("resumo", "Sem resumo.")
    except:
        resumo = "Erro ao resumir."
    return {"resumo": resumo}

def no_resumo_trabalho(state: EmailState):
    prompt = f"Resuma o e-mail em 2 linhas e crie um rascunho de resposta profissional.\nAssunto: {state['assunto']}\nCorpo: {state['corpo'][:1500]}\nResponda em JSON: {{\"resumo\": \"...\", \"rascunho\": \"...\"}}"
    try:
        dados = json.loads(llm.invoke([HumanMessage(content=prompt)]).content)
        return {"resumo": dados.get("resumo", "Sem resumo."), "rascunho": dados.get("rascunho", "")}
    except:
        return {"resumo": "Erro ao resumir.", "rascunho": ""}

def no_resumo_pessoal(state: EmailState):
    prompt = f"Resuma o e-mail em 2 linhas e crie um rascunho de resposta casual/amigável.\nAssunto: {state['assunto']}\nCorpo: {state['corpo'][:1500]}\nResponda em JSON: {{\"resumo\": \"...\", \"rascunho\": \"...\"}}"
    try:
        dados = json.loads(llm.invoke([HumanMessage(content=prompt)]).content)
        return {"resumo": dados.get("resumo", "Sem resumo."), "rascunho": dados.get("rascunho", "")}
    except:
        return {"resumo": "Erro ao resumir.", "rascunho": ""}

def no_resumo_geral(state: EmailState):
    prompt = f"Resuma o e-mail em 2 linhas.\nAssunto: {state['assunto']}\nCorpo: {state['corpo'][:1500]}\nResponda em JSON: {{\"resumo\": \"...\"}}"
    try:
        resumo = json.loads(llm.invoke([HumanMessage(content=prompt)]).content).get("resumo", "Sem resumo.")
    except:
        resumo = "Erro ao resumir."
    return {"resumo": resumo}

def no_salvar_rascunho(state: EmailState):
    """Nó final de ação: Só executa se o usuário aprovar no Streamlit"""
    criar_rascunho_imap(state['remetente'], state['assunto'], state['rascunho'])
    return {"rascunho": state["rascunho"] + "\n\n✅ [RASCUNHO SALVO NO SERVIDOR]"}

def decidir_proximo_passo(state: EmailState):
    cat = state["categoria"]
    if cat == "Finanças/Boletos": return "resumir_financas"
    elif cat == "Trabalho": return "resumir_trabalho"
    elif cat == "Pessoal": return "resumir_pessoal"
    else: return "resumir_geral"

# MONTANDO O GRAFO COM MEMÓRIA
memoria_estado = MemorySaver()

workflow = StateGraph(EmailState)
workflow.add_node("categorizador", no_categorizador)
workflow.add_node("resumir_financas", no_resumo_financas)
workflow.add_node("resumir_trabalho", no_resumo_trabalho)
workflow.add_node("resumir_pessoal", no_resumo_pessoal)
workflow.add_node("resumir_geral", no_resumo_geral)
workflow.add_node("salvar_rascunho", no_salvar_rascunho) 

workflow.set_entry_point("categorizador")
workflow.add_conditional_edges("categorizador", decidir_proximo_passo)

workflow.add_edge("resumir_financas", END)
workflow.add_edge("resumir_geral", END)
workflow.add_edge("resumir_trabalho", "salvar_rascunho")
workflow.add_edge("resumir_pessoal", "salvar_rascunho")
workflow.add_edge("salvar_rascunho", END)

# Compila o grafo com interrupção ANTES de salvar o rascunho
agente_langgraph = workflow.compile(
    checkpointer=memoria_estado,
    interrupt_before=["salvar_rascunho"]
)

# =====================================================================
#                      FUNÇÃO PRINCIPAL DE LEITURA
# =====================================================================

def buscar_emails_imap():
    """Busca e-mails brutos do servidor IMAP."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        mail.select("INBOX")

        limite_tempo = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)
        ontem = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
        _, mensagens = mail.search(None, f'(UNSEEN SINCE "{ontem}")')
        ids_emails = mensagens[0].split()

        emails_brutos = []
        for e_id in ids_emails:
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    data_email_str = msg.get("Date")
                    if data_email_str:
                        if parsedate_to_datetime(data_email_str) >= limite_tempo:
                            assunto_encoded, encoding = decode_header(msg["Subject"])[0]
                            assunto = assunto_encoded.decode(encoding if encoding else "utf-8") if isinstance(assunto_encoded, bytes) else assunto_encoded
                            
                            corpo = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        corpo = part.get_payload(decode=True).decode(errors="ignore")
                                        break
                            else:
                                corpo = msg.get_payload(decode=True).decode(errors="ignore")
                                
                            emails_brutos.append({
                                "id": e_id.decode(),
                                "remetente": msg.get("From"),
                                "assunto": assunto,
                                "corpo": limpar_html(corpo)
                            })
        mail.logout()
        return emails_brutos
    except Exception as e:
        st.error(f"Erro no IMAP: {e}")
        return []

# ================= INTERFACE DO STREAMLIT =================
st.set_page_config(page_title="Agente de E-mail IA", page_icon="📧", layout="wide")

st.title("📬 Painel do Agente com Aprovação Humana")
st.write("Verifique os e-mails. Rascunhos gerados pausarão e aguardarão sua aprovação antes de serem salvos.")

# Gerencia o estado da aplicação no Streamlit
if "emails_processados" not in st.session_state:
    st.session_state.emails_processados = []

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔄 Ler Caixa de Entrada", use_container_width=True):
        st.session_state.emails_processados = []
        with st.spinner("Baixando e analisando e-mails..."):
            emails_brutos = buscar_emails_imap()
            for em in emails_brutos:
                # Inicia o agente para cada e-mail com um ID único (thread_id)
                config = {"configurable": {"thread_id": f"thread_{em['id']}"}}
                estado_inicial = {
                    "id_email": em["id"],
                    "remetente": em["remetente"],
                    "assunto": em["assunto"],
                    "corpo": em["corpo"],
                    "categoria": "", "resumo": "", "rascunho": ""
                }
                
                # Executa o grafo (vai pausar se chegar no nó "salvar_rascunho")
                agente_langgraph.invoke(estado_inicial, config)
                
                # Coleta o estado atual (pausado ou finalizado)
                estado_atual = agente_langgraph.get_state(config)
                valores = estado_atual.values
                
                # Salva na memória RAG (somente na primeira leitura)
                salvar_email_no_rag(valores['remetente'], valores['assunto'], valores['corpo'], valores['categoria'])
                
                st.session_state.emails_processados.append({
                    "id": em["id"],
                    "config": config,
                })

# Renderiza os e-mails armazenados na sessão
if st.session_state.emails_processados:
    st.success(f"{len(st.session_state.emails_processados)} e-mails carregados e em memória.")
    st.divider()
    
    for em_dict in st.session_state.emails_processados:
        config = em_dict["config"]
        estado_do_grafo = agente_langgraph.get_state(config)
        valores = estado_do_grafo.values
        proximo_passo = estado_do_grafo.next # Verifica se está pausado
        
        with st.expander(f"[{valores.get('categoria', 'Outros')}] ✉️ {valores.get('assunto', '')}", expanded=True if proximo_passo else False):
            st.markdown(f"**De:** `{valores.get('remetente', '')}`")
            st.markdown(f"**Resumo:** \n> {valores.get('resumo', '')}")
            
            # Se a IA parou e está aguardando permissão no nó "salvar_rascunho"
            if proximo_passo and "salvar_rascunho" in proximo_passo:
                st.warning("⏳ **AGUARDANDO APROVAÇÃO:** A IA gerou um rascunho de resposta e pausou a execução.")
                st.text_area("Rascunho Sugerido (Pode ser editado no provedor):", valores.get('rascunho', ''), height=100, disabled=True)
                
                if st.button(f"✅ Aprovar e Salvar Rascunho no E-mail", key=f"btn_aprovar_{em_dict['id']}"):
                    with st.spinner("Conectando ao servidor e salvando rascunho..."):
                        # O segredo: Invocamos passando 'None' e o mesmo ID. Ele retoma de onde parou!
                        agente_langgraph.invoke(None, config)
                    st.rerun() # Atualiza a tela do Streamlit
            
            # Se o grafo já chegou ao END e o rascunho foi salvo
            elif "✅ [RASCUNHO SALVO NO SERVIDOR]" in valores.get('rascunho', ''):
                st.success("✅ Rascunho aprovado e salvo no seu provedor com sucesso!")
                st.markdown(f"**Rascunho Salvo:** \n> *{valores.get('rascunho').replace('✅ [RASCUNHO SALVO NO SERVIDOR]', '')}*")

# ================= CHAT COM A CAIXA DE ENTRADA (RAG) =================
st.divider()
st.subheader("💬 Converse com sua Caixa de Entrada")
pergunta = st.text_input("O que você deseja buscar nos seus e-mails antigos?")

if st.button("Perguntar à IA"):
    if pergunta:
        with st.spinner("🧠 Buscando na memória dos e-mails..."):
            resposta_texto, fontes = consultar_memoria(pergunta)
            if resposta_texto is None:
                st.warning("Não encontrei e-mails relacionados a essa pergunta no banco.")
            else:
                st.success("✅ Resposta Gerada!")
                st.markdown(f"> {resposta_texto}")
                with st.expander("🔍 Ver os e-mails usados como base"):
                    for i, doc in enumerate(fontes):
                        st.markdown(f"**Fonte {i+1}:** {doc.metadata.get('assunto')} *(Cat: {doc.metadata.get('categoria')})*")