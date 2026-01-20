#Conta Corrente - FastAPI
#Gerenciar saques e depositos de clientes
#------------------------------------------

#IMPORTACOES
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel, Field

#instancia da API
app = FastAPI(title = "Conta bancária - Conta Corrente")

#Adicionar clientes
db_clientes = {
    'João': 1000,
    'Maria': 2000,
    'Pedro': 3000,
}

#criar uma classe para movimentacoes (saque, deposito) obs: usar Pydantic (para não acontecer erros)
class Movimentacao(BaseModel):
    cliente: str = Field(..., description="Nome do cliente")
    valor: float = Field(..., description="Valor da movimentação", gt=0)
    tipo: str = Field(..., description="Tipo de movimentação")

#Criar um endpoint Home
@app.get("/")
def read_root():
    return {"message": "API de conta bancária - Conta Corrente"}

#Criar um endpoint para consultar o saldo
@app.post("/saldo/")
def read_saldo(cliente: str):
    return {"message": f"Saldo do cliente {cliente} é de {db_clientes[cliente]}"}

#Criar um endpoint para sacar
@app.post("/saque/")
def saque(movimentacao: Movimentacao):
    db_clientes[movimentacao.cliente] -= movimentacao.valor
    return {"message": {"cliente": movimentacao.cliente, "valor_movimentacao": -movimentacao.valor, "saldo": db_clientes[movimentacao.cliente]}}

#Criar um endpoint para depositar
@app.post("/deposito/")
def deposito(movimentacao: Movimentacao):
    db_clientes[movimentacao.cliente] += movimentacao.valor
    return {"message": {"cliente": movimentacao.cliente, "valor_movimentacao": movimentacao.valor, "saldo": db_clientes[movimentacao.cliente]}}


if __name__ == "__main__":
    uvicorn.run("exemplo2:app", host="0.0.0.0", port=8000, reload=True)