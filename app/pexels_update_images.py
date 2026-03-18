import argparse
import json
import os
import re
import sqlite3
import time
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "app.db")
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")

CATEGORY_KEYWORDS = {
    "Supermarket": ["grocery", "food"],
    "Health & Beauty": ["beauty", "skincare"],
    "Home & Office": ["home", "office"],
    "Phones & Tablets": ["smartphone", "tablet"],
    "Computing": ["laptop", "computer"],
    "Electronics": ["electronics", "gadget"],
    "Fashion": ["fashion", "clothing"],
    "Baby Products": ["baby", "infant"],
    "Gaming": ["gaming", "console"],
    "Sporting Goods": ["sports", "fitness"],
}

STOPWORDS = {
    "and", "with", "for", "set", "pack", "pro", "max", "mini", "ultra", "plus", "lite",
    "new", "classic", "modern", "digital", "wireless", "smart", "blue", "black", "white",
    "gold", "grey", "gray", "red", "green", "pink", "1l", "1kg", "2pk", "5g",
}


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def build_query(name, category):
    tokens = re.sub(r"[^a-z0-9 ]+", " ", name.lower()).split()
    tokens = [t for t in tokens if len(t) > 2 and not t.isdigit() and t not in STOPWORDS]
    tokens = tokens[:3]
    base = CATEGORY_KEYWORDS.get(category, ["product", "shopping"])
    query_terms = tokens + base
    return " ".join(query_terms) if query_terms else "product shopping"


def fetch_pexels_image(api_key, query, page=1, per_page=1, retries=2):
    url = (
        "https://api.pexels.com/v1/search"
        f"?query={quote(query)}&per_page={per_page}&page={page}"
    )
    headers = {
        "Authorization": api_key,
        "User-Agent": "ecommerce-image-updater/1.0",
    }
    req = Request(url, headers=headers)
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            snippet = detail[:200].strip().replace("\n", " ")
            if exc.code in (401, 403):
                raise RuntimeError(f"Pexels auth failed ({exc.code}): {snippet}") from exc
            if attempt >= retries:
                print(f"Skipping query after HTTP {exc.code}: {query}")
                return None
            time.sleep(1.0)
        except (URLError, TimeoutError) as exc:
            if attempt >= retries:
                print(f"Skipping query after error: {query} ({exc})")
                return None
            time.sleep(1.0)
    photos = payload.get("photos", [])
    if not photos:
        return None
    src = photos[0].get("src", {})
    return src.get("large") or src.get("medium") or src.get("original")


def main():
    parser = argparse.ArgumentParser(description="Update product images using Pexels.")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--limit", type=int, default=0, help="Max products to update (0 = all).")
    parser.add_argument("--start-id", type=int, default=0, help="Only update products with id >= this.")
    parser.add_argument("--end-id", type=int, default=0, help="Only update products with id <= this.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between API calls.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing image URLs.")
    args = parser.parse_args()

    load_env(ENV_PATH)
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise SystemExit("PEXELS_API_KEY not found. Set it in .env or environment variables.")

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, tag, image FROM products ORDER BY id").fetchall()
    updated = 0

    for idx, row in enumerate(rows, start=1):
        if args.start_id and row["id"] < args.start_id:
            continue
        if args.end_id and row["id"] > args.end_id:
            continue
        if args.limit and updated >= args.limit:
            break
        if row["image"] and row["image"].startswith("http") and not args.force:
            continue

        query = build_query(row["name"], row["tag"])
        page = (row["id"] % 5) + 1
        image_url = fetch_pexels_image(api_key, query, page=page, per_page=1)
        if not image_url:
            fallback = build_query(row["tag"], row["tag"])
            image_url = fetch_pexels_image(api_key, fallback, page=1, per_page=1)
        if image_url:
            cur.execute("UPDATE products SET image = ? WHERE id = ?", (image_url, row["id"]))
            updated += 1

        if args.sleep:
            time.sleep(args.sleep)

        if idx % 10 == 0:
            print(f"Processed {idx}/{len(rows)} products...")

    conn.commit()
    conn.close()
    print(f"Updated {updated} products.")


if __name__ == "__main__":
    main()
