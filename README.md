# EMI Group Site – Content Editing Guide

This guide is for non-technical editors who maintain the website content. All text, images, and metadata can be managed through Markdown files (`.md`) and static assets (`.png`, `.jpg`, etc.). You never have to touch the HTML templates in the `layouts/` directory.

## Repository structure overview

```
emigroupsite/
├── content/            # All Markdown pages
│   ├── _index.md       # Home page (front page)
│   ├── research/       # One file per research area
│   ├── people/         # Individual profiles (plus `alumni/` subfolder)
│   ├── positions/      # Positions page description & project cards
│   ├── facilities/     # Facilities information
│   └── publications/   # Intro text for the publications page
├── data/
│   └── publications.json  # List of publications (auto-generated, usually no manual edits)
├── images/             # All site images (referenced via `/images/...`)
├── layouts/            # Hugo templates (no edits needed for regular content updates)
└── scripts/            # Helper scripts (e.g., publications fetcher)
```

### Editing basics

1. **Open the relevant Markdown file inside `content/`.** Each page or section has its own file, e.g. `content/research/electrocatalysis.md`.
2. **Edit the front matter (the YAML between `---` lines)** to change titles, metadata, images, and structured information such as project assignments.
3. **Update the Markdown body** below the front matter for regular text, lists, and links.
4. **Add or replace images** in the `images/` folder and reference them from the appropriate front matter (`image: "/images/..."`).
5. **Save, preview locally, and commit/push** when finished (ask a developer if you’re unfamiliar with Git).

_Learn Markdown:_ Here is a brief but comprehensive [Markdown formatting guide](https://www.markdownguide.org/basic-syntax/) covering headings, images, lists, links, tables, and more.

## Page-specific notes

### Home page (`content/_index.md`)
- The banner, icon “pillars”, and call-to-action are defined in the front matter.
- Keep indentation consistent; each pillar looks like:
  ```yaml
  pillars:
    - icon: "🔬"
      title: "Operando Tools"
      description: "Characterising catalysts while they work."
  ```
- The main body (`{{ .Content }}`) is standard Markdown below the front matter.

### Research pages (`content/research/*.md`)
- `image`: path to the hero image (store under `images/...`).
- `projects` and `team` links are auto-generated from person profiles; to add or remove people, update their `projects:` list in `content/people/NAME.md`.
- The page body contains the descriptive text and bullet lists.

### People (`content/people/*.md`)
- Each person has front matter for:
  - `role` (e.g., `postdoc`, `phd`, `masters`, `pi`)
  - `photo` (image path in `images/people/`)
  - `tagline` (short description shown under their name)
  - `projects` (list of research slugs they work on; keeps research ⇄ people links in sync)
  - `email`, `website`, etc.
- Markdown below the front matter is used for the biography section.
- Alumni live under `content/people/alumni/`.

### Positions (`content/positions/_index.md`)
- Front matter includes a list `phd_projects:`. Each entry requires:
  ```yaml
  - title: "Project title"
    url: "https://..."
    research: "electrocatalysis"   # matches a research page slug
    collaborators:
      - "Prof Robert Weatherup"
      - "Dr Jane Doe"
    image: "/images/positions/project-image.png"
  ```
- To add a new project, copy an existing entry and adjust the fields.
- Images belong in `images/positions/`.

### Facilities & other pages
- Most sections (`content/facilities/_index.md`, `content/publications/_index.md`, etc.) are simple Markdown with short YAML headers (`title`, optional intro copy).

## Images
- Place images in the appropriate folder under `images/`. A few common directories:
  - `images/people/` for portraits
  - `images/positions/` for project cards
  - `images/projects/` or `images/research/` for research pages
- Reference images using the `/images/...` path in front matter or Markdown: `![Alt text](/images/projects/sample.png)`.

## Tips for safe editing
- **Stick to YAML + Markdown.** Avoid raw HTML unless absolutely necessary.
- **Keep indentation consistent** in YAML lists and nested structures.
- **Match slugs carefully.** Research slugs (e.g., `electrocatalysis`, `rechargeable-batteries`) are used across content files; use existing ones or consult the team before creating new slugs.
- **Preview locally** (`hugo server -D`) to catch formatting or YAML errors before committing.

Happy editing!
