# Snapdragon AI Smart Process Manager — website

Static presentation/demo layer over the frozen Python backend. Zero dependencies.

## Local preview

```powershell
cd website
python -m http.server 3000
# open http://127.0.0.1:3000/
```

With the backend running (`python app.py` in repo root), the site uses
**LIVE LOCAL DATA** from `http://127.0.0.1:8099`. Otherwise it falls back to
`assets/snapshot.json` in explicit **DEMO MODE**. Override: `?api=http://host:8099`.

## Deploy (Vercel)

```powershell
cd website
npx vercel --prod
```

Static only — no serverless functions, no secrets, no backend keys.
Live telemetry requires the viewer's own local backend; public visitors
see the clearly-labelled snapshot demo.

## GitHub

```powershell
git init -b main
git add .
git commit -m "Snapdragon AI Smart Process Manager — competition website"
gh repo create snapdragon-website --public --source=. --push
```
