# 1 - IMPORTS ===========================================================
import requests
import json
import streamlit as st

AGENT_ID = "agente_pdf"
ENDPOINT = f"https://agno-agent-api.onrender.com/agents/{AGENT_ID}/runs"

# 2 - Conexão com o Agno (SERVER) =========================================

def get_response_stream(message: str):
    try:
        response = requests.post(
            url=ENDPOINT,
            data={
                "message": message,
                "stream": "true"
            },
            stream=True,
            timeout=30
        )
        
        # Verificar status HTTP
        response.raise_for_status()  # Levanta exceção se status não for 2xx
        
        # 2.1 - Streaming (processamento) ====================================
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
                        
    except requests.exceptions.ConnectionError as e:
        yield {
            "event": "Error",
            "content": f"❌ Erro de conexão: Não foi possível conectar à API.\n\nVerifique se o servidor está rodando em:\n{ENDPOINT}\n\nErro: {str(e)}"
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if hasattr(e, 'response') and e.response else "desconhecido"
        reason = e.response.reason if hasattr(e, 'response') and e.response else "Erro HTTP"
        yield {
            "event": "Error",
            "content": f"❌ Erro HTTP {status_code}: {reason}\n\nURL: {ENDPOINT}\n\nErro: {str(e)}"
        }
    except requests.exceptions.Timeout as e:
        yield {
            "event": "Error",
            "content": f"❌ Timeout: A requisição demorou mais de 30 segundos.\n\nURL: {ENDPOINT}\n\nErro: {str(e)}"
        }
    except requests.exceptions.RequestException as e:
        yield {
            "event": "Error",
            "content": f"❌ Erro na requisição: {str(e)}\n\nURL: {ENDPOINT}"
        }
    except Exception as e:
        yield {
            "event": "Error",
            "content": f"❌ Erro inesperado: {str(e)}\n\nTipo: {type(e).__name__}"
        }


# 3 - Streamlit ==========================================================

st.set_page_config(page_title="Agent Chat PDF")
st.title("Agent Chat PDF")

# 3.1 - Histórico ==========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3.2 - Mostrar histórico ==================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("process"):
            with st.expander(label="Process", expanded=False):
                st.json(msg["process"])
        st.markdown(msg["content"])

# 3.3 - Input do usuário ==================================================
if prompt := st.chat_input("Digite sua mensagem..."):
    # Adicionar mensagem do usuário (memoria do streamlit)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
    
    # processamento streaming
    try:
        for event in get_response_stream(prompt):
            event_type = event.get("event", "")
            
            # Tratar erros
            if event_type == "Error":
                error_msg = event.get("content", "Erro desconhecido")
                response_placeholder.error(error_msg)
                full_response = error_msg
                break
            
            # Tool call iniciado
            if event_type == "ToolCallStarted":
                tool_name = event.get("tool", {}).get("tool_name")
                with st.status(f"Executando {tool_name}...", expanded=True):
                    st.json(event.get("tool", {}).get("tool_args", {}))
            
            # Conteúdo da resposta
            elif event_type == "RunContent":
                content = event.get("content", "")
                if content:
                    full_response += content
                    response_placeholder.markdown(full_response + "▌")
        
        # Se não houve erro, mostrar resposta final
        if full_response and not full_response.startswith("❌"):
            response_placeholder.markdown(full_response)
        elif not full_response:
            response_placeholder.warning("⚠️ Nenhuma resposta recebida da API.")
            
    except Exception as e:
        error_msg = f"❌ Erro ao processar resposta: {str(e)}\n\nTipo: {type(e).__name__}"
        response_placeholder.error(error_msg)
        full_response = error_msg

    # salvar a resposta e histórico na session state
    st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })