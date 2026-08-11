# 📧 Agente Inteligente de E-mail com IA (100% Local e Open-Source)

Um assistente pessoal automatizado que lê, categoriza e resume seus e-mails não lidos utilizando Inteligência Artificial executada localmente, garantindo **100% de privacidade** dos seus dados.

Construído com uma arquitetura avançada de roteamento (LangGraph), o agente possui "Especialistas em IA" dedicados a diferentes tipos de e-mails (como Finanças e Trabalho). A interface visual é gerada com Streamlit e tudo pode ser facilmente executado via Docker.

## ✨ Funcionalidades

- 🔒 **Privacidade Total:** Utiliza o Ollama (Llama 3 / Mistral) localmente. Nenhum dado de e-mail é enviado para APIs externas (como OpenAI ou Google).
- 🧠 **Roteamento Inteligente (LangGraph):** Os e-mails são categorizados e enviados para sub-agentes especialistas baseados no contexto (ex: extração de tarefas ou busca de valores financeiros).
- 💬 **Chat com a Caixa de Entrada (RAG):** O agente constrói uma memória de longo prazo usando um banco de dados vetorial. Você pode conversar com a IA e fazer perguntas como *"Qual o valor do boleto da internet?"* e ela buscará a resposta no seu histórico de e-mails.
- 🧹 **Organização Automática (Inbox Zero):** Capacidade ativa via IMAP para criar pastas (ex: `IA_Trabalho`, `IA_Finanças`) e mover os e-mails lidos, mantendo sua Caixa de Entrada limpa.
- ✍️ **Rascunhos Inteligentes:** O Especialista de "Trabalho" e "Pessoal" não apenas resumem, mas redigem automaticamente uma sugestão de resposta e a salvam diretamente na sua pasta `IA_Rascunhos` no provedor, pronta para envio.
- 📊 **Interface Web (Streamlit):** Um painel limpo e organizado por abas (Trabalho, Pessoal, Promoções, Newsletters, Finanças) para ler seus resumos rapidamente e interagir com o Chat.
- 🕒 **Filtro de Tempo:** Processa apenas os e-mails das últimas 6 horas, economizando processamento.
- ⏱️ **Execução em Segundo Plano:** Um script gerenciador (`rodar_tudo.py`) mantém um agendador oculto que processa e-mails e constrói a memória vetorial automaticamente em horários definidos (ex: 12h e 18h).
- 🐳 **Pronto para Docker:** Rode facilmente usando `docker compose` sem se preocupar com dependências.

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.11
- **IA Local:** [Ollama](https://ollama.com/) + Llama 3
- **Orquestração de IA:** LangChain & LangGraph
- **Banco de Dados Vetorial (RAG):** ChromaDB + Nomic Embeddings
- **Interface Gráfica:** Streamlit
- **Protocolo de E-mail:** IMAP nativo (`imaplib` e `email.message`)
- **Containerização:** Docker & Docker Compose

---

## ⚙️ Pré-requisitos

1. Ter o [Ollama](https://ollama.com/) instalado no seu computador.
2. Baixar o modelo desejado abrindo o terminal e digitando: `ollama run llama3`
3. Criar uma **Senha de Aplicativo** (App Password) no seu provedor de e-mail (Gmail, Yahoo, etc.). *Não use sua senha normal por questões de segurança.*

---

## 🚀 Como Configurar

1. Clone ou baixe este repositório.
2. Certifique-se de ter baixado o modelo principal e o modelo de embeddings (para o Chat) no seu terminal:
   ```bash
   ollama run llama3
   ollama pull nomic-embed-text
   ```
3. Na raiz do projeto, crie um arquivo chamado **`.env`** com as suas credenciais, podendo ser do provedor qualquerClone ou baixe este repositório.
```env
EMAIL_ACCOUNT=seu_email@yahoo.com.br
APP_PASSWORD=sua_senha_de_aplicativo_gerada_aqui
IMAP_SERVER=imap.mail.yahoo.com
```

## 💻 Como Rodar

Você pode executar o projeto de duas maneiras: localmente (via Python) ou através do Docker.

### Opção A: Localmente (Com Ambiente Virtual - venv)
É altamente recomendado usar um ambiente virtual para não misturar as dependências deste projeto com o seu Python global.

1. Abra o terminal na pasta do projeto e crie o ambiente virtual:
   ```text
   python -m venv venv
   ```
2. Ative o ambiente virtual:
   ```text
   venv\Scripts\activate
   ```
3. Instale as dependências:
    ```text
    pip install -r requirements.txt 
    ```
3. Rodar Script rodar_tudo.py:
    ```text
    python rodar_tudo.py
    ```

### Opção B: Usando o Docker (Recomendado)
Garante que o ambiente não terá conflitos de versões e dispensa a instalação manual de dependências locais.

1. Certifique-se de que o **Docker Desktop** está aberto e rodando no seu computador:
   *(O ícone na barra de tarefas deve indicar "Engine running")*

2. No terminal, na pasta do projeto, execute o comando para construir e iniciar o sistema em segundo plano:
   ```text
   docker-compose up -d
   ```
3. Abrir o docker desktop e abrir o endereço: http://localhost:8501

