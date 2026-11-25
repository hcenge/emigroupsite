#!/usr/bin/env bash
# Deploy the site to emi.materials.ox.ac.uk.
#
#   scripts/deploy.sh          copy the current gh-pages branch to the server
#   scripts/deploy.sh --build  build origin/main locally and push it to gh-pages
#                              first (use when GitHub Actions is down)
#
# Needs the Materials VPN and SSH access to emi@int-webs.materials.ox.ac.uk.
set -euo pipefail

SERVER="emi@int-webs.materials.ox.ac.uk"
REPO="$(git rev-parse --show-toplevel)"

if [[ "${1:-}" == "--build" ]]; then
  TMP="$(mktemp -d)"
  trap 'git -C "$REPO" worktree remove --force "$TMP/main" 2>/dev/null || true;
        git -C "$REPO" worktree remove --force "$TMP/pages" 2>/dev/null || true;
        rm -rf "$TMP"' EXIT

  git -C "$REPO" fetch -q origin main gh-pages
  SHA="$(git -C "$REPO" rev-parse origin/main)"
  git -C "$REPO" worktree add -q --detach "$TMP/main" origin/main
  git -C "$REPO" worktree add -q --detach "$TMP/pages" origin/gh-pages

  echo "Building $SHA..."
  (cd "$TMP/main" && nix develop "$REPO" --command hugo --minify)

  rsync -a --delete --exclude .git "$TMP/main/public/" "$TMP/pages/"
  touch "$TMP/pages/.nojekyll"
  git -C "$TMP/pages" add -A
  if git -C "$TMP/pages" diff --cached --quiet; then
    echo "gh-pages already up to date."
  else
    git -C "$TMP/pages" commit -qm "deploy: $SHA"
    git -C "$TMP/pages" push -q origin HEAD:gh-pages
    echo "Pushed to gh-pages."
  fi
elif [[ -n "${1:-}" ]]; then
  echo "Unknown option: $1" >&2
  exit 1
fi

echo "Copying gh-pages to the server..."
ssh "$SERVER" 'cd ~/emi-deploy && git pull --ff-only && git log --oneline -1 && cp -r ~/emi-deploy/* ~/emi'
echo "Live: https://emi.materials.ox.ac.uk/"
