"""Bundle report JSON into demo/data for static hosting (GitHub Pages / Vercel)."""

from chainsage.demo_build import build_demo_bundle

if __name__ == "__main__":
    path = build_demo_bundle()
    print(f"Wrote {path}")
