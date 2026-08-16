#!/usr/bin/env python3
"""Scrape product details from MDComputers search results.

Usage:
    python mdcomputers_scraper.py "external hard drive"
    python mdcomputers_scraper.py "external hard drive" --output products.csv

The script requests the public search-results page and extracts product name,
regular price, sale price, discount, product URL, and image URL when available.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://mdcomputers.in/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def build_search_url(search_term: str, page: int = 1) -> str:
    """Build an MDComputers product-search URL."""
    params = {
        "route": "product/search",
        "search": search_term,
    }
    if page > 1:
        params["page"] = page
    return f"{BASE_URL}?{urlencode(params)}"


def clean_text(value: str | None) -> str:
    """Normalize whitespace in scraped text."""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_price(value: str | None) -> float | None:
    """Convert strings such as ₹10,990 into a numeric price."""
    if not value:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def find_product_cards(soup: BeautifulSoup):
    """Find likely product cards while tolerating minor markup changes."""
    selectors = [
        ".product-thumb",
        ".product-layout",
        ".product-grid .product-layout",
        ".product-list .product-layout",
    ]

    for selector in selectors:
        cards = soup.select(selector)
        if cards:
            return cards

    # Fallback: locate product-title links and walk up the DOM.
    cards = []
    seen = set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        link = heading.find("a", href=True)
        if not link:
            continue
        parent = heading
        for _ in range(5):
            parent = parent.parent
            if parent is None:
                break
            text = clean_text(parent.get_text(" ", strip=True))
            if "₹" in text:
                marker = id(parent)
                if marker not in seen:
                    cards.append(parent)
                    seen.add(marker)
                break
    return cards


def extract_product(card, base_url: str) -> dict:
    """Extract common product fields from one card."""
    name = ""
    product_url = ""

    # Product title is commonly an h4/h3/h2 link.
    for selector in ["h4 a", "h3 a", "h2 a", ".name a", ".caption a"]:
        link = card.select_one(selector)
        if link:
            name = clean_text(link.get_text(" ", strip=True))
            product_url = urljoin(base_url, link.get("href", ""))
            if name:
                break

    if not name:
        link = card.find("a", href=True)
        if link:
            name = clean_text(link.get_text(" ", strip=True))
            product_url = urljoin(base_url, link.get("href", ""))

    image_url = ""
    image = card.find("img")
    if image:
        image_url = urljoin(
            base_url,
            image.get("data-src") or image.get("src") or "",
        )

    price_texts = [clean_text(x.get_text(" ", strip=True)) for x in card.select(".price")]
    card_text = clean_text(card.get_text(" ", strip=True))

    # Prefer explicit old/new price elements when present.
    old_price_text = ""
    new_price_text = ""
    old_price = card.select_one(".price-old, .price .old-price, del")
    new_price = card.select_one(".price-new, .price .new-price, .price")

    if old_price:
        old_price_text = clean_text(old_price.get_text(" ", strip=True))
    if new_price:
        new_price_text = clean_text(new_price.get_text(" ", strip=True))

    prices = []
    for text in price_texts + [card_text]:
        for match in re.findall(r"₹\s*[\d,]+(?:\.\d+)?", text):
            value = parse_price(match)
            if value is not None and value not in prices:
                prices.append(value)

    regular_price = parse_price(old_price_text) or (prices[0] if len(prices) > 1 else None)
    sale_price = parse_price(new_price_text) or (prices[-1] if prices else None)

    if regular_price is not None and sale_price is not None and sale_price > regular_price:
        regular_price, sale_price = sale_price, regular_price

    discount = ""
    discount_match = re.search(r"-\s*(\d+)%", card_text)
    if discount_match:
        discount = f"{discount_match.group(1)}%"

    return {
        "name": name,
        "regular_price_inr": regular_price,
        "sale_price_inr": sale_price,
        "discount": discount,
        "product_url": product_url,
        "image_url": image_url,
    }


def scrape(search_term: str, pages: int = 1, delay: float = 1.0) -> list[dict]:
    """Scrape one or more search-result pages."""
    session = requests.Session()
    session.headers.update(HEADERS)
    products = []
    seen_urls = set()

    for page in range(1, pages + 1):
        url = build_search_url(search_term, page)
        response = session.get(url, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = find_product_cards(soup)
        if not cards:
            print(f"No product cards found on page {page}: {url}")
            break

        page_count = 0
        for card in cards:
            product = extract_product(card, BASE_URL)
            if not product["name"]:
                continue
            key = product["product_url"] or product["name"]
            if key in seen_urls:
                continue
            seen_urls.add(key)
            products.append(product)
            page_count += 1

        print(f"Page {page}: found {page_count} products")
        time.sleep(delay)

    return products


def save_csv(products: list[dict], output_file: str) -> None:
    """Save scraped products as CSV."""
    fields = [
        "name",
        "regular_price_inr",
        "sale_price_inr",
        "discount",
        "product_url",
        "image_url",
    ]
    with open(output_file, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(products)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape MDComputers search results")
    parser.add_argument("search_term", help="Product search term, e.g. 'external hard drive'")
    parser.add_argument("--pages", type=int, default=1, help="Number of result pages to scrape")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")
    parser.add_argument("--output", default="products.csv", help="CSV output filename")
    args = parser.parse_args()

    products = scrape(args.search_term, pages=max(1, args.pages), delay=max(0, args.delay))
    save_csv(products, args.output)

    print(f"\nSaved {len(products)} products to {args.output}")
    for product in products:
        print(
            f"- {product['name']} | "
            f"₹{product['sale_price_inr'] if product['sale_price_inr'] is not None else 'N/A'}"
        )


if __name__ == "__main__":
    main()
