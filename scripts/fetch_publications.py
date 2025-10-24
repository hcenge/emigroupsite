#!/usr/bin/env python3
"""
Fetch publications from ORCID public API and save to Hugo data directory.
No authentication required for public ORCID data.
Requires: pip install requests
"""

import json
import requests
import sys
from pathlib import Path

def fetch_orcid_publications(orcid_id):
    """Fetch publications from ORCID public API."""
    try:
        print(f"Fetching publications for ORCID: {orcid_id}")

        # ORCID public API endpoint
        url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
        headers = {
            'Accept': 'application/json'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        publications = []

        # Parse ORCID works
        if 'group' in data:
            for group in data['group']:
                # Get the preferred/first work summary
                if 'work-summary' in group and len(group['work-summary']) > 0:
                    work = group['work-summary'][0]

                    # Only include journal articles
                    work_type = work.get('type', '')
                    if work_type != 'journal-article':
                        continue

                    # Extract basic info
                    title = work.get('title', {}).get('title', {}).get('value', 'Untitled')
                    year = work.get('publication-date', {}).get('year', {}).get('value', '')

                    # Get journal/venue
                    venue = work.get('journal-title', {}).get('value', '') if work.get('journal-title') else ''

                    # Get external IDs (DOI, etc.)
                    external_ids = work.get('external-ids', {}).get('external-id', [])
                    doi = None
                    pub_url = None

                    for ext_id in external_ids:
                        if ext_id.get('external-id-type') == 'doi':
                            doi = ext_id.get('external-id-value')
                            pub_url = f"https://doi.org/{doi}"
                            break

                    # If no DOI, try to get URL from external IDs
                    if not pub_url:
                        for ext_id in external_ids:
                            if ext_id.get('external-id-url', {}).get('value'):
                                pub_url = ext_id['external-id-url']['value']
                                break

                    # Get put-code to fetch detailed work information (for authors)
                    put_code = work.get('put-code')
                    authors = ''

                    if put_code:
                        authors = fetch_detailed_work(orcid_id, put_code)

                    publication = {
                        'title': title,
                        'authors': authors,
                        'year': year,
                        'venue': venue,
                        'doi': doi,
                        'url': pub_url,
                        'type': work_type
                    }

                    publications.append(publication)
                    print(f"  - {title} ({year})")

        # Sort by year (newest first)
        publications.sort(key=lambda x: int(x['year']) if x['year'] else 0, reverse=True)

        print(f"\nSuccessfully fetched {len(publications)} journal articles")
        return publications

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: ORCID {orcid_id} not found. Please check the ORCID ID.")
        else:
            print(f"HTTP Error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching publications: {e}")
        return []

def fetch_detailed_work(orcid_id, put_code):
    """Fetch detailed information for a specific work (including authors)."""
    try:
        url = f"https://pub.orcid.org/v3.0/{orcid_id}/work/{put_code}"
        headers = {'Accept': 'application/json'}

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        work = response.json()

        # Extract contributors/authors
        contributors = work.get('contributors', {}).get('contributor', [])
        authors = []

        for contrib in contributors:
            credit_name = contrib.get('credit-name', {})
            if credit_name and credit_name.get('value'):
                authors.append(credit_name['value'])

        return ', '.join(authors) if authors else ''

    except Exception as e:
        print(f"  Warning: Could not fetch detailed info for work {put_code}: {e}")
        return ''

def save_to_hugo_data(publications, output_file='data/publications.json'):
    """Save publications to Hugo data directory."""
    try:
        # Create data directory if it doesn't exist
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(publications, f, indent=2, ensure_ascii=False)

        print(f"\nSuccessfully saved {len(publications)} publications to {output_file}")

    except Exception as e:
        print(f"Error saving publications: {e}")

if __name__ == "__main__":
    # Default to Robert Weatherup's ORCID if no argument provided
    default_orcid = "0000-0002-3993-9045"

    if len(sys.argv) > 1:
        orcid_id = sys.argv[1]
    else:
        orcid_id = default_orcid
        print(f"No ORCID provided, using default: {orcid_id} (Robert Weatherup)")

    publications = fetch_orcid_publications(orcid_id)

    if publications:
        # Get the project root directory (one level up from scripts/)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        output_path = project_root / 'data' / 'publications.json'

        save_to_hugo_data(publications, str(output_path))
    else:
        print("No publications found or error occurred.")
