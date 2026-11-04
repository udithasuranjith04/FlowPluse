"""Opt-in genuine TMS freshness probe. Never assigns a measurement station to a camera."""

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.digitraffic import DigitrafficService, ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", help="Optional numeric TMS station ID")
    args = parser.parse_args()
    provider = DigitrafficService(Settings().digitraffic_user)
    report: dict = {
        "success": False,
        "origin": "Official roadside TMS, not camera-derived",
        "attempts": [],
    }
    try:
        rows = provider.tms_stations()
        ids = (
            [args.station]
            if args.station
            else [r["id"] for r in rows if r["collection_status"] == "GATHERING"][:5]
        )
        for ident in ids:
            result = provider.tms(ident)
            fresh = [r for r in result["measurements"] if not r["stale"]]
            report["attempts"].append({"station": ident, "fresh_measurements": len(fresh)})
            if fresh:
                report.update({"success": True, "result": result})
                break
        if not report["success"]:
            report["error"] = (
                "No valid fresh speed/count measurements in the bounded station sample"
            )
    except ProviderError as exc:
        report["error"] = str(exc)
    finally:
        provider.http.close()
    output = Path("runtime/tms-verification.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
