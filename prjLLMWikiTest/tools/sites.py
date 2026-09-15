"""The site manifest. Single source of truth for both build scripts.

Region and theme assignment is a curation decision, fixed by hand here and never
left to the model. `title` must be the English Wikipedia article title; the fetch
script follows redirects, so a near-miss title still resolves. `display` overrides
the name shown in the wiki when the article title is a poor label for the place.
"""

REGIONS = ["paphos", "limassol", "larnaca", "troodos", "famagusta"]
THEMES = ["ancient-sites", "monasteries", "beaches-nature"]

SITES = [
    {"title": "Paphos Archaeological Park", "slug": "paphos-archaeological-park",
     "region": "paphos", "themes": ["ancient-sites"]},
    {"title": "Tombs of the Kings (Paphos)", "slug": "tombs-of-the-kings",
     "region": "paphos", "themes": ["ancient-sites"]},
    {"title": "Petra tou Romiou", "slug": "petra-tou-romiou",
     "region": "paphos", "themes": ["beaches-nature"]},
    {"title": "Agios Neophytos Monastery", "slug": "agios-neophytos-monastery",
     "region": "paphos", "themes": ["monasteries"]},

    {"title": "Kourion", "slug": "kourion",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Hylates", "slug": "apollo-hylates", "display": "Sanctuary of Apollo Hylates",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Kolossi Castle", "slug": "kolossi-castle",
     "region": "limassol", "themes": ["ancient-sites"]},
    {"title": "Limassol Castle", "slug": "limassol-castle",
     "region": "limassol", "themes": ["ancient-sites"]},

    {"title": "Church of Saint Lazarus, Larnaca", "slug": "church-of-saint-lazarus",
     "region": "larnaca", "themes": ["monasteries"]},
    {"title": "Hala Sultan Tekke", "slug": "hala-sultan-tekke",
     "region": "larnaca", "themes": ["monasteries"]},
    {"title": "Choirokoitia", "slug": "choirokoitia",
     "region": "larnaca", "themes": ["ancient-sites"]},
    {"title": "Larnaca Salt Lake", "slug": "larnaca-salt-lake",
     "region": "larnaca", "themes": ["beaches-nature"]},

    {"title": "Kykkos Monastery", "slug": "kykkos-monastery",
     "region": "troodos", "themes": ["monasteries"]},
    {"title": "Painted Churches in the Troodos Region", "slug": "painted-churches-troodos",
     "region": "troodos", "themes": ["monasteries"]},

    {"title": "Cape Greco", "slug": "cape-greco",
     "region": "famagusta", "themes": ["beaches-nature"]},
]

REGION_TITLES = {
    "paphos": "Paphos",
    "limassol": "Limassol",
    "larnaca": "Larnaca",
    "troodos": "Troodos",
    "famagusta": "Famagusta (Ayia Napa & Protaras)",
}

THEME_TITLES = {
    "ancient-sites": "Ancient & Historic Sites",
    "monasteries": "Monasteries & Churches",
    "beaches-nature": "Beaches & Nature",
}


def display(site: dict) -> str:
    return site.get("display", site["title"])


def by_region(region: str) -> list[dict]:
    return [s for s in SITES if s["region"] == region]


def by_theme(theme: str) -> list[dict]:
    return [s for s in SITES if theme in s["themes"]]
