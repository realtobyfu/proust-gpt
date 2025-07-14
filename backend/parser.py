import pdfplumber
import re
import json

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file, adding page markers."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text += f"\n\n-- Page {page_num + 1} --\n\n" + page.extract_text()
    return text

def parse_text(text, book_title):
    """Parses the extracted text to identify chapters, content, and page numbers."""
    data = []
    current_part = ""
    current_chapter = ""
    current_page = 0
    current_id = 0

    lines = text.split("\n")
    part_pattern = re.compile(r"^\s*Part\s+\w+", re.IGNORECASE)  # Matches Part One, Part Two, etc.
    chapter_pattern = re.compile(r"^\s*Chapter\s+\w+|^\s*Overture", re.IGNORECASE)  # Matches Chapter X, Overture
    page_pattern = re.compile(r"^-- Page (\d+) --")

    current_text = ""
    for line in lines:
        page_match = page_pattern.match(line)
        if page_match:
            if current_text.strip():  # Save previous content before starting a new page
                data.append({
                    "id": current_id,
                    "book": book_title,
                    "chapter": current_chapter or current_part,
                    "text": current_text.strip(),
                    "page": current_page
                })
                current_text = ""
                current_id += 1
            current_page = int(page_match.group(1))
            continue

        part_match = part_pattern.match(line)
        if part_match:
            current_part = line.strip()
            continue

        chapter_match = chapter_pattern.match(line)
        if chapter_match:
            current_chapter = line.strip()
            continue

        current_text += line + "\n"

    # Append the last bit of text
    if current_text.strip():
        data.append({
            "id": current_id,
            "book": book_title,
            "chapter": current_chapter or current_part,
            "text": current_text.strip(),
            "page": current_page
        })

    return data

def process_pdf(pdf_path, book_title):
    """Processes a PDF to extract structured text."""
    text = extract_text_from_pdf(pdf_path)
    structured_data = parse_text(text, book_title)
    return structured_data

# Process each book
book1 = process_pdf("corpus/volume_1_yale.pdf", "Swann's Way")
book2 = process_pdf("corpus/volume_2_yale.pdf", "In the Shadow of Young Girls in Flower")
book3 = process_pdf("corpus/volume_3_yale.pdf", "The Guermantes Way")
book4 = process_pdf("corpus/volume_4_yale.pdf", "Sodom and Gomorrah")
book5 = process_pdf("corpus/volume_5_yale.pdf", "The Captive and the Fugitive")

book7 = process_pdf("corpus/volume_7.pdf", "Time Regained")

# Combine and save to JSON
all_books_data = book1 + book2
with open("proust_books.json", "w") as outfile:
    json.dump(all_books_data, outfile, indent=4)

print("Extraction complete. Data saved to proust_books.json.")
