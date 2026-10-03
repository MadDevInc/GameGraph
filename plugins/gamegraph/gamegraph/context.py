"""Agent context: merges GameGraph design metadata with normalized Godot data."""
import json
import os
import re

from godot import read_text, to_abs

ROLE_BY_KIND = {"scene": "scene", "scene_binary": "scene", "script": "script", "resource": "data",
                "resource_binary": "data", "csharp": "script"}


def design_path(root):
    return os.path.join(root, "gamegraph-out", "design.json")


def load_design(root):
    try:
        with open(design_path(root), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"nodes": [], "links": [], "relations": [], "rules": "", "instructions": ""}


def save_design(root, design):
    os.makedirs(os.path.dirname(design_path(root)), exist_ok=True)
    tmp = design_path(root) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(design, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, design_path(root))  # atomic: never leave a half-written design file


def scene_tree(parsed):
    lines = []
    for n in parsed["nodes"]:
        depth = 0 if n["path"] == "." else n["path"].count("/") + 1
        extra = "".join(f"  [{k}: {v}]" for k, v in (("script", n["script"]), ("instance", n["instance"])) if v)
        lines.append("  " * depth + f"- {n['name']} ({n['type']}){extra}")
    return "\n".join(lines)


def describe_file(index, path, include_code=False):
    f = index["files"].get(path)
    if not f:
        return f"{path}\n(FALTANDO no projeto)"
    p, kind, out = f.get("parsed"), f["kind"], [f"{path}  [{f['kind']}]"]
    if kind == "scene" and p:
        out += [f"Raiz: {p['root']['name']} ({p['root']['type']})" if p["root"] else "", "Árvore:", scene_tree(p)]
        if p["connections"]:
            out.append("Sinais: " + "; ".join(f"{c.get('from')}.{c.get('signal')} -> {c.get('to')}.{c.get('method')}" for c in p["connections"]))
    elif kind == "script" and p:
        if p["class_name"]:
            out.append(f"class_name {p['class_name']}")
        out.append(f"extends {p['extends'] or 'RefCounted'}")
        chain, cur, seen = [], p["extends"], set()
        while cur and cur in index["classes"] and cur not in seen:
            seen.add(cur)
            parent = index["files"][index["classes"][cur]].get("parsed") or {}
            cur = parent.get("extends")
            if cur:
                chain.append(cur)
        if chain:
            out.append("Herança: " + " -> ".join([p["extends"]] + chain))
        if p["signals"]:
            out.append("Sinais: " + ", ".join(s["name"] + (f"({s['args']})" if s["args"] else "") for s in p["signals"]))
        exp = [v for v in p["variables"] if v["exported"]]
        if exp:
            out.append("Exportadas: " + ", ".join(f"{v['name']}: {v['type'] or '?'}" + (f" = {v['default']}" if v["default"] else "") for v in exp))
        if p["functions"]:
            out.append("Funções: " + ", ".join(f"{fn['name']}({fn['args']})" for fn in p["functions"]))
        if include_code:
            out += ["```gdscript", read_text(to_abs(index["root"], path)).rstrip(), "```"]
    elif kind == "resource" and p:
        out.append(f"Tipo: {p['type']}" + (f" (script {p['script']})" if p["script"] else ""))
        out += [f"  {k}: {v}" for k, v in p["properties"].items()]
    elif include_code and kind in ("shader", "text", "csharp"):
        out += ["```", read_text(to_abs(index["root"], path)).rstrip(), "```"]
    return "\n".join(x for x in out if x)


KIND_ORDER = {"process": 0, "system": 1, "entity": 2}
KIND_PT = {"process": "processo", "system": "sistema", "entity": "entidade"}
GROUP_PT = {"process": "PROCESSOS", "system": "SISTEMAS", "entity": "ENTIDADES"}


def slug(node):
    s = re.sub(r"[^\w]+", "-", node["label"].lower()).strip("-")
    return s or node["id"][2:]


