"""GodotIntegration: parses any Godot 3/4 project into normalized data.

The rest of the app only consumes the dict returned by scan_project();
nothing else touches .gd/.tscn/.tres directly.
"""
import hashlib
import os
import re

SKIP_DIRS = {".godot", ".import", ".git", ".svn", "gamegraph-out", "__pycache__", "node_modules"}
KINDS = {
    ".gd": "script", ".tscn": "scene", ".scn": "scene_binary", ".tres": "resource", ".res": "resource_binary",
    ".gdshader": "shader", ".shader": "shader", ".cs": "csharp", ".godot": "project",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".svg": "image", ".bmp": "image",
    ".wav": "audio", ".ogg": "audio", ".mp3": "audio", ".ttf": "font", ".otf": "font",
    ".json": "text", ".cfg": "text", ".txt": "text", ".md": "text",
}
TEXT_KINDS = {"script", "scene", "resource", "shader", "csharp", "project", "text"}


# ---------- ProjectParser ----------

def parse_project_godot(text):
    info = {"name": None, "main_scene": None, "autoloads": {}}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.strip("[]")
            continue
        if "=" not in line or line.startswith(";"):
            continue
        key, val = (s.strip() for s in line.split("=", 1))
        val = val.strip('"')
        if section == "application" and key == "config/name":
            info["name"] = val
        elif section == "application" and key == "run/main_scene":
            info["main_scene"] = val
        elif section == "autoload":
            info["autoloads"][key] = val.lstrip("*")
    return info


# ---------- GDScriptParser ----------

_RES_STR = re.compile(r'"(res://[^"]+)"')
_LOAD = re.compile(r'\b(preload|load)\(\s*"([^"]+)"')
_VAR = re.compile(r'^(?:static\s+)?var\s+(\w+)\s*(?::\s*([\w\[\]\.]+))?\s*(?::?=\s*(.+))?')
_FUNC = re.compile(r'^(?:static\s+)?func\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([\w\[\]\.]+))?')
_SIGNAL = re.compile(r'^signal\s+(\w+)\s*(?:\(([^)]*)\))?')


def parse_gdscript(text):
    out = {"class_name": None, "extends": None, "signals": [], "variables": [], "constants": [],
           "functions": [], "inner_classes": [], "references": []}
    pending_export = False
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw or raw[0] in " \t#":  # top level only
            continue
        line = raw.split("#", 1)[0].strip() if '"' not in raw else raw.strip()
        m = re.match(r'class_name\s+(\w+)', line)
        if m:
            out["class_name"] = m.group(1)
            m2 = re.search(r'\bextends\s+(\S+)', line)  # Godot 3: class_name X extends Y
            if m2:
                out["extends"] = m2.group(1).strip('"')
            continue
        m = re.match(r'extends\s+(\S+)', line)
        if m:
            out["extends"] = m.group(1).strip('"')
            continue
        m = re.match(r'class\s+(\w+)', line)
        if m:
            out["inner_classes"].append(m.group(1))
            continue
        m = _SIGNAL.match(line)
        if m:
            out["signals"].append({"name": m.group(1), "args": (m.group(2) or "").strip(), "line": n})
            continue
        m = re.match(r'const\s+(\w+)\s*(?::\s*\w+)?\s*:?=\s*(.+)', line)
        if m:
            out["constants"].append({"name": m.group(1), "value": m.group(2).strip(), "line": n})
            continue
        # annotations may sit alone on the previous line ("@export" / "@onready")
        exported = pending_export or line.startswith("export") or "@export" in line
        stripped = re.sub(r'^((?:@\w+(?:\([^)]*\))?|export(?:\([^)]*\))?|onready)\s*)+', "", line)
        m = _VAR.match(stripped)
        if m:
            out["variables"].append({"name": m.group(1), "type": m.group(2), "default": (m.group(3) or "").strip() or None,
                                     "exported": exported, "onready": "onready" in line, "line": n})
            pending_export = False
            continue
        pending_export = stripped == "" and "@export" in line
        m = _FUNC.match(stripped)
        if m:
            out["functions"].append({"name": m.group(1), "args": m.group(2).strip(), "returns": m.group(3), "line": n})
    refs = {p for _, p in _LOAD.findall(text)} | set(_RES_STR.findall(text))
    out["references"] = sorted(refs)
    return out


