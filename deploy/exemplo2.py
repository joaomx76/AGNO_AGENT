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

# RUN ===========================================================
if __name__ == "__main__":
    knowledge.add_content(
        url="https://s3.sa-east-1.amazonaws.com/static.grendene.aatb.com.br/releases/2417_2T25.pdf",
        metadata={"source": "Grendene", "type":"pdf", "description": "Relatório Trimestral 2T25"},
        skip_if_exists=False,  # Força recarregamento (importante para Render com sistema de arquivos efêmero)
        reader=PDFReader()
    )
    port = int(os.getenv("PORT", "10000"))
    agent_os.serve(app="exemplo2:app", host="0.0.0.0", port=port, reload=False)