def stale_files(index, design, node_id):
    """Linked files whose content changed since the node was last reviewed/imported."""
    return [l["file"] for l in design["links"] if l["node"] == node_id and l.get("hash")
            and l["file"] in index["files"] and index["files"][l["file"]].get("hash") != l["hash"]]


def subclass_table(index, path):
    """For a base script: what each subclass changes. This is the 'do it like the Goblin' knowledge."""
    p = index["files"][path].get("parsed") or {}
    name = p.get("class_name")
    base_funcs = {f["name"] for f in p.get("functions", [])}
    kids = sorted((k, f) for k, f in index["files"].items() if f["kind"] == "script" and f.get("parsed")
                  and f["parsed"]["extends"] in (name, path) and k != path)
    out = []
    for k, f in kids[:20]:
        kp = f["parsed"]
        over = [fn["name"] for fn in kp["functions"] if fn["name"] in base_funcs]
        added = [fn["name"] for fn in kp["functions"] if fn["name"] not in base_funcs]
        exp = [f"{v['name']}={v['default']}" for v in kp["variables"] if v["exported"] and v["default"]]
        parts = [f"sobrescreve: {', '.join(over)}" if over else "", f"novas: {', '.join(added)}" if added else "",
                 f"exports: {', '.join(exp)}" if exp else ""]
        out.append(f"- {kp['class_name'] or os.path.basename(k)} ({k}): " + ("; ".join(x for x in parts if x) or "sem mudanças"))
    if len(kids) > 20:
        out.append(f"- … e mais {len(kids) - 20}")
    return out


def sibling_resources(index, path):
    """Same-type .tres side by side: a ready-made balance table."""
    p = index["files"][path].get("parsed") or {}
    same = sorted((k, f["parsed"]) for k, f in index["files"].items()
                  if f["kind"] == "resource" and f.get("parsed") and f["parsed"]["type"] == p.get("type"))
    if len(same) < 2:
        return []
    keys = list(dict.fromkeys(c for _, r in same for c in r["properties"] if len(r["properties"][c]) <= 40))[:8]
    rows = [f"| arquivo | {' | '.join(keys)} |", "|" + "---|" * (len(keys) + 1)]
    rows += [f"| {os.path.basename(k)} | " + " | ".join(r["properties"].get(c, "") for c in keys) + " |" for k, r in same[:25]]
    if len(same) > 25:
        rows.append(f"… e mais {len(same) - 25}")
    return rows


def _header(index, design):
    proj = index["project"]
    out = [f"# Contexto GameGraph — {proj.get('name') or os.path.basename(index['root'])}",
           f"Projeto Godot: {index['root']}"]
    if proj.get("main_scene"):
        out.append(f"Cena principal: {proj['main_scene']}")
    if proj.get("autoloads"):
        out.append("Autoloads: " + ", ".join(f"{k}={v}" for k, v in proj["autoloads"].items()))
    if design.get("rules"):
        out += ["", "## REGRAS DO JOGO", design["rules"]]
    if design.get("instructions"):
        out += ["", "## INSTRUÇÕES PARA OS AGENTES", design["instructions"]]
    return out


def context_index(index, design):
    """CONTEXT.md: short on purpose (read every session). One line per node; detail lives in nodes/<slug>.md."""
    out = _header(index, design)
    out += ["", "## COMO USAR",
            "Ache abaixo o PROCESSO da sua tarefa e leia o detalhe dele em `gamegraph-out/nodes/<nome>.md` antes de começar:",
            "passos, arquivos reais e o que muda entre os exemplos. Leia código só dos arquivos que ele aponta."]
    kind = None
    for n in sorted(design["nodes"], key=lambda n: (KIND_ORDER.get(n.get("kind"), 9), n["label"])):
        if n.get("kind") != kind:
            kind = n.get("kind")
            out += ["", "## " + GROUP_PT.get(kind, "OUTROS")]
        summary = (n.get("notes") or "").strip().split("\n")[0][:140]
        nl = sum(1 for l in design["links"] if l["node"] == n["id"])
        meta = ", ".join(x for x in (f"{len(n['steps'])} passos" if n.get("steps") else "", f"{nl} arquivos" if nl else "") if x)
        warn = " ⚠ REVISAR (arquivos mudaram)" if stale_files(index, design, n["id"]) else ""
        out.append(f"- **{n['label']}** → `nodes/{slug(n)}.md`" + (f" ({meta})" if meta else "") + (f": {summary}" if summary else "") + warn)
    return "\n".join(out) + "\n"


