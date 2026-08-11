import subprocess
import sys
import time

print("🚀 Iniciando os sistemas do Agente de IA...")

try:
    # 1. Inicia o agente de e-mail (agendador de 12h e 18h)
    processo_agente = subprocess.Popen([sys.executable, "agente_email.py"])
    print("✅ Agente de E-mail (Fundo) iniciado com sucesso!")

    # 2. Inicia o painel do Streamlit (Preparado para Local e Docker)
    processo_painel = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app.py", 
        "--server.port=8501", 
        "--server.address=0.0.0.0"
    ])
    print("✅ Painel Streamlit iniciado com sucesso!")

    print("\nTudo rodando! Pressione [Ctrl + C] aqui para desligar ambos.")
    
    # Mantém este script rodando para segurar os processos filhos
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Desligando os sistemas...")
    processo_agente.terminate()
    processo_painel.terminate()
    print("Sistemas encerrados. Até logo!")