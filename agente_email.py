import streamlit as st
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import os
import requests
import re
import json # NOVO: Importamos a biblioteca JSON
from dotenv import load_dotenv

load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")

def limpar_html(texto_html):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(texto_html))

def analisar_com_ia(assunto, remetente, corpo):
    """Novo prompt mais inteligente e forçando formato JSON."""
    
    prompt = f"""
    Você é um assistente de e-mail. Analise a mensagem e categorize-a corretamente.
    
    Regras de Categorias:
    - "Trabalho": assuntos da empresa, chefes, clientes, reuniões.
    - "Pessoal": amigos, família, conversas casuais.
    - "Finanças/Boletos": bancos, contas a pagar, notas fiscais, compras.
    - "Promoções": marketing, descontos, propagandas de lojas.
    - "Newsletters": boletins informativos, resumos do LinkedIn, artigos, Medium, notícias, blogs.
    - "Outros": apenas se não se encaixar de jeito nenhum nas opções acima.

    E-mail:
    Remetente: {remetente}
    Assunto: {assunto}
    Corpo: {corpo[:1500]} 

    Responda APENAS com um objeto JSON válido contendo as chaves "categoria" (com o nome exato da categoria) e "resumo" (com um resumo de até 2 linhas). 
    Exemplo: {{"categoria": "Newsletters", "resumo": "Resumo rápido aqui."}}
    """

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        # Pega a resposta que agora vem como um dicionário JSON perfeito
        resposta_texto = response.json().get('response', '{}')
        dados = json.loads(resposta_texto)
        
        return dados
    except Exception as e:
        return {"categoria": "Erro de IA", "resumo": f"Falha ao gerar resumo: {e}"}

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
                    
                    # =========== MUDANÇA AQUI ===========
                    # Agora a função retorna um dicionário (JSON) pronto para uso!
                    resultado_ia = analisar_com_ia(assunto, remetente, corpo_limpo)
                    
                    # Puxa as informações diretamente das chaves do JSON
                    categoria = resultado_ia.get("categoria", "Sem Categoria")
                    resumo = resultado_ia.get("resumo", "Resumo indisponível")
                    
                    # Corrige se a IA inventar uma categoria fora da lista
                    categorias_validas = ["Trabalho", "Pessoal", "Finanças/Boletos", "Promoções", "Newsletters", "Outros", "Erro de IA"]
                    if categoria not in categorias_validas:
                        categoria = "Outros"

                    resultados.append({
                        "remetente": remetente,
                        "assunto": assunto,
                        "categoria": categoria,
                        "resumo": resumo
                    })
            
            barra_progresso.progress((indice + 1) / total_emails)

        mail.logout()
        return resultados

    except Exception as e:
        st.error(f"Erro ao acessar e-mails: {e}")
        return None

# ================= INTERFACE DO STREAMLIT =================
st.set_page_config(page_title="Agente de E-mail IA", page_icon="📧", layout="wide")

st.title("📬 Painel do Agente")
st.write("Verifique e leia os resumos dos e-mails das **últimas 6 horas**.")

if st.button("🔄 Ler e Resumir Caixa de Entrada"):
    with st.spinner('Baixando e-mails e rodando a IA...'):
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