from flask import Flask, request, jsonify, session
from flask_cors import CORS
import json
import re
import numpy as np
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'

# 1. Load embedding model & LLaMA
embedding_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
model_path = "/path/to/your/llama/model/or/gguf"
llm = Llama(
    model_path=model_path,
    n_gpu_layers=-1,
    # other parameters...
)

# 2. Load your Proust data
with open("parsed.json", "r", encoding="utf-8") as f:
    parsed_data = json.load(f)

# ========== Utility RAG Functions ==========

def generate_keywords(query):
    """Generate up to 10 keywords from LLaMA for the user query."""
    prompt = f"Generate a list of up to 10 keywords (no explanations) related to the following query likely to appear in 'In Search of Lost Time': {query}"
    response = llm.create_chat_completion(messages=[{"role": "system", "content": prompt}])
    keywords = re.findall(r'\w+', response['choices'][0]['message']['content'].lower())
    return keywords

def find_passages_with_keywords(keywords, parsed_data):
    """Return all passages that contain at least one keyword."""
    relevant_passages = []
    for item in parsed_data:
        text = item["text"].lower()
        if any(kw in text for kw in keywords):
            relevant_passages.append(item)
    return relevant_passages

def compute_embeddings_and_retrieve(user_message, passages):
    query_embedding = embedding_model.encode(user_message, normalize_embeddings=True)
    passage_embeddings = embedding_model.encode([p["text"] for p in passages], normalize_embeddings=True)
    # simple dot-product similarity
    sim_vector = np.dot(query_embedding, passage_embeddings.T)
    # get top 2
    top_k_indices = sim_vector.argsort()[::-1][:2]
    top_passages = [passages[i] for i in top_k_indices]
    return top_passages

def rag_retrieve(user_message):
    """Combine steps to do keyword generation + retrieval from data."""
    keywords = generate_keywords(user_message)
    relevant_passages = find_passages_with_keywords(keywords, parsed_data)
    if not relevant_passages:
        return []
    # then rank them by embedding similarity
    top_passages = compute_embeddings_and_retrieve(user_message, relevant_passages)
    return top_passages

# ========== Routes ==========

@app.route('/api/explore_lost_time', methods=['POST'])
def explore_lost_time():
    """RAG mode: user asks about Proust's text; we retrieve relevant passages."""
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'passages': []})

    # 1. RAG retrieval
    retrieved_passages = rag_retrieve(user_message)

    # 2. Return them in JSON
    #   (We won't do a fancy LLM summary here, just return the passages to the frontend.)
    passages = []
    for passage in retrieved_passages:
        passages.append({
            "book": passage['book'],
            "chapter": passage['chapter'],
            "text": passage['text']
        })

    return jsonify({'passages': passages})


@app.route('/api/reflect', methods=['POST'])
def reflect_on_day():
    """
    A simpler mode: "Reflect on your day" with a system prompt
    that encourages introspection in a Proustian style.
    """
    data = request.json
    user_message = data.get('message', '')

    system_prompt = (
        "You are Marcel Proust, a wise and reflective conversationalist. "
        "You help the user reflect on their day, offering gentle, introspective questions "
        "and observations in your signature style."
    )

    if not user_message:
        return jsonify({'reply': 'No message received.'})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    response_data = llm.create_chat_completion(messages=messages)
    response_content = response_data['choices'][0]['message']['content']

    return jsonify({'reply': response_content})


if __name__ == '__main__':
    app.run(debug=True)
