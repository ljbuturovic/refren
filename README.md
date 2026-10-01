![License](https://img.shields.io/badge/License-MIT-yellow.svg)

# refren: scientific manuscript PDF renamer

Scenario: when you download a scientific paper from the Internet, the PDF file is usually named someting cryptic like 2506.19540v1.pdf

refren renames it to `FirstAuthor_SecondAuthor_JournalAbbrev_Year.pdf` using Claude AI to extract bibliographic metadata from the PDF

Conveniently, it can also download the supplemental data for the
manuscript automatically

## Usage

```
refren <pdf_file> [--remove] [--supplement]
```

`--remove` deletes the original PDF after creating the renamed copy.

`--supplement` also searches the web for the paper's supplementary material and downloads it. If a supplement is found and successfully downloaded, refren creates a `FirstAuthor_SecondAuthor_JournalAbbrev_Year/` folder and puts both the renamed PDF and the downloaded supplement inside it. If no supplement can be found or downloaded (e.g. the publisher blocks automated downloads), refren falls back to the normal behavior: just rename the PDF in place, no folder created.

### `--supplement` reliability by source

Many publishers block automated downloads outright, so this is best-effort, not guaranteed. As last verified:

| Source                     | Status | Notes |
|-----------------------------|--------|-------|
| arXiv                       | ✅ Works | Checked directly via arXiv's own ancillary-files listing, not a web search |
| Nature-branded titles (nature.com) | ✅ Works | Nature, Nature Medicine, Nature Biotechnology, Nature Catalysis, Nature Energy, Signal Transduction and Targeted Therapy, etc. — anything with a `10.1038` DOI, checked directly via nature.com. (Springer Nature also publishes non-Nature-branded journals on a different platform — see below.) |
| Springer/BioMed Central titles (link.springer.com, biomedcentral.com) | ❓ Unknown | Untested as a deterministic check — a different site than nature.com, despite shared corporate ownership. One example (*J Cheminform*) hit a separate issue: its article page is a JS-rendered SPA with no text in the raw HTML |
| PubMed Central (PMC)        | ❌ Doesn't work | Article pages are readable, but file downloads are blocked by NCBI's bot-detection challenge |
| Elsevier / ScienceDirect     | ❌ Doesn't work | Site returns 403 to automated requests outright |
| The Lancet                   | ❌ Doesn't work | Site blocks automated access; recent trials checked had no PMC copy to fall back to either |
| Annals of Oncology           | ❌ Doesn't work | Same ScienceDirect/Elsevier block; recent papers checked had no PMC copy either |
| NEJM                         | ❌ Doesn't work | Site returns a Cloudflare bot-challenge page instead of the file |
| Other publishers             | ❓ Unknown | Untested |

## Examples

```
$ refren 1758-2946-6-10.pdf 
  (calling Claude API...)
  First author last name : Krstajic
  Second author last name: Buturovic
  Journal                : Journal of Cheminformatics -> J Cheminform
  Year                   : 2014

  1758-2946-6-10.pdf  ->  Krstajic_Buturovic_JCheminform_2014.pdf
Copied to: Krstajic_Buturovic_JCheminform_2014.pdf

```

```

$ refren 2608.14705v1.pdf --supplement
  (calling Claude API...)
  Article type           : research
  First author last name : Buturović
  Second author last name: 
  Journal                : arXiv -> arXiv
  Year                   : 2026

  (checking arXiv for ancillary files...)

  2608.14705v1.pdf  ->  Buturović__arXiv_2026/Buturović__arXiv_2026.pdf
  Supplement saved to: Buturović__arXiv_2026/
    arXiv-2608.14705v1.tar.gz
```

## Install

```
$ pipx install refren # Linux, Mac
```

Requires an `ANTHROPIC_API_KEY` environment variable. If you don't have the API key, please read SETUP.md for instructions.

## Development

```bash
cd ~/github/refren
rm -f dist/*
uv run python -m build
uv run twine upload dist/*
```
