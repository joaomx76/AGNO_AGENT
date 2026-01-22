from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# RAG
vector_db = ChromaDb(collection="pdf_agent", path="tmp/chromadb", persistent_client=True)
knowledge = Knowledge(vector_db=vector_db)

db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

agent = Agent(
    id="agente_pdf",
    name="Agente de PDF",
    model=OpenAIChat(id="gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY")),
    db=db,
    knowledge=knowledge,
    enable_user_memories=True,
    instructions="Você deve chamar o usuário de senhor e busque informações no PDF",
    description="",
    search_knowledge=True,
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
        skip_if_exists=True,
        reader=PDFReader()
    )
    agent_os.serve(app="exemplo2:app", host="0.0.0.0", port=10000, reload=True)