def context_node(index, design, n, include_code=False):
    nodes = {x["id"]: x for x in design["nodes"]}
    label = lambda i: nodes.get(i, {}).get("label", "?")
    out = [f"# {n['label']}" + (f"  ({KIND_PT.get(n.get('kind'), n.get('kind'))})" if n.get("kind") else "")]
    stale = stale_files(index, design, n["id"])
    if stale:
        out += ["", "> ⚠ ESTES ARQUIVOS MUDARAM desde a última revisão deste nó. Confira se os passos ainda valem:"]
        out += [f"> - {f}" for f in stale]
    if n.get("notes"):
        out += ["", n["notes"]]
    if n.get("steps"):
        out += ["", "## PASSOS"] + [f"{i}. {st}" for i, st in enumerate(n["steps"], 1)]
    links = [l for l in design["links"] if l["node"] == n["id"]]
    if links:
        out += ["", "## ARQUIVOS"]
        out += [f"- {l.get('label') or l['role']} → {l['file']}" + ("" if l["file"] in index["files"] else " (FALTANDO)") for l in links]
    rels = [r for r in design["relations"] if n["id"] in (r["source"], r["target"])]
    if rels:
        out += ["", "## RELAÇÕES"] + [f"- {label(r['source'])} → {r['label']} → {label(r['target'])}" for r in rels]
    for l in links:
        if l["file"] not in index["files"]:
            continue
        out += ["", f"## {(l.get('label') or l['role']).upper()}", describe_file(index, l["file"], include_code)]
        kind = index["files"][l["file"]]["kind"]
        t = subclass_table(index, l["file"]) if kind == "script" else sibling_resources(index, l["file"]) if kind == "resource" else []
        if t:
            out += ["", "### O QUE CADA VARIAÇÃO MUDA (use como modelo)" if kind == "script" else "### OUTROS RECURSOS DO MESMO TIPO (compare valores)"] + t
    return "\n".join(out) + "\n"


def find_node(design, node_id):
    for n in design["nodes"]:
        if node_id in (n["id"], "d:" + node_id) or n["label"].lower() == node_id.lower() or slug(n) == node_id.lower():
            return n
    raise KeyError(f"nenhum nó chamado '{node_id}'")


def build_context(index, design, node_id=None, include_code=False):
    """node_id=None -> short index of the whole game. node_id -> full detail for one node."""
    if node_id is None:
        return context_index(index, design)
    return "\n".join(_header(index, design)) + "\n\n" + context_node(index, design, find_node(design, node_id), include_code)


def write_outputs(root, index, design):
    """CONTEXT.md (index) + nodes/<slug>.md (detail): agents read these directly, no tool run needed."""
    out = os.path.join(root, "gamegraph-out")
    nd = os.path.join(out, "nodes")
    os.makedirs(nd, exist_ok=True)
    keep = set()
    for n in design["nodes"]:
        name = slug(n) + ".md"
        keep.add(name)
        with open(os.path.join(nd, name), "w", encoding="utf-8") as fh:
            fh.write(context_node(index, design, n))
    for f in os.listdir(nd):
        if f.endswith(".md") and f not in keep:
            os.remove(os.path.join(nd, f))
    with open(os.path.join(out, "CONTEXT.md"), "w", encoding="utf-8") as fh:
        fh.write(context_index(index, design))


