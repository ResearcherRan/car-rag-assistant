from src.ingestion.document_loader import load_pdf
from src.ingestion.text_cleaner import clean_text

def main():
    pdf_path = "data/raw/manual.pdf"

    pages = load_pdf(pdf_path)

    clean = clean_text(pages[1]["text"])

    print(clean[:900])
if __name__ == "__main__":
    main()