# ---------- SceneParser / ResourceParser (shared Godot text format) ----------

_HEADER = re.compile(r'^\[(\w+)(.*)\]\s*$')
_ATTR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\w+\([^)]*\)|[^\s\]]+)')
_EXT_REF = re.compile(r'ExtResource\(\s*"?([^")\s]+)"?\s*\)')
_SUB_REF = re.compile(r'SubResource\(\s*"?([^")\s]+)"?\s*\)')


def _attrs(s):
    return {k: v[1:-1] if v.startswith('"') else v for k, v in _ATTR.findall(s)}


def _balance(s, depth=0, in_str=False):
    """Bracket depth after s, carrying state across lines (linear, not quadratic)."""
    esc = False
    for c in s:
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            depth += (c in "([{") - (c in ")]}")
    return depth, in_str


MAX_VALUE = 2000  # tile data / animation tracks / byte arrays are useless to humans & agents


def _clip(v):
    return v if len(v) <= MAX_VALUE else f"{v[:200]}… <{len(v)} chars truncated>"


def parse_text_resource(text):
    """Split .tscn/.tres into sections: [{tag, attrs, props}]."""
    sections, cur, key, parts, state = [], None, None, [], (0, False)
    for line in text.splitlines():
        if key is not None:  # continuing a multi-line value
            parts.append(line)
            state = _balance(line, *state)
            if state[0] <= 0:
                cur["props"][key], key = _clip("\n".join(parts)), None
            continue
        m = _HEADER.match(line)
        if m:
            cur = {"tag": m.group(1), "attrs": _attrs(m.group(2)), "props": {}}
            sections.append(cur)
            continue
        if cur is None or "=" not in line or line.startswith(";"):
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        state = _balance(v)
        if state[0] > 0:
            key, parts = k, [v]
        else:
            cur["props"][k] = _clip(v)
    return sections


def _resolve_refs(props, ext):
    """Replace ExtResource("id") with the res:// path for readability."""
    return {k: _EXT_REF.sub(lambda m: f'ExtResource({ext.get(m.group(1), {}).get("path", m.group(1))})', v)
            for k, v in props.items()}


def parse_scene(text):
    secs = parse_text_resource(text)
    ext = {s["attrs"].get("id"): s["attrs"] for s in secs if s["tag"] == "ext_resource"}
    subs = [{"id": s["attrs"].get("id"), "type": s["attrs"].get("type"), "props": _resolve_refs(s["props"], ext)}
            for s in secs if s["tag"] == "sub_resource"]
    nodes, root = [], None
    for s in secs:
        if s["tag"] != "node":
            continue
        a = s["attrs"]
        parent = a.get("parent")
        path = "." if parent is None else (a["name"] if parent == "." else f"{parent}/{a['name']}")
        node = {"name": a.get("name"), "type": a.get("type"), "path": path,
                "parent": parent, "props": _resolve_refs(s["props"], ext), "script": None, "instance": None,
                "groups": a.get("groups")}
        m = _EXT_REF.search(s["props"].get("script", ""))
        if m and m.group(1) in ext:
            node["script"] = ext[m.group(1)].get("path")
        m = _EXT_REF.search(a.get("instance", ""))
        if m and m.group(1) in ext:
            node["instance"] = ext[m.group(1)].get("path")
            node["type"] = node["type"] or "(instance)"
        if parent is None:
            root = node
        nodes.append(node)
    conns = [s["attrs"] for s in secs if s["tag"] == "connection"]
    return {"root": root and {"name": root["name"], "type": root["type"]},
            "nodes": nodes, "ext_resources": list(ext.values()), "sub_resources": subs, "connections": conns}


