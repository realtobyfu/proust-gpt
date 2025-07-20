from flask import Flask, request, jsonify, session
from flask_cors import CORS
import json
import re
import numpy as np
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')

# Load models
embedding_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
model_path = "/path/to/your/llama/model/or/gguf"
llm = Llama(
    model_path=model_path,
    n_gpu_layers=-1,
    n_ctx=2048,
)

# Load enhanced data
try:
    with open("parsed_enhanced.json", "r", encoding="utf-8") as f:
        parsed_data = json.load(f)
except FileNotFoundError:
    # Fallback to original if enhanced version doesn't exist
    with open("parsed.json", "r", encoding="utf-8") as f:
        parsed_data = json.load(f)

# Load reading paths
with open("reading_paths.json", "r", encoding="utf-8") as f:
    reading_paths_data = json.load(f)

# ========== Session Management ==========

def init_user_session():
    """Initialize user session with progress tracking."""
    if 'user_id' not in session:
        session['user_id'] = f"user_{datetime.now().timestamp()}"
    
    if 'progress' not in session:
        session['progress'] = {
            'passages_read': [],
            'current_path': None,
            'path_progress': {},
            'bookmarks': [],
            'reading_stats': {
                'total_time': 0,
                'volumes_progress': {str(i): 0 for i in range(1, 8)},
                'themes_explored': {}
            }
        }

def update_reading_progress(passage_id: str, reading_time: int = 0):
    """Update user's reading progress."""
    init_user_session()
    
    progress = session['progress']
    
    # Add to passages read
    if passage_id not in progress['passages_read']:
        progress['passages_read'].append(passage_id)
    
    # Update reading time
    progress['reading_stats']['total_time'] += reading_time
    
    # Update volume progress if passage has metadata
    passage = next((p for p in parsed_data if str(p.get('index')) == passage_id), None)
    if passage and 'metadata' in passage:
        volume = str(passage.get('volume', 1))
        progress['reading_stats']['volumes_progress'][volume] += 1
        
        # Update themes explored
        for theme in passage['metadata'].get('themes', []):
            theme_name = theme['name']
            if theme_name not in progress['reading_stats']['themes_explored']:
                progress['reading_stats']['themes_explored'][theme_name] = 0
            progress['reading_stats']['themes_explored'][theme_name] += 1
    
    session.modified = True

# ========== Enhanced RAG Functions ==========

def generate_keywords(query: str) -> List[str]:
    """Generate keywords using LLaMA for the user query."""
    prompt = f"""Generate a list of up to 10 keywords related to this query about Proust's 'In Search of Lost Time': "{query}"
    
    Return only keywords, no explanations. Focus on:
    - Character names
    - Place names  
    - Key themes (memory, time, love, etc.)
    - Specific objects or scenes
    
    Keywords:"""
    
    response = llm(prompt, max_tokens=100, temperature=0.7)
    keywords = re.findall(r'\w+', response['choices'][0]['text'].lower())
    return keywords[:10]

def context_aware_retrieval(query: str, mode: str = "explore", context: Dict = None) -> List[Dict]:
    """Enhanced retrieval with context awareness."""
    # Generate keywords
    keywords = generate_keywords(query)
    
    # Find passages with keywords
    relevant_passages = []
    for passage in parsed_data:
        text = passage.get("text", "").lower()
        if any(kw in text for kw in keywords):
            relevant_passages.append(passage)
    
    if not relevant_passages:
        relevant_passages = parsed_data[:20]  # Fallback
    
    # Compute embeddings
    query_embedding = embedding_model.encode(query, normalize_embeddings=True)
    passage_embeddings = embedding_model.encode(
        [p.get("text", "") for p in relevant_passages], 
        normalize_embeddings=True
    )
    
    # Calculate similarity scores
    similarities = np.dot(query_embedding, passage_embeddings.T)
    
    # Apply context-aware ranking
    if context and 'current_path' in context:
        # Boost passages related to current reading path
        path_boost = apply_path_context_boost(relevant_passages, context['current_path'])
        similarities = similarities * 0.7 + path_boost * 0.3
    
    # Consider user's reading history
    if session.get('progress', {}).get('passages_read'):
        history_boost = apply_reading_history_boost(relevant_passages)
        similarities = similarities * 0.8 + history_boost * 0.2
    
    # Get top passages
    top_indices = similarities.argsort()[::-1][:5]
    top_passages = [relevant_passages[i] for i in top_indices]
    
    # Enhance with metadata
    enhanced_passages = []
    for i, passage in enumerate(top_passages):
        enhanced = {
            **passage,
            'relevance_score': float(similarities[top_indices[i]]),
            'retrieval_context': {
                'query': query,
                'matched_keywords': [kw for kw in keywords if kw in passage.get('text', '').lower()],
                'ranking_factors': ['similarity', 'context', 'history'] if context else ['similarity']
            }
        }
        enhanced_passages.append(enhanced)
    
    return enhanced_passages

