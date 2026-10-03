# GameGraph — Spec (Godot primary target)

## Core idea
Open a Godot project → GameGraph indexes it → user builds a visual knowledge graph linked to real project files → humans and AI agents navigate design knowledge AND implementation.

**Guiding question:** "If I give an AI agent access to this GameGraph and my Godot project, can it understand how this game is designed AND how that design is actually implemented?"

## Godot file support
- **`.gd`**: detect, display, read; class_name, extends, @export props, vars, funcs, signals, refs to other scripts/resources.
- **`.tscn`**: scene name, root node, hierarchy, node types, attached scripts, ext/sub resources, exported props, instanced scenes, key properties.
- **`.tres` / `.res`**: type + properties (e.g. health=50, damage=10).

## Features
- **Project Explorer**: tree of the real project (needs `project.godot`); click a file to open the matching viewer.
- **File ↔ Node links**: drag a file onto a graph node; type is detected automatically (`.tscn`→scene, `.gd`→script, `.tres`→data).
- **Godot-aware graph**, with three relationship kinds kept separate:
  - DESIGN (manual): Goblin → belongs_to → Forest
  - CODE (detected): goblin.gd → inherits → BaseEnemy.gd
  - FILE (detected): goblin.tscn → uses → goblin.gd
- **Live indexing**: rescan and detect added/removed/modified files. Never delete manual nodes because a file changed. Keep Godot data separate from GameGraph design metadata.
- **Code viewer** (.gd): syntax highlighting, line numbers, search; read-only at first.
- **Scene viewer** (.tscn): hierarchy + properties; asset preview if feasible. Not a Godot editor replacement.
- **Resource inspector** (.tres/.res): type + parsed properties.
- **Agent context export**: combine design docs, graph relations, scene structure, GDScript info, resource properties, relevant files and agent instructions/design rules.

## Architecture
A parser/indexer layer outputs normalized project data. The rest of the app consumes only that data and never parses Godot files directly.

```
GodotIntegration
├── ProjectParser
├── GDScriptParser
├── SceneParser
├── ResourceParser
├── AssetIndexer
├── DependencyAnalyzer
└── ProjectWatcher
```

Future engines (Unity, Unreal) plug in at this layer. Godot is the only fully supported engine at first.
