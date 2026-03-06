#!/usr/bin/env python3
"""
SEC EDGAR Filings Scraper

Scrapes recent filings from the SEC EDGAR submissions API
(data.sec.gov), truncates filing content to a summary, and saves
results as JSON/CSV organized by company name. Designed to be run daily.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests

# SEC requires a User-Agent header with contact info
DEFAULT_USER_AGENT = "EdgarScraper/1.0 (your-email@example.com)"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"

OUTPUT_DIR = "edgar_data"
MAX_TRUNCATE_LENGTH = 500  # characters to keep from filing description


def get_headers(user_agent: str) -> dict:
    """Return required headers for SEC EDGAR requests."""
    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }


def fetch_company_filings(
    cik: str,
    filing_types: list[str],
    user_agent: str,
) -> list[dict]:
    """Fetch filings for a specific company by CIK number."""
    cik_padded = cik.zfill(10)
    url = f"{EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json"
    headers = get_headers(user_agent)

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    company_name = data.get("name", "Unknown")
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    filings = []
    for i, form in enumerate(forms):
        if filing_types and form not in filing_types:
            continue
        accession_clean = accessions[i].replace("-", "")
        filing = {
            "company_name": company_name,
            "cik": cik,
            "form_type": form,
            "filing_date": dates[i],
            "accession_number": accessions[i],
            "primary_document": primary_docs[i] if i < len(primary_docs) else "",
            "description": descriptions[i] if i < len(descriptions) else "",
            "filing_url": (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
                f"{primary_docs[i]}"
                if i < len(primary_docs)
                else ""
            ),
        }
        filings.append(filing)

    return filings


def fetch_filing_content(filing_url: str, user_agent: str) -> str:
    """Fetch the raw text content of a filing document."""
    headers = get_headers(user_agent)
    try:
        resp = requests.get(filing_url, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return f"[Error fetching content: {e}]"


def truncate_content(text: str, max_length: int = MAX_TRUNCATE_LENGTH) -> str:
    """Truncate filing content to a manageable summary length."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= max_length:
        return clean
    return clean[:max_length] + "..."


def scrape_filings(
    ciks: list[str],
    filing_types: list[str],
    days_back: int,
    user_agent: str,
    fetch_content: bool = False,
    max_content_length: int = MAX_TRUNCATE_LENGTH,
) -> list[dict]:
    """
    Main scraping function. Fetches filings for given CIKs.

    Args:
        ciks: List of CIK numbers to scrape
        filing_types: Form types to include (e.g. ["10-K", "10-Q", "8-K"])
        days_back: Number of days back to search
        user_agent: SEC-required User-Agent string
        fetch_content: Whether to fetch and truncate actual filing content
        max_content_length: Max characters to keep from filing content

    Returns:
        List of filing dictionaries with truncated data
    """
    date_to = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    all_filings = []

    for cik in ciks:
        print(f"Fetching filings for CIK {cik}...")
        try:
            filings = fetch_company_filings(cik, filing_types, user_agent)
        except Exception as e:
            print(f"  Error fetching CIK {cik}: {e}")
            continue

        # Filter by date range
        filings = [
            f for f in filings if date_from <= f.get("filing_date", "") <= date_to
        ]

        if fetch_content:
            for filing in filings:
                url = filing.get("filing_url", "")
                if url:
                    print(f"  Fetching content: {filing['form_type']} ({filing['filing_date']})...")
                    raw = fetch_filing_content(url, user_agent)
                    filing["content_truncated"] = truncate_content(raw, max_content_length)
                    time.sleep(0.1)  # Rate limit: SEC asks for <= 10 req/sec

        for filing in filings:
            filing["scraped_at"] = datetime.now().isoformat()

        all_filings.extend(filings)
        print(f"  Found {len(filings)} filings in date range.")
        time.sleep(0.1)  # Rate limit

    return all_filings


def save_json(filings: list[dict], output_path: str) -> None:
    """Save filings to a JSON file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(filings, f, indent=2)
    print(f"Saved {len(filings)} filings to {output_path}")


def save_csv(filings: list[dict], output_path: str) -> None:
    """Save filings to a CSV file."""
    if not filings:
        print("No filings to save.")
        return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fieldnames = list(filings[0].keys())

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filings)
    print(f"Saved {len(filings)} filings to {output_path}")


def group_by_company(filings: list[dict]) -> dict[str, list[dict]]:
    """Group filings by company name."""
    grouped = {}
    for filing in filings:
        name = filing.get("company_name", "Unknown")
        grouped.setdefault(name, []).append(filing)
    return grouped


def main():
    parser = argparse.ArgumentParser(
        description="Scrape SEC EDGAR filings with truncated content summaries."
    )
    parser.add_argument(
        "--ciks",
        nargs="+",
        required=True,
        help="CIK numbers of companies to scrape (e.g. 320193 for Apple)",
    )
    parser.add_argument(
        "--forms",
        nargs="*",
        default=[],
        help="Filing form types to include (default: all types)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days back to search (default: 1 for daily scraping)",
    )
    parser.add_argument(
        "--fetch-content",
        action="store_true",
        help="Fetch and truncate actual filing document content",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=MAX_TRUNCATE_LENGTH,
        help=f"Max characters for truncated content (default: {MAX_TRUNCATE_LENGTH})",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help=f"Output directory for saved data (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header (SEC requires name + email)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("SEC EDGAR Filings Scraper")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"CIKs: {', '.join(args.ciks)}")
    print(f"Forms: {', '.join(args.forms) if args.forms else 'ALL'}")
    print(f"Days back: {args.days}")
    print("=" * 60)

    filings = scrape_filings(
        ciks=args.ciks,
        filing_types=args.forms,
        days_back=args.days,
        user_agent=args.user_agent,
        fetch_content=args.fetch_content,
        max_content_length=args.max_length,
    )

    if not filings:
        print("\nNo filings found for the given criteria.")
        sys.exit(0)

    # Group by company and display summary
    grouped = group_by_company(filings)
    print(f"\nFound {len(filings)} total filings across {len(grouped)} companies:\n")
    for company, company_filings in grouped.items():
        print(f"  {company}:")
        for f in company_filings:
            print(f"    - {f['form_type']} ({f['filing_date']}): {f.get('description', 'N/A')}")

    # Save output
    date_stamp = datetime.now().strftime("%Y%m%d")

    if args.format in ("json", "both"):
        json_path = os.path.join(args.output_dir, f"filings_{date_stamp}.json")
        save_json(filings, json_path)

        # Also save per-company files
        for company, company_filings in grouped.items():
            safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in company)
            safe_name = safe_name.strip().replace(" ", "_")
            company_path = os.path.join(
                args.output_dir, "by_company", f"{safe_name}_{date_stamp}.json"
            )
            save_json(company_filings, company_path)

    if args.format in ("csv", "both"):
        csv_path = os.path.join(args.output_dir, f"filings_{date_stamp}.csv")
        save_csv(filings, csv_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
