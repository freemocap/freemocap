"""Combine Electron updater entries for the separately built macOS architectures."""
import argparse
from copy import deepcopy
from pathlib import Path

import yaml


def merge_metadata(artifacts: Path, version: str) -> dict:
    merged = None
    for label in ('macos-arm64-apple-silicon', 'macos-x64-intel'):
        paths = list((artifacts / f'update-metadata-{label}').rglob('latest-mac.yml'))
        if len(paths) != 1:
            raise ValueError(f'Expected one updater metadata file for {label}, found {len(paths)}')
        data = yaml.safe_load(paths[0].read_text())
        if str(data['version']) != version:
            raise ValueError(f'Updater version mismatch for {label}: {data["version"]}')
        if not data.get('files'):
            raise ValueError(f'Missing updater files for {label}')
        files = deepcopy(data['files'])
        for item in files:
            extension = Path(item['url']).suffix
            if extension not in ('.zip', '.dmg'):
                raise ValueError(f'Unexpected macOS updater asset: {item["url"]}')
            item['url'] = f'freemocap_{version}_{label}{extension}'
        if merged is None:
            merged = deepcopy(data)
            merged['files'] = []
            if data.get('path'):
                merged['path'] = f'freemocap_{version}_{label}{Path(data["path"]).suffix}'
        merged['files'].extend(files)
    return merged


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('version')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(yaml.safe_dump(merge_metadata(args.artifacts, args.version), sort_keys=False))
