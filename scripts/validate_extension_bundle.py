from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from zona4_graph_loader.io.extensions import ALLOWED_EXTENSION_KEYS, load_extension_collections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida paquetes de extension para el loader de ZONA4")
    parser.add_argument(
        "--extensions-dir",
        default="data/extensions",
        help="Directorio a validar (por defecto: data/extensions)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extensions_dir = Path(args.extensions_dir)
    merged, files = load_extension_collections(extensions_dir)

    print(f"extensions_dir: {extensions_dir}")
    print(f"files_detected: {len(files)}")
    if files:
        print("files:")
        for path in files:
            print(f"  - {path}")

    print("row_counts:")
    for key in sorted(ALLOWED_EXTENSION_KEYS):
        print(f"  {key}: {len(merged[key])}")


if __name__ == "__main__":
    main()
