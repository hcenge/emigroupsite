#!/usr/bin/env python3
"""Process GitHub issue form submissions into Hugo content files."""

import os
import re
import unicodedata
import urllib.request
from pathlib import Path

import yaml


def parse_issue_body(body):
    """Parse GitHub issue form body into {header: value} dict.

    GitHub renders issue forms as:
        ### Label\n\nValue\n\n### Next Label\n\n...
    """
    sections = {}
    current_header = None
    current_lines = []

    for line in body.splitlines():
        if line.startswith("### "):
            if current_header is not None:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_header is not None:
        sections[current_header] = "\n".join(current_lines).strip()

    # Treat GitHub's empty-field sentinel as blank
    for key in sections:
        if sections[key] == "_No response_":
            sections[key] = ""

    return sections


def slugify(text):
    """Convert text to a URL-friendly slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def download_image(text, dest_dir):
    """Extract first image URL from text, download it, return local path.

    GitHub drag-and-drop produces markdown like:
        ![image](https://github.com/user-attachments/assets/...)
    or a bare URL.
    """
    # Match markdown image syntax or bare GitHub user-attachments URL
    patterns = [
        r"!\[.*?\]\((https://.*?)\)",
        r"(https://github\.com/user-attachments/assets/[^\s)]+)",
        r"(https://github\.com/.*?/assets/[^\s)]+)",
    ]
    url = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group(1)
            break

    if not url:
        return None

    # Determine file extension from URL or default to .jpg
    ext_match = re.search(r"\.(jpe?g|png|gif|webp)", url, re.IGNORECASE)
    ext = ext_match.group(0).lower() if ext_match else ".jpg"

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Derive filename from the last path segment of the URL
    url_filename = url.rstrip("/").split("/")[-1]
    # Clean up query params
    url_filename = url_filename.split("?")[0]
    if not re.search(r"\.\w+$", url_filename):
        url_filename += ext

    dest_path = dest_dir / url_filename
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


PROJECT_SLUG_MAP = {
    "Electrocatalysis": "electrocatalysis",
    "Electrolyte Solvation": "electrolyte-solvation",
    "Electronic Structure": "electronic-structure",
    "Operando X-ray Techniques": "operando-xray-techniques",
    "Rechargeable Batteries": "rechargeable-batteries",
    "Thermocatalysis": "thermocatalysis",
}


def parse_checkboxes(text):
    """Parse checkbox items, return list of checked labels."""
    results = []
    for line in text.splitlines():
        match = re.match(r"- \[([xX ])\] (.+)", line.strip())
        if match and match.group(1).lower() == "x":
            results.append(match.group(2).strip())
    return results


def process_news(fields):
    """Create a news post from parsed issue fields."""
    title = fields.get("Article Title", "").strip()
    date = fields.get("Date", "").strip()
    summary = fields.get("Summary", "").strip()
    featured_text = fields.get("Featured?", "No").strip()
    featured = featured_text == "Yes"
    content = fields.get("Article Content", "").strip()
    image_text = fields.get("Featured Image", "")

    slug = slugify(title)
    filename = f"{date}-{slug}.md"

    # Download image if provided
    image_path = ""
    if image_text:
        downloaded = download_image(image_text, "assets/images/news")
        if downloaded:
            # Store path relative to project root, with leading /
            image_path = f"/images/news/{downloaded.name}"

    # Build front matter
    front_matter = {
        "title": title,
        "date": f"{date}T00:00:00Z",
        "summary": summary,
        "featured": featured,
    }
    if image_path:
        front_matter["image"] = image_path

    dest = Path("content/news") / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(front_matter, default_flow_style=False, allow_unicode=True))
        f.write("---\n")
        if content:
            f.write(f"\n{content}\n")

    print(f"Created {dest}")


def write_bio(dest, fm, body):
    """Write a bio markdown file with front matter and body."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(fm, default_flow_style=False, allow_unicode=True))
        f.write("---\n")
        if body:
            f.write(f"\n{body}\n")


def process_new_bio(fields):
    """Create a new bio from parsed issue fields."""
    name = fields.get("Full Name", "").strip()
    slug = slugify(name)
    dest = Path("content/people") / f"{slug}.md"

    role = fields.get("Role", "").strip()
    tagline = fields.get("Tagline", "").strip()
    email = fields.get("Email", "").strip()
    join_year = fields.get("Year Joined", "").strip()
    photo_text = fields.get("Profile Photo", "")
    research_interests = fields.get("Research Interests", "").strip()
    projects_text = fields.get("Projects", "")
    biography = fields.get("Biography", "").strip()

    # Download photo if provided
    photo_path = ""
    if photo_text:
        downloaded = download_image(photo_text, "assets/images/people")
        if downloaded:
            photo_path = f"/images/people/{downloaded.name}"

    # Parse project checkboxes
    checked = parse_checkboxes(projects_text)
    project_slugs = [PROJECT_SLUG_MAP[label] for label in checked if label in PROJECT_SLUG_MAP]

    fm = {"title": name}
    if role:
        fm["role"] = role
    if tagline:
        fm["tagline"] = tagline
    if photo_path:
        fm["photo"] = photo_path
    if email:
        fm["email"] = email
    if join_year:
        try:
            fm["join_year"] = int(join_year)
        except ValueError:
            fm["join_year"] = join_year
    if research_interests:
        fm["research_interests"] = research_interests + "\n"
    if project_slugs:
        fm["projects"] = project_slugs
    fm["showdate"] = False

    write_bio(dest, fm, biography)
    print(f"Created {dest}")


def process_bio_update(fields):
    """Update an existing bio, only overwriting fields the user ticked."""
    name = fields.get("Person to Update", "").strip()
    slug = slugify(name)
    dest = Path("content/people") / f"{slug}.md"

    if not dest.exists():
        raise FileNotFoundError(f"No existing bio found at {dest}")

    # Load existing content
    text = dest.read_text()
    match = re.match(r"^---\n(.+?)\n---\n?(.*)", text, re.DOTALL)
    existing_fm = {}
    existing_body = ""
    if match:
        existing_fm = yaml.safe_load(match.group(1)) or {}
        existing_body = match.group(2).strip()

    fm = dict(existing_fm)

    role = fields.get("Role", "").strip()
    if role and role != "No change":
        fm["role"] = role

    tagline = fields.get("Tagline", "").strip()
    if tagline:
        fm["tagline"] = tagline

    email = fields.get("Email", "").strip()
    if email:
        fm["email"] = email

    join_year = fields.get("Year Joined", "").strip()
    if join_year:
        try:
            fm["join_year"] = int(join_year)
        except ValueError:
            fm["join_year"] = join_year

    photo_text = fields.get("Profile Photo", "")
    if photo_text:
        downloaded = download_image(photo_text, "assets/images/people")
        if downloaded:
            fm["photo"] = f"/images/people/{downloaded.name}"

    research_interests = fields.get("Research Interests", "").strip()
    if research_interests:
        fm["research_interests"] = research_interests + "\n"

    checked = parse_checkboxes(fields.get("Projects", ""))
    project_slugs = [PROJECT_SLUG_MAP[label] for label in checked if label in PROJECT_SLUG_MAP]
    if project_slugs:
        fm["projects"] = project_slugs

    body = existing_body
    biography = fields.get("Biography", "").strip()
    if biography:
        body = biography

    write_bio(dest, fm, body)
    print(f"Updated {dest}")


def main():
    body = os.environ.get("ISSUE_BODY", "")
    labels = os.environ.get("ISSUE_LABELS", "")

    if not body:
        print("No issue body found")
        return

    fields = parse_issue_body(body)

    if "news" in labels:
        process_news(fields)
    elif "new-bio" in labels:
        process_new_bio(fields)
    elif "bio-update" in labels:
        process_bio_update(fields)
    else:
        print(f"Unknown submission type. Labels: {labels}")


if __name__ == "__main__":
    main()
