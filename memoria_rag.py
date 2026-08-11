import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Carrega as variáveis de ambiente (Docker/Local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

def _obter_banco_vetorial():
    """Função interna para inicializar a conexão com o ChromaDB."""
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=OLLAMA_BASE_URL
    )
    return Chroma(
        collection_name="meus_emails",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )

def salvar_email_no_rag(remetente, assunto, corpo, categoria):
    """Fatia o e-mail longo em pedaços menores, transforma em vetores e salva no banco."""
    try:
        vector_store = _obter_banco_vetorial()
        
        # Junta tudo que queremos salvar
        conteudo_completo = f"De: {remetente}\nAssunto: {assunto}\nCorpo:\n{corpo}"
        
        # ====================================================================
        # Picotador de Texto para evitar o erro "exceeds context length"
        # ====================================================================
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Tamanho máximo de cada pedaço (1000 caracteres)
            chunk_overlap=200, # Mantém 200 caracteres repetidos entre um pedaço e outro para não perder o contexto
            length_function=len
        )
        
        # Divide o texto grande em uma lista de pedaços menores
        pedacos = text_splitter.split_text(conteudo_completo)
        
        # Converte os pedaços em Documentos do LangChain
        documentos = []
        for pedaco in pedacos:
            doc = Document(
                page_content=pedaco,
                metadata={"categoria": categoria, "assunto": assunto}
            )
            documentos.append(doc)
            
        # Adiciona todos os pedaços de forma segura no banco de dados
        vector_store.add_documents(documentos)
        return True
        
    except Exception as e:
        print(f"Erro ao salvar no banco vetorial: {e}")
        return False

def consultar_memoria(pergunta):
    """Busca a resposta para a pergunta do usuário no histórico de e-mails."""
    vector_store = _obter_banco_vetorial()
    
    # Busca os 4 pedaços mais relevantes do banco
    resultados_busca = vector_store.similarity_search(pergunta, k=4)
    
    if not resultados_busca:
        return None, []
        
    contexto_textos = "\n\n---\n\n".join([doc.page_content for doc in resultados_busca])
    
    llm_chat = ChatOllama(
        model=OLLAMA_MODEL, 
        temperature=0.3, # Temperatura baixa para a IA ser mais direta e focar nos fatos
        base_url=OLLAMA_BASE_URL
    )
    
    prompt_rag = f"""
    Você é um assistente inteligente. Responda à pergunta do usuário baseando-se APENAS nos e-mails abaixo.
    Se a resposta não estiver nos e-mails, diga: 'Não encontrei essa informação nos e-mails processados.'
    Responda de forma clara e direta em português.
    
    E-MAILS RECUPERADOS:
    {contexto_textos}
    
    PERGUNTA DO USUÁRIO:
    {pergunta}
    """
    
    resposta_ia = llm_chat.invoke([HumanMessage(content=prompt_rag)])
    return resposta_ia.content, resultados_busca

def limpar_memoria_diaria():
    """Apaga a coleção do banco de dados vetorial para começar um novo dia limpo."""
    try:
        # A forma mais garantida de limpar o ChromaDB é deletando a coleção
        vector_store = _obter_banco_vetorial()
        vector_store.delete_collection()
        print("🧹 Memória do RAG (ChromaDB) limpa com sucesso!")
        return True
    except Exception as e:
        # Se a coleção já estiver vazia ou não existir, ele cai aqui e ignora o erro
        print(f"⚠️ Aviso ao limpar memória: {e}")
        return False