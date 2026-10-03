---
name: gamephy
description: "GameGraph by MadDev Studios, for Godot projects. Claude reads any Godot 3/4 project and BUILDS a knowledge graph of how the game is made: processes (e.g. CRIAR INIMIGO) with concrete steps linked to the real scenes/scripts/resources, systems and entities. It opens a web UI where the user edits it. The output (gamegraph-out/CONTEXT.md + nodes/*.md) replaces CLAUDE.md as the guide for agents. Use when the user types /gamephy, or before working in a Godot project that has gamegraph-out/."
---

# /gamephy: GameGraph by MadDev Studios

Talk to the user in Brazilian Portuguese. Write all graph content in pt-BR: labels, notes, steps, link labels, rules and instructions.

The tool ships with this plugin. It needs Python 3.10+ and nothing else. Below, `GG` means `python "${CLAUDE_PLUGIN_ROOT}/gamegraph"`. On macOS/Linux, use `python3` if `python` is not found. If Python is missing, tell the user to install Python 3.10+ and stop.

```
/gamephy                    # build the graph for the current Godot project + open UI
/gamephy <path>             # same, for <path>
/gamephy --update           # cheap incremental update: re-check only what changed
/gamephy ui                 # only open the UI
/gamephy --help             # print this block and stop
```

**You (Claude) build the graph. The user only edits it.** **Spend tokens once, on building it, so every later task is cheaper.**

## Using an existing graph (every task in the project)
Do this before grepping or reading code:
1. Read `gamegraph-out/CONTEXT.md`. It is a short index: rules, instructions, and one line per node.
2. Read the `gamegraph-out/nodes/<nome>.md` file of the matching process. It has the steps, the real files, the scene tree and script summary, **what each existing variation changes**, and the values of same-type resources.
3. Open source code **only** for the files that node points to. Do not explore the whole project.
4. If the node says **⚠ ESTES ARQUIVOS MUDARAM**, verify the steps against those files before following them.
5. After creating something new (a new enemy, a new system), run `/gamephy --update`.

## Build (first run)

### Step 1: Index (seconds)
Resolve the project path (default `.`). It must contain `project.godot`. If it doesn't, look one level down. Then run:
```
GG "<path>" --no-serve
```
**Never** run `GG "<path>"` without `--no-serve` in the foreground. That starts the UI server, which never exits.

### Step 2: Understand, cheaply
Start from `gamegraph-out/ARCHITECTURE.md`, which lists classes (with extends), scenes and resources. That alone shows the families:
- **Base classes with several children** (BaseEnemy → Goblin, Slime). Each one is a **process** ("Criar inimigo").
- **Folders of similar things** (`weapons/`, `levels/`, `ui/`, `items/`). These are also processes.
- **Autoloads / managers / state machines / event buses**. These are **systems**.
- **Concrete things** (Goblin, Player). These are **entities**. They serve as examples.

Read **one or two representative examples per family**, not every file. The tool already computes "what each subclass changes" and resource value tables. Don't spend tokens reproducing those.

Big projects (>300 scripts/scenes): dispatch parallel subagents per top-level folder. Each one returns a partial JSON. Merge them and import once.

### Step 3: Write the graph
Write `<path>/gamegraph-out/ai_design.json`:
```json
{
  "nodes": [
    {"id": "criar-inimigo", "label": "Criar inimigo", "kind": "process",
     "notes": "Inimigos herdam BaseEnemy; status ficam num EnemyData .tres. (1ª linha = resumo que vai no índice)",
     "steps": ["Duplicar res://enemies/goblin/goblin.tscn e trocar o sprite",
               "Script: class_name X extends BaseEnemy; sobrescrever só attack()",
               "Criar X_data.tres (EnemyData) copiando goblin_data.tres e ajustando health/damage/speed",
               "Ligar o .tres no export `data` da cena",
               "Adicionar a cena em spawn_table.tres"]},
    {"id": "event-bus", "label": "Event Bus", "kind": "system", "notes": "Autoload com os sinais globais."},
    {"id": "goblin", "label": "Goblin", "kind": "entity", "notes": "Inimigo melee da floresta. Exemplo mais simples."}
  ],
  "links": [
    {"node": "criar-inimigo", "file": "res://enemies/base/base_enemy.gd", "label": "herdar de"},
    {"node": "criar-inimigo", "file": "res://enemies/goblin/goblin.tscn", "label": "copiar esta cena"},
    {"node": "criar-inimigo", "file": "res://enemies/goblin/goblin_data.tres", "label": "copiar estes dados"}
  ],
  "relations": [{"source": "criar-inimigo", "target": "goblin", "label": "exemplo"}],
  "rules": "- Inimigos herdam BaseEnemy\n- Status em .tres, nunca no código",
  "instructions": "Antes de criar algo, leia o nodes/<processo>.md e siga os passos."
}
```

**Quality bar. A process is worthless if it's generic:**
- ❌ "Criar a cena", "Criar o script". These teach nothing.
- ✅ Each step names a **real file to copy or extend** and **what to change**. Steps should be in the order a dev would do them, including the easy-to-forget registration step (spawner, autoload, menu list, translation…).
- The first line of `notes` is the summary shown in the index, so keep it short and specific.
- Link labels say what the file is for **in this process** ("herdar de", "copiar esta cena", "registrar aqui").
- Link the **base** script and **one good example**. The node file already lists all other variations.
- Prefer 5–20 really useful processes over hundreds of nodes. Keep `id`s stable (slug of label).

Then run:
```
GG "<path>" --import "<path>/gamegraph-out/ai_design.json"
```
The import keeps nodes the user edited, never recreates deleted ones, and marks imported nodes as reviewed.

### Step 4: Open the UI (background)
Run `GG "<path>" --no-browser` **in the background** and tell the user to open http://127.0.0.1:8765. Use `--port N` if that port is busy. The **? Guia** button explains the UI. The full tutorial (pt-BR) is `${CLAUDE_PLUGIN_ROOT}/TUTORIAL.md`.

### Step 5: Make agents use it
Offer to replace or extend the project's `CLAUDE.md` with:
```
Antes de qualquer tarefa neste projeto Godot: leia gamegraph-out/CONTEXT.md, depois o gamegraph-out/nodes/<processo>.md da tarefa, e siga os passos.
Abra código só dos arquivos que o nó aponta. Se o nó disser ⚠ ARQUIVOS MUDARAM, confira antes de seguir.
Depois de criar algo novo, rode /gamephy --update.
```

## /gamephy --update (incremental: don't rebuild)
1. Run `GG "<path>" --stale`. It prints JSON:
   - `stale`: nodes whose linked files changed, or point to missing files;
   - `unlinked`: scripts and scenes that no node covers yet.
2. For each stale node, read **only its changed files**. Fix steps and links if needed and re-emit just that node. Skip nodes with `edited: true`; the user owns those, so tell them which ones to review in the UI.
3. Look at `unlinked`. If new files form a new family or belong to an existing process, add or extend nodes. Ignore one-off files.
4. Write only the changed or new nodes to `ai_design.json` and `--import` it. The importer merges, and untouched nodes stay as they are.

Never edit `design.json` by hand. Always go through `--import`.
