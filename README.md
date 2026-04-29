![License](https://img.shields.io/badge/License-MIT-yellow.svg)

# refren: scientific manuscript PDF renamer

Renames a PDF file - assumed to contain a scientific manuscript - to `FirstAuthor_SecondAuthor_JournalAbbrev_Year.pdf` using Claude AI to extract bibliographic metadata from the PDF

## Usage

```
refren <pdf_file> [--remove]
```

`--remove` deletes the original PDF after creating the renamed copy.

## Example

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