def apply_path_context_boost(passages: List[Dict], current_path: str) -> np.ndarray:
    """Apply relevance boost based on current reading path."""
    boost_scores = np.zeros(len(passages))
    
    path_info = reading_paths_data['paths'].get(current_path, {})
    if not path_info:
        return boost_scores
    
    # Boost passages that match path themes or characters
    for i, passage in enumerate(passages):
        if 'metadata' in passage:
            # Theme matching
            passage_themes = {t['name'].lower() for t in passage['metadata'].get('themes', [])}
            path_themes = {path_info.get('theme_focus', '').lower()}
            
            if passage_themes & path_themes:
                boost_scores[i] += 0.5
            
            # Character matching
            if 'character_focus' in path_info:
                if path_info['character_focus'] in passage['metadata'].get('characters', []):
                    boost_scores[i] += 0.5
    
    return boost_scores

def apply_reading_history_boost(passages: List[Dict]) -> np.ndarray:
    """Apply boost to connect with previously read passages."""
    boost_scores = np.zeros(len(passages))
    read_passages = set(session['progress']['passages_read'])
    
    for i, passage in enumerate(passages):
        passage_id = str(passage.get('index', ''))
        
        # Slight penalty for already read passages
        if passage_id in read_passages:
            boost_scores[i] -= 0.2
        
        # Boost passages from the same volume as recently read
        if len(read_passages) > 0:
            recent_volumes = get_recent_volumes(read_passages)
            if passage.get('volume') in recent_volumes:
                boost_scores[i] += 0.3
    
    return boost_scores

def get_recent_volumes(read_passages: set) -> set:
    """Get volumes from recently read passages."""
    recent_volumes = set()
    for passage_id in list(read_passages)[-10:]:  # Last 10 read
        passage = next((p for p in parsed_data if str(p.get('index')) == passage_id), None)
        if passage:
            recent_volumes.add(passage.get('volume'))
    return recent_volumes

# ========== API Endpoints ==========

@app.route('/api/explore_lost_time', methods=['POST'])
def explore_lost_time():
    """Enhanced explore endpoint with context awareness."""
    init_user_session()
    
    data = request.json
    query = data.get('query', '')
    context = data.get('context', {})
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    try:
        # Get context-aware passages
        passages = context_aware_retrieval(query, mode="explore", context=context)
        
        # Update reading progress for returned passages
        for passage in passages:
            update_reading_progress(str(passage.get('index', '')))
        
        # Generate contextual response
        response_prompt = f"""Based on these passages from Proust about "{query}", provide a brief introduction (2-3 sentences) that helps the reader understand the context and significance of these passages.

Do not summarize the passages, but rather explain why they matter in Proust's work."""
        
        response = llm(response_prompt, max_tokens=150, temperature=0.7)
        intro_text = response['choices'][0]['text'].strip()
        
        return jsonify({
            'passages': passages,
            'introduction': intro_text,
            'session_info': {
                'passages_read_count': len(session['progress']['passages_read']),
                'current_path': session['progress'].get('current_path')
            }
        })
        
    except Exception as e:
        print(f"Error in explore_lost_time: {e}")
        return jsonify({'error': 'Failed to retrieve passages'}), 500

