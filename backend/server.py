from flask import Flask, request, jsonify
from llama_cpp import Llama
from flask_cors import CORS
import streamlit as st

app = Flask(__name__)
CORS(app)

# Load the LLaMA model
model_path = "/Users/realtobyfu/jan/models/llama3-8b-instruct/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
llm = Llama(
    model_path=model_path,
    n_gpu_layers=-1
)

# Initialize Streamlit state to store conversation history
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    mode = data.get('mode', 'qa')  # Default to Q&A mode

    # Define system messages based on mode, ensuring responses in the tone of Marcel Proust
    if mode == 'refine_prose':
        system_prompt = (
            "You are Marcel Proust, a sophisticated writer known for your elaborate and introspective style. "
            "Help refine and improve the user's prose, providing suggestions in a way that reflects your own literary voice."
        )
    elif mode == 'explore_lost_time':
        system_prompt = (
            "You are Marcel Proust, the author of 'In Search of Lost Time'. Engage with the user by providing insights "
            "or relevant passages from your work. Respond with the same depth and reflective nature characteristic of your writing."
        )
    else:  # Q&A mode
        system_prompt = (
            "You are Marcel Proust, a renowned writer. Answer the user's questions in your unique, reflective tone, "
            "drawing on your vast knowledge and introspective style."
        )

    # Append the current message to the conversation history
    if user_message:
        st.session_state.conversation_history.append({"role": "user", "content": user_message})

        # Include the system prompt at the start of the conversation history
        conversation = [{"role": "system", "content": system_prompt}] + st.session_state.conversation_history

        # Generate a response using LLaMA
        response_data = llm.create_chat_completion(
            messages=conversation
        )

        response_content = response_data['choices'][0]['message']['content']

        # Append the LLM response to the conversation history
        st.session_state.conversation_history.append({"role": "assistant", "content": response_content})

        return jsonify({'reply': response_content})

    else:
        return jsonify({'reply': 'No message received.'})

if __name__ == '__main__':
    app.run(debug=True)
