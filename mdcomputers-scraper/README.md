# MDComputers Product Scraper

A small Python scraper that searches MDComputers and exports product details to CSV.

## Features

- Search by any product term
- Supports multiple search-result pages
- Extracts product name, regular price, sale price, discount, product URL, and image URL
- Exports results to CSV
- Uses a configurable delay between requests

## Setup

```bash
cd mdcomputers-scraper
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Usage

```bash
python mdcomputers_scraper.py "external hard drive"
```

Scrape three pages:

```bash
python mdcomputers_scraper.py "external hard drive" --pages 3 --output external_hard_drives.csv
```

## Notes

The scraper targets the public MDComputers search-results HTML. Website markup can change, so CSS selectors may need maintenance if MDComputers changes its page structure. Use a reasonable request delay and respect MDComputers' terms, robots rules, and applicable laws.

## Example search URL

`https://mdcomputers.in/?route=product/search&search=external%20hard%20drive`
