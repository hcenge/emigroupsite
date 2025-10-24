#!/usr/bin/env python3
"""
Fetch publications from Google Scholar (BASIC VERSION - essential fields only).
Uses the scholarly library to scrape Google Scholar author profiles.
This version captures only the core fields for faster, more reliable execution.
Requires: pip install scholarly
"""

import json
import sys
import time
from pathlib import Path

try:
    from scholarly import scholarly
except ImportError:
    print("Error: scholarly library not installed.")
    print("Install it with: pip install scholarly")
    sys.exit(1)


def fetch_scholar_publications(scholar_id):
    """Fetch publications from Google Scholar (basic fields only)."""
    try:
        print(f"Fetching publications for Google Scholar ID: {scholar_id}")
        print("This may take a few minutes due to rate limiting...")

        # Search for author by Google Scholar ID
        print("\nSearching for author...")
        author = scholarly.search_author_id(scholar_id)
        print("Author found, fetching details...")

        # Fill author details to get publications
        author_filled = scholarly.fill(author)

        print(f"\nFound author: {author_filled.get('name', 'Unknown')}")
        print(f"Affiliation: {author_filled.get('affiliation', 'Unknown')}")

        publications = []
        scholar_pubs = author_filled.get('publications', [])

        print(f"\nProcessing {len(scholar_pubs)} publications...")

        for i, pub in enumerate(scholar_pubs, 1):
            try:
                # Add delay to avoid rate limiting (important!)
                if i > 1:
                    time.sleep(2)  # 2 second delay between requests

                # Fill publication details
                print(f"  [{i}/{len(scholar_pubs)}] Fetching details...")
                pub_filled = scholarly.fill(pub)
                bib = pub_filled.get('bib', {})

                # Extract basic information only
                title = bib.get('title', 'Untitled')
                year = bib.get('pub_year', '')

                # Get authors - can be string or list
                authors_raw = bib.get('author', '')
                if isinstance(authors_raw, list):
                    authors = ', '.join(authors_raw)
                else:
                    authors = authors_raw

                # Determine publication type (default to journal-article)
                pub_type = 'journal-article'
                
                # Get additional bib fields
                # Get venue (journal/conference)
                venue = bib.get('venue', '')
                journal = bib.get('journal', '')
                conference = bib.get('conference', '')
                volume = bib.get('volume', '')
                number = bib.get('number', '')
                pages = bib.get('pages', '')

                # Create publication entry matching ORCID json format
                publication = {
                    'title': title,
                    'authors': authors,
                    'year': str(year) if year else '',
                    'venue': venue,
                    'journal': journal,
                    'conference': conference,
                    'volume': volume,
                    'number': number,
                    'pages': pages,
                }

                publications.append(publication)
                print(f"      ✓ {title[:60]}... ({year})")

            except Exception as e:
                print(f"      ✗ Error processing publication {i}: {e}")
                continue

        # Sort by year (newest first)
        publications.sort(
            key=lambda x: int(x['year']) if x['year'] and x['year'].isdigit() else 0,
            reverse=True
        )

        print(f"\n{'='*60}")
        print(f"Successfully fetched {len(publications)} publications")
        print(f"{'='*60}")
        return publications

    except Exception as e:
        print(f"\nError fetching publications: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check that the Google Scholar ID is correct")
        print("2. If you're getting rate limited, try again later")
        print("3. Consider using a proxy (see scholarly documentation)")
        print("4. Try installing free-proxy: pip install free-proxy")
        return []


def save_to_hugo_data(publications, output_file='data/publications.json'):
    """Save publications to Hugo data directory."""
    try:
        # Create data directory if it doesn't exist
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(publications, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Successfully saved {len(publications)} publications to {output_file}")

    except Exception as e:
        print(f"\n✗ Error saving publications: {e}")


if __name__ == "__main__":
    # Default to Robert Weatherup's Google Scholar ID
    default_scholar_id = "DLUsdFkAAAAJ"

    if len(sys.argv) > 1:
        scholar_id = sys.argv[1]
    else:
        scholar_id = default_scholar_id
        print(f"No Google Scholar ID provided, using default: {scholar_id} (Robert Weatherup)")

    print("\n" + "="*60)
    print("BASIC MODE: Fetching essential fields only")
    print("="*60 + "\n")

    publications = fetch_scholar_publications(scholar_id)

    if publications:
        # Get the project root directory (one level up from scripts/)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        output_path = project_root / 'data' / 'publications.json'

        save_to_hugo_data(publications, str(output_path))
    else:
        print("\nNo publications found or error occurred.")
        print("Please check the Google Scholar ID and try again.")
