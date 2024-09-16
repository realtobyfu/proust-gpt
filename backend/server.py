from flask import Flask, request, jsonify, session
from llama_cpp import Llama
from flask_cors import CORS
import json
import re
from sentence_transformers import SentenceTransformer
import numpy as np

app = Flask(__name__)
CORS(app)

# Secret key for managing Flask sessions (needed for session management)
app.secret_key = 'your_secret_key'

# Load the embedding model and LLaMA model

embedding_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
model_path = "/Users/realtobyfu/jan/models/llama3-8b-instruct/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
llm = Llama(
    model_path=model_path,
    n_gpu_layers=-1,
    # max_tokens=32
)

# Load the parsed data (parsed.json)
with open("parsed.json", "r", encoding="utf-8") as f:
    parsed_data = json.load(f)

# # Convert parsed passages into chunks for embedding processing
# chunks = [item["text"] for item in parsed_data]

# 1. Generate related keywords from LLaMA
def generate_keywords(query):
    prompt = f"Generate a list of up to 10 keywords (no explanations, just words) related to the following query that are likely to appear in 'In Search of Lost Time': {query}"
    response = llm.create_chat_completion(messages=[{"role": "system", "content": prompt}])
    print("generated key words:", response['choices'][0]['message']['content'].lower())
    keywords = re.findall(r'\w+', response['choices'][0]['message']['content'].lower())
    return keywords

# 2. Find passages containing keywords
def find_passages_with_keywords(keywords, parsed_data):
    relevant_passages = []
    for item in parsed_data:
        text = item["text"].lower()
        if any(keyword in text for keyword in keywords):
            relevant_passages.append(item)
    return relevant_passages

# 3. Embed and calculate similarity between query and passages
def compute_embeddings_and_retrieve(user_message, parsed_data):
    # Convert the user query and all text chunks to embeddings
    query_embedding = embedding_model.encode(user_message, normalize_embeddings=True)
    passage_embeddings = embedding_model.encode([item["text"] for item in parsed_data], normalize_embeddings=True)

    # Compute similarity using matrix multiplication
    sim_vector = np.dot(query_embedding, passage_embeddings.T)

    # Get indices of the top 2 most relevant passages
    top_k_indices = sim_vector.argsort()[::-1][:2]

    # Return the most relevant passages
    relevant_passages = [parsed_data[i] for i in top_k_indices]


    return relevant_passages

# 4. RAG retrieval logic for relevant passages based on keyword search
def rag_retrieve(user_message, source="in_search_of_lost_time"):
    # Generate keywords using LLaMA
    keywords = generate_keywords(user_message)

    # Find relevant passages using keywords
    relevant_passages = find_passages_with_keywords(keywords, parsed_data)

    # If no relevant passages found, return a message
    if not relevant_passages:
        return "No relevant passages found."

    # Compute similarity between query and passages, retrieve top 2
    top_passages = compute_embeddings_and_retrieve(user_message, relevant_passages)

    # Format and return the top passages
    return top_passages

# Function to get the conversation history from session
def get_conversation_history():
    if 'conversation_history' not in session:
        session['conversation_history'] = []
    return session['conversation_history']

# Function to update the conversation history in session
def update_conversation_history(role, content):
    conversation_history = get_conversation_history()
    conversation_history.append({"role": role, "content": content})
    session['conversation_history'] = conversation_history

# 1. Route for Refine Prose
@app.route('/api/refine_prose', methods=['POST'])
def refine_prose():
    data = request.json
    user_message = data.get('message', '')

    system_prompt = (
        "You are Marcel Proust, a sophisticated writer known for your elaborate and introspective style. "
        "Help refine and improve the user's prose, providing suggestions in a way that reflects your own literary voice."
    )

    if user_message:
        update_conversation_history("user", user_message)
        conversation = [{"role": "system", "content": system_prompt}] + get_conversation_history()

        # Generate a response using LLaMA
        response_data = llm.create_chat_completion(messages=conversation)
        response_content = response_data['choices'][0]['message']['content']

        update_conversation_history("assistant", response_content)
        return jsonify({'reply': response_content})

    return jsonify({'reply': 'No message received.'})

# 2. Route for Explore Lost Time using RAG (In Search of Lost Time)
@app.route('/api/explore_lost_time', methods=['POST'])
def explore_lost_time():
    data = request.json
    user_message = data.get('message', '')

    system_prompt = (
        "You are Marcel Proust, the author of 'In Search of Lost Time'. Engage with the user by providing insights "
        "or relevant passages from your work. "
    )

    if user_message:
        update_conversation_history("user", user_message)
        conversation = [{"role": "system", "content": system_prompt}] + get_conversation_history()

        # Retrieve passages using RAG logic
        retrieved_passages = rag_retrieve(user_message, source="in_search_of_lost_time")

        # Prepare the retrieved passage for response
        if isinstance(retrieved_passages, str):  # Handle case where no relevant passages are found
            response_content = {'passages': []}
        else:
            passages = [{"book": passage['book'], "chapter": passage['chapter'], "text": passage['text']} for passage in retrieved_passages]
            response_content = {'passages': passages}

        update_conversation_history("assistant", response_content)
        return jsonify(response_content)

    return jsonify({'reply': 'No message received.'})

# 3. Route for Q&A using RAG (general knowledge or other content)
@app.route('/api/qa', methods=['POST'])
def qa():
    data = request.json
    user_message = data.get('message', '')

    system_prompt = (
        "You are Marcel Proust, a renowned writer. Answer the user's questions in your unique, reflective tone."
    )

    if user_message:
        update_conversation_history("user", user_message)
        conversation = [{"role": "system", "content": system_prompt}] + get_conversation_history()

        # Insert your RAG logic here to retrieve relevant information from a general knowledge base or other contents
        retrieved_info = rag_retrieve(user_message, source="general_knowledge")
        response_content = f"{retrieved_info}\n\nProustGPT: {llm.create_chat_completion(messages=conversation)['choices'][0]['message']['content']}"

        update_conversation_history("assistant", response_content)
        return jsonify({'reply': response_content})

    return jsonify({'reply': 'No message received.'})

if __name__ == '__main__':
    app.run(debug=True)
