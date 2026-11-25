# Deployment Guide

The live site (<https://emi.materials.ox.ac.uk>) is served by Apache on `int-webs.materials.ox.ac.uk`. The server does **not** pull updates by itself — each deploy is copied over by hand.

```
push/merge to main → GitHub Actions builds to gh-pages → copy gh-pages to the server
```

## Local Development

```bash
nix develop
hugo server -D   # preview at http://localhost:1313
```

## Deploying

1. Push or merge to `main`.
2. Wait for the green tick on the **Build and Deploy** run in GitHub → Actions.
3. With the Materials VPN on, run:

   ```bash
   scripts/deploy.sh
   ```

   This is the same as doing it by hand:

   ```bash
   ssh emi@int-webs.materials.ox.ac.uk
   cd ~/emi-deploy && git pull --ff-only && cp -r ~/emi-deploy/* ~/emi
   ```

   `~/emi` is a symlink to `/var/www/emi.materials.ox.ac.uk`.

If the pull says "divergent branches", run `git reset --hard origin/gh-pages` in `~/emi-deploy`, then copy.

### If GitHub Actions is down

Build `main` on your own computer and push it to `gh-pages` before copying:

```bash
scripts/deploy.sh --build
```

## Server layout

- `~/emi-deploy` — checkout of the `gh-pages` branch
- `~/emi` → `/var/www/emi.materials.ox.ac.uk` — what Apache serves
- `~/nrg-int`, `~/emigroupsite` — old setup, not live

## Missing Publications

- Run the fetch script: `nix develop --command python scripts/fetch_publications.py`
- Rebuild and deploy
