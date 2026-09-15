from sites import SITES, REGIONS, THEMES


def test_fifteen_sites():
    assert len(SITES) == 15


def test_slugs_unique_and_filename_safe():
    slugs = [s["slug"] for s in SITES]
    assert len(set(slugs)) == 15
    for slug in slugs:
        assert slug == slug.lower()
        assert all(c.isalnum() or c == "-" for c in slug)


def test_regions_and_themes_are_known():
    assert set(REGIONS) == {"paphos", "limassol", "larnaca", "troodos", "famagusta"}
    assert set(THEMES) == {"ancient-sites", "monasteries", "beaches-nature"}
    for s in SITES:
        assert s["region"] in REGIONS
        assert s["themes"], f"{s['slug']} has no theme"
        for t in s["themes"]:
            assert t in THEMES


def test_every_region_and_theme_has_a_member():
    used_regions = {s["region"] for s in SITES}
    used_themes = {t for s in SITES for t in s["themes"]}
    assert used_regions == set(REGIONS)
    assert used_themes == set(THEMES)
