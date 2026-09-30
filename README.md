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

`--supplement` also searches the web for the paper's supplementary material and downloads it. When used, refren creates a `FirstAuthor_SecondAuthor_JournalAbbrev_Year/` folder and puts both the renamed PDF and the downloaded supplement inside it

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

  2608.14705v1.pdf  ->  Buturović__arXiv_2026/Buturović__arXiv_2026.pdf

  (checking arXiv for ancillary files...)
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
