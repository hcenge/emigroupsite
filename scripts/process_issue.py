#!/usr/bin/env python3
"""Process GitHub issue form submissions into Hugo content files."""

import os
import re
import unicodedata
from pathlib import Path

import requests
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


CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def download_image(text, dest_dir, filename):
    """Extract first image URL from text, download it with the given filename.

    GitHub drag-and-drop produces markdown like:
        ![image](https://github.com/user-attachments/assets/...)
    or a bare URL.

    The filename should not include an extension — it will be derived from the
    response Content-Type header (with the URL as a fallback).
    """
    # Match markdown image syntax or bare GitHub user-attachments URL
    patterns = [
        r"!\[.*?\]\((https://[^\s)\"]+)\)",
        r"(https://github\.com/user-attachments/assets/[^\s)\"<>]+)",
        r"(https://github\.com/.*?/assets/[^\s)\"<>]+)",
    ]
    url = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group(1)
            break

    if not url:
        return None

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # GitHub user-attachment URLs are publicly accessible and redirect to
    # pre-signed S3 URLs. Sending an Authorization header can conflict with
    # the S3 signed URL auth, so we download without credentials.
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    # Determine extension from Content-Type header
    content_type = resp.headers.get("Content-Type", "")
    ext = CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip())
    if not ext:
        # Fall back to URL-based detection
        ext_match = re.search(r"\.(jpe?g|png|gif|webp)", url, re.IGNORECASE)
        ext = ext_match.group(0).lower() if ext_match else ".jpg"

    dest_path = dest_dir / f"{filename}{ext}"
    dest_path.write_bytes(resp.content)

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


def write_front_matter(f, items):
    """Write front matter preserving key order.

    items is a list of (key, value) tuples. Values can be strings, bools,
    ints, or lists of strings.
    """
    f.write("---\n")
    for key, value in items:
        if isinstance(value, bool):
            f.write(f"{key}: {str(value).lower()}\n")
        elif isinstance(value, list):
            f.write(f"{key}:\n")
            for item in value:
                f.write(f"  - {item}\n")
        elif isinstance(value, str) and "\n" in value:
            f.write(f"{key}: |\n")
            for line in value.splitlines():
                f.write(f"    {line}\n")
        elif isinstance(value, int):
            f.write(f"{key}: {value}\n")
        else:
            f.write(f'{key}: "{value}"\n')
    f.write("---\n")


def process_news(fields):
    """Create a news post from parsed issue fields."""
    title = fields.get("Article Title", "").strip()
    date = fields.get("Date", "").strip()
    summary = fields.get("Summary", "").strip()
    content = fields.get("Article Content", "").strip()
    image_text = fields.get("Featured Image", "")

    slug = slugify(title)
    filename = f"{date}-{slug}.md"

    # Download image if provided
    image_path = ""
    if image_text:
        downloaded = download_image(image_text, "assets/images/news", slug)
        if downloaded:
            image_path = f"/images/news/{downloaded.name}"

    # Build front matter in conventional order: title, date, summary, image, featured
    fm_items = [
        ("title", title),
        ("date", f"{date}T00:00:00Z"),
        ("summary", summary),
    ]
    if image_path:
        fm_items.append(("image", image_path))

    dest = Path("content/news") / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        write_front_matter(f, fm_items)
        if content:
            f.write(f"\n{content}\n")

    print(f"Created {dest}")


def write_bio(dest, fm_items, body):
    """Write a bio markdown file with ordered front matter and body."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        write_front_matter(f, fm_items)
        if body:
            f.write(f"\n{body}\n")


# Canonical key order for bio front matter
BIO_KEY_ORDER = [
    "title", "role", "tagline", "photo", "email", "join_year",
    "research_interests", "projects", "showdate",
]


def bio_fm_to_items(fm):
    """Convert a bio front matter dict to an ordered list of (key, value) tuples."""
    items = []
    for key in BIO_KEY_ORDER:
        if key in fm:
            items.append((key, fm[key]))
    # Include any extra keys not in the canonical order
    for key in fm:
        if key not in BIO_KEY_ORDER:
            items.append((key, fm[key]))
    return items


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

    # Download photo named after the person (e.g. helen-engelhardt.jpg)
    photo_path = ""
    if photo_text:
        downloaded = download_image(photo_text, "assets/images/people", slug)
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

    write_bio(dest, bio_fm_to_items(fm), biography)
    print(f"Created {dest}")


def process_bio_update(fields):
    """Update an existing bio, only overwriting non-empty submitted fields."""
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
        downloaded = download_image(photo_text, "assets/images/people", slug)
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

    write_bio(dest, bio_fm_to_items(fm), body)
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
