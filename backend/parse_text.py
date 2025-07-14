import re
import json

# Predefine book, chapter, and volume structure
books_and_chapters = {
    "Swann’s Way": {
        "volume": 1,
        "chapters": ["Overture", "Combray", "Swann in Love", "Place-Names: The Name"]
    },
    "Within a Budding Grove": {
        "volume": 2,
        "chapters": ["Madame Swann at Home", "Place-Names: The Place", "Seascape, with Frieze of Girls"]
    },
    "The Guermantes Way": {
        "volume": 3,
        "chapters": ["Chapter 1", "Chapter 2"]
    },
    "Cities of the Plain": {
        "volume": 4,
        "chapters": ["Introduction", "Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"]
    },
    "The Captive": {
        "volume": 5,
        "chapters": ["Chapter 1 — Life with Albertine", "Chapter 2 — The Verdurins Quarrel with M. De Charlus", "Chapter 3 — Flight of Albertine"]
    },
    "The Sweet Cheat Gone": {
        "volume": 6,
        "chapters": ["Chapter 1 — Grief and Oblivion", "Chapter 2 — Mademoiselle De Forcheville", "Chapter 3 — Venice", "Chapter 4 — A Fresh Light Upon Robert De Saint-Loup"]
    },
    "Time Regained": {
        "volume": 7,
        "chapters": ["Chapter 1 — Tansonville", "Chapter 2 — M. de Charlus During the War, His Opinions, His Pleasures", "Chapter 3 — An Afternoon Party at the House of the Princesse de Guermantes"]
    }
}

# Initialize variables
current_book = None
current_chapter = None
index = 1
json_data = []

# Load the content from a text file
file_path = "in_search_of_lost_time.txt"
with open(file_path, 'r', encoding='utf-8') as file:
    lines = file.readlines()

# Helper function to detect the book
# Helper function to detect the book loosely, not requiring an exact match
def detect_book(line):
    for book in books_and_chapters.keys():
        # Check if the book name appears in the line, but avoid lines with too much extra text
        if book.lower() in line.lower() and len(line.strip()) <= len(book) + 20:
            return book
    return None

# Helper function to detect the chapter based on the current book, loosely
def detect_chapter(line, current_book):
    if current_book and current_book in books_and_chapters:
        chapters = books_and_chapters[current_book]["chapters"]
        for chapter in chapters:
            # Check if the chapter name appears in the line, but avoid lines with too much extra text
            if chapter.lower() in line.lower() and len(line.strip()) <= len(chapter) + 20:
                return chapter
    return None



# Process the lines
paragraph_buffer = []
previous_line_empty = False  # Track if the previous line was empty

for line in lines:
    line = line.strip()

    # Detect and store the current book if a match is found
    detected_book = detect_book(line)
    if detected_book:
        # If switching books, store the last paragraph before moving on
        if paragraph_buffer:
            json_data.append({
                "book": current_book,
                "volume": books_and_chapters[current_book]["volume"],  # Get volume based on book
                "chapter": current_chapter,
                "text": " ".join(paragraph_buffer),
                "index": index
            })
            paragraph_buffer = []
            index += 1

        current_book = detected_book
        current_chapter = None  # Reset the chapter when a new book is found
        continue

    # Detect and store the chapter based on the current book
    detected_chapter = detect_chapter(line, current_book)
    if detected_chapter:
        # Store the last paragraph before moving to the new chapter
        if paragraph_buffer:
            json_data.append({
                "book": current_book,
                "volume": books_and_chapters[current_book]["volume"],  # Get volume based on book
                "chapter": current_chapter,
                "text": " ".join(paragraph_buffer),
                "index": index
            })
            paragraph_buffer = []
            index += 1

        current_chapter = detected_chapter
        continue

    # Handle regular paragraphs
    if line and current_book:
        if previous_line_empty:
            # Store the current paragraph and start a new one
            if paragraph_buffer:
                json_data.append({
                    "book": current_book,
                    "volume": books_and_chapters[current_book]["volume"],  # Get volume based on book
                    "chapter": current_chapter,
                    "text": " ".join(paragraph_buffer),
                    "index": index
                })
                paragraph_buffer = []
                index += 1
        paragraph_buffer.append(line)
        previous_line_empty = False
    else:
        # If an empty line is encountered, mark the paragraph as complete
        if paragraph_buffer:
            json_data.append({
                "book": current_book,
                "volume": books_and_chapters[current_book]["volume"],  # Get volume based on book
                "chapter": current_chapter,
                "text": " ".join(paragraph_buffer),
                "index": index
            })
            paragraph_buffer = []
            index += 1
        previous_line_empty = True

# Handle any remaining paragraphs at the end of the file
if paragraph_buffer:
    json_data.append({
        "book": current_book,
        "volume": books_and_chapters[current_book]["volume"],  # Get volume based on book
        "chapter": current_chapter,
        "text": " ".join(paragraph_buffer),
        "index": index
    })

# Convert the list to JSON format
json_output = json.dumps(json_data, indent=4)

# Save the output to a JSON file
with open("parsed.json", "w", encoding='utf-8') as f:
    f.write(json_output)

# Output the JSON for review
print(json_output)
