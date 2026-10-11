"""Offline validation of the repository's documented braced BibTeX subset."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

KEY = r"[A-Za-z][A-Za-z0-9_:.+-]*"
SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.test-artifacts',
        '.pytest_cache', '.mypy_cache', '.ruff_cache', '.docusaurus', 'build',
        'dist', 'target', 'generated', 'evidence'}
EXTENSIONS = {'.md', '.mdx', '.py', '.rs', '.ts', '.tsx', '.js', '.jsx',
              '.yaml', '.yml', '.json', '.tex'}


def parse_bib(text: str) -> dict[str, dict[str, str]]:
    """Fail closed on malformed/unsupported input; allow nested braced values."""
    pos = 0
    entries = {}

    def skip() -> None:
        nonlocal pos
        while pos < len(text):
            if text[pos].isspace():
                pos += 1
            elif text[pos] == '%':
                end = text.find('\n', pos)
                pos = len(text) if end < 0 else end + 1
            else:
                break

    def match(pattern: str) -> str:
        nonlocal pos
        skip()
        found = re.match(pattern, text[pos:])
        if not found:
            raise ValueError(f'Invalid bibliography syntax near character {pos}')
        pos += len(found[0])
        return found[0]

    while True:
        skip()
        if pos == len(text):
            return entries
        kind = match(r'@[A-Za-z]+')[1:].lower()
        if kind not in {'article', 'book', 'inbook', 'incollection', 'inproceedings',
                        'proceedings', 'manual', 'mastersthesis', 'phdthesis',
                        'techreport', 'misc', 'unpublished', 'booklet'}:
            raise ValueError(f'Unsupported entry type: {kind}')
        match(r'\{')
        key = match(KEY)
        match(',')
        if key in entries:
            raise ValueError(f'Duplicate key: {key}')
        fields = {}
        while True:
            skip()
            if pos < len(text) and text[pos] == '}':
                pos += 1
                break
            name = match(r'[A-Za-z][A-Za-z0-9_-]*').lower()
            if name in fields:
                raise ValueError(f'{key}: duplicate field {name}')
            match('=')
            match(r'\{')
            start, depth = pos, 1
            while pos < len(text) and depth:
                char = text[pos]
                if char == '\\':
                    pos += 2
                    continue
                depth += (char == '{') - (char == '}')
                pos += 1
            if depth:
                raise ValueError(f'{key}: unclosed field {name}')
            fields[name] = text[start:pos - 1].strip()
            skip()
            if pos < len(text) and text[pos] == ',':
                pos += 1
            elif pos >= len(text) or text[pos] != '}':
                raise ValueError(f'{key}: missing field separator')
        entries[key] = fields


def validate_entries(entries: dict[str, dict[str, str]]) -> list[str]:
    errors = []
    seen = {}
    if not entries:
        errors.append('Bibliography is empty')
    for key, fields in entries.items():
        for name in ('title', 'url', 'urldate', 'review', 'claim'):
            if not fields.get(name):
                errors.append(f'{key}: missing {name}')
        if not (fields.get('author') or fields.get('editor')):
            errors.append(f'{key}: missing author/editor')
        review = fields.get('review')
        if review not in {'metadata', 'abstract', 'excerpt', 'full-text', 'source-code'}:
            errors.append(f'{key}: invalid review')
        if review in {'metadata', 'abstract', 'excerpt'} and not fields.get('note'):
            errors.append(f'{key}: limited review requires note')
        date = fields.get('urldate', '')
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                raise ValueError()
            dt.date.fromisoformat(date)
        except ValueError:
            errors.append(f'{key}: invalid urldate')
        if 'year' in fields and not re.fullmatch(r'\d{4}', fields['year']):
            errors.append(f'{key}: invalid publication year')
        url = fields.get('url', '')
        parts = urlsplit(url)
        if parts.scheme not in {'http', 'https'} or not parts.netloc or re.search(r'\s', url):
            errors.append(f'{key}: invalid URL')
        for name in ('url', 'doi'):
            value = fields.get(name, '')
            if not value:
                continue
            normalized = value.rstrip('/') if name == 'url' else value.lower()
            if name == 'doi' and not re.fullmatch(r'10\.\d{4,9}/\S+', value):
                errors.append(f'{key}: DOI must be a bare DOI')
            identity = (name, normalized)
            if identity in seen:
                errors.append(f'{key}: duplicate {name} with {seen[identity]}')
            seen[identity] = key
    return errors


def citation_keys(text: str) -> set[str]:
    # Bracketed Pandoc-style citations, including groups and page locators.
    return {key for group in re.findall(r'\[(\s*-?@[A-Za-z][^\[\]\n]*)\](?!\()', text)
            for key in re.findall(r'@(' + KEY + r')', group)}


def check(root: Path) -> tuple[int, list[str]]:
    try:
        entries = parse_bib((root / 'references.bib').read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as error:
        return 0, [str(error)]
    errors = validate_entries(entries)
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP and not name.startswith('.venv')
                   and not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if path.suffix.lower() not in EXTENSIONS or path.is_symlink():
                continue
            # The validator's regression fixtures deliberately contain unknown keys.
            if path == root / 'tools' / 'test_references.py':
                continue
            # Legacy prose includes non-UTF-8 punctuation. Citation keys are ASCII;
            # replacement preserves their bytes without rewriting unrelated files.
            # references.bib itself remains strictly UTF-8 above.
            text = path.read_text(encoding='utf-8-sig', errors='replace')
            for key in sorted(citation_keys(text) - entries.keys()):
                errors.append(f'{path.relative_to(root)}: unknown citation {key}')
    return len(entries), errors


if __name__ == '__main__':
    count, errors = check(Path(__file__).resolve().parents[1])
    for error in errors:
        print(error, file=sys.stderr)
    print(f'{count} references; {len(errors)} errors')
    raise SystemExit(bool(errors))
