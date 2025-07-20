# Enhanced Parser for ProustGPT

This enhanced parsing system adds rich metadata to Proust passages for the guided exploration features.

## Features

### Enhanced Metadata
Each passage now includes:
- **Characters**: Automatically extracted character names
- **Locations**: Places mentioned in the text
- **Themes**: Key Proustian themes (memory, time, love, etc.)
- **Literary Devices**: Metaphors, stream-of-consciousness, etc.
- **Temporal Markers**: Time context (childhood, night, past, etc.)
- **Mood**: Emotional tone (nostalgic, dreamlike, etc.)
- **Difficulty Level**: 1-5 scale based on sentence complexity
- **Reading Time**: Estimated minutes to read
- **Connections**: Related passages and theme continuations

### Connection Mapping
- Semantic similarity between passages using embeddings
- Character journey tracking across volumes
- Theme progression paths
- Pre-built reading paths for different user types

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

## Usage

### 1. Run Enhanced Parser
```bash
python enhanced_parser.py
```
This will:
- Read `parsed.json`
- Add metadata to each passage
- Output `enhanced_parsed.json`

### 2. Build Connections
```bash
python connection_mapper.py
```
This will:
- Read `enhanced_parsed.json`
- Generate embeddings for all passages
- Find similar passages
- Create reading paths
- Output `connected_parsed.json` and `passage_indices.json`

### 3. Test the System
```bash
python test_enhanced_parser.py
```
This demonstrates the metadata extraction on sample passages.

## Integration with Server

Update your `server.py` to use the enhanced data:

```python
# Load enhanced data
with open('connected_parsed.json', 'r') as f:
    passages = json.load(f)

# Load indices for quick lookup
with open('passage_indices.json', 'r') as f:
    indices = json.load(f)
```

Now you can:
- Filter passages by theme/character
- Provide reading paths
- Show related passages
- Track user progress through themes

## Example Enhanced Passage

```json
{
  "book": "Swann's Way",
  "volume": 1,
  "chapter": "Overture",
  "text": "For a long time I used to go to bed early...",
  "index": 2,
  "metadata": {
    "narrative_position": {
      "percentage_in_work": 0.03,
      "reading_time_minutes": 1.5,
      "word_count": 375
    },
    "characters": ["narrator", "mamma"],
    "locations": ["combray", "bedroom"],
    "themes": ["memory", "sleep", "childhood", "time"],
    "literary_devices": ["stream_of_consciousness", "sensory_description"],
    "temporal_markers": ["childhood", "night", "past"],
    "mood": ["nostalgic", "dreamlike"],
    "difficulty_level": 4,
    "connections": {
      "related_passages": [8, 15, 42, 156, 203],
      "similarity_scores": [0.89, 0.85, 0.82, 0.78, 0.75],
      "theme_continuations": ["memory_passage_15", "sleep_passage_8"]
    }
  }
}
```

## Next Steps

1. **Frontend Integration**: Update React components to use metadata
2. **User Progress Tracking**: Store which passages/themes user has explored
3. **Dynamic Path Generation**: Create personalized paths based on user interests
4. **Analytics**: Track which paths are most successful