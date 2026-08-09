"""
load_to_auradb.py

Loads graph.json into your Neo4j AuraDB database.

FIRST run: it creates a file called auradb_secrets.json for you to fill in,
           then stops.
SECOND run (after you've pasted your details in): it connects and loads
           everything, then prints a count so you can confirm it worked.

Before running, install the Neo4j driver once:   pip install neo4j

IMPORTANT: add auradb_secrets.json to your .gitignore so your password is
never pushed to GitHub. (A ready .gitignore is included alongside this file.)
"""

import json
import os
import sys

try:
    from neo4j import GraphDatabase
except ImportError:
    print("The Neo4j driver isn't installed yet. Run this first:\n    pip install neo4j")
    sys.exit(1)

SECRETS_FILE = "auradb_secrets.json"
GRAPH_FILE = "graph.json"

# No database name is set anywhere in this file, deliberately. Aura serves one
# database per instance, and the driver will use whichever one the connection
# considers its home. Naming it explicitly means editing this file every time
# the instance is recreated -- and getting it wrong fails in a way that looks
# like a password problem. Letting the driver decide removes that whole class
# of mistake.

SECRETS_TEMPLATE = {
    "uri": "neo4j+s://XXXXXXXX.databases.neo4j.io",
    "user": "neo4j",
    "password": "paste-your-generated-password-here",
}


def load_secrets():
    """Read the connection details, or create a blank template on first run."""
    if not os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump(SECRETS_TEMPLATE, f, indent=2)
        print(f"Created {SECRETS_FILE}.")
        print("Open it, paste in your AuraDB uri / user / password, then run this again.")
        print("Then add it to .gitignore so the password never reaches GitHub.")
        sys.exit(0)
    with open(SECRETS_FILE, encoding="utf-8") as f:
        return json.load(f)


def chunked(items, size=1000):
    """Yield the list in batches, so we don't send everything in one giant query."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    secrets = load_secrets()

    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)
    nodes, links = graph["nodes"], graph["links"]

    driver = GraphDatabase.driver(secrets["uri"], auth=(secrets["user"], secrets["password"]))
    try:
        driver.verify_connectivity()
    except Exception as error:
        print(f"\nCouldn't connect: {error}")
        print("Double-check the uri and password in auradb_secrets.json, and that the")
        print("instance isn't paused (resume it in the AuraDB console if so).")
        driver.close()
        return

    def run(query, **params):
        driver.execute_query(query, **params)

    # --- Constraints: make each node's id unique (also speeds up loading) ---
    for label in ("Dataset", "Organisation", "Theme", "Keyword"):
        run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")

    # --- Split the nodes by type ---
    datasets = [n for n in nodes if n["type"] == "Dataset"]
    orgs = [n for n in nodes if n["type"] == "Organisation"]
    themes = [n for n in nodes if n["type"] == "Theme"]
    keywords = [n for n in nodes if n["type"] == "Keyword"]

    # MERGE = "create it if it isn't there, otherwise reuse it" -> safe to re-run.
    print("Loading nodes ...")
    for batch in chunked(datasets):
        run("""UNWIND $rows AS r
               MERGE (d:Dataset {id: r.id})
               SET d.title = r.label, d.license = r.license,
                   d.url = r.url, d.issued = r.issued,
                   d.publisher_raw = r.publisher_raw""", rows=batch)
    for batch in chunked(orgs):
        run("""UNWIND $rows AS r
               MERGE (o:Organisation {id: r.id})
               SET o.name = r.label, o.count = r.count""", rows=batch)
    for batch in chunked(themes):
        run("""UNWIND $rows AS r
               MERGE (t:Theme {id: r.id})
               SET t.name = r.label, t.count = r.count""", rows=batch)
    for batch in chunked(keywords):
        run("""UNWIND $rows AS r
               MERGE (k:Keyword {id: r.id})
               SET k.name = r.label, k.count = r.count""", rows=batch)

    # --- Relationships ---
    print("Loading relationships ...")
    published = [l for l in links if l["rel"] == "PUBLISHED_BY"]
    has_theme = [l for l in links if l["rel"] == "HAS_THEME"]
    has_keyword = [l for l in links if l["rel"] == "HAS_KEYWORD"]
    for batch in chunked(published):
        run("""UNWIND $rows AS r
               MATCH (d:Dataset {id: r.source})
               MATCH (o:Organisation {id: r.target})
               MERGE (d)-[:PUBLISHED_BY]->(o)""", rows=batch)
    for batch in chunked(has_theme):
        run("""UNWIND $rows AS r
               MATCH (d:Dataset {id: r.source})
               MATCH (t:Theme {id: r.target})
               MERGE (d)-[:HAS_THEME]->(t)""", rows=batch)
    for batch in chunked(has_keyword):
        run("""UNWIND $rows AS r
               MATCH (d:Dataset {id: r.source})
               MATCH (k:Keyword {id: r.target})
               MERGE (d)-[:HAS_KEYWORD]->(k)""", rows=batch)

    # --- Verify: count what's now in the database ---
    print("\nDone. Here's what's now in AuraDB:")
    records, _, _ = driver.execute_query(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC")
    for rec in records:
        print(f"   {rec['c']:>5}  {rec['label']} nodes")
    records, _, _ = driver.execute_query(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC")
    for rec in records:
        print(f"   {rec['c']:>5}  {rec['t']} relationships")

    driver.close()


if __name__ == "__main__":
    main()
