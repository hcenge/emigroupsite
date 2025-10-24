# Publications Fetcher

`fetch_publications.py` pulls publications from Google Scholar, enriches them with CrossRef metadata, and writes the unified list to `data/publications.json` for Hugo to consume. It supports both full initialization and incremental updates.

## Setup

1. Enter the Nix development environment (all dependencies are already configured in flake.nix):
   ```bash
   nix develop
   ```

2. Find your Google Scholar ID:
   - Go to your Google Scholar profile
   - The ID is in the URL: `https://scholar.google.com/citations?user=YOUR_ID_HERE`

## Usage

Run the script from the repository root (inside the Nix shell):

```bash
python scripts/fetch_publications.py [SCHOLAR_ID] [--init] [--dry-run]
```

### Common commands

| Command | Description |
| --- | --- |
| `python scripts/fetch_publications.py` | Update mode. Loads the existing JSON, fetches only publications newer than the most recent entry, merges, sorts, and writes back. |
| `python scripts/fetch_publications.py --init` | Initialization mode. Ignores the existing file, fetches every publication from Scholar, enriches with CrossRef, and overwrites `publications.json`. |
| `python scripts/fetch_publications.py --dry-run` | Preview mode. Performs all network requests and merging logic but does **not** write files. |
| `python scripts/fetch_publications.py SOME_ID --init` | Force a full rebuild using a custom Scholar profile. |

The script automatically creates a timestamped backup (e.g. `publications.json.20241024_173500.bak`) before writing an updated file.

### What the script does

1. Loads `data/publications.json` (if it exists) and determines the newest year present.
2. Queries Google Scholar for the provided ID (Weatherup by default) and retrieves publications newer than the recorded max year (or all publications in `--init`).
3. For each new publication, attempts to augment missing metadata (DOI, venue, year) via the CrossRef API.
4. Merges the new records with the existing ones, removing duplicates (preferring entries with DOIs) and sorting by year, newest first.
5. Writes the merged list back to `data/publications.json`.

Re-run the script whenever you publish new work. Because the update mode only fetches publications newer than the most recent entry, this usually takes a few seconds.

## GitHub Action (Optional)

To automatically update publications weekly, create `.github/workflows/update-publications.yml`:

```yaml
name: Update Publications
on:
  schedule:
    - cron: '0 0 * * 0'  # Every Sunday at midnight
  workflow_dispatch:  # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: cachix/install-nix-action@v23
        with:
          github_access_token: ${{ secrets.GITHUB_TOKEN }}
      - name: Fetch publications
        run: nix develop --command python scripts/fetch_publications.py ${{ secrets.SCHOLAR_ID }}
      - name: Commit changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/publications.json
          git commit -m "Update publications from Google Scholar" || exit 0
          git push
```

Then add your Scholar ID as a repository secret named `SCHOLAR_ID`.