@app.route('/api/reading_paths', methods=['GET'])
def get_reading_paths():
    """Get available reading paths for the user."""
    init_user_session()
    
    paths = reading_paths_data['paths']
    user_progress = session['progress']
    
    # Add user progress info to each path
    enhanced_paths = {}
    for path_id, path_info in paths.items():
        enhanced_paths[path_id] = {
            **path_info,
            'user_progress': user_progress['path_progress'].get(path_id, {
                'started': False,
                'completed_modules': 0,
                'total_modules': len(path_info.get('modules', []))
            }),
            'is_unlocked': check_path_unlocked(path_id, user_progress)
        }
    
    return jsonify({
        'paths': enhanced_paths,
        'current_path': user_progress.get('current_path')
    })

@app.route('/api/reading_paths/<path_id>/start', methods=['POST'])
def start_reading_path(path_id):
    """Start or resume a reading path."""
    init_user_session()
    
    if path_id not in reading_paths_data['paths']:
        return jsonify({'error': 'Invalid path ID'}), 404
    
    # Check if path is unlocked
    if not check_path_unlocked(path_id, session['progress']):
        return jsonify({'error': 'Path not yet unlocked'}), 403
    
    # Set current path
    session['progress']['current_path'] = path_id
    
    # Initialize path progress if needed
    if path_id not in session['progress']['path_progress']:
        session['progress']['path_progress'][path_id] = {
            'started': True,
            'started_date': datetime.now().isoformat(),
            'completed_modules': 0,
            'current_module': 0
        }
    
    session.modified = True
    
    # Get first/current module
    path_info = reading_paths_data['paths'][path_id]
    current_module_index = session['progress']['path_progress'][path_id]['current_module']
    
    if current_module_index < len(path_info.get('modules', [])):
        current_module = path_info['modules'][current_module_index]
        
        # Get passage for current module
        passages = context_aware_retrieval(
            query=json.dumps(current_module.get('search_criteria', {})),
            mode="path",
            context={'current_path': path_id}
        )
        
        return jsonify({
            'path': path_info,
            'current_module': current_module,
            'module_index': current_module_index,
            'passages': passages[:1] if passages else [],  # Return best match
            'progress': session['progress']['path_progress'][path_id]
        })
    
    return jsonify({'message': 'Path completed!', 'path': path_info})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get user's reading progress and statistics."""
    init_user_session()
    
    progress = session['progress']
    
    # Calculate additional stats
    total_passages = len(progress['passages_read'])
    total_volumes = sum(1 for v, count in progress['reading_stats']['volumes_progress'].items() if count > 0)
    
    # Calculate streaks (simplified)
    current_streak = calculate_reading_streak()
    
    return jsonify({
        'stats': {
            'passages_read': total_passages,
            'reading_time': progress['reading_stats']['total_time'],
            'volumes_touched': total_volumes,
            'current_streak': current_streak,
            'favorite_themes': get_top_themes(progress['reading_stats']['themes_explored'], 3)
        },
        'volume_progress': progress['reading_stats']['volumes_progress'],
        'paths': progress['path_progress'],
        'bookmarks': progress['bookmarks']
    })

def check_path_unlocked(path_id: str, user_progress: Dict) -> bool:
    """Check if a reading path is unlocked for the user."""
    unlock_rules = reading_paths_data.get('progression_rules', {}).get('unlock_criteria', {})
    
    if path_id not in unlock_rules:
        return True  # No restrictions
    
    criteria = unlock_rules[path_id]
    
    # Check required completions
    if 'required_completion' in criteria:
        for required_path in criteria['required_completion']:
            if required_path not in user_progress['path_progress']:
                return False
            if user_progress['path_progress'][required_path].get('completed_modules', 0) == 0:
                return False
    
    # Check minimum passages read
    if 'min_passages_read' in criteria:
        if len(user_progress['passages_read']) < criteria['min_passages_read']:
            return False
    
    return True

def calculate_reading_streak() -> int:
    """Calculate current reading streak (simplified)."""
    # This is a simplified version - in production, you'd track daily activity
    return len(session.get('progress', {}).get('passages_read', [])) // 5

