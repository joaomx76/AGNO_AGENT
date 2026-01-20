from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title="API de Exemplo",
    description="Esta é uma API de exemplo para o curso de FastAPI",
    version="1.0.0",
    contact={
        "name": "João Pedro Moreira",
        "email": "joaomx76@gmail.com"
    }
)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
def read_hello(name: str):
    return {"message": f"Hello {name}"}


if __name__ == "__main__":
    uvicorn.run("exemplo1:app", host="0.0.0.0", port=8000, reload=True)