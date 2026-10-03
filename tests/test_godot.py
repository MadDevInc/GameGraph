"""Run: python tests/test_godot.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "plugins", "gamegraph", "gamegraph"))
from context import build_context  # noqa: E402
from godot import parse_gdscript, scan_project, to_abs  # noqa: E402

idx = scan_project(os.path.join(HERE, "fixture"))
F = idx["files"]

assert idx["project"] == {"name": "Fixture Game", "main_scene": "res://enemies/goblin/goblin.tscn",
                          "autoloads": {"Events": "res://enemies/base/events.gd"}}
g = F["res://enemies/goblin/goblin.gd"]["parsed"]
assert (g["class_name"], g["extends"]) == ("Goblin", "BaseEnemy")
v = {x["name"]: x for x in g["variables"]}
assert v["aggro_range"]["exported"] and v["rage"]["exported"] and not v["_state"]["exported"], v
assert v["sprite"]["onready"] and v["sprite"]["type"] == "Sprite2D"
assert [f["name"] for f in g["functions"]] == ["_ready", "attack"]
assert g["signals"][0]["name"] == "attacked" and g["references"] == ["res://enemies/goblin/goblin_data.tres"]
assert parse_gdscript("extends Node\nexport(int) var hp = 5\nonready var x = 1")["variables"][0]["exported"]  # Godot 3

s = F["res://enemies/goblin/goblin.tscn"]["parsed"]
assert s["root"] == {"name": "Goblin", "type": "CharacterBody2D"}
paths = [n["path"] for n in s["nodes"]]
assert paths == [".", "Sprite2D", "CollisionShape2D", "AnimationPlayer", "StateMachine", "StateMachine/Idle", "StateMachine/Chase", "Hitbox"], paths
assert s["nodes"][0]["script"] == "res://enemies/goblin/goblin.gd"
assert s["nodes"][-1]["instance"] == "res://enemies/base/hitbox.tscn"
assert "metadata/_edit_group_" in s["nodes"][0]["props"] and "Idle" not in s["nodes"][0]["props"]  # multi-line value
assert s["connections"][0]["signal"] == "attacked"

r = F["res://enemies/goblin/goblin_data.tres"]["parsed"]
assert r["type"] == "EnemyData" and r["properties"]["health"] == "50" and r["script"] == "res://enemies/base/enemy_data.gd"

E = {(e["source"], e["type"], e["target"]): e for e in idx["edges"]}
assert ("res://enemies/goblin/goblin.gd", "inherits", "res://enemies/base/base_enemy.gd") in E
assert E[("res://enemies/goblin/goblin.tscn", "uses", "res://enemies/goblin/goblin.gd")]["kind"] == "file"
assert E[("res://enemies/goblin/goblin.tscn", "instances", "res://enemies/base/hitbox.tscn")]["missing"]

try:
    to_abs(idx["root"], "res://../../etc/passwd")
    raise SystemExit("path escape not blocked")
except ValueError:
    pass

design = {"nodes": [{"id": "d:1", "label": "Goblin", "notes": "Melee forest enemy."}],
          "links": [{"node": "d:1", "file": "res://enemies/goblin/goblin.tscn", "role": "scene"},
                    {"node": "d:1", "file": "res://enemies/goblin/goblin.gd", "role": "script"},
                    {"node": "d:1", "file": "res://enemies/goblin/goblin_data.tres", "role": "data"}],
          "relations": [], "rules": "All enemies must use EnemyStateMachine.", "instructions": ""}
ctx = build_context(idx, design, "goblin", include_code=True)
for needle in ("Melee forest enemy", "Raiz: Goblin (CharacterBody2D)", "  - Idle (Node)", "Herança: BaseEnemy -> CharacterBody2D",
               "health: 50", "func attack", "EnemyStateMachine"):
    assert needle in ctx, needle
print("ok")

# AI import: merges, keeps user edits, never resurrects deleted nodes
import json, shutil, tempfile  # noqa: E401,E402
from context import import_design, load_design, save_design, stale_files, stale_report, write_outputs  # noqa: E402
tmp = tempfile.mkdtemp()
shutil.copytree(os.path.join(HERE, "fixture"), tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("gamegraph-out"))
try:
    idx2 = scan_project(tmp)
    ai = {"nodes": [{"id": "criar-inimigos", "label": "Criar inimigos", "kind": "process", "steps": ["herdar BaseEnemy"]},
                    {"id": "goblin", "label": "Goblin", "kind": "entity"}, {"id": "slime", "label": "Slime"}],
          "links": [{"node": "criar-inimigos", "file": "res://enemies/base/base_enemy.gd", "label": "1. herdar de"},
                    {"node": "goblin", "file": "res://nope.gd"}],
          "relations": [{"source": "criar-inimigos", "target": "goblin", "label": "exemplo"}], "rules": "R1"}
    d, warn = import_design(tmp, idx2, ai)
    assert len(d["nodes"]) == 3 and d["links"][0]["role"] == "script" and warn == ["arquivo não existe: res://nope.gd"]
    d["nodes"][1]["edited"], d["nodes"][1]["notes"] = True, "mine"     # user edits goblin
    d["nodes"] = [n for n in d["nodes"] if n["id"] != "d:slime"]; d["deleted"] = ["d:slime"]  # user deletes slime
    save_design(tmp, d)
    ai["nodes"][1]["notes"] = "ai overwrite"
    d, _ = import_design(tmp, idx2, ai)
    ids = [n["id"] for n in d["nodes"]]
    assert ids == ["d:criar-inimigos", "d:goblin"] and d["nodes"][1]["notes"] == "mine" and len(d["relations"]) == 1, d
    d = load_design(tmp)
    ctx = build_context(idx2, d)  # short index
    assert ctx.index("## PROCESSOS") < ctx.index("## ENTIDADES") and "`nodes/criar-inimigos.md`" in ctx and "Passo" not in ctx, ctx
    det = build_context(idx2, d, "criar-inimigos")
    assert "1. herdar BaseEnemy" in det and "1. herdar de → res://enemies/base/base_enemy.gd" in det, det
    # "do it like X": variation table of BaseEnemy subclasses
    assert "- Goblin (res://enemies/goblin/goblin.gd): novas: _ready, attack; exports: aggro_range=120.0" in det, det
    # per-node files written for agents
    write_outputs(tmp, idx2, d)
    assert os.path.exists(os.path.join(tmp, "gamegraph-out", "nodes", "criar-inimigos.md"))
    # staleness: change a linked file -> node flagged, re-import clears it
    with open(os.path.join(tmp, "enemies", "base", "base_enemy.gd"), "a", encoding="utf-8") as fh:
        fh.write("\nfunc take_damage(n): pass\n")
    idx3 = scan_project(tmp)
    assert stale_files(idx3, d, "d:criar-inimigos") == ["res://enemies/base/base_enemy.gd"]
    assert "REVISAR" in build_context(idx3, d) and stale_report(idx3, d)["stale"][0]["label"] == "Criar inimigos"
    d, _ = import_design(tmp, idx3, {"nodes": [ai["nodes"][0]]})
    assert stale_files(idx3, d, "d:criar-inimigos") == []
finally:
    shutil.rmtree(tmp)
print("import ok")
