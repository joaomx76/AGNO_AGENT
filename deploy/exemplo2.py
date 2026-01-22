from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS


import os
from dotenv import load_dotenv

# Carrega .env da raiz primeiro, depois do .venv
load_dotenv()
load_dotenv('.venv/.env')

# Verificar se a chave da OpenAI está configurada
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY não encontrada. Configure a variável de ambiente no Render.")

# RAG
# IMPORTANTE:
# - Se você mudou embedder/modelo, apague a coleção antiga para não misturar embeddings incompatíveis.
# - A linha abaixo força o uso do embedder da OpenAI (text-embedding-3-small) para indexar e buscar.
# - Adicionado retry para lidar com erros de conexão
embedder = OpenAIEmbedder(
    id="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY"),
)

vector_db = ChromaDb(
    collection="pdf_agent",
    path="tmp/chromadb",
    persistent_client=True,
    embedder=embedder,
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
    agents=[agent],
    telemetry=False,
)

app = agent_os.get_app()


# RUN ===========================================================
if __name__ == "__main__":
    import asyncio
    
    # Carregar PDF de forma assíncrona com retry e validação
    async def load_pdf():
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Tentativa {attempt + 1}/{max_retries}: Carregando PDF...")
                await knowledge.add_content_async(
                    url="https://s3.sa-east-1.amazonaws.com/static.grendene.aatb.com.br/releases/2417_2T25.pdf",
                    metadata={"source": "Grendene", "type":"pdf", "description": "Relatório Trimestral 2T25"},
                    skip_if_exists=False,  # Forçar carregar sempre (Render apaga tmp/ a cada deploy)
                    reader=PDFReader()
                )
                print("PDF processado! Aguardando geração de embeddings...")
                
                # Aguardar mais tempo para garantir que todos os embeddings foram gerados
                # (os erros de conexão podem causar atrasos)
                await asyncio.sleep(10)
                
                # Verificar se há documentos na base usando método síncrono
                try:
                    # Usar search() síncrono ao invés de search_async
                    results = knowledge.search("Grendene", num_results=1)
                    if results and len(results) > 0:
                        print(f"✅ PDF carregado com sucesso! {len(results)} documento(s) encontrado(s) na busca de teste.")
                        return True
                    else:
                        print(f"⚠️ PDF processado mas nenhum documento encontrado na busca. Tentativa {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(10)  # Aguardar mais tempo antes de tentar novamente
                            continue
                except Exception as search_error:
                    print(f"⚠️ Erro ao verificar documentos: {search_error}. Tentativa {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)
                        continue
                
            except Exception as e:
                print(f"❌ Erro ao carregar PDF (tentativa {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # Backoff exponencial
                    print(f"Aguardando {wait_time}s antes de tentar novamente...")
                    await asyncio.sleep(wait_time)
                else:
                    print("❌ Falha ao carregar PDF após todas as tentativas. Servidor iniciará sem PDF.")
                    return False
        
        return False
    
    # Carregar PDF antes de iniciar o servidor
    pdf_loaded = asyncio.run(load_pdf())
    
    if not pdf_loaded:
        print("⚠️ AVISO: PDF não foi carregado completamente. O agente pode não funcionar corretamente.")
    
    # Em produção (Render), use a porta do ambiente
    # O Render define a variável PORT automaticamente
    port = int(os.getenv("PORT", "10000"))
    print(f"🚀 Iniciando servidor na porta {port} (host: 0.0.0.0)...")
    print(f"📡 Servidor estará disponível em: http://0.0.0.0:{port}")
    agent_os.serve(app="exemplo2:app", reload=False, host="0.0.0.0", port=port)

