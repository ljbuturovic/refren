#!/usr/bin/env python3
"""
Rename a scientific PDF as: FirstAuthorLastName_SecondAuthorLastName_JournalAbbrev_Year.pdf
Usage: ./refren.py <pdf_file>
"""

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import anthropic
import httpx
import pymupdf
from pydantic import BaseModel

try:
    __version__ = version("refren")
except PackageNotFoundError:
    __version__ = "unknown"


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
    title: str = ""  # full paper title, used only for supplement lookup, not the filename
    doi: str = ""  # used only for supplement lookup, not the filename
    arxiv_id: str = ""  # e.g. "2608.14705v1", used only for supplement lookup, not the filename


class SupplementResult(BaseModel):
    found: bool
    supplement_urls: list[str] = []
    notes: str = ""


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
                "IMPORTANT SPECIAL CASE — preprint servers: "
                "If the paper is hosted on a preprint server, use the server name as both journal_full_name and journal_abbreviation. "
                "arXiv: identified by an arXiv ID (e.g. 'arXiv:2506.19540') or the arXiv logo -> use 'arXiv'. "
                "SSRN: identified by an SSRN ID or ssrn.com URL -> use 'SSRN'. "
                "bioRxiv or medRxiv: identified by a biorxiv.org or medrxiv.org URL or logo -> use 'bioRxiv' or 'medRxiv'. "
                "Do NOT use the name of a conference, workshop, or subject area as the journal name for preprints. "
                "Key abbreviations: Nature Medicine -> NatMed, Nature Communications -> NatCommun, "
                "Nature -> Nature, New England Journal of Medicine -> NEnglJMed, "
                "JAMA -> JAMA, BMJ -> BMJ, Lancet -> Lancet, Science -> Science, Cell -> Cell, "
                "PLOS One -> PLoSOne, Circulation -> Circulation, "
                "Journal of Clinical Oncology -> JClinOncol, "
                "BMJ Medicine -> BMJMed "
                "Return only last names for authors (no initials, no titles, no credentials). "
                "You must capitalize the last names, respecting the culture-specific special names like vanBeethoven"
                "Author lists often contain superscript affiliation numbers or symbols — ignore them. "
                "first_author_last_name is the last name of the FIRST person listed in the author byline. "
                "second_author_last_name is the last name of the SECOND person listed in the author byline. "
                "Ignore seniority, prominence, and correspondence — use only the order names appear in the byline. "
                "The author byline may appear at the end of the paper. "
                "For article_type: use 'research' for original research articles; "
                "for other types use the exact article type label as it appears in the paper "
                "(e.g. 'Editorial', 'Commentary', 'Perspective', 'Review', 'Letter'). "
                "Always populate first_author_last_name and second_author_last_name when a byline is present, "
                "even for non-research articles like Perspectives, Commentaries, Reviews, and Letters. "
                "Leave them empty only when there is genuinely no author byline (e.g. unsigned Editorials). "
                "Also extract the paper's full title into 'title', and its DOI into 'doi' if one is printed "
                "anywhere in the text (often near the header, footer, or first page — look for a string starting "
                "with '10.'). Leave 'doi' empty if none is present. "
                "If the paper is an arXiv preprint, also extract the arXiv identifier (e.g. '2608.14705' or "
                "'2608.14705v1', found near an 'arXiv:' label, often in the header/footer) into 'arxiv_id'. "
                "Leave 'arxiv_id' empty for non-arXiv papers."
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


def find_arxiv_ancillary_files(arxiv_id: str) -> SupplementResult:
    """Check arXiv's ancillary-files listing directly. arXiv's URL scheme for this is fixed and
    documented, so a direct HTTP check is more reliable than asking a general web search to find
    and correctly interpret the (JS-augmented) abstract page."""
    print("  (checking arXiv for ancillary files...)")
    clean_id = arxiv_id.strip()
    check_url = f"https://arxiv.org/src/{clean_id}/anc"
    try:
        with httpx.Client(
            follow_redirects=True, timeout=30.0, headers={"User-Agent": "Mozilla/5.0 (compatible; refren/1.0)"}
        ) as client:
            resp = client.get(check_url)
    except httpx.HTTPError as e:
        return SupplementResult(found=False, notes=f"Could not reach arXiv: {e}")

    if resp.status_code == 404:
        return SupplementResult(found=False, notes="No ancillary files listed on arXiv for this paper.")
    if resp.is_error:
        return SupplementResult(found=False, notes=f"arXiv returned an unexpected status ({resp.status_code}).")

    # arXiv bundles all ancillary files together with the paper's source into one tarball.
    return SupplementResult(found=True, supplement_urls=[f"https://arxiv.org/src/{clean_id}"])


