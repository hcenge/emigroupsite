#!/usr/bin/env python3
"""Unified Google Scholar → CrossRef publications fetcher.

Usage
-----
python3 scripts/fetch_publications.py [SCHOLAR_ID] [--init] [--dry-run]

Default Scholar ID: DLUsdFkAAAAJ (Prof Robert Weatherup)
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    from scholarly import scholarly
except ImportError as exc:
    print("Error: scholarly library missing. Install with 'pip install scholarly'.")
    raise SystemExit(1) from exc

try:
    import requests
except ImportError as exc:
    print("Error: requests library missing. Install with 'pip install requests'.")
    raise SystemExit(1) from exc

GOOGLE_SCHOLAR_ID_DEFAULT = "DLUsdFkAAAAJ"  # Prof Robert Weatherup
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
DATA_PATH = DATA_DIR / "publications.json"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_SUFFIX = datetime.now().strftime(".%Y%m%d_%H%M%S.bak")
CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = {
    "User-Agent": "EMI-group-site/1.0 (mailto:robert.weatherup@materials.ox.ac.uk)",
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def load_publications(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_publications(path: Path, publications: Iterable[Dict]) -> None:
    # Preserve deterministic ordering of keys for prettier diffs
    ordered = [OrderedDict(sorted(pub.items())) for pub in publications]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def make_backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"publications.{timestamp}.json"
    backup_path = BACKUP_DIR / backup_name
    shutil.copy(path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def parse_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Scholar fetching
# ---------------------------------------------------------------------------

def fetch_from_scholar(
    scholar_id: str,
    min_year: Optional[int] = None,
    existing_count: int = 0,
) -> List[Dict]:
    print(f"Fetching publications from Google Scholar (ID={scholar_id})")

    try:
        author = scholarly.search_author_id(scholar_id)
        author_filled = scholarly.fill(author, sections=["publications"])
    except Exception as error:  # pragma: no cover - network errors
        print(f"✗ Failed to query Google Scholar: {error}")
        return []

    pubs = []
    total = len(author_filled.get("publications", []))
    print(f"  Found {total} publications on Scholar")

    if min_year and total <= existing_count:
        print("  No additional publications detected since last update – skipping fetch")
        return []

    consecutive_older = 0
    MAX_OLDER_BREAK = 5

    for idx, pub in enumerate(author_filled.get("publications", []), 1):
        try:
            if idx > 1:
                time.sleep(1.5)  # gentle rate limiting

            pub_filled = scholarly.fill(pub)
            bib = pub_filled.get("bib", {})
            title = bib.get("title") or "Untitled"
            year = parse_year(bib.get("pub_year"))

            if min_year and year and year <= min_year:
                consecutive_older += 1
                if consecutive_older >= MAX_OLDER_BREAK:
                    print("  Reached previously catalogued publications – stopping early")
                    break
                continue
            else:
                consecutive_older = 0

            authors = bib.get("author")
            if isinstance(authors, list):
                authors = ", ".join(authors)

            venue = bib.get("venue") or ""
            doi, url = extract_doi_and_url(pub_filled)

            pubs.append(
                {
                    "title": title,
                    "authors": format_authors(authors) if authors else "",
                    "year": str(year) if year else "",
                    "journal": venue,
                    "conference": "",
                    "doi": doi,
                    "url": url,
                }
            )
            print(f"    [{idx}/{total}] {title[:70]} ({year or 'n/a'})")

        except KeyboardInterrupt:  # pragma: no cover
            print("\n⚠ Interrupted by user")
            break
        except Exception as error:  # pragma: no cover - network issues
            print(f"    ⚠ Error reading publication {idx}: {error}")

    print(f"✓ Retrieved {len(pubs)} publications from Scholar")
    return pubs


def extract_doi_and_url(pub: Dict) -> (Optional[str], Optional[str]):
    bib = pub.get("bib", {})
    doi = None
    url = None

    for candidate in (bib.get("pub_url"), pub.get("eprint_url")):
        if not candidate:
            continue
        if "doi.org" in candidate:
            doi = candidate.split("doi.org/")[-1]
            url = candidate
            break
        if url is None:
            url = candidate

    return doi, url


# ---------------------------------------------------------------------------
# CrossRef enrichment
# ---------------------------------------------------------------------------

def enrich_with_crossref(publications: List[Dict]) -> None:
    print("Enriching publications with CrossRef metadata…")

    for index, pub in enumerate(publications, 1):
        needs_lookup = not pub.get("doi")
        if not needs_lookup:
            continue

        title = pub.get("title", "")
        if not title:
            continue

        try:
            params = {"query.title": title, "rows": 1}
            response = requests.get(CROSSREF_API, params=params, headers=USER_AGENT, timeout=10)
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
            if not items:
                continue

            item = items[0]
            pub["doi"] = item.get("DOI") or pub.get("doi")
            pub["journal"] = item.get("container-title", [pub.get("journal")])[0] or pub.get("journal")
            pub["conference"] = item.get("event", {}).get("name") or pub.get("conference")

            year = None
            for date_field in ("published-print", "published-online", "issued"):
                parts = item.get(date_field, {}).get("date-parts")
                if parts and parts[0]:
                    year = parts[0][0]
                    break
            if year:
                pub["year"] = str(year)

        except requests.HTTPError as error:  # pragma: no cover - network
            print(f"    ⚠ CrossRef HTTP error for '{title[:50]}…': {error}")
        except requests.RequestException as error:  # pragma: no cover
            print(f"    ⚠ CrossRef request error for '{title[:50]}…': {error}")
        except Exception as error:  # pragma: no cover
            print(f"    ⚠ CrossRef unknown error for '{title[:50]}…': {error}")

        time.sleep(0.2)  # rate limit


# ---------------------------------------------------------------------------
# Merge & sort
# ---------------------------------------------------------------------------

def merge_publications(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    combined: Dict[str, Dict] = {}

    for pub in existing + new:
        key = pub.get("doi") or pub.get("title")
        if not key:
            continue
        combined[key] = pub

    def sort_key(pub: Dict):
        year = parse_year(pub.get("year")) or 0
        title = pub.get("title", "")
        return (-year, title.lower())

    return sorted(combined.values(), key=sort_key)


def format_authors(authors: str) -> str:
    if not authors:
        return ""
    formatted = authors.replace(" and ", ", ")
    # collapse repeated commas/spaces
    parts = [part.strip() for part in formatted.split(",") if part.strip()]
    return ", ".join(parts)


def mark_preprints(publications: List[Dict]) -> None:
    for pub in publications:
        journal = pub.get("journal", "")
        conference = pub.get("conference", "")
        if "arXiv" in journal or "arXiv" in conference:
            pub["type"] = "preprint"
        else:
            pub.setdefault("type", "journal-article")


def sanitize_publications(publications: List[Dict]) -> None:
    for pub in publications:
        pub["authors"] = format_authors(pub.get("authors", ""))
    mark_preprints(publications)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch / update publications from Google Scholar")
    parser.add_argument("scholar_id", nargs="?", default=GOOGLE_SCHOLAR_ID_DEFAULT)
    parser.add_argument("--init", action="store_true", help="Force full re-fetch and overwrite data")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without writing files")
    args = parser.parse_args(argv)

    existing = load_publications(DATA_PATH)
    mode_init = args.init or not existing
    print(f"Loaded {len(existing)} existing publications from {DATA_PATH}")

    print(f"Mode: {'INIT' if mode_init else 'UPDATE'}")
    if args.dry_run:
        print("(Dry run - no files will be written)")

    min_year = None if mode_init else max(filter(None, map(parse_year, (pub.get("year") for pub in existing))), default=None)

    try:
        new_publications = fetch_from_scholar(
            args.scholar_id,
            min_year=min_year,
            existing_count=len(existing),
        )
        enrich_with_crossref(new_publications)

        if mode_init:
            merged = merge_publications([], new_publications)
        else:
            merged = merge_publications(existing, new_publications)

        sanitize_publications(merged)

        if args.dry_run:
            print(f"Dry run: would write {len(merged)} publications to {DATA_PATH}")
            return 0

        make_backup(DATA_PATH)
        save_publications(DATA_PATH, merged)
        print(f"✓ Saved {len(merged)} publications to {DATA_PATH}")
        return 0

    except KeyboardInterrupt:  # pragma: no cover
        print("\n⚠ Aborted by user")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
