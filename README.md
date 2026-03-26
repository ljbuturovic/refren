# refren: scientific manuscript PDF renamer

Renames a PDF file (assumed to contain a scientific manuscript) to `FirstAuthor_SecondAuthor_JournalAbbrev_Year.pdf` using Claude AI to extract bibliographic metadata from the first page.

## Usage

```
refren <pdf_file> [--remove]
```

`--remove` deletes the original PDF after creating the renamed copy.

## Example

```
$ refren s41467-020-14975-w.pdf
  (calling Claude API...)
  First author last name : Mayhew
  Second author last name: Buturovic
  Journal                : Nature Communications -> Nat Commun
  Year                   : 2020

  s41467-020-14975-w.pdf  ->  Mayhew_Buturovic_NatCommun_2020.pdf
Copied to: Mayhew_Buturovic_NatCommun_2020.pdf
```

## Install

```
pipx install refren
```

The program uses Claude, and therefore requires an `ANTHROPIC_API_KEY` environment variable.

## Development

```bash
cd ~/github/refren
uv run python -m build
uv run twine upload dist/*
```
