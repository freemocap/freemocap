from pathlib import Path

import pytest

from freemocap.core.recording.exports.guides import CSV, NPY, OVERVIEW, stage_guides


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_pre_terminology_guides_refresh_without_overwriting_edits(tmp_path, newline):
    published, staging = tmp_path / 'published', tmp_path / 'staging'
    published.mkdir()
    staging.mkdir()
    guides = [('overview', 'README.md', OVERVIEW), ('csv', 'csv/README.md', CSV), ('npy', 'npy/README.md', NPY)]
    for name, relative, current in guides:
        old = Path(__file__).parent / 'fixtures' / 'export_guides' / f'pre_terminology_{name}.md'
        content = old.read_text().replace('\n', newline).encode()
        target = published / relative
        target.parent.mkdir(exist_ok=True, parents=True)
        target.write_bytes(content)
        assert 'scientific' not in current.lower()
    assert set(stage_guides(published, staging, ['wide_csv', 'npy'])) == {item[1] for item in guides}
    for _, relative, current in guides:
        assert (staging / relative).read_text() == current
        with (published / relative).open('a') as document:
            document.write('\nUser analysis notes\n')
    assert stage_guides(published, staging, ['wide_csv', 'npy']) == ()
