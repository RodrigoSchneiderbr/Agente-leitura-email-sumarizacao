import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import os
import requests
import re
import json
import time
import schedule
from dotenv import load_dotenv

from memoria_rag import salvar_email_no_rag, limpar_memoria_diaria

load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")

# Adaptado para funcionar no Docker e Localmente
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

def limpar_html(texto_html):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(texto_html))

def analisar_com_ia(assunto, remetente, corpo):
    prompt = f"""
    Você é um assistente de e-mail. Analise a mensagem e categorize-a corretamente.
    
    Regras de Categorias:
    - "Trabalho": assuntos da empresa, chefes, clientes, reuniões.
    - "Pessoal": amigos, família, conversas casuais.
    - "Finanças/Boletos": bancos, contas a pagar, notas fiscais, compras.
    - "Promoções": marketing, descontos, propagandas de lojas.
    - "Newsletters": boletins informativos, resumos do LinkedIn, artigos.
    - "Outros": apenas se não se encaixar de jeito nenhum nas opções acima.

    E-mail:
    Remetente: {remetente}
    Assunto: {assunto}
    Corpo: {corpo[:1500]} 

    Responda APENAS com um objeto JSON válido contendo as chaves "categoria" e "resumo". 
    """

    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        resposta_texto = response.json().get('response', '{}')
        dados = json.loads(resposta_texto)
        
        return dados
    except Exception as e:
        return {"categoria": "Erro de IA", "resumo": f"Falha ao gerar resumo: {e}"}

def checar_emails_agendado():
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Iniciando varredura silenciosa de e-mails...")
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            print("❌ Erro: Não foi possível abrir a caixa de entrada (INBOX).")
            return

        # Busca e-mails das últimas 6 horas
        limite_tempo = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)
        ontem = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")

        status, mensagens = mail.search(None, f'(UNSEEN SINCE "{ontem}")')
        ids_emails = mensagens[0].split()

        if not ids_emails:
            print("✅ Nenhum e-mail novo nas últimas 6 horas.")
            mail.logout()
            return

        emails_recentes = []
        for e_id in ids_emails:
            _, msg_data = mail.fetch(e_id, '(BODY[HEADER.FIELDS (DATE)])')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg_data_header = email.message_from_bytes(response_part[1])
                    data_email_str = msg_data_header.get("Date")
                    if data_email_str:
                        data_email = parsedate_to_datetime(data_email_str)
                        if data_email >= limite_tempo:
                            emails_recentes.append(e_id)

        if not emails_recentes:
            print("✅ Nenhum e-mail novo nas últimas 6 horas.")
            mail.logout()
            return

        print(f"📥 Encontrados {len(emails_recentes)} e-mails. Processando com a IA...")
        
        for e_id in emails_recentes:
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
                    
                    # Chama a IA de forma silenciosa
                    resultado_ia = analisar_com_ia(assunto, remetente, corpo_limpo)
                    
                    # Como é um script de fundo, nós apenas logamos no terminal
                    print(f"✉️ [ {resultado_ia.get('categoria', 'Outros')} ] {assunto}")
                    print(f"   ↳ Resumo: {resultado_ia.get('resumo', 'Sem resumo')}\n")

        print("✅ Varredura concluída com sucesso!")
        mail.logout()

    except Exception as e:
        print(f"❌ Erro ao acessar e-mails no robô de fundo: {e}")

def rotina_de_limpeza():
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Iniciando limpeza diária da memória...")
    limpar_memoria_diaria()

# Configura os horários que o robô vai ler os e-mails
schedule.every().day.at("12:00").do(checar_emails_agendado)
schedule.every().day.at("18:00").do(checar_emails_agendado)

# NOVO: Limpa a memória toda meia-noite!
schedule.every().day.at("00:00").do(rotina_de_limpeza)

print("🤖 Agente de E-mail (Background) iniciado!")
print("Ele fará verificações às 12:00 e 18:00, e limpará a memória às 00:00.")

# Loop infinito para manter o script vivo
while True:
    schedule.run_pending()
    time.sleep(60)