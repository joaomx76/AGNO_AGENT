from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS

import os
import asyncio
from dotenv import load_dotenv

# Tentar importar RateLimitError, mas não é obrigatório
try:
    from openai import RateLimitError
except ImportError:
    RateLimitError = None

# Carrega .env da raiz primeiro, depois do .venv
load_dotenv()
load_dotenv('.venv/.env')

# Verificar se a chave da OpenAI está configurada
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY não encontrada. Verifique o arquivo .env na raiz do projeto ou em .venv/.env")

# RAG
embedder = OpenAIEmbedder(
    id="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY"),
)
vector_db = ChromaDb(
    collection="pdf_agent",
    path="tmp/chromadb",
    persistent_client=True,
    embedder=embedder
)
knowledge = Knowledge(vector_db=vector_db)

db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

agent = Agent(
    id="agente_pdf",
    name="Agente de PDF",
    model=OpenAIChat(id="gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY")),
    db=db,
    knowledge=knowledge,
    enable_user_memories=True,
    instructions=[
        "Você deve chamar o usuário de senhor.",
        "Sempre use a ferramenta de busca na knowledge para responder perguntas sobre o PDF.",
        "Quando responder, inclua os números e o contexto exato (trecho curto) encontrados no PDF.",
    ],
    description="",
    search_knowledge=True,
    add_knowledge_to_context=True,
    num_history_runs=3,
    debug_mode=True
)

# AGENTOS ===========================================================
agent_os = AgentOS(
    name="Agente de PDF",
    agents=[agent]
)

app = agent_os.get_app()

# FUNÇÃO HELPER PARA PROCESSAR PDF COM RETRY E LOTES ===========
async def load_pdf_with_retry_and_batches(
    knowledge: Knowledge,
    url: str,
    metadata: dict,
    reader: PDFReader,
    batch_size: int = 4,
    max_retries: int = 5
):
    """
    Carrega PDF processando em lotes menores com retry automático e tratamento de rate limit.
    
    Args:
        knowledge: Instância do Knowledge
        url: URL do PDF
        metadata: Metadados do PDF
        reader: Reader do PDF
        batch_size: Número de documentos por lote (padrão: 4)
        max_retries: Número máximo de tentativas por lote (padrão: 5)
    """
    print(f"📄 Iniciando carregamento do PDF em lotes de {batch_size} documentos...")
    
    # Função auxiliar para retry com exponential backoff
    async def retry_with_backoff(func, *args, **kwargs):
        retry_delays = [2, 4, 8, 16, 60]  # Exponential backoff: 2s, 4s, 8s, 16s, 60s
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Verificar se é erro 429 (rate limit)
                error_str = str(e).lower()
                is_rate_limit = (
                    (RateLimitError and isinstance(e, RateLimitError)) or
                    "429" in error_str or 
                    "rate limit" in error_str or 
                    "too many requests" in error_str
                )
                
                if is_rate_limit:
                    if attempt < max_retries - 1:
                        delay = 60  # Wait 60s para erro 429 (conforme solicitado)
                        print(f"⏳ Rate limit (429) detectado. Aguardando {delay}s antes de tentar novamente... (Tentativa {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise
                else:
                    # Outros erros: retry com exponential backoff normal
                    if attempt < max_retries - 1:
                        delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                        print(f"⚠️  Erro ao processar: {str(e)[:100]}. Aguardando {delay}s antes de tentar novamente... (Tentativa {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise
        raise Exception(f"Falhou após {max_retries} tentativas")
    
    # Processar PDF com retry
    try:
        # Usar add_content_async com retry automático
        await retry_with_backoff(
            knowledge.add_content_async,
            url=url,
            metadata=metadata,
            skip_if_exists=False,
            reader=reader
        )
        print("✅ PDF carregado com sucesso! Base de conhecimento pronta.")
    except Exception as e:
        # Se falhar completamente, tentar processamento manual em lotes
        print(f"⚠️  Método padrão falhou: {str(e)[:200]}")
        print("🔄 Tentando processamento alternativo...")
        raise e  # Por enquanto, apenas re-raise. Processamento em lotes manual seria mais complexo

# RUN ===========================================================
if __name__ == "__main__":
    # Carregar PDF de forma assíncrona com retry e tratamento de erros
    try:
        asyncio.run(load_pdf_with_retry_and_batches(
            knowledge=knowledge,
            url="https://s3.sa-east-1.amazonaws.com/static.grendene.aatb.com.br/releases/2417_2T25.pdf",
            metadata={"source": "Grendene", "type":"pdf", "description": "Relatório Trimestral 2T25"},
            reader=PDFReader(),
            batch_size=4,
            max_retries=5
        ))
    except Exception as e:
        print(f"❌ ERRO ao carregar PDF: {str(e)}")
        print(f"⚠️  Tipo do erro: {type(e).__name__}")
        print("⚠️  O servidor será iniciado, mas a base de conhecimento pode estar vazia.")
        # Não interrompe o servidor, mas avisa sobre o problema
    
    # Iniciar servidor
    port = int(os.getenv("PORT", "10000"))
    print(f"🚀 Iniciando servidor na porta {port}...")
    agent_os.serve(app="exemplo2:app", host="0.0.0.0", port=port, reload=False)