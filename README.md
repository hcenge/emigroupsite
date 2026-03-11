# EMI Group Site

Hugo static site for the Electrochemical Materials & Interfaces group.

## Submitting content without Git

Group members can submit news articles and bio updates directly from GitHub — no Git or code editing required. Go to the repo's **Issues** tab, click **New Issue**, and pick a template:

### Submit News Post
Creates a news article. Fill in the title, date, summary, and article body (Markdown). You can drag-and-drop a featured image. A pull request is created automatically for an admin to review and merge.

### Add New Group Member
Creates a new bio page. Fill in your name, role, tagline, and any other fields. The photo will be saved as `firstname-lastname.jpg` in `assets/images/people/`.

### Update Existing Bio
Updates an existing member's page. Select your name from the dropdown, then only fill in the fields you want to change — everything else is preserved.

**How it works:** When an issue is submitted, a GitHub Action (`process-issue.yml`) runs `scripts/process_issue.py`, which parses the form fields, downloads any uploaded images, and creates the appropriate Hugo content files. It then opens a PR via `peter-evans/create-pull-request` for review.

**Maintainer note:** When a group member joins or leaves, update the person dropdown in `.github/ISSUE_TEMPLATE/bio-update.yml`.

## Repository structure

```
emigroupsite/
├── content/              # Markdown pages
│   ├── _index.md         # Home page
│   ├── research/         # One file per research area
│   ├── people/           # Profiles (plus alumni/ subfolder)
│   ├── news/             # News articles
│   ├── positions/        # Open positions
│   ├── facilities/       # Facilities info
│   └── publications/     # Publications page intro
├── assets/
│   ├── css/              # Stylesheets (SCSS)
│   └── images/           # All site images (processed by Hugo)
│       ├── people/       # Portraits (firstname-lastname.jpg)
│       ├── news/         # News article images
│       └── ...
├── data/
│   └── publications.json # Auto-generated from Google Scholar
├── layouts/              # Hugo templates
├── scripts/
│   ├── process_issue.py  # Issue form → Hugo content
│   └── fetch_publications.py
└── .github/
    ├── ISSUE_TEMPLATE/   # Issue form definitions
    └── workflows/        # GitHub Actions
```

## Editing content directly

1. Open the relevant Markdown file in `content/`.
2. Edit the front matter (YAML between `---` lines) for metadata, images, etc.
3. Edit the Markdown body below for text content.
4. Images go in `assets/images/` and are referenced as `/images/...` in front matter.

## Research project slugs

People are linked to research areas via the `projects` list in their front matter. Use these exact slugs:

- `electrocatalysis`
- `electrolyte-solvation`
- `electronic-structure`
- `operando-xray-techniques`
- `rechargeable-batteries`
- `thermocatalysis`

## Local development

```bash
nix develop          # enter dev environment
hugo server -D       # preview at localhost:1313
```