def find_supplement(meta: PaperMetadata) -> SupplementResult:
    """Use Claude with web search to locate direct download URL(s) for a paper's supplementary material."""
    if meta.arxiv_id:
        return find_arxiv_ancillary_files(meta.arxiv_id)

    print("  (searching the web for supplementary material...)")
    query_lines = [f"Journal: {meta.journal_full_name}", f"Year: {meta.year}"]
    if meta.title:
        query_lines.insert(0, f"Title: {meta.title}")
    if meta.first_author_last_name:
        query_lines.append(f"First author: {meta.first_author_last_name}")
    if meta.doi:
        query_lines.append(f"DOI: {meta.doi}")

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
            system=(
                "You are a research assistant that locates supplementary material for scientific papers. "
                "Given a paper's bibliographic details, find the direct download URL(s) for its supplementary "
                "material (sometimes labeled 'Supplementary Information', 'Supporting Information', "
                "'Supplemental Data', or, on PubMed Central, 'Appendix A: Supplementary data'). "
                "IMPORTANT — prefer PubMed Central (PMC) over the publisher's own site: many publishers "
                "(Elsevier/ScienceDirect journal microsites especially) block automated access to their article "
                "pages, but PMC (pmc.ncbi.nlm.nih.gov) does not and frequently mirrors the full text including "
                "supplementary files. If the paper has a PMC ID (search '<title> site:ncbi.nlm.nih.gov/pmc' or "
                "'<DOI> PMC' if not already known), fetch its PMC page and look there first — PMC supplementary "
                "files are direct links shaped like pmc.ncbi.nlm.nih.gov/articles/instance/<numeric id>/bin/<filename> "
                "(e.g. mmc1.pdf, mmc2.pdf). Only fall back to the publisher's own site if there's no PMC copy. "
                "Prefer direct file links (ending in .pdf, .zip, .docx, .xlsx, etc.) over HTML landing pages. "
                "If there are several separate supplementary files, list all of their direct URLs. If there is a "
                "single combined supplement (e.g. one PDF or one ZIP), list just that one URL. "
                "When you are done, respond with ONLY a JSON object (no markdown fences, no other text) matching "
                'this schema: {"found": bool, "supplement_urls": [string], "notes": string}. '
                "Set found to false and briefly explain in notes if no supplementary material could be located. "
                "Your final response must contain ONLY that JSON object — no explanation before or after it."
            ),
            messages=[{"role": "user", "content": "\n".join(query_lines)}],
        )
    except anthropic.AuthenticationError:
        print("Error: invalid or missing ANTHROPIC_API_KEY. Please get and set ANTHROPIC_API_KEY to use this program")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Error: could not connect to the Anthropic API. Check your internet connection.")
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"Error: Anthropic API returned an error ({e.status_code}).")
        sys.exit(1)

    # The model may emit commentary text blocks between web searches; only the
    # final text block is the answer, and even that may wrap the JSON in prose.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    text = text_blocks[-1].strip() if text_blocks else ""

    decoder = json.JSONDecoder()
    idx = 0
    while True:
        idx = text.find("{", idx)
        if idx == -1:
            return SupplementResult(found=False, notes=f"Could not parse search result: {text[:200]}")
        try:
            data, _ = decoder.raw_decode(text, idx)
            return SupplementResult(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            idx += 1


def normalize_pmc_url(url: str) -> str:
    """PMC supplementary files are actually served at /articles/instance/<id>/bin/<file>, but
    search results (and the model) commonly give the reader-facing /articles/PMC<id>/bin/<file>
    form instead, which 404s. Rewrite it to the working form."""
    return re.sub(r"(pmc\.ncbi\.nlm\.nih\.gov/articles/)PMC(\d+/bin/)", r"\1instance/\2", url)


# Magic bytes for extensions we expect supplements to arrive as. Sites that block automated
# downloads (anti-bot interstitials, login walls) typically respond 200 with an HTML page instead
# of an error, so a status check alone isn't enough to catch a failed download.
_MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".zip": b"PK\x03\x04",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
    ".pptx": b"PK\x03\x04",
    ".gz": b"\x1f\x8b",
    ".tar.gz": b"\x1f\x8b",
}


def content_matches_extension(content: bytes, filename: str) -> bool:
    """Check downloaded bytes actually look like the file type their extension claims."""
    name = filename.lower()
    for ext, magic in _MAGIC_BYTES.items():
        if name.endswith(ext):
            return content.startswith(magic)
    return True  # unknown extension — nothing to validate against


