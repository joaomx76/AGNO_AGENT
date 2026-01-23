# 1 - IMPORTS ===========================================================
import requests
import json
import streamlit as st
import time

AGENT_ID = "agente_pdf"
ENDPOINT = f"https://agno-agent-api.onrender.com/agents/{AGENT_ID}/runs"

# 2 - Conexão com o Agno (SERVER) =========================================

def get_response_stream(message: str, max_retries=3):
    """
    Faz requisição com retry automático para erro 429 (Too Many Requests)
    """
    retry_delays = [5, 10, 20]  # Backoff exponencial em segundos
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url=ENDPOINT,
                data={
                    "message": message,
                    "stream": "true"
                },
                stream=True,
                timeout=120  # Aumentado para 120 segundos (permite serviço "acordar" e processar)
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
            return  # Sucesso, sair da função
                        
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else "desconhecido"
            reason = e.response.reason if hasattr(e, 'response') and e.response else "Erro HTTP"
            
            # Tratamento específico para erro 429 (Too Many Requests)
            if status_code == 429:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    yield {
                        "event": "Retry",
                        "content": f"⏳ Muitas requisições (429). Aguardando {delay}s antes de tentar novamente... (Tentativa {attempt + 1}/{max_retries})"
                    }
                    time.sleep(delay)
                    continue  # Tentar novamente
                else:
                    # Última tentativa falhou
                    yield {
                        "event": "Error",
                        "content": f"❌ Erro 429 - Muitas requisições: O servidor está limitando requisições.\n\n💡 Dicas:\n- Aguarde alguns minutos antes de tentar novamente\n- O plano gratuito do Render tem limites de requisições\n- Tente novamente mais tarde\n\nURL: {ENDPOINT}"
                    }
                    return
            else:
                # Outros erros HTTP não fazem retry
                yield {
                    "event": "Error",
                    "content": f"❌ Erro HTTP {status_code}: {reason}\n\nURL: {ENDPOINT}\n\nErro: {str(e)}"
                }
                return
                
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                yield {
                    "event": "Retry",
                    "content": f"⏳ Erro de conexão. Aguardando {delay}s antes de tentar novamente... (Tentativa {attempt + 1}/{max_retries})"
                }
                time.sleep(delay)
                continue
            else:
                yield {
                    "event": "Error",
                    "content": f"❌ Erro de conexão: Não foi possível conectar à API após {max_retries} tentativas.\n\nVerifique se o servidor está rodando em:\n{ENDPOINT}\n\nErro: {str(e)}"
                }
                return
                
        except requests.exceptions.Timeout as e:
            yield {
                "event": "Error",
                "content": f"❌ Timeout: A requisição demorou mais de 120 segundos.\n\n💡 Dica: O serviço pode estar 'dormindo' (Render gratuito). Tente novamente em alguns segundos.\n\nURL: {ENDPOINT}\n\nErro: {str(e)}"
            }
            return
        except requests.exceptions.RequestException as e:
            yield {
                "event": "Error",
                "content": f"❌ Erro na requisição: {str(e)}\n\nURL: {ENDPOINT}"
            }
            return
        except Exception as e:
            yield {
                "event": "Error",
                "content": f"❌ Erro inesperado: {str(e)}\n\nTipo: {type(e).__name__}"
            }
            return


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
        
        # Mostrar mensagem de processamento inicial
        response_placeholder.info("⏳ Processando... (A primeira requisição pode demorar mais se o serviço estiver 'dormindo')")
    
    # processamento streaming
    first_event_received = False
    try:
        for event in get_response_stream(prompt):
            event_type = event.get("event", "")
            
            # Limpar mensagem de processamento no primeiro evento válido
            if not first_event_received and event_type not in ["Error", "Retry"]:
                response_placeholder.empty()
                first_event_received = True
            
            # Mostrar mensagem de retry
            if event_type == "Retry":
                retry_msg = event.get("content", "Tentando novamente...")
                response_placeholder.warning(retry_msg)
                continue  # Continuar para próxima tentativa
            
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