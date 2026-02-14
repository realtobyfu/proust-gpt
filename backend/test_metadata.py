import json
from metadata import EnhancedProustParser

def test_parser():
    """Test the enhanced parser on sample passages"""
    
    # Load a few passages
    with open('parsed.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Take first 5 passages for testing
    test_passages = data[:5]
    
    # Initialize parser
    parser = EnhancedProustParser()
    
    print("=== Testing Enhanced Parser ===\n")
    
    for i, passage in enumerate(test_passages):
        print(f"\n--- Passage {i+1} ---")
        print(f"Book: {passage['book']}")
        print(f"Chapter: {passage['chapter']}")
        print(f"Text preview: {passage['text'][:150]}...")
        
        # Extract metadata
        metadata = parser.extract_metadata(passage, len(data), i)
        
        print(f"\nExtracted Metadata:")
        print(f"- Characters: {metadata['characters']}")
        print(f"- Locations: {metadata['locations']}")
        print(f"- Themes: {metadata['themes']}")
        print(f"- Literary Devices: {metadata['literary_devices']}")
        print(f"- Temporal Markers: {metadata['temporal_markers']}")
        print(f"- Mood: {metadata['mood']}")
        print(f"- Difficulty Level: {metadata['difficulty_level']}")
        print(f"- Reading Time: {metadata['narrative_position']['reading_time_minutes']} minutes")
        print(f"- Word Count: {metadata['narrative_position']['word_count']} words")
        print("-" * 50)

def demonstrate_full_pipeline():
    """Demonstrate the complete enhancement pipeline"""
    
    print("\n=== Full Pipeline Demonstration ===\n")
    
    # Step 1: Run enhanced parser
    print("Step 1: Running enhanced parser on first 10 passages...")
    
    with open('parsed.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process only first 10 passages for demo
    demo_data = data[:10]
    
    parser = EnhancedProustParser()
    for i, passage in enumerate(demo_data):
        metadata = parser.extract_metadata(passage, len(data), i)
        passage['metadata'] = metadata
    
    # Save demo output
    with open('demo_enhanced_parsed.json', 'w', encoding='utf-8') as f:
        json.dump(demo_data, f, indent=2, ensure_ascii=False)
    
    print("✓ Enhanced metadata added to passages")
    
    # Step 2: Show statistics
    print("\nStep 2: Analyzing extracted metadata...")
    
    all_themes = []
    all_characters = []
    all_devices = []
    
    for passage in demo_data:
        metadata = passage.get('metadata', {})
        all_themes.extend(metadata.get('themes', []))
        all_characters.extend(metadata.get('characters', []))
        all_devices.extend(metadata.get('literary_devices', []))
    
    print(f"\nUnique themes found: {set(all_themes)}")
    print(f"Unique characters found: {set(all_characters)}")
    print(f"Literary devices detected: {set(all_devices)}")
    
    print("\n✓ Demo complete! Check 'demo_enhanced_parsed.json' for full output")

if __name__ == "__main__":
    # Run basic test
    test_parser()
    
    # Run full pipeline demo
    demonstrate_full_pipeline()