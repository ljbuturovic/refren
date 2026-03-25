#!/usr/bin/env python3
"""
Rename a scientific PDF as: FirstAuthorLastName_SecondAuthorLastName_JournalAbbrev_Year.pdf
Usage: ./renamer.py <pdf_file>
"""

import re
import sys
from pathlib import Path

import anthropic
import pdfplumber
from pydantic import BaseModel


# --- Journal abbreviation lookup ---
JOURNAL_ABBREVIATIONS = {
    "diagnostic and prognostic research": "DiagProgRes",
    "nature medicine": "NatMed",
    "nature communications": "NatCommun",
    "nature": "Nature",
    "science": "Science",
    "cell": "Cell",
    "the lancet": "Lancet",
    "lancet": "Lancet",
    "new england journal of medicine": "NEJM",
    "n engl j med": "NEJM",
    "jama": "JAMA",
    "bmj": "BMJ",
    "annals of internal medicine": "AnnInternMed",
    "plos medicine": "PLoSMed",
    "plos one": "PLoSOne",
    "plos biology": "PLoSBiol",
    "plos computational biology": "PLoSComputBiol",
    "bioinformatics": "Bioinformatics",
    "nucleic acids research": "NucleicAcidsRes",
    "genome biology": "GenomeBiol",
    "genome research": "GenomeRes",
    "molecular cell": "MolCell",
    "cell reports": "CellRep",
    "cell systems": "CellSyst",
    "elife": "eLife",
    "journal of clinical oncology": "JClinOncol",
    "cancer research": "CancerRes",
    "cancer cell": "CancerCell",
    "clinical cancer research": "ClinCancerRes",
    "journal of the american medical informatics association": "JAMIA",
    "npj digital medicine": "NPJDigitMed",
    "artificial intelligence in medicine": "ArtifIntellMed",
    "medical image analysis": "MedImageAnal",
    "radiology": "Radiology",
    "european radiology": "EurRadiol",
    "circulation": "Circulation",
    "european heart journal": "EurHeartJ",
    "journal of the american college of cardiology": "JACC",
    "diabetes care": "DiabetesCare",
    "statistics in medicine": "StatMed",
    "biometrics": "Biometrics",
    "american journal of epidemiology": "AmJEpidemiol",
    "epidemiology": "Epidemiology",
    "international journal of epidemiology": "IntJEpidemiol",
    "brain": "Brain",
    "journal of neurology": "JNeurol",
    "neurology": "Neurology",
    "gut": "Gut",
}


def abbreviate_journal(full_name: str) -> str:
    """Return a known abbreviation or derive a CamelCase abbreviation from the title."""
    lower = full_name.lower().strip()
    for key, abbr in JOURNAL_ABBREVIATIONS.items():
        if key in lower:
            return abbr
    stop = {"a", "an", "the", "of", "in", "on", "and", "for", "to", "with", "&"}
    words = re.sub(r"[^\w\s]", "", full_name).split()
    return "".join(w.capitalize() for w in words if w.lower() not in stop) or "UnknownJournal"


def extract_last_name(name: str) -> str:
    """Return the last name from a full author name string (final word only)."""
    name = name.strip().rstrip(",*0123456789† ")
    parts = name.split()
    return parts[-1] if parts else name


def parse_authors_and_year(text: str):
    """
    Extract (first_author_last, second_author_last, year) from first-page text.
    Returns (first, second, year) — any may be None if not found.
    """
    year = None
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if year_match:
        year = year_match.group(1)

    first, second = None, None

    # Pattern 1: "Surname et al." header
    et_al_match = re.search(r"([A-Z][a-z]+(?:\s+[a-z]+)*)\s+et al\.", text)
    if et_al_match:
        first = et_al_match.group(1).strip()

    # Pattern 2: full author line — comma-separated "Firstname Lastname, ..."
    author_line_pattern = re.compile(
        r"([A-Z][a-z]+(?:\s+[a-z]+)*\s+[A-Z][a-zA-Z\-]+[0-9†*,]*"
        r"(?:\s*,\s*[A-Z][a-z]+(?:\s+[a-z]+)*\s+[A-Z][a-zA-Z\-]+[0-9†*,]*){1,})"
    )
    for match in author_line_pattern.finditer(text):
        candidate = match.group(0)
        raw_authors = [a.strip() for a in re.split(r",\s*", candidate) if a.strip()]
        if len(raw_authors) >= 2:
            last_names = [extract_last_name(a) for a in raw_authors]
            if not first:
                first = last_names[0]
            second = last_names[1]
            break

    return first, second, year


def extract_journal(text: str) -> str | None:
    """Try to find the journal name from the first-page text."""
    lower = text.lower()
    for key in JOURNAL_ABBREVIATIONS:
        if key in lower:
            idx = lower.find(key)
            return text[idx: idx + len(key)]
    patterns = [
        r"(?:published in|journal)[:\s]+([A-Z][^\n]+)",
        r"https?://doi\.org/[^\s]+\s+([A-Z][A-Za-z &]+)\n",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def sanitize(s: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r"[^\w]", "", s)


# --- Claude API fallback ---

class PaperMetadata(BaseModel):
    first_author_last_name: str
    second_author_last_name: str
    journal_full_name: str
    journal_abbreviation: str
    year: str


def extract_via_llm(text: str, metadata: dict | None = None) -> PaperMetadata:
    """Use Claude to extract paper metadata from first-page text."""
    print("  (direct parsing incomplete — calling Claude API...)")
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


def rename_pdf(pdf_path: str):
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

    first, second, year = parse_authors_and_year(first_page_text)
    journal_full = extract_journal(first_page_text)
    journal_abbr = abbreviate_journal(journal_full) if journal_full else None

    # Try to extract year from PDF metadata if not found in text
    if not year:
        meta_str = " ".join(str(v) for v in metadata.values())
        m = re.search(r"\b(20\d{2}|19\d{2})\b", meta_str)
        if m:
            year = m.group(1)

    missing = [label for label, val in [
        ("first author", first), ("second author", second),
        ("year", year), ("journal", journal_full),
    ] if not val]

    if missing:
        # When LLM is needed, trust it for all fields — regex results may also be wrong
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
    confirm = input("Rename? [y/N] ").strip().lower()
    if confirm == "y":
        path.rename(new_path)
        print(f"Renamed to: {new_path}")
    else:
        print("Aborted.")


def main():
    if len(sys.argv) != 2:
        print("Usage: ./renamer.py <pdf_file>")
        sys.exit(1)
    rename_pdf(sys.argv[1])


if __name__ == "__main__":
    main()
