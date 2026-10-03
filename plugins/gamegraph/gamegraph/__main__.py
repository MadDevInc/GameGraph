"""GameGraph CLI + web server.

  python gamegraph <godot_project>                 scan, write gamegraph-out/, open web UI
  python gamegraph <godot_project> --no-serve      scan + write outputs only
  python gamegraph <godot_project> --context Goblin [--code]   print agent context
"""
import argparse
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import architecture_summary, build_context, import_design, load_design, save_design, stale_report, write_outputs  # noqa: E402
from godot import TEXT_KINDS, parse_file, read_text, scan_project, signature, to_abs  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")


class State:
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.lock = threading.Lock()
        self.index = None
        self.rescan()

    def rescan(self):
        with self.lock:
            self.index = scan_project(self.root)
            out = os.path.join(self.root, "gamegraph-out")
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, ".gdignore"), "a").close()  # hide from Godot FileSystem dock
            with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
                json.dump(self.index, fh, indent=1, ensure_ascii=False)
            with open(os.path.join(out, "ARCHITECTURE.md"), "w", encoding="utf-8") as fh:
                fh.write(architecture_summary(self.index))
            design = load_design(self.root)
            if not os.path.exists(os.path.join(out, "design.json")):
                save_design(self.root, design)
            write_outputs(self.root, self.index, design)
        return self.index

    def save(self, design):
        with self.lock:
            save_design(self.root, design)
            write_outputs(self.root, self.index, design)  # UI edits reach agents immediately


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="application/json", code=200):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
                ctype += "; charset=utf-8"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    return self.send(read_text(STATIC), "text/html")
                if u.path == "/api/index":
                    return self.send(state.index)
                if u.path == "/api/signature":  # ProjectWatcher polling
                    return self.send({"signature": signature(state.root), "current": state.index["signature"]})
                if u.path == "/api/rescan":
                    return self.send(state.rescan())
                if u.path == "/api/file":
                    p = to_abs(state.root, q["path"])
                    f = state.index["files"].get(q["path"], {})
                    text = read_text(p) if f.get("kind") in TEXT_KINDS else None
                    return self.send({"path": q["path"], "kind": f.get("kind"), "size": os.path.getsize(p), "text": text,
                                      "parsed": parse_file(f.get("kind"), text) if text is not None else None})
                if u.path == "/api/raw":
                    p = to_abs(state.root, q["path"])
                    with open(p, "rb") as fh:
                        return self.send(fh.read(), mimetypes.guess_type(p)[0] or "application/octet-stream")
                if u.path == "/api/design":
                    return self.send(load_design(state.root))
                if u.path == "/api/context":
                    design = load_design(state.root)
                    text = build_context(state.index, design, q.get("node") or None, q.get("code") == "1")
                    return self.send(text, "text/plain")
                self.send({"error": "not found"}, code=404)
            except (KeyError, ValueError, FileNotFoundError) as e:
                self.send({"error": str(e)}, code=400)

        def do_POST(self):
            if urlparse(self.path).path != "/api/design":
                return self.send({"error": "not found"}, code=404)
            try:
                design = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if not all(isinstance(design.get(k), list) for k in ("nodes", "links", "relations")):
                    raise ValueError("bad design payload")
            except (ValueError, TypeError) as e:
                return self.send({"error": str(e)}, code=400)
            state.save(design)
            self.send({"ok": True})

    return H


def main():
    ap = argparse.ArgumentParser(prog="gamegraph")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--context", metavar="NODE", help="print agent context for a design node ('all' = every node)")
    ap.add_argument("--code", action="store_true", help="include full source of linked scripts in context")
    ap.add_argument("--stale", action="store_true", help="list nodes whose files changed + unlinked scripts/scenes (for --update)")
    ap.add_argument("--import", dest="imp", metavar="FILE", help="merge an AI-built design JSON into design.json")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        state = State(args.project)
    except FileNotFoundError as e:
        sys.exit(f"gamegraph: {e}")
    idx = state.index
    if args.stale:
        print(json.dumps(stale_report(idx, load_design(state.root)), indent=1, ensure_ascii=False))
        return
    if args.imp:
        with open(args.imp, encoding="utf-8") as fh:
            d, warnings = import_design(state.root, idx, json.load(fh))
        state.rescan()  # refresh CONTEXT.md
        print(f"design.json: {len(d['nodes'])} nós, {len(d['links'])} arquivos ligados, {len(d['relations'])} relações")
        for w in warnings:
            print("AVISO:", w)
        return
    if args.context:
        node = None if args.context == "all" else args.context
        try:
            print(build_context(idx, load_design(state.root), node, args.code))
        except KeyError as e:
            sys.exit(f"gamegraph: {e}")
        return
    kinds = {}
    for f in idx["files"].values():
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    print(f"GameGraph: {idx['project'].get('name')} — {len(idx['files'])} arquivos, {len(idx['classes'])} classes, "
          f"{len(idx['edges'])} ligações detectadas  {kinds}")
    print(f"Saída: {os.path.join(state.root, 'gamegraph-out')}")
    if args.no_serve:
        return
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    url = f"http://127.0.0.1:{args.port}"
    print(f"GameGraph by MadDev Studios rodando em {url}  (Ctrl+C para parar)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
