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
import pymupdf
from pydantic import BaseModel

__version__ = "0.9.0"


def sanitize(s: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r"[^\w]", "", s)


class PaperMetadata(BaseModel):
    article_type: str  # "research" for original research; otherwise e.g. "Editorial", "Commentary", "Perspective"
    first_author_last_name: str
    second_author_last_name: str
    journal_full_name: str
    journal_abbreviation: str
    year: str


def extract_via_llm(full_text: str, metadata: dict | None = None) -> PaperMetadata:
    """Use Claude to extract paper metadata from text."""
    print("  (calling Claude API...)")
    try:
        client = anthropic.Anthropic()
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=512,
            system=(
                "You are a scientific literature assistant. "
                "Extract bibliographic metadata from a scientific paper. "
                "For journal_abbreviation, use the standard ISO/NLM abbreviation. "
                "Key abbreviations: Nature Medicine -> NatMed, Nature Communications -> NatCommun, "
                "Nature -> Nature, New England Journal of Medicine -> NEnglJMed, "
                "JAMA -> JAMA, BMJ -> BMJ, Lancet -> Lancet, Science -> Science, Cell -> Cell, "
                "PLOS One -> PLoSOne, Circulation -> Circulation, "
                "Journal of Clinical Oncology -> JClinOncol, "
                "BMJ Medicine -> BMJMed "
                "Return only last names for authors (no initials, no titles, no credentials). "
                "Author lists often contain superscript affiliation numbers or symbols — ignore them. "
                "first_author_last_name is the last name of the FIRST person listed in the author byline. "
                "second_author_last_name is the last name of the SECOND person listed in the author byline. "
                "Ignore seniority, prominence, and correspondence — use only the order names appear in the byline. "
                "The author byline may appear at the end of the paper. "
                "For article_type: use 'research' for original research articles; "
                "for other types use the exact article type label as it appears in the paper "
                "(e.g. 'Editorial', 'Commentary', 'Perspective', 'Review', 'Letter'). "
                "For non-research articles, first_author_last_name and second_author_last_name may be left empty."
            ),
            messages=[{
                "role": "user",
                "content": (
                    "Extract the metadata from this scientific paper.\n\n"
                    + (f"PDF metadata: {metadata}\n\n" if metadata else "")
                    + f"Paper text:\n{full_text}"
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


def extract_text(path: Path) -> str:
    """Extract text from PDF using pymupdf (handles multi-column layouts)."""
    doc = pymupdf.open(str(path))
    return chr(12).join(page.get_text() for page in doc)


def rename_pdf(pdf_path: str, remove_original: bool = False, debug: bool = False):
    path = Path(pdf_path)
    if not path.exists():
        print(f"Error: file not found: {pdf_path}")
        sys.exit(1)
    if path.suffix.lower() != ".pdf":
        print(f"Error: not a PDF file: {pdf_path}")
        sys.exit(1)

    full_text = extract_text(path)

    if debug:
        debug_file = path.with_suffix(".txt")
        debug_file.write_text(full_text)
        print(f"  [debug] extracted text saved to {debug_file}")

    meta = extract_via_llm(full_text)
    article_type = meta.article_type
    first = meta.first_author_last_name
    second = meta.second_author_last_name
    year = meta.year
    journal_full = meta.journal_full_name
    journal_abbr = meta.journal_abbreviation

    print(f"  Article type           : {article_type}")
    print(f"  First author last name : {first}")
    print(f"  Second author last name: {second}")
    print(f"  Journal                : {journal_full} -> {journal_abbr}")
    print(f"  Year                   : {year}")

    if article_type.lower() != "research":
        new_name = f"{sanitize(article_type)}_{sanitize(journal_abbr)}_{sanitize(year)}.pdf"
    else:
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
        description=f"refren {__version__} — scientific manuscript PDF file renamer"
    )
    parser.add_argument("pdf_file", nargs="?")
    parser.add_argument("--remove", action="store_true", help="Remove the original PDF after copying")
    parser.add_argument("--debug", action="store_true", help="Save extracted text to .txt file for inspection")
    args = parser.parse_args()

    if not args.pdf_file:
        print(f"refren {__version__}")
        parser.print_usage()
        return

    rename_pdf(args.pdf_file, remove_original=args.remove, debug=args.debug)


if __name__ == "__main__":
    main()
