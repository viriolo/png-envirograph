# PNG EnviroGraph

An interactive knowledge graph of Papua New Guinea's environmental datasets, built from the open data published on the [PNG Environment Data Portal](https://png-data.sprep.org) (run by SPREP).

The portal holds 880 datasets as a flat, searchable catalogue. This project reshapes that catalogue into a connected graph — every dataset linked to the body that published it, the environmental themes it covers, and the keywords it shares with other datasets — so the whole field is visible at once: which organisations carry the data, where the themes overlap, and how it all hangs together.

**Live version:** https://viriolo.github.io/png-envirograph/

## What the data showed

The most useful thing this project surfaced wasn't in the graph itself — it was in the cleanup.

The Secretariat of the Pacific Regional Environment Programme (SPREP) is one of the portal's two largest publishers. But its datasets were recorded under six different publisher names: the full name, two variants with "(SPREP)" appended — one of them misspelled as "Secreteriat" — a bare "SPREP", and two of its own sub-units (EMG and PEIN) listed as if they were separate organisations.

To the portal's search, those read as six different publishers. Anyone asking "show me everything SPREP has published" would get a fraction of the real answer, scattered across records that don't know about each other. Resolved into a single organisation, SPREP accounts for **318 datasets** — level with the PNG Conservation and Environment Protection Authority at the top of the portal.

It wasn't only SPREP. The National Fisheries Authority appeared as two organisations because one record carried an invisible leading space; the Smithsonian was split by nothing more than the word "The". The themes, by contrast, were already clean — because they come from a fixed dropdown rather than a free-text field. Typed fields drift; controlled fields don't.

That gap — between a messy catalogue and a coherent picture — is the point of the project. The data is open and anyone can download it. The value is in resolving it into something you can reason over.

### The geography is there, but it can't be read

The obvious next question was whether the datasets could be linked by place. They can't — not as recorded.

Of the 880 datasets, **298 carry a value in the `spatial` field** and 582 leave it empty. Every one of those 298 holds WKT geometry — a `POLYGON` or a `POINT`. Not one names a province. So province-level linking isn't a matter of parsing harder; the labels simply aren't in the data.

The coordinates themselves are in worse shape. Only **31** of the 298 have longitudes inside the valid −180…180 range. Another **122** fall outside it — values like −218° and 501° — but land squarely on PNG once you unwrap them by multiples of 360°. A further **29** describe boxes spanning more than 60° of latitude: near-global extents, not PNG ones.

PNG sits at roughly 141–156°E, hard against the antimeridian, which makes it the geography most exposed to this kind of error. The pattern is consistent with a map-picker that let the extent be dragged across the date line, accumulating a full turn each pass — though that cause is inferred from the values, not confirmed against the portal's software.

The practical consequence: read the `spatial` field literally and about nine in ten of these datasets plot into open ocean or the wrong hemisphere. The geography was captured. It just can't be trusted without repair.

## How it's built

Three steps, deliberately kept simple:

1. **Fetch.** The portal runs on DKAN, which publishes its entire catalogue as a single `data.json` file. One request pulls all 880 records — no scraping.
2. **Clean and shape** (`build_graph.py`). Publisher names are normalised against a curated lookup — this is where the SPREP variants fold into one — and the records are rewritten as a graph of nodes and edges in `graph.json`. The original publisher string is kept on every dataset, so the merge stays fully reversible and auditable.
3. **Render** (`index.html`). The page loads `graph.json` and draws it with [vis-network](https://visjs.org): searchable, filterable, click any node for detail.

The whole thing is static files, and the Python uses only the standard library — no dependencies, no database, no server. It hosts for free on GitHub Pages, Netlify, or Cloudflare Pages.

Reading the graph: datasets are the small sage dots, organisations are the clay hubs, keywords are the violet diamonds, and the themes are coloured by what they are — green for Biodiversity, blue for Coastal and Marine, earth-amber for Land, and so on.

Seven themes carry a hue of their own. The two smallest — Nuclear Legacy and Disaster Risk Management, nine datasets between them — share a neutral stone instead, because nine categorical colours is past the point where neighbouring ones stay apart. They keep their names in the graph, the legend and the detail panel; nothing is merged in the data, and `graph.json` still holds all nine themes with their true counts.

Alongside publishers and themes there's a **keyword layer**, which links datasets carrying the same tag across different publishers and themes. Three filters keep it useful rather than noisy: keywords used only once are skipped (they connect nothing), a few too-generic terms are dropped (`png`, `papua new guinea`, `data` — true of almost everything, so they'd hub the whole graph together), and obvious variants are folded via an alias lookup. Of 1,895 unique keywords, 468 earn a node.

## Running it yourself

```
python build_graph.py            # downloads the catalogue, writes graph.json
python -m http.server 8000       # then open http://localhost:8000
```

Opening `index.html` directly won't work — browsers block local files from reading one another. The local server above, or any real host, resolves that.

## Scope and limits

This is the backbone graph: datasets, organisations, themes, and shared keywords, with the `PUBLISHED_BY`, `HAS_THEME` and `HAS_KEYWORD` relationships between them. The underlying files (resources) are left out to keep the view readable, and there are no geographic links — for the reason set out above: the `spatial` field carries no province names, and its coordinates need repair before they can be used. The publisher cleanup is curated by hand from the most common names — it catches the large duplicates, but isn't claimed to be exhaustive.

Dataset counts move as the portal is updated; the figures quoted in this README were current at the last rebuild. The live page doesn't have that problem — it counts whatever is in `graph.json` when you open it, and a scheduled job (`.github/workflows/refresh-graph.yml`) rebuilds that file from the portal on the first of each month, committing only when something has actually changed. You can also trigger it by hand from the Actions tab, or just run `build_graph.py` yourself.

## Data and attribution

Data: PNG Environment Data Portal, published by SPREP under open licences (chiefly the SPREP Public Licence). This is an independent project built on that open data; it is not affiliated with or endorsed by SPREP, and dataset content remains the property of its original publishers.

---

Built by Bradley Mulavo · Yanda Tec
