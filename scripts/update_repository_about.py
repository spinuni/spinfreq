"""Review or apply SpinFreq's GitHub About metadata using authenticated gh."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Update description, website and topics on GitHub")
    args = parser.parse_args()
    metadata = json.loads((Path(__file__).resolve().parents[1]/".github/repository.json").read_text())
    if not args.apply:
        print(json.dumps(metadata, indent=2))
        return
    for method, endpoint, payload in (
        ("PATCH", "repos/spinuni/spinfreq", {key: metadata[key] for key in ("description", "homepage")}),
        ("PUT", "repos/spinuni/spinfreq/topics", {"names": metadata["topics"]}),
    ):
        result = subprocess.run(["gh", "api", "--method", method, endpoint, "--input", "-"],
                                input=json.dumps(payload), text=True, capture_output=True)
        if result.returncode:
            parser.exit(1, f"GitHub About update failed ({endpoint}): {result.stderr.strip()}\n")
    print("Updated spinuni/spinfreq description, website and topics.")


if __name__ == "__main__":
    main()