def stale_report(index, design):
    """What --update must re-check: only these nodes need the AI to re-read files (cheap incremental update)."""
    rows = []
    for n in design["nodes"]:
        st = stale_files(index, design, n["id"])
        miss = [l["file"] for l in design["links"] if l["node"] == n["id"] and l["file"] not in index["files"]]
        if st or miss:
            rows.append({"id": n["id"], "label": n["label"], "edited": bool(n.get("edited")), "changed": st, "missing": miss})
    linked = {l["file"] for l in design["links"]}
    unlinked = sorted(k for k, f in index["files"].items() if f["kind"] in ("script", "scene") and k not in linked)
    return {"stale": rows, "unlinked": unlinked}


def import_design(root, index, new):
    """Merge an AI-built design into design.json without clobbering the user's work:
    nodes the user edited (edited=true) or deleted (design['deleted']) are left alone.
    Re-imported nodes count as reviewed: their links get the files' current hash."""
    d = load_design(root)
    d.setdefault("deleted", [])
    fix = lambda i: i if i.startswith("d:") else "d:" + i
    by_id = {n["id"]: n for n in d["nodes"]}
    warnings, protected = [], {i for i, n in by_id.items() if n.get("edited")} | set(d["deleted"])
    for n in new.get("nodes", []):
        n = {**n, "id": fix(n["id"])}
        if n["id"] in protected:
            continue
        if n["id"] in by_id:
            n["pos"] = by_id[n["id"]].get("pos")
            by_id[n["id"]].clear()
            by_id[n["id"]].update(n)
        else:
            d["nodes"].append(n)
            by_id[n["id"]] = n
    have = {(l["node"], l["file"]) for l in d["links"]}
    for l in new.get("links", []):
        l = {**l, "node": fix(l["node"])}
        f = index["files"].get(l["file"], {})
        l.setdefault("role", ROLE_BY_KIND.get(f.get("kind"), "asset"))
        if l["node"] not in by_id or l["node"] in protected:
            continue
        if not f:
            warnings.append(f"arquivo não existe: {l['file']}")
        if (l["node"], l["file"]) in have:
            next(x for x in d["links"] if (x["node"], x["file"]) == (l["node"], l["file"])).update(l)
        else:
            d["links"].append(l)
            have.add((l["node"], l["file"]))
    reviewed = {fix(n["id"]) for n in new.get("nodes", [])} - protected
    for l in d["links"]:
        h = index["files"].get(l["file"], {}).get("hash")
        if h and (l["node"] in reviewed or "hash" not in l):
            l["hash"] = h
    rels = {(r["source"], r["target"], r["label"]) for r in d["relations"]}
    for r in new.get("relations", []):
        key = (fix(r["source"]), fix(r["target"]), r["label"])
        if key in rels or key[0] not in by_id or key[1] not in by_id:
            continue
        d["relations"].append({"id": f"{key[0]}>{key[1]}>{key[2]}", "source": key[0], "target": key[1], "label": key[2]})
        rels.add(key)
    for k in ("rules", "instructions"):
        if new.get(k) and not d.get(f"{k}_edited"):
            d[k] = new[k]
    save_design(root, d)
    return d, warnings


def architecture_summary(index):
    """Whole-project view for agents when no design node is chosen."""
    out = [f"# Arquitetura Godot — {index['project'].get('name')}", "", "## Classes"]
    for name, path in sorted(index["classes"].items()):
        out.append(f"- {name} ({path}) extends {index['files'][path]['parsed']['extends']}")
    out += ["", "## Cenas"]
    for path, f in sorted(index["files"].items()):
        if f["kind"] == "scene" and f.get("parsed") and f["parsed"]["root"]:
            out.append(f"- {path}: {f['parsed']['root']['name']} ({f['parsed']['root']['type']})")
    out += ["", "## Recursos"]
    for path, f in sorted(index["files"].items()):
        if f["kind"] == "resource" and f.get("parsed"):
            out.append(f"- {path}: {f['parsed']['type']}")
    return "\n".join(out) + "\n"
