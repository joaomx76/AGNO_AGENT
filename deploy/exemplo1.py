from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.chroma import ChromaDb

from fastapi import FastAPI
import uvicorn
import asyncio

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
    name="Agente de PDF",
    model=OpenAIChat(id="gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY")),
    db=db,
    knowledge=knowledge,
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


# FASTAPI ===========================================================
app = FastAPI(title="Agente de PDF", description="API para responder perguntas sobre o PDF")

@app.post("/agente_pdf")
def agente_pdf(pergunta: str):
    response = agent.run(pergunta)
    message = response.messages[-1]
    return {"message": message.content}

# RUN ===========================================================
if __name__ == "__main__":
    asyncio.run(knowledge.add_content_async(
        url="https://s3.sa-east-1.amazonaws.com/static.grendene.aatb.com.br/releases/2417_2T25.pdf",
        metadata={"source": "Grendene", "type":"pdf", "description": "Relatório Trimestral 2T25"},
        skip_if_exists=True,
        reader=PDFReader()
    ))
    uvicorn.run("exemplo1:app", host="0.0.0.0", port=8000, reload=True)


