import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import pickle

class ConnectionMapper:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings = None
        self.passages = None
        
    def load_passages(self, filepath: str):
        """Load enhanced passages from JSON file"""
        print("Loading passages...")
        with open(filepath, 'r', encoding='utf-8') as f:
            self.passages = json.load(f)
        print(f"Loaded {len(self.passages)} passages")
        
    def generate_embeddings(self):
        """Generate embeddings for all passages"""
        print("Generating embeddings...")
        texts = [p['text'] for p in self.passages]
        
        # Generate embeddings in batches
        batch_size = 32
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = self.model.encode(batch, show_progress_bar=True)
            all_embeddings.extend(embeddings)
        
        self.embeddings = np.array(all_embeddings)
        print(f"Generated embeddings with shape: {self.embeddings.shape}")
        
    def find_similar_passages(self, passage_idx: int, top_k: int = 5) -> List[Tuple[int, float]]:
        """Find similar passages using cosine similarity"""
        if self.embeddings is None:
            raise ValueError("Embeddings not generated yet")
        
        # Get embedding for target passage
        target_embedding = self.embeddings[passage_idx].reshape(1, -1)
        
        # Calculate similarities
        similarities = cosine_similarity(target_embedding, self.embeddings)[0]
        
        # Get top k similar passages (excluding self)
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        
        return [(idx, similarities[idx]) for idx in similar_indices]
    
    def build_character_connections(self) -> Dict[str, List[int]]:
        """Build index of which passages contain which characters"""
        character_index = defaultdict(list)
        
        for idx, passage in enumerate(self.passages):
            characters = passage.get('metadata', {}).get('characters', [])
            for character in characters:
                character_index[character].append(idx)
        
        return dict(character_index)
    
    def build_theme_connections(self) -> Dict[str, List[int]]:
        """Build index of which passages contain which themes"""
        theme_index = defaultdict(list)
        
        for idx, passage in enumerate(self.passages):
            themes = passage.get('metadata', {}).get('themes', [])
            for theme in themes:
                theme_index[theme].append(idx)
        
        return dict(theme_index)
    
    def track_character_journey(self, character: str) -> List[Dict]:
        """Track a character's appearances throughout the work"""
        journey = []
        
        for idx, passage in enumerate(self.passages):
            characters = passage.get('metadata', {}).get('characters', [])
            if character.lower() in [c.lower() for c in characters]:
                journey.append({
                    'index': idx,
                    'book': passage['book'],
                    'chapter': passage['chapter'],
                    'themes': passage.get('metadata', {}).get('themes', []),
                    'excerpt': passage['text'][:200] + '...'
                })
        
        return journey
    
    def create_theme_progression(self, theme: str) -> List[Dict]:
        """Create a progression path for a specific theme"""
        progression = []
        
        for idx, passage in enumerate(self.passages):
            themes = passage.get('metadata', {}).get('themes', [])
            if theme in themes:
                progression.append({
                    'index': idx,
                    'book': passage['book'],
                    'chapter': passage['chapter'],
                    'related_themes': [t for t in themes if t != theme],
                    'narrative_position': passage.get('metadata', {}).get('narrative_position', {})
                })
        
        return progression
    
    def generate_reading_paths(self) -> Dict[str, List[int]]:
        """Generate different reading paths through the work"""
        paths = {}
        
        # First Timer's Path - key passages from each volume
        first_timer = []
        for volume in range(1, 8):
            volume_passages = [i for i, p in enumerate(self.passages) 
                             if p.get('volume') == volume]
            # Select passages with multiple themes and moderate difficulty
            candidates = []
            for idx in volume_passages:
                metadata = self.passages[idx].get('metadata', {})
                difficulty = metadata.get('difficulty_level', 3)
                themes = metadata.get('themes', [])
                if 2 <= difficulty <= 3 and len(themes) >= 2:
                    candidates.append(idx)
            
            # Take first 5 good candidates from each volume
            first_timer.extend(candidates[:5])
        
        paths['first_timer'] = first_timer
        
        # Memory Explorer Path
        memory_passages = []
        for idx, passage in enumerate(self.passages):
            themes = passage.get('metadata', {}).get('themes', [])
            if 'memory' in themes:
                memory_passages.append(idx)
        paths['memory_explorer'] = memory_passages[:50]  # First 50 memory passages
        
        # Character Focus Paths
        main_characters = ['swann', 'albertine', 'charlus', 'gilberte']
        for character in main_characters:
            char_journey = [p['index'] for p in self.track_character_journey(character)]
            paths[f'{character}_journey'] = char_journey[:30]  # First 30 appearances
        
        return paths
    
    def update_passage_connections(self):
        """Update each passage with its connections"""
        print("Building passage connections...")
        
        # Build indices
        character_index = self.build_character_connections()
        theme_index = self.build_theme_connections()
        
        # Update each passage
        for idx, passage in enumerate(self.passages):
            if idx % 100 == 0:
                print(f"Processing passage {idx}/{len(self.passages)}...")
            
            # Find similar passages
            similar = self.find_similar_passages(idx, top_k=5)
            
            # Find thematic connections
            themes = passage.get('metadata', {}).get('themes', [])
            theme_connections = []
            for theme in themes:
                related_indices = theme_index.get(theme, [])
                # Get 2 other passages with same theme
                for related_idx in related_indices[:3]:
                    if related_idx != idx:
                        theme_connections.append(f"{theme}_passage_{related_idx}")
            
            # Update metadata
            passage['metadata']['connections'] = {
                'related_passages': [idx for idx, _ in similar],
                'similarity_scores': [float(score) for _, score in similar],
                'theme_continuations': theme_connections
            }
    
    def save_enhanced_data(self, output_file: str):
        """Save passages with connection data"""
        print(f"Saving enhanced data to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.passages, f, indent=2, ensure_ascii=False)
    
    def save_indices(self, output_dir: str = '.'):
        """Save character and theme indices for quick lookup"""
        character_index = self.build_character_connections()
        theme_index = self.build_theme_connections()
        reading_paths = self.generate_reading_paths()
        
        indices = {
            'characters': character_index,
            'themes': theme_index,
            'reading_paths': reading_paths
        }
        
        output_file = f"{output_dir}/passage_indices.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(indices, f, indent=2)
        
        print(f"Saved indices to {output_file}")
    
    def save_embeddings(self, output_file: str = 'passage_embeddings.pkl'):
        """Save embeddings for later use"""
        if self.embeddings is not None:
            with open(output_file, 'wb') as f:
                pickle.dump(self.embeddings, f)
            print(f"Saved embeddings to {output_file}")

def main():
    """Process enhanced passages and add connections"""
    mapper = ConnectionMapper()
    
    # Load enhanced passages
    mapper.load_passages('enhanced_parsed.json')
    
    # Generate embeddings
    mapper.generate_embeddings()
    
    # Update passages with connections
    mapper.update_passage_connections()
    
    # Save everything
    mapper.save_enhanced_data('connected_parsed.json')
    mapper.save_indices()
    mapper.save_embeddings()
    
    # Print some statistics
    print("\n=== Connection Statistics ===")
    
    # Character journey example
    swann_journey = mapper.track_character_journey('swann')
    print(f"\nSwann appears in {len(swann_journey)} passages")
    if swann_journey:
        print(f"First appearance: {swann_journey[0]['book']} - {swann_journey[0]['chapter']}")
        print(f"Last appearance: {swann_journey[-1]['book']} - {swann_journey[-1]['chapter']}")
    
    # Theme progression example
    memory_progression = mapper.create_theme_progression('memory')
    print(f"\nMemory theme appears in {len(memory_progression)} passages")
    
    # Reading paths
    paths = mapper.generate_reading_paths()
    print(f"\nGenerated {len(paths)} reading paths")
    for path_name, indices in paths.items():
        print(f"  {path_name}: {len(indices)} passages")

if __name__ == "__main__":
    main()