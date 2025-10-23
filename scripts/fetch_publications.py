#!/usr/bin/env python3
"""
Fetch publications from Google Scholar and save to Hugo data directory.
Requires: pip install scholarly
"""

import json
from scholarly import scholarly
import sys

def fetch_publications(scholar_id):
    """Fetch publications for a given Google Scholar ID."""
    try:
        # Search for the author
        print(f"Fetching publications for Scholar ID: {scholar_id}")
        author = scholarly.search_author_id(scholar_id)
        author = scholarly.fill(author, sections=['publications'])

        publications = []

        for pub in author['publications']:
            # Fill in publication details
            pub_filled = scholarly.fill(pub)

            publication = {
                'title': pub_filled.get('bib', {}).get('title', 'Untitled'),
                'authors': pub_filled.get('bib', {}).get('author', ''),
                'year': pub_filled.get('bib', {}).get('pub_year', ''),
                'venue': pub_filled.get('bib', {}).get('venue', ''),
                'citation': pub_filled.get('bib', {}).get('citation', ''),
                'citations': pub_filled.get('num_citations', 0),
                'url': pub_filled.get('pub_url', ''),
                'scholar_url': pub_filled.get('author_pub_id', '')
            }
            publications.append(publication)
            
            print(f"Fetched publication: {publication['title']}")

        # Sort by year (newest first)
        publications.sort(key=lambda x: int(x['year']) if x['year'] else 0, reverse=True)

        return publications

    except Exception as e:
        print(f"Error fetching publications: {e}")
        return []

def save_to_hugo_data(publications, output_file='data/publications.json'):
    """Save publications to Hugo data directory."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(publications, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved {len(publications)} publications to {output_file}")
    except Exception as e:
        print(f"Error saving publications: {e}")

if __name__ == "__main__":
    # Replace with your Google Scholar ID
    # You can find it in your Google Scholar profile URL
    # e.g., https://scholar.google.com/citations?user=SCHOLAR_ID

    if len(sys.argv) > 1:
        scholar_id = sys.argv[1]
    else:
        print("Usage: python fetch_publications.py YOUR_SCHOLAR_ID")
        print("Example: python fetch_publications.py abcdef123456")
        sys.exit(1)

    publications = fetch_publications(scholar_id)

    if publications:
        save_to_hugo_data(publications, '../data/publications.json')
    else:
        print("No publications found or error occurred.")
