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

_SI_PREFIXES = (
    "supporting information",
    "supplementary information",
    "data in support of",
)


def _is_supplementary(title: str) -> bool:
    t = title.lower().strip()
    return any(t.startswith(prefix) for prefix in _SI_PREFIXES)


def _is_duplicate(title: str, existing_titles: List[str]) -> bool:
    for existing in existing_titles:
        if _titles_match(title, existing):
            return True
    return False


def fetch_from_scholar(
    scholar_id: str,
    existing_titles: Optional[List[str]] = None,
    min_year: Optional[int] = None,
) -> List[Dict]:
    """Fetch new publications from Google Scholar.

    Makes one scholarly.fill(author) call to get all titles/years,
    then only calls scholarly.fill(pub) for new publications not
    already in the JSON.
    """
    print(f"Fetching publications from Google Scholar (ID={scholar_id})")

    try:
        author = scholarly.search_author_id(scholar_id)
        author_filled = scholarly.fill(author, sections=["publications"])
    except Exception as error:  # pragma: no cover - network errors
        print(f"✗ Failed to query Google Scholar: {error}")
        return []

    all_pubs = author_filled.get("publications", [])
    total = len(all_pubs)
    print(f"  Found {total} publications on Scholar")

    if existing_titles is None:
        existing_titles = []

    # First pass: identify which publications are new
    new_pubs = []
    skipped = 0
    skipped_si = 0
    for pub in all_pubs:
        bib = pub.get("bib", {})
        title = (bib.get("title") or "").strip()
        year = parse_year(bib.get("pub_year"))

        if not title:
            continue
        if _is_supplementary(title):
            skipped_si += 1
            continue
        if min_year and year and year < min_year:
            skipped += 1
            continue
        if _is_duplicate(title, existing_titles):
            skipped += 1
            continue

        new_pubs.append(pub)

    print(f"  {len(new_pubs)} new, {skipped} skipped as known/old, {skipped_si} skipped as SI")

    if not new_pubs:
        return []

    # Second pass: fill only new publications (the expensive calls)
    pubs = []
    for idx, pub in enumerate(new_pubs, 1):
        try:
            if idx > 1:
                time.sleep(1.5)  # rate limiting for Scholar

            pub_filled = scholarly.fill(pub)
            bib = pub_filled.get("bib", {})
            title = bib.get("title") or "Untitled"
            year = parse_year(bib.get("pub_year"))

            authors = bib.get("author")
            if isinstance(authors, list):
                authors = ", ".join(authors)

            venue = bib.get("venue") or ""
            doi, url = _extract_doi_and_url(pub_filled)

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
            print(f"    [{idx}/{len(new_pubs)}] {title[:70]} ({year or 'n/a'})")

        except KeyboardInterrupt:  # pragma: no cover
            print("\n⚠ Interrupted by user")
            break
        except Exception as error:  # pragma: no cover - network issues
            print(f"    ⚠ Error reading publication {idx}: {error}")

    print(f"✓ Retrieved {len(pubs)} new publications from Scholar")
    return pubs


def _extract_doi_and_url(pub: Dict):
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
    """Look up each publication on CrossRef to fill in authors, DOI, journal, URL."""
    if not publications:
        return
    print(f"Enriching {len(publications)} publications with CrossRef metadata…")

    for index, pub in enumerate(publications, 1):
        title = pub.get("title", "")
        if not title:
            continue

        try:
            params = {"query.title": title, "rows": 1}
            response = requests.get(CROSSREF_API, params=params, headers=USER_AGENT, timeout=10)
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
            if not items:
                print(f"    [{index}/{len(publications)}] No CrossRef match: {title[:60]}")
                continue

            item = items[0]

            # Only use the result if the title is a close match
            cr_title = (item.get("title") or [""])[0].lower().strip()
            if cr_title and _titles_match(title, cr_title):
                pub["doi"] = item.get("DOI") or pub.get("doi")
                pub["url"] = f"https://doi.org/{pub['doi']}" if pub.get("doi") else pub.get("url")

                container = item.get("container-title", [])
                if container:
                    pub["journal"] = container[0]
                pub["conference"] = item.get("event", {}).get("name") or pub.get("conference")

                # Authors
                if not pub.get("authors") and item.get("author"):
                    author_parts = []
                    for a in item["author"]:
                        given = a.get("given", "")
                        family = a.get("family", "")
                        author_parts.append(f"{given} {family}".strip())
                    pub["authors"] = ", ".join(author_parts)

                # Year
                for date_field in ("published-print", "published-online", "issued"):
                    parts = item.get(date_field, {}).get("date-parts")
                    if parts and parts[0]:
                        pub["year"] = str(parts[0][0])
                        break

                print(f"    [{index}/{len(publications)}] ✓ {title[:60]}")
            else:
                print(f"    [{index}/{len(publications)}] Title mismatch, skipped: {title[:60]}")

        except requests.HTTPError as error:  # pragma: no cover - network
            print(f"    ⚠ CrossRef HTTP error for '{title[:50]}…': {error}")
        except requests.RequestException as error:  # pragma: no cover
            print(f"    ⚠ CrossRef request error for '{title[:50]}…': {error}")
        except Exception as error:  # pragma: no cover
            print(f"    ⚠ CrossRef unknown error for '{title[:50]}…': {error}")

        time.sleep(0.2)  # rate limit


