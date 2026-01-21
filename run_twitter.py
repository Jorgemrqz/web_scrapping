"""Utility script to scrape only X/Twitter and persist the results.

Usage examples (from repository root):
    python run_twitter.py --topic "cambio climatico"
    python run_twitter.py --output data/mi_archivo.json

If credentials are stored in config.py they will be reused automatically.
You can also provide them via CLI flags.
"""

import argparse
import json
import os
import re
from datetime import datetime

from scrapers.twitter import scrape_twitter

import config


def slugify(value: str) -> str:
    """Convert text into a filesystem-friendly slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scrape"


def default_output(topic: str) -> str:
    stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = slugify(topic) if topic else "twitter"
    return os.path.join("data", f"twitter_{safe_topic}_{stamped}.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Twitter/X for a topic")
    parser.add_argument("--topic", help="Topic or search query", default=config.DEFAULT_TOPIC)
    parser.add_argument("--username", help="Username for X", default=config.X_USER)
    parser.add_argument("--password", help="Password for X", default=config.X_PASSWORD)
    parser.add_argument("--output", help="Destination JSON path")
    return parser.parse_args()


def ensure_output_dir(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def main() -> None:
    args = parse_args()

    if not args.topic:
        raise SystemExit("Debes proporcionar un --topic o definir DEFAULT_TOPIC en config.py")

    output_path = args.output or default_output(args.topic)
    ensure_output_dir(output_path)

    print(f"[Runner] Buscando en X el tema: {args.topic}")
    data = scrape_twitter(args.topic, args.username, args.password)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    print(f"[Runner] Guardados {len(data)} registros en {output_path}")


if __name__ == "__main__":
    main()
