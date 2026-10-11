from src.ingestion.document_loader import load_pdf
from src.ingestion.text_cleaner import clean_text
from src.ingestion.chunker import split_text

def main():
    pdf_path = "data/raw/manual.pdf"

    pdf_pages = load_pdf(pdf_path)

    clean = clean_text(pdf_pages)

    chunk = split_text(clean)
    print(chunk[20])
    print(chunk[21])
    print(chunk[22])

if __name__ == "__main__":
    main()