def _titles_match(a: str, b: str) -> bool:
    """Check if two titles are similar enough to be the same publication."""
    a = a.lower().strip().rstrip(".")
    b = b.lower().strip().rstrip(".")
    # Exact match after normalisation
    if a == b:
        return True
    # One contains the other (handles subtitle differences)
    if a in b or b in a:
        return True
    # Check word overlap ratio
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
    return overlap > 0.7


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


def remove_supplementary(publications: List[Dict]) -> List[Dict]:
    """Remove supporting information / supplementary entries."""
    before = len(publications)
    cleaned = [pub for pub in publications if not _is_supplementary(pub.get("title", ""))]
    removed = before - len(cleaned)
    if removed:
        print(f"  Removed {removed} supplementary/SI entries")
    return cleaned


def _needs_journal_refresh(pub: Dict) -> bool:
    """Check if a publication has a missing or preprint-only journal."""
    journal = (pub.get("journal") or "").strip()
    venue = (pub.get("venue") or "").strip()
    combined = (journal + " " + venue).lower()
    if not journal and not venue:
        return True
    return any(x in combined for x in ("rxiv", "preprint"))


def refresh_missing_journals(publications: List[Dict]) -> None:
    """Re-check CrossRef for publications with missing or preprint journals."""
    to_refresh = [pub for pub in publications if _needs_journal_refresh(pub)]
    if not to_refresh:
        print("All publications have journal metadata.")
        return

    print(f"Re-checking {len(to_refresh)} publications with missing/preprint journals…")

    updated = 0
    for idx, pub in enumerate(to_refresh, 1):
        title = pub.get("title", "")
        if not title:
            continue

        try:
            params = {"query.title": title, "rows": 1}
            response = requests.get(CROSSREF_API, params=params, headers=USER_AGENT, timeout=10)
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
            if not items:
                print(f"    [{idx}/{len(to_refresh)}] No match: {title[:60]}")
                continue

            item = items[0]
            cr_title = (item.get("title") or [""])[0]
            if not _titles_match(title, cr_title):
                print(f"    [{idx}/{len(to_refresh)}] Title mismatch: {title[:60]}")
                continue

            container = item.get("container-title", [])
            new_journal = container[0] if container else ""
            if new_journal and "rxiv" not in new_journal.lower():
                pub["journal"] = new_journal
                # Also update DOI/URL if missing
                if not pub.get("doi") and item.get("DOI"):
                    pub["doi"] = item["DOI"]
                    pub["url"] = f"https://doi.org/{pub['doi']}"
                # Update authors if missing
                if not pub.get("authors") and item.get("author"):
                    parts = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item["author"]]
                    pub["authors"] = ", ".join(parts)
                updated += 1
                print(f"    [{idx}/{len(to_refresh)}] ✓ {title[:50]} → {new_journal}")
            else:
                print(f"    [{idx}/{len(to_refresh)}] Still preprint/missing: {title[:60]}")

        except Exception as error:
            print(f"    [{idx}/{len(to_refresh)}] ⚠ Error: {error}")

        time.sleep(0.2)

    print(f"✓ Updated journal for {updated}/{len(to_refresh)} publications")


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

    # Build list of known publication titles for fuzzy deduplication
    existing_titles = []
    min_year = None
    if not mode_init:
        for pub in existing:
            title = (pub.get("title") or "").strip().lower()
            if title:
                existing_titles.append(title)
        # Use min_year as a cutoff: skip anything strictly before this year
        # (subtract 1 so we re-check publications from the most recent year)
        max_year = max(filter(None, map(parse_year, (pub.get("year") for pub in existing))), default=None)
        min_year = (max_year - 1) if max_year else None

    try:
        new_publications = fetch_from_scholar(
            args.scholar_id,
            existing_titles=existing_titles,
            min_year=min_year,
        )
        enrich_with_crossref(new_publications)

        if mode_init:
            merged = merge_publications([], new_publications)
        else:
            merged = merge_publications(existing, new_publications)

        merged = remove_supplementary(merged)
        sanitize_publications(merged)
        refresh_missing_journals(merged)

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
