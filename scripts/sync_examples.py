"""Generate/check the offline wheel gallery from canonical example recipes."""
import argparse
import json
from pathlib import Path

from spinfreq.bundled_examples import RECIPES
from spinfreq.config import JobConfig
from spinfreq.studies import StudyConfig


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    records = {}
    for name, metadata in RECIPES.items():
        source = ROOT/'examples'/metadata['source']
        (JobConfig if metadata['kind'] == 'job' else StudyConfig).load(source)
        records[name] = json.loads(source.read_text(encoding='utf-8'))
    expected = json.dumps({'schema_version': 1, 'examples': records}, indent=2, sort_keys=True)+'\n'
    target = ROOT/'spinfreq/data/examples.json'
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf-8') != expected:
            parser.exit(1, 'Bundled gallery is stale; run python scripts/sync_examples.py\n')
        print(f'{len(records)} bundled examples match canonical sources')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected.encode('utf-8'))
    print(f'Bundled {len(records)} examples')


if __name__ == '__main__':
    main()
