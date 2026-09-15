from pathlib import Path

import lint_okf


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def good_bundle(tmp_path: Path) -> Path:
    write(tmp_path / "index.md", '---\ntype: index\nokf_version: "0.2"\n---\n# Wiki\n')
    write(tmp_path / "sites" / "kourion.md",
          '---\ntype: attraction\ntitle: "Kourion"\n---\n# Overview\ntext\n')
    return tmp_path


def test_good_bundle_has_no_errors(tmp_path):
    errors, warnings = lint_okf.lint(good_bundle(tmp_path))
    assert errors == []
    assert warnings == []


def test_missing_type_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "broken.md", '---\ntitle: "No type"\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert any("broken.md" in e and "type" in e for e in errors)


def test_empty_type_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "empty.md", '---\ntype: ""\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert any("empty.md" in e for e in errors)


def test_unparseable_frontmatter_is_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "nofm.md", "# No frontmatter at all\n")
    errors, _ = lint_okf.lint(bundle)
    assert any("nofm.md" in e for e in errors)


def test_index_is_exempt_from_the_type_rule(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "index.md", "---\ntitle: Sites\n---\n# Sites\n")
    errors, _ = lint_okf.lint(bundle)
    assert errors == []


def test_missing_okf_version_is_an_error(tmp_path):
    write(tmp_path / "index.md", "---\ntype: index\n---\n# Wiki\n")
    errors, _ = lint_okf.lint(tmp_path)
    assert any("okf_version" in e for e in errors)


def test_broken_link_is_a_warning_not_an_error(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "linky.md",
          '---\ntype: attraction\n---\n[gone](/sites/gone.md)\n')
    errors, warnings = lint_okf.lint(bundle)
    assert errors == []
    assert any("/sites/gone.md" in w for w in warnings)


def test_unknown_keys_are_tolerated(tmp_path):
    bundle = good_bundle(tmp_path)
    write(bundle / "sites" / "extra.md",
          '---\ntype: attraction\nregion: /regions/limassol.md\nwhatever: 42\n---\n# Overview\n')
    errors, _ = lint_okf.lint(bundle)
    assert errors == []