def parse_resource(text):
    secs = parse_text_resource(text)
    head = secs[0]["attrs"] if secs else {}
    ext = {s["attrs"].get("id"): s["attrs"] for s in secs if s["tag"] == "ext_resource"}
    res = next((s for s in secs if s["tag"] == "resource"), {"props": {}})
    props = _resolve_refs(res["props"], ext)
    script = None
    m = _EXT_REF.search(res["props"].get("script", ""))
    if m and m.group(1) in ext:
        script = ext[m.group(1)].get("path")
    return {"type": head.get("script_class") or head.get("type"), "base_type": head.get("type"),
            "script": script, "properties": {k: v for k, v in props.items() if k not in ("script", "resource_name")},
            "resource_name": props.get("resource_name", "").strip('"') or None,
            "ext_resources": list(ext.values()),
            "sub_resources": [{"id": s["attrs"].get("id"), "type": s["attrs"].get("type")} for s in secs if s["tag"] == "sub_resource"]}


# ---------- AssetIndexer ----------

def to_res(root, abspath):
    return "res://" + os.path.relpath(abspath, root).replace(os.sep, "/")


def to_abs(root, res_path):
    """res:// path -> absolute path, refusing anything outside the project."""
    rel = res_path[6:] if res_path.startswith("res://") else res_path
    p = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([p, os.path.realpath(root)]) != os.path.realpath(root):
        raise ValueError("path escapes project")
    return p


def walk(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not os.path.exists(os.path.join(d, x, ".gdignore")))
        for f in sorted(files):
            if not f.endswith((".import", ".uid")):
                yield os.path.join(d, f)


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_file(kind, text):
    return {"script": parse_gdscript, "scene": parse_scene, "resource": parse_resource,
            "project": parse_project_godot}.get(kind, lambda t: None)(text)


# ---------- DependencyAnalyzer ----------

def analyze(files, classes):
    """Detected edges. kind='code' (from GDScript) or 'file' (from scenes/resources)."""
    edges = []

    def add(s, t, typ, kind):
        if t and s != t:
            edges.append({"source": s, "target": t, "type": typ, "kind": kind, "missing": t not in files})

    for path, f in files.items():
        p = f.get("parsed")
        if not p:
            continue
        if f["kind"] == "script":
            ext = p["extends"]
            if ext:
                add(path, ext if ext.startswith("res://") else classes.get(ext), "inherits", "code")
            for r in p["references"]:
                add(path, r, "references", "code")
        elif f["kind"] == "scene":
            for e in p["ext_resources"]:
                typ = {"Script": "uses", "PackedScene": "instances"}.get(e.get("type"), "references")
                add(path, e.get("path"), typ, "file")
        elif f["kind"] == "resource":
            if p["script"]:
                add(path, p["script"], "uses", "file")
            for e in p["ext_resources"]:
                if e.get("path") != p["script"]:
                    add(path, e.get("path"), "references", "file")
    return edges


# ---------- ProjectWatcher ----------

def signature(root):
    h = hashlib.md5()
    for p in walk(root):
        try:
            st = os.stat(p)
        except OSError:
            continue
        h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}".encode())
    return h.hexdigest()


def scan_project(root):
    root = os.path.realpath(root)
    if not os.path.isfile(os.path.join(root, "project.godot")):
        raise FileNotFoundError(f"nenhum project.godot em {root}")
    files, classes = {}, {}
    for p in walk(root):
        kind = KINDS.get(os.path.splitext(p)[1].lower(), "other")
        st = os.stat(p)
        entry = {"kind": kind, "size": st.st_size, "mtime": st.st_mtime}
        if kind in TEXT_KINDS:
            try:
                text = read_text(p)
                entry["hash"] = hashlib.md5(text.encode()).hexdigest()[:12]  # lets links detect "file changed since review"
                if kind in ("script", "scene", "resource", "project"):
                    entry["parsed"] = parse_file(kind, text)
            except Exception as e:  # one broken file must not kill the scan
                entry["error"] = str(e)
        files[to_res(root, p)] = entry
        if kind == "script" and entry.get("parsed", {}).get("class_name"):
            classes[entry["parsed"]["class_name"]] = to_res(root, p)
    project = files.get("res://project.godot", {}).get("parsed") or {}
    return {"root": root, "project": project, "files": files, "classes": classes,
            "edges": analyze(files, classes), "signature": signature(root)}
