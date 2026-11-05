"""Candidate source loading must not replace or share the active workbook cache."""
import hashlib
from pathlib import Path
from zipfile import BadZipFile

import pytest

from lib import workbooks


class EmptySheet:
    def __init__(self, name):
        self.title = name

    def iter_rows(self, **kwargs):
        return iter(())


class EmptyWorkbook:
    """Read-only stand-in exercising the parser and real store_current enrichment."""
    def __init__(self):
        names = ['DATABASE', 'SELLING CASH', 'SELLING CREDIT', 'PAYMENT CREDIT',
                 'PAYMENT SUPPLIER', 'EXPENSES', 'REPORT', 'PURCHASE', 'TRANSFER']
        self.sheets = {name: EmptySheet(name) for name in names}
        self.closed = False

    def __getitem__(self, name):
        return self.sheets[name]

    def __contains__(self, name):
        return name in self.sheets

    def __iter__(self):
        return iter(self.sheets.values())

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.delenv('STORE_WORKBOOK_PATH', raising=False)
    workbooks.dataset.cache_clear()
    yield
    workbooks.dataset.cache_clear()


def test_candidates_have_separate_digest_filename_and_cache_without_replacing_default(tmp_path, monkeypatch):
    monkeypatch.setattr(workbooks, '__file__', str(tmp_path / 'backend/lib/workbooks.py'))
    default = tmp_path / 'refrensi-spreadsheet/Perkasa Jaya - Store information system (1).xlsx'
    default.parent.mkdir()
    default.write_bytes(b'active source bytes')
    first = tmp_path / 'candidate-one.xlsx'
    second = tmp_path / 'candidate-two.xlsx'
    first.write_bytes(b'first candidate bytes')
    second.write_bytes(b'second candidate bytes')
    opened = []

    def load(path, **options):
        assert options == {'read_only': True, 'data_only': True}
        workbook = EmptyWorkbook()
        opened.append((Path(path), workbook))
        return workbook

    monkeypatch.setattr(workbooks.openpyxl, 'load_workbook', load)
    active = workbooks.dataset('store_current')
    candidate = workbooks.dataset('store_current', first)
    other = workbooks.dataset('store_current', second)
    for data, path in [(active, default), (candidate, first), (other, second)]:
        assert data['source'] == 'store_current'
        assert data['filename'] == path.name
        assert data['digest'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert data['purchases'] == [] and data['transfers'] == []
        assert data['daily_inputs'] is None and data['source_rows'] == []
    assert len({data['digest'] for data in (active, candidate, other)}) == 3
    assert workbooks.dataset('store_current') is active
    assert workbooks.dataset('store_current', first) is candidate
    assert [path for path, _ in opened] == [default, first, second]
    assert all(workbook.closed for _, workbook in opened)
    assert default.read_bytes() == b'active source bytes'


@pytest.mark.parametrize('source', ['store', 'september', 'unsupported'])
def test_candidate_override_rejects_other_source_parsers(source, tmp_path):
    with pytest.raises(ValueError, match='only supported for store_current'):
        workbooks.dataset(source, tmp_path / 'candidate.xlsx')


def test_candidate_override_rejects_missing_directory_or_wrong_extension(tmp_path):
    with pytest.raises(FileNotFoundError):
        workbooks.dataset('store_current', tmp_path / 'missing.xlsx')
    with pytest.raises(ValueError, match='existing .xlsx file'):
        workbooks.dataset('store_current', tmp_path)
    unsupported = tmp_path / 'candidate.txt'
    unsupported.write_text('not a workbook')
    with pytest.raises(ValueError, match='existing .xlsx file'):
        workbooks.dataset('store_current', unsupported)


def test_candidate_override_rejects_invalid_workbook_contents(tmp_path):
    invalid = tmp_path / 'invalid.xlsx'
    invalid.write_bytes(b'not an XLSX archive')
    with pytest.raises(BadZipFile):
        workbooks.dataset('store_current', invalid)


def test_environment_selector_and_explicit_candidate_are_separate(tmp_path, monkeypatch):
    selected = tmp_path / 'selected.xlsx'
    candidate = tmp_path / 'candidate.xlsx'
    legacy = tmp_path / workbooks.FILES['store']
    selected.write_bytes(b'environment source bytes')
    candidate.write_bytes(b'explicit candidate bytes')
    legacy.write_bytes(b'legacy source bytes')
    monkeypatch.setenv('STORE_WORKBOOK_PATH', str(selected))
    monkeypatch.setenv('WORKBOOK_DIR', str(tmp_path))
    monkeypatch.setattr(workbooks.openpyxl, 'load_workbook', lambda *args, **kwargs: EmptyWorkbook())
    active = workbooks.dataset('store_current')
    explicit = workbooks.dataset('store_current', candidate)
    assert active['filename'] == selected.name
    assert active['digest'] == hashlib.sha256(selected.read_bytes()).hexdigest()
    assert explicit['filename'] == candidate.name and explicit['digest'] != active['digest']
    assert workbooks.dataset('store_current') is active
    assert workbooks.dataset('store')['filename'] == legacy.name
    assert selected.read_bytes() == b'environment source bytes'


@pytest.mark.parametrize('kind', ['missing', 'directory', 'extension'])
def test_environment_selector_rejects_invalid_paths(tmp_path, monkeypatch, kind):
    path = tmp_path / ('missing.xlsx' if kind == 'missing' else 'wrong.txt')
    if kind == 'directory':
        path = tmp_path
    elif kind == 'extension':
        path.write_text('not a workbook')
    monkeypatch.setenv('STORE_WORKBOOK_PATH', str(path))
    with pytest.raises(FileNotFoundError if kind == 'missing' else ValueError):
        workbooks.dataset('store_current')
