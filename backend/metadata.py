import re
import json
import spacy
import nltk
from collections import Counter
from typing import Dict, List, Any, Set
import numpy as np
from sentence_transformers import SentenceTransformer

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

class EnhancedProustParser:
    def __init__(self):
        # Initialize NLP models
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            print("Please install spacy model: python -m spacy download en_core_web_sm")
            self.nlp = None
            
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Define Proust-specific themes and keywords
        self.theme_keywords = {
            "memory": ["remember", "recall", "memory", "past", "forgotten", "reminiscence", "recollection"],
            "time": ["time", "hour", "moment", "years", "temporal", "duration", "eternity"],
            "love": ["love", "passion", "desire", "heart", "beloved", "affection", "romance"],
            "jealousy": ["jealous", "suspicion", "doubt", "torment", "obsession", "mistrust"],
            "art": ["painting", "music", "literature", "artist", "aesthetic", "beauty", "creation"],
            "society": ["salon", "aristocracy", "bourgeois", "society", "class", "reception", "dinner"],
            "sleep": ["sleep", "dream", "awake", "drowsy", "slumber", "insomnia", "bed"],
            "childhood": ["childhood", "youth", "young", "child", "boyhood", "innocence"],
            "death": ["death", "dying", "mortality", "grave", "funeral", "deceased"],
            "nature": ["flower", "tree", "garden", "landscape", "season", "weather", "hawthorn"]
        }
        
        # Literary devices patterns
        self.literary_devices = {
            "metaphor": r'\b(like|as|resembl|seem|appear)\b',
            "stream_of_consciousness": r'[;—].*[;—].*[;—]',  # Multiple clauses
            "sensory_description": r'\b(smell|taste|touch|sound|sight|fragran|odor|flavor)\b',
            "temporal_shift": r'\b(suddenly|then|meanwhile|later|before|after|when)\b'
        }
        
        # Character names (expand this list based on the work)
        self.known_characters = {
            "narrator", "marcel", "swann", "odette", "gilberte", "albertine", 
            "charlus", "guermantes", "verdurin", "saint-loup", "bergotte",
            "elstir", "vinteuil", "morel", "jupien", "françoise", "combray",
            "mamma", "grandmother", "aunt léonie"
        }
        
        # Location names
        self.known_locations = {
            "combray", "paris", "balbec", "tansonville", "guermantes",
            "méséglise", "venice", "doncières"
        }

    def extract_metadata(self, passage: Dict[str, Any], total_passages: int, 
                        current_position: int) -> Dict[str, Any]:
        """Extract enhanced metadata from a passage"""
        
        text = passage.get("text", "")
        book = passage.get("book", "")
        chapter = passage.get("chapter", "")
        
        metadata = {
            "narrative_position": self._calculate_narrative_position(
                current_position, total_passages, text
            ),
            "characters": self._extract_characters(text),
            "locations": self._extract_locations(text),
            "themes": self._extract_themes(text),
            "literary_devices": self._detect_literary_devices(text),
            "temporal_markers": self._extract_temporal_markers(text),
            "mood": self._analyze_mood(text),
            "difficulty_level": self._calculate_difficulty(text),
            "connections": {
                "related_passages": [],  # Will be filled by connection_mapper
                "theme_continuations": []
            }
        }
        
        return metadata

    def _calculate_narrative_position(self, position: int, total: int, 
                                    text: str) -> Dict[str, Any]:
        """Calculate position metrics"""
        word_count = len(text.split())
        reading_time = word_count / 250  # Average reading speed
        
        return {
            "percentage_in_work": round(position / total * 100, 2),
            "reading_time_minutes": round(reading_time, 1),
            "word_count": word_count
        }

    def _extract_characters(self, text: str) -> List[str]:
        """Extract character names from text"""
        characters = set()
        
        # Use known characters
        text_lower = text.lower()
        for character in self.known_characters:
            if character in text_lower:
                characters.add(character)
        
        # Use NER if available
        if self.nlp:
            doc = self.nlp(text[:1000])  # Limit for performance
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name = ent.text.lower()
                    if len(name) > 2:  # Filter out initials
                        characters.add(name)
        
        return list(characters)

    def _extract_locations(self, text: str) -> List[str]:
        """Extract location names from text"""
        locations = set()
        
        # Use known locations
        text_lower = text.lower()
        for location in self.known_locations:
            if location in text_lower:
                locations.add(location)
        
        # Use NER if available
        if self.nlp:
            doc = self.nlp(text[:1000])
            for ent in doc.ents:
                if ent.label_ in ["LOC", "GPE"]:
                    locations.add(ent.text.lower())
        
        return list(locations)

    def _extract_themes(self, text: str) -> List[str]:
        """Extract themes based on keyword matching"""
        text_lower = text.lower()
        themes = []
        
        for theme, keywords in self.theme_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                themes.append(theme)
        
        return themes

    def _detect_literary_devices(self, text: str) -> List[str]:
        """Detect literary devices in the text"""
        devices = []
        
        for device, pattern in self.literary_devices.items():
            if re.search(pattern, text, re.IGNORECASE):
                devices.append(device)
        
        # Check for long sentences (Proustian style)
        sentences = text.split('.')
        if any(len(s.split()) > 50 for s in sentences):
            devices.append("long_sentence")
        
        return devices

    def _extract_temporal_markers(self, text: str) -> List[str]:
        """Extract temporal context clues"""
        markers = []
        
        temporal_patterns = {
            "childhood": r'\b(child|young|boy|girl|youth)\b',
            "past": r'\b(ago|former|previous|once|used to)\b',
            "present": r'\b(now|today|current|present)\b',
            "night": r'\b(night|evening|midnight|dark)\b',
            "morning": r'\b(morning|dawn|sunrise|awake)\b'
        }
        
        for marker, pattern in temporal_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                markers.append(marker)
        
        return markers

    def _analyze_mood(self, text: str) -> List[str]:
        """Simple mood analysis based on keywords"""
        moods = []
        
        mood_keywords = {
            "nostalgic": ["remember", "past", "childhood", "once"],
            "melancholic": ["sad", "sorrow", "grief", "tears"],
            "dreamlike": ["dream", "float", "hazy", "unclear"],
            "anxious": ["worry", "anxious", "nervous", "fear"],
            "romantic": ["love", "passion", "heart", "desire"],
            "contemplative": ["think", "ponder", "reflect", "consider"]
        }
        
        text_lower = text.lower()
        for mood, keywords in mood_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                moods.append(mood)
        
        return moods

    def _calculate_difficulty(self, text: str) -> int:
        """Calculate reading difficulty (1-5 scale)"""
        sentences = text.split('.')
        avg_sentence_length = np.mean([len(s.split()) for s in sentences if s.strip()])
        
        # Complex vocabulary check
        complex_words = len([w for w in text.split() if len(w) > 10])
        
        # Calculate difficulty score
        if avg_sentence_length > 40 or complex_words > 20:
            return 5
        elif avg_sentence_length > 30 or complex_words > 15:
            return 4
        elif avg_sentence_length > 20 or complex_words > 10:
            return 3
        elif avg_sentence_length > 15 or complex_words > 5:
            return 2
        else:
            return 1

    def process_file(self, input_file: str, output_file: str):
        """Process the parsed.json file and add metadata"""
        
        print("Loading parsed data...")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total_passages = len(data)
        print(f"Processing {total_passages} passages...")
        
        # Process each passage
        for i, passage in enumerate(data):
            if i % 100 == 0:
                print(f"Processing passage {i}/{total_passages}...")
            
            metadata = self.extract_metadata(passage, total_passages, i)
            passage['metadata'] = metadata
        
        # Save enhanced data
        print(f"Saving enhanced data to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print("Processing complete!")
        
        # Print statistics
        self._print_statistics(data)

    def _print_statistics(self, data: List[Dict]):
        """Print statistics about the processed data"""
        
        all_themes = []
        all_characters = []
        all_locations = []
        
        for passage in data:
            metadata = passage.get('metadata', {})
            all_themes.extend(metadata.get('themes', []))
            all_characters.extend(metadata.get('characters', []))
            all_locations.extend(metadata.get('locations', []))
        
        print("\n=== Processing Statistics ===")
        print(f"Total passages: {len(data)}")
        print(f"\nTop themes: {Counter(all_themes).most_common(10)}")
        print(f"\nTop characters: {Counter(all_characters).most_common(10)}")
        print(f"\nTop locations: {Counter(all_locations).most_common(10)}")

if __name__ == "__main__":
    parser = EnhancedProustParser()
    parser.process_file("parsed.json", "enhanced_parsed.json")