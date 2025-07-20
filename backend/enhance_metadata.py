import json
import re
from typing import List, Dict, Any
from collections import defaultdict

# Volume mapping for Proust's work
VOLUME_INFO = {
    1: {"title": "Swann's Way", "parts": ["Combray", "Swann in Love", "Place Names: The Name"]},
    2: {"title": "Within a Budding Grove", "parts": ["Madame Swann at Home", "Place Names: The Place"]},
    3: {"title": "The Guermantes Way", "parts": ["Part One", "Part Two"]},
    4: {"title": "Sodom and Gomorrah", "parts": ["Part One", "Part Two"]},
    5: {"title": "The Captive", "parts": ["Part One", "Part Two"]},
    6: {"title": "The Fugitive", "parts": ["Albertine Gone", "Grief and Forgetting"]},
    7: {"title": "Time Regained", "parts": ["The Final Reception"]}
}

# Key characters that appear throughout the work
KEY_CHARACTERS = [
    "Marcel", "Narrator", "Swann", "Odette", "Gilberte", "Albertine", 
    "Charlus", "Baron de Charlus", "Guermantes", "Duchess", "Duke",
    "Saint-Loup", "Robert", "Françoise", "Mamma", "Mother", "Grandmother",
    "Bergotte", "Elstir", "Vinteuil", "Verdurin", "Madame Verdurin",
    "Morel", "Rachel", "Andrée", "Léa", "Bloch", "Cottard", "Brichot"
]

# Major themes in Proust
THEMES = {
    "memory": ["remember", "memory", "memories", "recall", "reminisce", "past", "childhood", "madeleine"],
    "time": ["time", "temporal", "years", "age", "aging", "moment", "duration", "eternal"],
    "love": ["love", "passion", "desire", "jealousy", "romantic", "heart", "affection", "longing"],
    "art": ["art", "artist", "painting", "music", "literature", "beauty", "aesthetic", "creation"],
    "society": ["society", "social", "aristocracy", "salon", "reception", "manners", "class"],
    "nature": ["nature", "flowers", "hawthorn", "garden", "landscape", "season", "weather"],
    "sleep": ["sleep", "dream", "awake", "awakening", "night", "morning", "consciousness"],
    "death": ["death", "dying", "mortality", "loss", "grief", "funeral", "illness"]
}

def extract_characters(text: str) -> List[str]:
    """Extract characters mentioned in the passage."""
    found_characters = []
    text_lower = text.lower()
    
    for character in KEY_CHARACTERS:
        if character.lower() in text_lower:
            # Normalize character names
            if character in ["Baron de Charlus", "Charlus"]:
                if "Charlus" not in found_characters:
                    found_characters.append("Charlus")
            elif character in ["Duchess", "Duke"] and "guermantes" in text_lower:
                if f"{character} de Guermantes" not in found_characters:
                    found_characters.append(f"{character} de Guermantes")
            elif character in ["Marcel", "Narrator"]:
                if "Marcel (Narrator)" not in found_characters:
                    found_characters.append("Marcel (Narrator)")
            elif character not in found_characters:
                found_characters.append(character)
    
    return found_characters

def extract_themes(text: str) -> List[Dict[str, Any]]:
    """Extract themes from the passage with relevance scores."""
    text_lower = text.lower()
    found_themes = []
    
    for theme, keywords in THEMES.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            found_themes.append({
                "name": theme.capitalize(),
                "score": min(score / len(keywords), 1.0)  # Normalize to 0-1
            })
    
    # Sort by relevance score
    found_themes.sort(key=lambda x: x["score"], reverse=True)
    return found_themes[:3]  # Return top 3 themes

def estimate_reading_time(text: str) -> int:
    """Estimate reading time in minutes (assuming 200 words per minute)."""
    word_count = len(text.split())
    return max(1, round(word_count / 200))

def determine_narrative_position(index: int, total: int, volume: int) -> str:
    """Determine the narrative position within the volume."""
    position_ratio = index / total
    
    if volume == 1:
        if position_ratio < 0.4:
            return "Early memories in Combray"
        elif position_ratio < 0.7:
            return "Swann's love affair with Odette"
        else:
            return "Marcel's fascination with names and places"
    elif volume == 2:
        if position_ratio < 0.5:
            return "Marcel's entry into the Swann household"
        else:
            return "The summer at Balbec"
    # Add more specific positions for other volumes as needed
    else:
        if position_ratio < 0.33:
            return "Beginning of the volume"
        elif position_ratio < 0.66:
            return "Middle of the volume"
        else:
            return "End of the volume"

def enhance_passage_metadata(passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enhance each passage with additional metadata."""
    enhanced_passages = []
    
    # Group passages by volume for context
    volume_passages = defaultdict(list)
    for passage in passages:
        volume_passages[passage.get("volume", 1)].append(passage)
    
    # Process each passage
    for passage in passages:
        if not passage.get("text", "").strip():
            continue
            
        volume = passage.get("volume", 1)
        volume_index = passage.get("index", 1)
        total_in_volume = len(volume_passages[volume])
        
        enhanced = {
            **passage,  # Keep existing fields
            "metadata": {
                "volume_title": VOLUME_INFO.get(volume, {}).get("title", "Unknown"),
                "characters": extract_characters(passage["text"]),
                "themes": extract_themes(passage["text"]),
                "reading_time": estimate_reading_time(passage["text"]),
                "narrative_position": determine_narrative_position(volume_index, total_in_volume, volume),
                "word_count": len(passage["text"].split()),
                "complexity_score": calculate_complexity_score(passage["text"])
            }
        }
        
        # Add chapter info if available
        if passage.get("chapter"):
            enhanced["metadata"]["chapter"] = passage["chapter"]
        
        enhanced_passages.append(enhanced)
    
    return enhanced_passages

def calculate_complexity_score(text: str) -> float:
    """Calculate a simple complexity score based on sentence length and vocabulary."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return 0.5
    
    # Average words per sentence
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
    
    # Normalize to 0-1 scale (assuming 40+ words per sentence is very complex)
    complexity = min(avg_sentence_length / 40, 1.0)
    
    return round(complexity, 2)

def main():
    """Main function to enhance the parsed.json file."""
    print("Loading parsed.json...")
    with open("parsed.json", "r", encoding="utf-8") as f:
        passages = json.load(f)
    
    print(f"Loaded {len(passages)} passages")
    
    print("Enhancing metadata...")
    enhanced_passages = enhance_passage_metadata(passages)
    
    # Save enhanced version
    output_file = "parsed_enhanced.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enhanced_passages, f, ensure_ascii=False, indent=2)
    
    print(f"Saved enhanced passages to {output_file}")
    
    # Print sample enhanced passage
    print("\nSample enhanced passage:")
    sample = next((p for p in enhanced_passages if p.get("metadata", {}).get("characters")), None)
    if sample:
        print(json.dumps(sample, indent=2, ensure_ascii=False)[:1000] + "...")

if __name__ == "__main__":
    main()