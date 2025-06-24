import streamlit as st
import time
import os
import sqlite3
from typing import Generator
from hashlib import sha256

# Importar la biblioteca de Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Configuración de la página
st.set_page_config(
    page_title="Proyecto remo-bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados para mejorar la apariencia
st.markdown("""
<style>
.chat-message {
    padding: 1.5rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    display: flex;
}
.chat-message.user {
    background-color: #2b313e;
}
.chat-message.assistant {
    background-color: #475063;
}
.chat-message .avatar {
    width: 20%;
}
.chat-message .avatar img {
    max-width: 78px;
    max-height: 78px;
    border-radius: 50%;
    object-fit: cover;
}
.chat-message .message {
    width: 80%;
    padding: 0 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# Inicializar la base de datos
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  chat_name TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (username) REFERENCES users(username))''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (chat_id) REFERENCES chat_history(id))''')
    conn.commit()
    conn.close()

# Función para registrar usuario
def register_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Capitalizar el nombre de usuario
    username = username.capitalize()
    
    # Verificar si el usuario ya existe
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    if c.fetchone() is not None:
        conn.close()
        return False
    
    # Hashear la contraseña antes de guardarla
    hashed_password = sha256(password.encode()).hexdigest()
    c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
    conn.commit()
    conn.close()
    return True

# Función para verificar credenciales
def verify_credentials(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Capitalizar el nombre de usuario
    username = username.capitalize()
    
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result is None:
        return False
    
    hashed_password = sha256(password.encode()).hexdigest()
    return hashed_password == result[0]

# Inicializar la base de datos
init_db()

# Inicializar variables de sesión si no existen
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "interface_ready" not in st.session_state:
    st.session_state.interface_ready = False

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
    
if "chat_list" not in st.session_state:
    st.session_state.chat_list = []
    
# Función para cerrar sesión
def logout():
    st.session_state.user_name = ""
    st.session_state.interface_ready = False
    st.session_state.messages = []
    st.session_state.current_chat_id = None
    st.session_state.chat_list = []

# Pantalla de login/registro
if not st.session_state.user_name or not st.session_state.interface_ready:
    st.title("Bienvenido a Proyecto remo-bot")
    
    # Tabs para login y registro
    tab1, tab2 = st.tabs(["Iniciar sesión", "Registrarse"])
    
    with tab1:
        st.markdown("""Por favor, ingresa tus credenciales para acceder.""")
        login_user = st.text_input("Usuario", key="login_user")
        login_pass = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Iniciar sesión"):
            if verify_credentials(login_user, login_pass):
                st.session_state.user_name = login_user.capitalize()
                st.session_state.interface_ready = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario no existe")
    
    with tab2:
        st.markdown("""Regístrate para acceder al chatbot""")
        reg_user = st.text_input("Usuario", key="reg_user")
        reg_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        
        if st.button("Registrarse"):
            if reg_user.strip() and reg_pass.strip():
                if register_user(reg_user, reg_pass):
                    st.success("Registro exitoso. Por favor inicia sesión.")
                else:
                    st.error("El usuario ya existe")
            else:
                st.error("Por favor completa todos los campos")
    
    # Detener la ejecución del resto del código si no se ha autenticado
    st.stop()

# Título y descripción de la aplicación (solo se muestra después de ingresar el nombre)
col1, col2 = st.columns([6, 1])
with col1:
    st.title("Proyecto remo-bot")
    st.markdown(f"""Bienvenido {st.session_state.user_name}""")
with col2:
    if st.button("Cerrar sesión", key="logout_button"):
        logout()
        st.rerun()

# Funciones para gestionar el historial de chats
def save_chat_to_db(username, messages, chat_name=None):
    """Guarda un chat en la base de datos."""
    if not messages:
        return None
        
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Si no se proporciona un nombre para el chat, usar la fecha actual
    if not chat_name:
        chat_name = f"Chat {time.strftime('%d/%m/%Y %H:%M')}"
    
    # Insertar el chat en la tabla chat_history
    c.execute("INSERT INTO chat_history (username, chat_name) VALUES (?, ?)", 
              (username, chat_name))
    chat_id = c.lastrowid
    
    # Insertar los mensajes en la tabla chat_messages
    for msg in messages:
        c.execute("INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
                  (chat_id, msg["role"], msg["content"]))
    
    conn.commit()
    conn.close()
    return chat_id

def load_chat_list(username):
    """Carga la lista de chats de un usuario con la última pregunta del usuario."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Primero obtenemos los IDs de los chats del usuario
    c.execute("SELECT id, chat_name, created_at FROM chat_history WHERE username = ? ORDER BY created_at DESC", 
              (username,))
    chats_basic = c.fetchall()
    
    # Lista para almacenar los resultados finales
    chats = []
    
    # Para cada chat, buscamos la última pregunta del usuario
    for chat_id, chat_name, created_at in chats_basic:
        # Buscar el último mensaje del usuario en este chat
        c.execute("""SELECT content FROM chat_messages 
                   WHERE chat_id = ? AND role = 'user' 
                   ORDER BY timestamp DESC LIMIT 1""", (chat_id,))
        last_question = c.fetchone()
        
        # Si encontramos una pregunta, la usamos como nombre del chat
        if last_question and last_question[0]:
            # Truncar la pregunta si es muy larga
            display_name = last_question[0][:30] + '...' if len(last_question[0]) > 30 else last_question[0]
        else:
            # Si no hay preguntas, usamos el nombre original del chat
            display_name = chat_name
            
        chats.append((chat_id, display_name, created_at))
    
    conn.close()
    return chats

def load_chat_messages(chat_id):
    """Carga los mensajes de un chat específico."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE chat_id = ? ORDER BY timestamp", 
              (chat_id,))
    messages = [{"role": role, "content": content} for role, content in c.fetchall()]
    conn.close()
    return messages

# Cargar la lista de chats del usuario
st.session_state.chat_list = load_chat_list(st.session_state.user_name)

# Sidebar para gestionar los chats
with st.sidebar:
    st.header("Mis conversaciones")
    
    # Botón para crear un nuevo chat
    if st.button("Nuevo chat"):
        st.session_state.messages = []
        st.session_state.current_chat_id = None
        st.rerun()
    
    # Mostrar la lista de chats existentes
    if st.session_state.chat_list:
        st.subheader("Historial de chats")
        for chat_id, display_name, created_at in st.session_state.chat_list:
            # Formatear la fecha para mostrarla como tooltip
            try:
                # Intentar convertir la fecha si es un timestamp (número)
                if isinstance(created_at, (int, float)):
                    fecha_formateada = time.strftime("%d/%m/%Y %H:%M", time.localtime(created_at))
                else:
                    # Si es una cadena de texto (formato SQLite), mostrarla directamente
                    fecha_formateada = created_at
            except Exception:
                # En caso de error, usar un formato genérico
                fecha_formateada = str(created_at)
            # Mostrar el botón con la última pregunta y un tooltip con la fecha
            if st.button(f"{display_name}", key=f"chat_{chat_id}", help=f"Creado: {fecha_formateada}"):
                st.session_state.current_chat_id = chat_id
                st.session_state.messages = load_chat_messages(chat_id)
                st.rerun()

# Función para generar respuestas usando Groq API
def generate_groq_response(prompt, model="llama-3.3-70b-versatile") -> Generator[str, None, None]:
    """Genera respuestas utilizando la API de Groq.

    Args:
        prompt (str): El mensaje del usuario.
        model (str): El modelo de Groq a utilizar.

    Yields:
        str: Cada fragmento de la respuesta generada.
    """
    try:
        # Obtener la API key de Groq desde las variables de entorno o secrets
        api_key = st.secrets.get("api_keys", {}).get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        
        if not api_key:
            error_msg = "⚠️ API key de Groq no configurada. Por favor, configura GROQ_API_KEY en tus secrets o variables de entorno."
            for char in error_msg:
                yield char
                time.sleep(0.01)
            return
            
        # Inicializar el cliente de Groq
        client = Groq(api_key=api_key)
        
        # Realizar la solicitud a la API
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model=model,
            stream=True  # Habilitar streaming para mostrar la respuesta gradualmente
        )
        
        # Procesar la respuesta en streaming
        for chunk in chat_completion:
            content = chunk.choices[0].delta.content
            if content:
                yield content
                time.sleep(0.005)  # Pequeña pausa para simular escritura natural
                
    except Exception as e:
        error_msg = f"⚠️ Error al conectar con Groq API: {str(e)}"
        for char in error_msg:
            yield char
            time.sleep(0.01)

# Función para simular la generación de respuestas del chatbot
def generate_chat_responses(prompt, selected_model="Modelo básico") -> Generator[str, None, None]:
    """Genera respuestas de chat, mostrando carácter por carácter.

    Args:
        prompt (str): El mensaje del usuario.
        selected_model (str): El modelo seleccionado por el usuario.

    Yields:
        str: Cada fragmento de la respuesta generada.
    """
    # Si se selecciona Groq y está disponible, usar la API de Groq
    if selected_model == "Groq" and GROQ_AVAILABLE:
        yield from generate_groq_response(prompt)
        return
        
    # Respuestas predefinidas basadas en palabras clave (para el modelo básico)
    responses = {
        "hola": "¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        "ayuda": "Puedo ayudarte con información, responder preguntas o simplemente conversar. ¿Qué necesitas?",
        "gracias": "¡De nada! Estoy aquí para ayudarte. ¿Hay algo más en lo que pueda asistirte?",
        "adiós": "¡Hasta luego! Ha sido un placer ayudarte. Vuelve pronto si necesitas algo más."
    }
    
    # Respuesta por defecto
    if selected_model == "Groq" and not GROQ_AVAILABLE:
        response = "⚠️ La biblioteca de Groq no está instalada. Por favor, instala 'groq' con pip para usar este modelo."
    else:
        response = "Gracias por tu mensaje. Como chatbot de demostración, tengo respuestas limitadas. En una implementación real, aquí se conectaría con un modelo de lenguaje como MistralAI, Groq u Ollama."
    
    # Buscar palabras clave en el prompt (solo para el modelo básico)
    for key, value in responses.items():
        if key in prompt.lower():
            response = value
            break
    
    # Simular escritura carácter por carácter
    for char in response:
        yield char
        time.sleep(0.01)  # Pequeña pausa para simular escritura

# Inicializar el historial de chat si no existe
if "messages" not in st.session_state:
    st.session_state.messages = []

# Configuración fija: modelo, amabilidad y creatividad
MODEL = "Groq"
FRIENDLINESS = 40
CREATIVITY = 20

# Área principal para el chat actual
st.subheader("Nuevo chat")

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada de chat del usuario
prompt = st.chat_input("¿Con qué puedo ayudarte?")

# Procesar el mensaje del usuario
if prompt:
    # Mostrar el mensaje del usuario
    st.chat_message("user").markdown(prompt)
    
    # Agregar mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Generar y mostrar la respuesta del asistente
    with st.chat_message("assistant"):
        response_generator = generate_chat_responses(prompt, MODEL)
        full_response = st.write_stream(response_generator)
    
    # Agregar respuesta del asistente al historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Guardar la conversación en la base de datos si hay mensajes
    if st.session_state.messages and len(st.session_state.messages) >= 2:
        if st.session_state.current_chat_id is None:
            # Es una nueva conversación, guardarla en la base de datos
            chat_id = save_chat_to_db(st.session_state.user_name, st.session_state.messages)
            if chat_id:
                st.session_state.current_chat_id = chat_id
                # Actualizar la lista de chats
                st.session_state.chat_list = load_chat_list(st.session_state.user_name)
        else:
            # Es una conversación existente, actualizar los mensajes
            # Primero eliminar los mensajes anteriores
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("DELETE FROM chat_messages WHERE chat_id = ?", (st.session_state.current_chat_id,))
            conn.commit()
            
            # Luego insertar los mensajes actualizados
            for msg in st.session_state.messages:
                c.execute("INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
                          (st.session_state.current_chat_id, msg["role"], msg["content"]))
            conn.commit()
            conn.close()

# Botón para guardar la conversación actual con un nombre personalizado
if st.session_state.messages and len(st.session_state.messages) >= 2:
    with st.expander("Guardar esta conversación"):
        chat_name = st.text_input("Nombre para esta conversación:", 
                                 value=f"Chat {time.strftime('%d/%m/%Y %H:%M')}")
        if st.button("Guardar conversación"):
            chat_id = save_chat_to_db(st.session_state.user_name, st.session_state.messages, chat_name)
            if chat_id:
                st.session_state.current_chat_id = chat_id
                st.session_state.chat_list = load_chat_list(st.session_state.user_name)
                st.success(f"Conversación guardada como: {chat_name}")
                st.rerun()

# Fin de la aplicación