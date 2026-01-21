"""Utility script to scrape only LinkedIn and persist the results.

Usage examples:
    python run_linkedin.py --topic "inteligencia artificial"
    python run_linkedin.py --output data/mi_archivo_linkedin.json
"""

import argparse
import json
import os
import re
from datetime import datetime

# Importamos el scraper de linkedin
from scrapers.linkedin import scrape_linkedin

import config


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scrape"


def default_output(topic: str) -> str:
    stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = slugify(topic) if topic else "linkedin"
    return os.path.join("data", f"linkedin_{safe_topic}_{stamped}.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape LinkedIn for a topic")
    parser.add_argument("--topic", help="Topic or search query", default=config.DEFAULT_TOPIC)
    parser.add_argument("--email", help="LinkedIn Email", default=config.LI_EMAIL)
    parser.add_argument("--password", help="LinkedIn Password", default=config.LI_PASSWORD)
    parser.add_argument("--limit", help="Number of posts to scrape", type=int, default=10)
    parser.add_argument("--output", help="Destination JSON path")
    return parser.parse_args()


def ensure_output_dir(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def main() -> None:
    args = parse_args()

    if not args.topic:
        raise SystemExit("Debes proporcionar un --topic")

    output_path = args.output or default_output(args.topic)
    ensure_output_dir(output_path)

    print(f"[Runner] Buscando en LinkedIn el tema: {args.topic} | Límite: {args.limit}")
    
    # Ejecutamos el scraper
    # Nota: Si ya tienes las cookies guardadas, email y password pueden dejarse vacíos
    data = scrape_linkedin(args.topic, args.email, args.password, target_count=args.limit)

    if data:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        print(f"[Runner] Guardados {len(data)} registros en {output_path}")
    else:
        print("[Runner] No se obtuvieron datos (lista vacía).")


if __name__ == "__main__":
    main()
