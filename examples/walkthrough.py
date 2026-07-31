"""Walk loop tour — commit_turn, recall previews, ticketed walk, optional root.

Run:

    pip install forest-custody-memory
    python examples/walkthrough.py

Creates ``walkthrough_woods.db`` and ``walkthrough.scroll`` next to cwd.
"""

import os

from forest_memory import (
    CeremonyRefusal,
    ForestError,
    ForestStore,
    Scroll,
    commit_turn,
    fruits_near,
    plant_question,
    root_to_ground,
)

DB = "walkthrough_woods.db"
SCROLL = "walkthrough.scroll"
for path in (DB, SCROLL):
    if os.path.exists(path):
        os.remove(path)


def act(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


store = ForestStore(DB)
store.init_schema()
scroll = Scroll(SCROLL)

act("ACT 1 - commit_turn: scroll head + pair with scroll_ptr.")
pair = commit_turn(store, scroll, "My grandmother kept bees until she was ninety.")
print(f"Stored as entry #{pair}, jurisdiction=home, bucket=pair.")
print(f"meta scroll_ptr: {store.get(pair)['meta_json']}")

act("ACT 2 - Model guess goes in as inference — never ground.")
guess = store.write(
    body="The grandmother probably taught the narrator about bees.",
    bucket="inference",
    signature="model",
    origins=[(pair, "derived_from")],
)
print(f"Stored as entry #{guess}. current_ground is still empty (root is optional).")
print(f"  ground rows: {store.conn.execute('SELECT COUNT(*) AS n FROM current_ground').fetchone()['n']}")

act("ACT 3 - recall_similar — bounded preview; jurisdiction first.")
for scrap in store.recall_similar("bees"):
    assert "body" not in scrap
    print(f"  {scrap['jurisdiction']} #{scrap['id']} · {scrap.get('excerpt', '')[:50]}...")

act("ACT 4 - Cheats refused.")
print("Cheat 1: writing an adoption_record at the front door...")
try:
    store.write(body="fake", bucket="adoption_record", signature="model", origins=[(pair, "derived_from")])
except ForestError as e:
    print(f"  REFUSED: {e}")

print("Cheat 2: praise as root...")
guess_row = store.get(guess)
try:
    root_to_ground(
        store,
        entry_id=guess,
        adopting_words="oh, that's lovely!",
        adopting_signature="author",
        expected_body_hash=guess_row["body_hash"],
    )
except CeremonyRefusal as e:
    print(f"  REFUSED: {e}")

print("Cheat 3: forged ticket read...")
from forest_memory import Trail

try:
    store.read(Trail(position=guess, ticket="forged"))
except ForestError as e:
    print(f"  REFUSED: {e}")

act("ACT 5 - Optional root — only when it must stay true.")
guess_row = store.get(guess)
grounded = root_to_ground(
    store,
    entry_id=guess,
    adopting_words="Yes — root this entry exactly as displayed.",
    adopting_signature="author",
    expected_body_hash=guess_row["body_hash"],
)
print(f"Rooted entry #{grounded} in place (no canon mint).")
print("  body_hash shown before rooting must equal stored hash — verified.")
for row in store.conn.execute("SELECT id, body FROM current_ground"):
    print(f"  current_ground: #{row['id']}: {row['body'][:60]}...")

act("ACT 6 - open -> around -> step -> read (ticketed; no walk receipts).")
before = store.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
trail = store.open(pair)
for scrap in store.around(trail):
    routes = ",".join(f"{r['direction']}/{r['relation']}" for r in scrap["routes"])
    print(
        f"  around: {scrap['jurisdiction']} #{scrap['id']} "
        f"[{routes}] · {scrap.get('excerpt', '')[:40]}..."
    )
trail = store.step(trail, "in", target=guess)
got = store.read(trail)
after = store.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
print(f"Read #{got['id']}: {got['body'][:50]}...")
print(f"Entry count unchanged ({before} -> {after}).")

act("EPILOGUE - Optional question (mycelium fruit).")
plant_question(
    store,
    body="What happened to the hives after she died?",
    about_ids=[grounded],
    signature="author",
)
disturbed = [s["id"] for s in store.recall_similar("bees", scope="both")]
for fruit in fruits_near(store, disturbed):
    print(f"  ripe question: {fruit['question']['body']}")

store.close()
print()
print(f"DB={DB} scroll={SCROLL}. Nothing in the DB can be unwritten.")
