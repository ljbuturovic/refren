#!/usr/bin/env python3
"""
Rename a scientific PDF as: FirstAuthorLastName_SecondAuthorLastName_JournalAbbrev_Year.pdf
Usage: ./refren.py <pdf_file>
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import anthropic
import pdfplumber
from pydantic import BaseModel


def sanitize(s: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r"[^\w]", "", s)


class PaperMetadata(BaseModel):
    first_author_last_name: str
    second_author_last_name: str
    journal_full_name: str
    journal_abbreviation: str
    year: str


def extract_via_llm(text: str, metadata: dict | None = None) -> PaperMetadata:
    """Use Claude to extract paper metadata from first-page text."""
    print("  (calling Claude API...)")
    try:
        client = anthropic.Anthropic()
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=512,
            system=(
                "You are a scientific literature assistant. "
                "Extract bibliographic metadata from the first page of a scientific paper. "
                "For journal_abbreviation, use the standard ISO/NLM abbreviation (e.g. 'Circulation', "
                "'N Engl J Med', 'JAMA', 'Nat Med'). "
                "Return only last names for authors (no initials, no titles, no credentials)."
            ),
            messages=[{
                "role": "user",
                "content": (
                    "Extract the metadata from this scientific paper.\n\n"
                    + (f"PDF metadata: {metadata}\n\n" if metadata else "")
                    + f"First page text:\n{text[:4000]}"
                ),
            }],
            output_format=PaperMetadata,
        )
        return response.parsed_output
    except (anthropic.AuthenticationError, TypeError):
        print("Error: invalid or missing ANTHROPIC_API_KEY. Please get and set ANTHROPIC_API_KEY to use this program")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Error: could not connect to the Anthropic API. Check your internet connection.")
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"Error: Anthropic API returned an error ({e.status_code}).")
        sys.exit(1)


def rename_pdf(pdf_path: str, remove_original: bool = False):
    path = Path(pdf_path)
    if not path.exists():
        print(f"Error: file not found: {pdf_path}")
        sys.exit(1)
    if path.suffix.lower() != ".pdf":
        print(f"Error: not a PDF file: {pdf_path}")
        sys.exit(1)

    with pdfplumber.open(path) as pdf:
        metadata = pdf.metadata or {}
        first_page_text = pdf.pages[0].extract_text() or ""
        if len(first_page_text) < 200 and len(pdf.pages) > 1:
            first_page_text += "\n" + (pdf.pages[1].extract_text() or "")

    meta = extract_via_llm(first_page_text, metadata)
    first = meta.first_author_last_name
    second = meta.second_author_last_name
    year = meta.year
    journal_full = meta.journal_full_name
    journal_abbr = meta.journal_abbreviation

    print(f"  First author last name : {first}")
    print(f"  Second author last name: {second}")
    print(f"  Journal                : {journal_full} -> {journal_abbr}")
    print(f"  Year                   : {year}")

    new_name = f"{sanitize(first)}_{sanitize(second)}_{sanitize(journal_abbr)}_{sanitize(year)}.pdf"
    new_path = path.parent / new_name

    print(f"\n  {path.name}  ->  {new_name}")
    shutil.copy2(path, new_path)
    print(f"Copied to: {new_path}")
    if remove_original:
        path.unlink()
        print(f"Removed: {path.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Scientific manuscript PDF file renamer: rename to FirstAuthor_SecondAuthor_Journal_Year"
    )
    parser.add_argument("pdf_file")
    parser.add_argument("--remove", action="store_true", help="Remove the original PDF after copying")
    args = parser.parse_args()
    rename_pdf(args.pdf_file, remove_original=args.remove)


if __name__ == "__main__":
    main()
