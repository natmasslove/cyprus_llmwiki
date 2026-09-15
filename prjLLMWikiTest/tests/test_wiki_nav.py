import pytest

from wiki_nav import tools as wn


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    (tmp_path / "sites").mkdir()
    (tmp_path / "index.md").write_text('---\ntype: index\n---\n# Wiki\n', encoding="utf-8")
    (tmp_path / "sites" / "kourion.md").write_text(
        '---\ntype: attraction\ntitle: "Kourion"\n---\n# Overview\nRoman mosaics here.\n',
        encoding="utf-8")
    (tmp_path / "sites" / "kolossi-castle.md").write_text(
        '---\ntype: attraction\ntitle: "Kolossi Castle"\n---\n# Overview\nA keep.\n',
        encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not markdown", encoding="utf-8")
    monkeypatch.setenv("WIKI_ROOT", str(tmp_path))
    return tmp_path


def test_read_wiki_returns_frontmatter_and_body(wiki):
    out = wn.read_wiki("/sites/kourion.md")
    assert "type: attraction" in out
    assert "Roman mosaics" in out


def test_read_wiki_rejects_escape(wiki, tmp_path):
    outside = tmp_path.parent / "outside.md"
    # Distinct sentinel: the fixture's own secret.txt appears in the fallback
    # listing, so "secret" cannot tell a leak from the listing.
    outside.write_text("ESCAPED-CONTENT", encoding="utf-8")
    out = wn.read_wiki("../outside.md")
    assert "ESCAPED-CONTENT" not in out
    assert "outside the wiki" in out


def test_list_wiki_rejects_escape(wiki):
    out = wn.list_wiki("/../..")
    assert "outside the wiki" in out
    assert "sites/" in out  # falls back to the root listing


def test_read_wiki_missing_file_returns_a_listing_and_does_not_raise(wiki):
    out = wn.read_wiki("/sites/nicosia.md")
    assert "not found" in out
    assert "kourion.md" in out


def test_list_wiki_lists_dirs_and_files(wiki):
    out = wn.list_wiki("/")
    assert "sites/" in out
    assert "index.md" in out


def test_list_wiki_unknown_path_falls_back_to_nearest_parent(wiki):
    out = wn.list_wiki("/sites/deep/deeper")
    assert "kourion.md" in out


def test_search_wiki_is_case_insensitive_and_returns_paths(wiki):
    out = wn.search_wiki("ROMAN MOSAICS")
    assert "/sites/kourion.md:" in out


def test_search_wiki_no_matches_returns_root_listing(wiki):
    out = wn.search_wiki("zzzzzz")
    assert "no matches" in out
    assert "sites/" in out
