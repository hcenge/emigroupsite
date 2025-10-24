#!/usr/bin/env python3
"""
Update missing DOIs in publications.json using CrossRef API.
CrossRef is the official DOI registration agency and provides a free API.
This script reads the existing publications and fills in missing DOIs.
Requires: pip install requests
"""

import json
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: requests library not installed.")
    print("Install it with: pip install requests")
    sys.exit(1)


def get_metadata_from_crossref(title, author=None):
    """
    Query CrossRef API to find metadata for a given paper title.

    Args:
        title: Paper title to search for
        author: Optional author name to improve matching

    Returns:
        Dictionary with metadata fields if found, None otherwise
        Returns: doi, year, venue, volume, issue, pages, publisher
    """
    url = "https://api.crossref.org/works"

    # Build query parameters - get ALL metadata
    params = {
        "query.title": title,
        "rows": 1,  # Only get top result
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("message", {}).get("items"):
            item = data["message"]["items"][0]

            # Extract all useful metadata
            metadata = {}

            # DOI
            metadata['doi'] = item.get("DOI")

            # Year - try multiple date fields
            year = None
            if item.get("published-print", {}).get("date-parts"):
                year = item["published-print"]["date-parts"][0][0]
            elif item.get("published-online", {}).get("date-parts"):
                year = item["published-online"]["date-parts"][0][0]
            elif item.get("created", {}).get("date-parts"):
                year = item["created"]["date-parts"][0][0]
            metadata['year'] = str(year) if year else None

            # Venue/Journal
            container_title = item.get("container-title", [])
            metadata['venue'] = container_title[0] if container_title else None
            metadata['journal'] = container_title[0] if container_title else None

            # Volume, Issue, Pages
            metadata['volume'] = item.get("volume")
            metadata['number'] = item.get("issue")  # CrossRef calls it 'issue'
            metadata['pages'] = item.get("page")

            # Publisher
            metadata['publisher'] = item.get("publisher")

            # URL
            metadata['url'] = f"https://doi.org/{metadata['doi']}" if metadata['doi'] else None

            return metadata

    except requests.exceptions.Timeout:
        print(f"      ⚠ Timeout querying CrossRef")
    except requests.exceptions.RequestException as e:
        print(f"      ⚠ Error querying CrossRef: {e}")
    except Exception as e:
        print(f"      ⚠ Unexpected error: {e}")

    return None


def load_publications(file_path):
    """Load publications from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)


def save_publications(publications, file_path, create_backup=True):
    """Save publications to JSON file with optional backup."""
    if create_backup:
        # Create backup with timestamp
        backup_path = file_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        shutil.copy2(file_path, backup_path)
        print(f"\n✓ Backup created: {backup_path.name}")

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(publications, f, indent=2, ensure_ascii=False)


def update_dois(file_path, dry_run=False):
    """
    Update missing metadata in publications file using CrossRef.

    Args:
        file_path: Path to publications.json
        dry_run: If True, show what would be updated without saving
    """
    print("="*70)
    print("Metadata Update Script - Using CrossRef API")
    print("="*70)
    print(f"\nReading: {file_path}")

    publications = load_publications(file_path)

    print(f"Total publications: {len(publications)}")

    # Find publications with missing critical fields (DOI or year)
    needs_update = []
    for i, pub in enumerate(publications):
        # Safely check for empty/None fields
        doi = pub.get('doi')
        year = pub.get('year')

        # Check if DOI is empty (None or empty string)
        doi_empty = doi is None or (isinstance(doi, str) and doi.strip() == '')
        # Check if year is empty (None or empty string)
        year_empty = year is None or (isinstance(year, str) and year.strip() == '')

        # Add to list if missing DOI or year
        if doi_empty or year_empty:
            needs_update.append(i)

    print(f"Publications needing updates: {len(needs_update)}")

    # Count missing fields safely
    missing_doi = 0
    missing_year = 0
    for i in needs_update:
        doi = publications[i].get('doi')
        year = publications[i].get('year')
        if doi is None or (isinstance(doi, str) and doi.strip() == ''):
            missing_doi += 1
        if year is None or (isinstance(year, str) and year.strip() == ''):
            missing_year += 1

    print(f"  - Missing DOI: {missing_doi}")
    print(f"  - Missing year: {missing_year}")

    if len(needs_update) == 0:
        print("\n✓ All publications have complete metadata!")
        return

    if dry_run:
        print("\n⚠ DRY RUN MODE - No changes will be saved")

    print(f"\nQuerying CrossRef for {len(needs_update)} publications...")
    print("(This may take a few minutes)")
    print("-"*70)

    # Statistics
    found = 0
    not_found = 0
    fields_updated = {
        'doi': 0,
        'year': 0,
        'venue': 0,
        'volume': 0,
        'number': 0,
        'pages': 0,
        'publisher': 0,
        'url': 0
    }

    for count, idx in enumerate(needs_update, 1):
        try:
            pub = publications[idx]
            title = pub.get('title', '') if pub else ''
            authors = pub.get('authors', '') if pub else ''
            current_year = pub.get('year', '') if pub else ''

            print(f"\n[{count}/{len(needs_update)}] {title[:60]}...")
            print(f"      Current - Year: {current_year or 'MISSING'}, DOI: {pub.get('doi', 'MISSING')[:30] if pub.get('doi') else 'MISSING'}...")

            # Skip if no title
            if not title:
                print(f"      ⚠ Skipping - no title")
                not_found += 1
                continue

            # Query CrossRef for complete metadata
            metadata = get_metadata_from_crossref(title, authors)

            if metadata and metadata.get('doi'):
                print(f"      ✓ Found metadata from CrossRef")

                # Update each field if it's missing or empty in our data
                updated_fields = []

                for field in ['doi', 'year', 'venue', 'journal', 'volume', 'number', 'pages', 'publisher', 'url']:
                    current_value = pub.get(field)
                    new_value = metadata.get(field)

                    # Check if current value is empty (None or empty string)
                    is_empty = current_value is None or (isinstance(current_value, str) and current_value.strip() == '')

                    # Update if current is empty and new value exists
                    if is_empty and new_value:
                        publications[idx][field] = new_value
                        updated_fields.append(field)
                        if field in fields_updated:
                            fields_updated[field] += 1

                if updated_fields:
                    print(f"      ✓ Updated: {', '.join(updated_fields)}")
                    if 'year' in updated_fields:
                        print(f"        Year: {metadata.get('year')}")
                    if 'doi' in updated_fields:
                        print(f"        DOI: {metadata.get('doi')}")

                found += 1
            else:
                print(f"      ✗ Metadata not found in CrossRef")
                not_found += 1

            # Rate limiting - be polite to CrossRef API
            # 50 requests per second limit
            if count < len(needs_update):  # Don't wait after last one
                time.sleep(0.1)  # 100 milliseconds between requests

        except Exception as e:
            print(f"      ✗ Error processing publication: {e}")
            not_found += 1
            continue

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total processed: {len(needs_update)}")
    print(f"Metadata found: {found}")
    print(f"Metadata not found: {not_found}")
    print(f"Success rate: {(found/len(needs_update)*100):.1f}%")
    print("\nFields updated:")
    for field, count in fields_updated.items():
        if count > 0:
            print(f"  - {field}: {count}")

    # Save results
    if not dry_run:
        print("\nSaving updated publications...")
        save_publications(publications, file_path, create_backup=True)
        print(f"✓ Updated file saved: {file_path}")
    else:
        print("\n⚠ Dry run complete - no changes saved")
        print("Run without --dry-run to save changes")


if __name__ == "__main__":
    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    # Get file path
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        file_path = Path(sys.argv[1])
    else:
        # Default to data/publications.json
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        file_path = project_root / 'data' / 'publications.json'

    try:
        update_dois(file_path, dry_run=dry_run)
        print("\n✓ Complete!")
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        print("Partial progress has been saved (if any)")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
