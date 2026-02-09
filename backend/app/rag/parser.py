from pypdf import PdfReader
import os


def parse_file(file_path: str) -> str:

    ext = os.path.splitext(file_path)[1].lower()

    # ---------- PDF ----------
    if ext == ".pdf":

        reader = PdfReader(file_path)

        text = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text.append(page_text)

        return "\n".join(text)


    # ---------- TXT ----------
    if ext == ".txt":

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


    raise ValueError("Unsupported file format")
