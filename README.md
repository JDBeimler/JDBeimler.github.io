
# Minimal Math Personal Website (Static)

A tiny, math-friendly static site scaffold for academics. No build step required.

## Quick start
1. Open the folder in VS Code.
2. Install the "Live Server" extension (Ritwick Dey).
3. Right-click `index.html` → "Open with Live Server".

Edit `index.html`, `research.html`, `papers.html`, and `misc.html`. Math renders via MathJax.

## Custom domain + GitHub Pages
1. Create a GitHub repo and push this folder.
2. In GitHub → Settings → Pages → Branch: `main` (root).
3. Add your domain in "Custom domain" (e.g., `yourname.example`).
4. In your DNS provider, create a `CNAME` record pointing `www` to `<username>.github.io` (or root via ALIAS/ANAME if supported). GitHub will create a `CNAME` file automatically; or place one at repo root with your domain.
5. Enable HTTPS.

## Netlify (alternative)
- Drag & drop this folder onto app.netlify.com or connect the repo. No build command needed; publish dir = `/`.

## Math
MathJax v3 is preconfigured. Use `$...$` for inline and `$$...$$` for display.

## Tips
- Put PDFs in `/img` or another folder and link them in `papers.html`.
- You can later migrate to a generator (Hugo, Jekyll, Astro, Quarto) without changing the domain.