def filename_from_download(resp: httpx.Response, url: str, index: int) -> str:
    """Derive a filename for a downloaded supplement from headers, or fall back to the URL/content-type."""
    cd = resp.headers.get("content-disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if match:
        return Path(match.group(1)).name
    url_name = Path(httpx.URL(url).path).name
    if url_name and Path(url_name).suffix:
        return url_name
    ext = mimetypes.guess_extension(resp.headers.get("content-type", "").split(";")[0].strip()) or ""
    return f"supplement_{index}{ext}"


def download_supplements(urls: list[str], dest_dir: Path) -> list[Path]:
    """Download each supplement URL, saving into dest_dir. Skips (with a warning) any that fail,
    and skips any whose content duplicates one already saved (the model can list the same file
    twice, e.g. via two different mirror URLs)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    seen_hashes = set()
    with httpx.Client(
        follow_redirects=True, timeout=60.0, headers={"User-Agent": "Mozilla/5.0 (compatible; refren/1.0)"}
    ) as client:
        for i, url in enumerate(dict.fromkeys(normalize_pmc_url(u) for u in urls), start=1):
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"  Warning: failed to download {url} ({e})")
                continue
            content_hash = hashlib.sha256(resp.content).hexdigest()
            if content_hash in seen_hashes:
                print(f"  Skipping {url}: duplicate of an already-downloaded file")
                continue
            seen_hashes.add(content_hash)
            out_name = filename_from_download(resp, url, i)
            if not content_matches_extension(resp.content, out_name):
                print(f"  Warning: {url} did not return a valid file (likely blocked by the site) — skipping")
                continue
            out_path = dest_dir / out_name
            out_path.write_bytes(resp.content)
            saved.append(out_path)
    return saved


def rename_in_place(path: Path, new_name: str, remove_original: bool) -> None:
    """Rename/copy the PDF next to itself, same as refren does with no --supplement."""
    new_path = path.parent / new_name
    if new_path.resolve() == path.resolve():
        print(f"\n  {path.name} is already correctly named — skipping rename.")
    else:
        print(f"\n  {path.name}  ->  {new_name}")
        shutil.copy2(path, new_path)
        print(f"Copied to: {new_path}")
        if remove_original:
            path.unlink()
            print(f"Removed: {path.name}")


def rename_pdf(pdf_path: str, remove_original: bool = False, debug: bool = False, fetch_supplement: bool = False):
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

    if first:
        new_name = f"{sanitize(first)}_{sanitize(second)}_{sanitize(journal_abbr)}_{sanitize(year)}.pdf"
    else:
        new_name = f"{sanitize(article_type)}_{sanitize(journal_abbr)}_{sanitize(year)}.pdf"

    if fetch_supplement:
        print()
        result = find_supplement(meta)
        saved = []
        if result.found and result.supplement_urls:
            # Only create the <name>/ folder if we actually have something to put in it.
            dest_dir = path.parent / Path(new_name).stem
            saved = download_supplements(result.supplement_urls, dest_dir)
            if not saved and not any(dest_dir.iterdir()):
                dest_dir.rmdir()  # download_supplements created it but left it empty

        if saved:
            new_path = dest_dir / new_name
            shutil.copy2(path, new_path)
            print(f"\n  {path.name}  ->  {new_path}")
            if remove_original:
                path.unlink()
                print(f"Removed: {path.name}")
            print(f"  Supplement saved to: {dest_dir}/")
            for p in saved:
                print(f"    {p.name}")
        else:
            if result.found and result.supplement_urls:
                note = " Supplement URL(s) were found but none could be downloaded."
            else:
                note = f" {result.notes}" if result.notes else ""
            print(f"  No supplementary material downloaded.{note}")
            rename_in_place(path, new_name, remove_original)
    else:
        rename_in_place(path, new_name, remove_original)


SUPPLEMENT_RELIABILITY = """\
--supplement reliability by source (as last verified):
  arXiv                        works — checked via arXiv's own ancillary-files listing
  Nature / Springer journals   inconsistent — direct links sometimes stale/403 even when valid
  PubMed Central (PMC)         doesn't work — file downloads blocked by a bot-detection challenge
  Elsevier / ScienceDirect     doesn't work — site blocks automated access outright
  other publishers             unknown — untested
"""


def main():
    parser = argparse.ArgumentParser(
        description=f"refren {__version__} — scientific manuscript PDF file renamer",
        epilog=SUPPLEMENT_RELIABILITY,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf_file", nargs="?")
    parser.add_argument("--remove", action="store_true", help="Remove the original PDF after copying")
    parser.add_argument("--debug", action="store_true", help="Save extracted text to .txt file for inspection")
    parser.add_argument(
        "--supplement",
        action="store_true",
        help="Also search the web for and download the paper's supplementary material (reliability varies "
        "by publisher — see below)",
    )
    args = parser.parse_args()

    if not args.pdf_file:
        print(f"refren {__version__}")
        parser.print_usage()
        return

    rename_pdf(args.pdf_file, remove_original=args.remove, debug=args.debug, fetch_supplement=args.supplement)


if __name__ == "__main__":
    main()
