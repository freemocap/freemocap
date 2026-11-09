"""In-memory regression tests; no application imports or generated files."""
import unittest
from pathlib import Path
from unittest.mock import patch
from check_references import check, citation_keys, parse_bib, validate_entries

VALID = r'''@misc{example,
  author = {{Example Project}}, title = {A {GPU} guide with \{escaped\} braces},
  url = {https://example.org/guide}, urldate = {2026-10-10},
  review = {excerpt}, note = {Selected sections read}, claim = {Describes a graph}
}'''


class ReferencesTests(unittest.TestCase):
    def test_nested_braces_escapes_comments_and_multiple_entries(self):
        entries = parse_bib('% comment\n' + VALID + '\n' + VALID.replace('example,', 'second,'))
        self.assertEqual(set(entries), {'example', 'second'})
        self.assertEqual(validate_entries(parse_bib(VALID)), [])

    def test_malformed_and_unsupported_syntax_fails(self):
        for text in (VALID[:-1], VALID.replace('}, urldate', '} urldate'),
                     VALID.replace('{excerpt}', '"excerpt"'), '@string{x={y}}',
                     VALID + ' trailing garbage', VALID.replace('{excerpt}', '{excerpt} # {other}')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_bib(text)

    def test_duplicate_keys_and_fields_fail(self):
        for text in (VALID + VALID, VALID.replace('review =', 'title = {Other}, review =')):
            with self.assertRaises(ValueError):
                parse_bib(text)

    def test_required_metadata(self):
        for field in ('title', 'url', 'urldate', 'review', 'claim', 'author', 'note'):
            entries = parse_bib(VALID)
            del entries['example'][field]
            with self.subTest(field=field):
                self.assertTrue(validate_entries(entries))

    def test_bad_dates_reviews_urls_and_dois(self):
        for field, value in [('urldate', '2026-02-30'), ('review', 'verified'),
                             ('url', 'file:///private'), ('doi', 'https://doi.org/10.1234/a')]:
            entries = parse_bib(VALID)
            entries['example'][field] = value
            self.assertTrue(validate_entries(entries))

    def test_duplicate_sources(self):
        entries = parse_bib(VALID + VALID.replace('example,', 'second,'))
        self.assertTrue(any('duplicate url' in e for e in validate_entries(entries)))

    def test_grouped_citations_and_non_citations(self):
        self.assertEqual(citation_keys('[@known; @missing, p. 3] # [@code]\nuser@example.org'),
                         {'known', 'missing', 'code'})
        self.assertEqual(citation_keys('decorator @property and array[index]'), set())
        self.assertEqual(citation_keys('["@scope/package"] and [@user](https://example.org)'), set())

    def test_repository_check_reports_unknown_key_and_skips_dependency_directories(self):
        root = Path('/repository')
        directories = ['node_modules', 'docs']
        def read(path, **kwargs):
            return VALID if path.name == 'references.bib' else 'Known [@example]; unknown [@missing]'
        with patch('check_references.os.walk', return_value=[(str(root), directories, ['note.md'])]), \
             patch.object(Path, 'read_text', read), patch.object(Path, 'is_symlink', return_value=False):
            count, errors = check(root)
        self.assertEqual(count, 1)
        self.assertEqual(directories, ['docs'])
        self.assertEqual(errors, ['note.md: unknown citation missing'])


if __name__ == '__main__':
    unittest.main()
