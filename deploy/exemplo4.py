#1 - IMPORTS
import requests
import json
from pprint import pprint
import streamlit as st

AGENT_ID = "agente_pdf"
ENDPOINT = f"http://localhost:7777/agents/{AGENT_ID}/runs"

#2 - Conexão com AGNO (server)
def get_response_stream(message: str):
    response = requests.post(
        url=ENDPOINT,
        data={
            "message": message,
            "stream": "true"
        },
        stream=True
    )
    
    #2.1 - Streaming (processamento)
    for line in response.iter_lines():
        if line:
            # Parse Server-Sent Events
            if line.startswith(b'data: '):
                data = line[6:] # Remove 'data: ' prefix
                try:
                    event = json.loads(data)
                    yield event
                except json.JSONDecodeError:
                    continue

#3 - Streamlit
st.set_page_config(page_title="Agente Chat PDF")
st.title("Agente Chat PDF")

#3.1 - Histórico de Conversas
if "messages" not in st.session_state:
    st.session_state.messages = []

#3.2 - Mostrar Histórico de Conversas
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and message.get("process"):
            with st.expander(label="Process", expanded=False):
                st.json(message["process"])
        st.markdown(message["content"])

#3.3 - Input do Usuário
if prompt := st.chat_input("Digite sua mensagem:"):
    #3.3.1 - Adicionar Mensagem do Usuário (á memória do Streamlit)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    #3.3.2 - Resposta do assistente 
    with st.chat_message("assistant"):
        process_placeholder = st.empty()
        response_placeholder = st.empty()
        full_response = ""

    #3.3.3 - Processamento Streamlit
    for event in get_response_stream(prompt):
        event_type = event.get("event", "")

        if event_type == "ToolCallStarted":
            tool_name = event.get("tool", {}).get("tool_name")
            with st.status(f"Executando: {tool_name}...", expanded=True):
                st.json(event.get("tool", {}).get("tool_args", {}))

        # Conteúdo da resposta
        elif event_type == "RunContent":
            content = event.get("content", "")
            if content:
                full_response += content
                response_placeholder.markdown(full_response)

    response_placeholder.markdown(full_response)

    #3.3.4 - Salvar a resposta e histórico na session_state
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response, 
        })

        
