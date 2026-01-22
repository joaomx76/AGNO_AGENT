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

# RAG
# IMPORTANTE:
# - Se você mudou embedder/modelo, apague a coleção antiga para não misturar embeddings incompatíveis.
# - A linha abaixo força o uso do embedder da OpenAI (text-embedding-3-small) para indexar e buscar.
vector_db = ChromaDb(
    collection="pdf_agent",
    path="tmp/chromadb",
    persistent_client=True,
    embedder=OpenAIEmbedder(
        id="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
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
    
    # Carregar PDF de forma assíncrona
    async def load_pdf():
        try:
            await knowledge.add_content_async(
                url="https://s3.sa-east-1.amazonaws.com/static.grendene.aatb.com.br/releases/2417_2T25.pdf",
                metadata={"source": "Grendene", "type":"pdf", "description": "Relatório Trimestral 2T25"},
                skip_if_exists=False,  # Forçar carregar sempre (Render apaga tmp/ a cada deploy)
                reader=PDFReader()
            )
            print("PDF carregado com sucesso!")
        except Exception as e:
            print(f"Erro ao carregar PDF: {e}")
    
    # Carregar PDF antes de iniciar o servidor
    asyncio.run(load_pdf())
    
    # Em produção (Render), use a porta do ambiente e faça bind em 0.0.0.0
    port = int(os.getenv("PORT", "10000"))
    agent_os.serve(app="exemplo2:app", reload=False, host="0.0.0.0", port=port)

