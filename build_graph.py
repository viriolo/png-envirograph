"""
build_graph.py

Turns the PNG Environment Data Portal catalogue into a graph.

Downloads data.json, cleans the messy publisher names, and writes graph.json
(nodes + edges) -- the file that feeds both the web page and Neo4j AuraDB.

Includes a KEYWORD layer: keywords shared by several datasets become their own
nodes, linking datasets that carry the same tag across different publishers and
themes. Three filters keep that layer useful rather than noisy:
  * keywords used only once are skipped (they connect nothing);
  * a few too-generic "stopword" keywords are dropped (they connect everything);
  * obvious variants are folded together via a small alias lookup.

Run:  python build_graph.py
Standard library only.
"""

import json
import re
import urllib.request
from collections import Counter

DATA_URL = "https://png-data.sprep.org/data.json"
OUTPUT_FILE = "graph.json"

# A keyword must be used by at least this many datasets to earn a node.
# Raise for a cleaner graph; lower (minimum 2) for a denser one.
MIN_KEYWORD_USES = 2

# Keywords so common they tag a huge share of datasets carry no signal -- like
# stopwords ("the", "and"). In a PNG environment portal, "png" is true of almost
# everything, so it builds a giant hub that links everything to everything.
# We drop these. Edit the set to taste (all lower-case).
KEYWORD_STOPLIST = {"png", "papua new guinea", "data"}

# Genuine keyword variants to fold together -- same idea as the publisher lookup.
# Add more here as you spot them in the printed "top keywords" list.
KEYWORD_ALIASES = {
    "protected areas - management": "protected areas",
}

# ---- Publisher cleanup lookup (unchanged) ----
SPREP = "Secretariat of the Pacific Regional Environment Programme"
PUBLISHER_ALIASES = {
    "Secretariat of the Pacific Regional Environment Programme (SPREP)": SPREP,
    "Secreteriat of the Pacific Regional Environment Programme (SPREP)": SPREP,  # misspelled
    "SPREP": SPREP,
    "SPREP Environmental Monitoring and Governance (EMG)": SPREP,
    "SPREP Pacific Environment Information Network (PEIN)": SPREP,
    "The Smithsonian Institution": "Smithsonian Institution",
    "Applied Geoscience and Technology Division (SOPAC) of SPC": "Pacific Community (SPC)",
}


def fetch_catalogue(url):
    print(f"Fetching {url} ...")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_publisher(raw_name):
    if not raw_name:
        return None
    tidy = re.sub(r"\s+", " ", raw_name).strip()
    return PUBLISHER_ALIASES.get(tidy, tidy)


def publisher_raw(dataset):
    pub = dataset.get("publisher")
    if isinstance(pub, dict):
        return pub.get("name")
    return pub


def clean_keyword(kw):
    """Lower-case and tidy a keyword, so 'Marine' and 'marine ' count as one."""
    if not kw:
        return None
    return re.sub(r"\s+", " ", kw).strip().lower() or None


def main():
    try:
        catalogue = fetch_catalogue(DATA_URL)
    except Exception as error:
        print(f"\nCouldn't fetch the catalogue: {error}")
        return

    datasets = catalogue.get("dataset", [])
    print(f"Found {len(datasets)} datasets.\n")
    if not datasets:
        return

    nodes = {}
    links = []

    def add_node(node_id, label, node_type, **extra):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "type": node_type, **extra}
        return node_id

    ds_keywords = {}            # dataset id -> its cleaned, kept-eligible keywords
    keyword_counts = Counter()  # how many datasets use each keyword

    for d in datasets:
        # --- Dataset node ---
        ds_id = "ds::" + str(d.get("identifier", d.get("title", "")))
        add_node(ds_id, d.get("title", "(untitled)"), "Dataset",
                 license=d.get("license", ""), url=d.get("landingPage", ""),
                 issued=d.get("issued", ""))

        # --- Organisation node (cleaned), keeping the original spelling too ---
        raw = publisher_raw(d)
        canonical = clean_publisher(raw)
        if canonical:
            org_id = "org::" + canonical
            add_node(org_id, canonical, "Organisation")
            links.append({"source": ds_id, "target": org_id, "rel": "PUBLISHED_BY"})
            nodes[ds_id]["publisher_raw"] = raw

        # --- Theme nodes (clean dropdown values) ---
        for theme in d.get("theme", []):
            theme_id = "theme::" + theme
            add_node(theme_id, theme, "Theme")
            links.append({"source": ds_id, "target": theme_id, "rel": "HAS_THEME"})

        # --- Collect keywords: normalise, fold variants, drop stopwords ---
        kws = []
        for kw in d.get("keyword", []):
            ck = clean_keyword(kw)
            if not ck:
                continue
            ck = KEYWORD_ALIASES.get(ck, ck)
            if ck in KEYWORD_STOPLIST:
                continue
            kws.append(ck)
            keyword_counts[ck] += 1
        ds_keywords[ds_id] = kws

    # Keep only keywords shared by enough datasets to actually connect things.
    kept = {kw for kw, c in keyword_counts.items() if c >= MIN_KEYWORD_USES}
    for ds_id, kws in ds_keywords.items():
        for kw in kws:
            if kw in kept:
                kw_id = "kw::" + kw
                add_node(kw_id, kw, "Keyword")
                links.append({"source": ds_id, "target": kw_id, "rel": "HAS_KEYWORD"})

    # Give each hub node a count = how many datasets point at it.
    incoming = Counter(link["target"] for link in links)
    for node_id, node in nodes.items():
        if node["type"] in ("Organisation", "Theme", "Keyword"):
            node["count"] = incoming[node_id]

    graph = {"nodes": list(nodes.values()), "links": links}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    # ---- Verification / stats ----
    print(f"Wrote {OUTPUT_FILE}: {len(nodes)} nodes, {len(links)} edges.")
    print(f"Keywords: {len(keyword_counts)} unique; {len(kept)} kept "
          f"(used by >= {MIN_KEYWORD_USES} datasets).")
    print(f"Dropped as too-generic: {', '.join(sorted(KEYWORD_STOPLIST))}\n")

    org_counts = Counter({n['label']: n['count'] for n in nodes.values() if n['type'] == 'Organisation'})
    print("--- Top organisations after cleanup ---")
    for name, count in org_counts.most_common(8):
        print(f"   {count:>4}  {name}")

    kw_counts = Counter({n['label']: n['count'] for n in nodes.values() if n['type'] == 'Keyword'})
    print("\n--- Top keywords kept (eyeball for more variants worth merging) ---")
    for name, count in kw_counts.most_common(20):
        print(f"   {count:>4}  {name}")


if __name__ == "__main__":
    main()
