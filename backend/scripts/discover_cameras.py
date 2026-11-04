"""Explicit metadata discovery; writes backend-only candidates, never activates cameras."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.providers import CaltransProvider, fetch_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", type=int, required=True)
    parser.add_argument("--input", type=Path, help="Optional saved official JSON; no network")
    args = parser.parse_args()
    provider = CaltransProvider()
    provider.catalog_url(args.district)
    try:
        payload = (
            json.loads(args.input.read_text())
            if args.input
            else fetch_catalog(provider, args.district)
        )
        cameras = provider.parse(payload)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(
            f"Catalog unavailable or schema invalid ({type(exc).__name__}). "
            "Check official documentation; no source activated."
        ) from None
    output = Path("runtime/provider-catalog.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(c) for c in cameras], indent=2) + "\n")
    output.chmod(0o600)
    print(
        f"Saved {len(cameras)} unverified candidates to {output}. "
        "Permissions remain false; no media fetched."
    )


if __name__ == "__main__":
    main()
