# Publications Fetcher

This script fetches your publications from Google Scholar and saves them to Hugo's data directory.

## Setup

1. Enter the Nix development environment (all dependencies are already configured in flake.nix):
   ```bash
   nix develop
   ```

2. Find your Google Scholar ID:
   - Go to your Google Scholar profile
   - The ID is in the URL: `https://scholar.google.com/citations?user=YOUR_ID_HERE`

## Usage

Run the script from the scripts directory:

```bash
cd scripts
python fetch_publications.py YOUR_SCHOLAR_ID
```

Example:
```bash
python fetch_publications.py abc123def456
```

The script will:
1. Fetch all publications from your Google Scholar profile
2. Save them to `data/publications.json`
3. Hugo will automatically use this data to display publications on the Publications page

## Updating Publications

Simply re-run the script whenever you want to update the publications list. You can:
- Run it manually when you publish new papers
- Set up a cron job to run it automatically
- Use a GitHub Action to run it on a schedule (see below)

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
