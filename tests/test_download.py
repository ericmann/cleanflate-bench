import hashlib

import pytest

from cfbench import download

DATA = b"hello pinned world"
SHA = hashlib.sha256(DATA).hexdigest()
URL = "https://example.invalid/pkg-1.0.tar.gz"


def test_sha_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_fetch_bytes", lambda url: DATA)
    with pytest.raises(download.DownloadError, match="mismatch"):
        download.fetch(URL, "0" * 64, tmp_path)
    assert not (tmp_path / "pkg-1.0.tar.gz").exists()


def test_empty_sha_reports_computed_value(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_fetch_bytes", lambda url: DATA)
    with pytest.raises(download.DownloadError, match=SHA):
        download.fetch(URL, "", tmp_path)


def test_cached_file_is_not_refetched(tmp_path, monkeypatch):
    calls = []

    def fake(url):
        calls.append(url)
        return DATA

    monkeypatch.setattr(download, "_fetch_bytes", fake)
    p1 = download.fetch(URL, SHA, tmp_path)
    p2 = download.fetch(URL, SHA, tmp_path)
    assert p1 == p2 and p1.read_bytes() == DATA
    assert len(calls) == 1
