# Deployment Guide

## Local Development

1. Enter the Nix development environment:

   ```bash
   nix develop
   ```

2. Start the Hugo development server:

   ```bash
   hugo server -D
   ```

3. View your site at: <http://localhost:1313>

## Building for Production

Build the site with minification:

```bash
nix develop --command hugo --minify
```

This generates the production-ready site in the `public/` directory.

## Deploying to Cloudflare Workers

### First-time Setup

1. Make sure you have Wrangler installed and logged in:

   ```bash
   npx wrangler login
   ```

### Deploy Workflow

1. **Clean build** (recommended before deploying):

   ```bash
   rm -rf public
   nix develop --command hugo --minify
   ```

2. **Deploy to production**:

   ```bash
   npx wrangler deploy
   ```

   or

   ```bash
   npx wrangler publish
   ```

### Quick Deploy (One Command)

```bash
rm -rf public && nix develop --command hugo --minify && npx wrangler deploy
```

## Configuration Files

- **wrangler.toml** - Cloudflare Workers configuration with static site serving
- **worker.js** - Worker script that serves static files with clean URL support
- **hugo.toml** - Hugo site configuration including minify settings
- **flake.nix** - Nix development environment with Hugo and Python

## Troubleshooting

### Error 1101 or CSS Issues

- Delete `public/` and rebuild: `rm -rf public && nix develop --command hugo --minify`
- Check that images are in `static/images/`

### Deploy Errors

- Ensure `public/` directory exists and has content
- Check that `bucket = "./public"` is set in wrangler.toml

### Missing Publications

- Run the fetch script: `nix develop --command python scripts/fetch_publications.py YOUR_SCHOLAR_ID`
- Rebuild the site after fetching

## Custom Domain

To use a custom domain:

1. Go to Cloudflare Workers dashboard
2. Select your worker
3. Go to "Triggers" → "Custom Domains"
4. Add your domain and follow DNS instructions
5. Update `baseURL` in `hugo.toml` to match your domain