def get_top_themes(themes_dict: Dict[str, int], limit: int = 3) -> List[str]:
    """Get top explored themes."""
    sorted_themes = sorted(themes_dict.items(), key=lambda x: x[1], reverse=True)
    return [theme for theme, _ in sorted_themes[:limit]]

# ========== Writer's Studio Endpoints ==========

@app.route('/api/writing_techniques', methods=['GET'])
def get_writing_techniques():
    """Get Proust's writing techniques with examples."""
    techniques = {
        'extended_metaphor': {
            'name': 'Extended Metaphor',
            'description': 'Proust develops metaphors over many sentences, exploring every facet',
            'example_search': ['metaphor', 'like', 'as though', 'resembled'],
            'exercise': 'Describe a simple object (e.g., a cup of coffee) using an extended metaphor that unfolds over at least 5 sentences.'
        },
        'sensory_memory': {
            'name': 'Sensory Memory Triggers',
            'description': 'Physical sensations that unlock vast memories',
            'example_search': ['taste', 'smell', 'touch', 'madeleine', 'tea'],
            'exercise': 'Write about a childhood memory triggered by a specific smell or taste.'
        },
        'temporal_layers': {
            'name': 'Temporal Layering',
            'description': 'Multiple time periods existing simultaneously in one scene',
            'example_search': ['years later', 'remembered', 'time', 'past', 'present'],
            'exercise': 'Describe a place as it exists in three different time periods within a single paragraph.'
        }
    }
    
    return jsonify({'techniques': techniques})

@app.route('/api/analyze_writing', methods=['POST'])
def analyze_writing():
    """Analyze user's writing for Proustian elements."""
    data = request.json
    user_text = data.get('text', '')
    technique = data.get('technique', '')
    
    if not user_text:
        return jsonify({'error': 'No text provided'}), 400
    
    # Simple analysis
    analysis = {
        'word_count': len(user_text.split()),
        'sentence_count': len(re.split(r'[.!?]+', user_text)),
        'avg_sentence_length': len(user_text.split()) / max(1, len(re.split(r'[.!?]+', user_text))),
        'complexity_score': calculate_text_complexity(user_text)
    }
    
    # Generate feedback using LLM
    feedback_prompt = f"""Analyze this text written in Proust's style, focusing on the technique "{technique}":

"{user_text}"

Provide constructive feedback on:
1. How well it captures Proust's style
2. Specific strengths
3. Areas for improvement
4. One specific suggestion

Keep feedback encouraging and specific."""
    
    response = llm(feedback_prompt, max_tokens=300, temperature=0.7)
    
    analysis['feedback'] = response['choices'][0]['text'].strip()
    analysis['technique_score'] = assess_technique_usage(user_text, technique)
    
    return jsonify(analysis)

def calculate_text_complexity(text: str) -> float:
    """Calculate text complexity score."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return 0.5
    
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
    complexity = min(avg_sentence_length / 40, 1.0)
    
    return round(complexity, 2)

def assess_technique_usage(text: str, technique: str) -> float:
    """Assess how well the text uses a specific technique."""
    # Simplified scoring - in production, this would be more sophisticated
    score = 0.5  # Base score
    
    if technique == 'extended_metaphor':
        if 'like' in text or 'as though' in text or 'resembled' in text:
            score += 0.2
        if len(text) > 500:  # Rewards length for extended metaphors
            score += 0.2
    
    elif technique == 'sensory_memory':
        sensory_words = ['taste', 'smell', 'touch', 'feel', 'hear', 'see']
        matches = sum(1 for word in sensory_words if word in text.lower())
        score += min(matches * 0.1, 0.4)
    
    elif technique == 'temporal_layers':
        temporal_words = ['then', 'now', 'before', 'after', 'remembered', 'years']
        matches = sum(1 for word in temporal_words if word in text.lower())
        score += min(matches * 0.1, 0.4)
    
    return min(score, 1.0)

if __name__ == '__main__':
    app.run(debug=True, port=5000)