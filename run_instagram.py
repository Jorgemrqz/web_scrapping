"""
Utility script to scrape only Instagram and persist the results.

Examples:
  python run_instagram.py --topic "inteligencia artificial" --limit 10
  python run_instagram.py --topic "#python" --output data/ig_test.json
"""

import argparse
import json
import os
import re
from datetime import datetime

from scrapers.instagram import scrape_instagram


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scrape"


def default_output(topic: str) -> str:
    stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = slugify(topic) if topic else "instagram"
    return os.path.join("data", f"instagram_{safe_topic}_corpus.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Instagram for a hashtag/topic")
    p.add_argument("--topic", required=True, help="Topic/hashtag (ej. 'python' o '#python')")
    p.add_argument("--username", default="", help="IG username (opcional si usas perfil persistente)")
    p.add_argument("--password", default="", help="IG password (opcional si usas perfil persistente)")
    p.add_argument("--limit", type=int, default=10, help="Number of posts to scrape")
    p.add_argument("--output", default=None, help="Destination JSON path")
    return p.parse_args()


def ensure_output_dir(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def main() -> None:
    args = parse_args()
    output_path = args.output or default_output(args.topic)
    ensure_output_dir(output_path)

    print(f"[Runner] Instagram | topic={args.topic} limit={args.limit}")
    data = scrape_instagram(args.topic, args.username, args.password, target_count=args.limit)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[Runner] Guardados {len(data)} registros en {output_path}")


if __name__ == "__main__":
    main()
