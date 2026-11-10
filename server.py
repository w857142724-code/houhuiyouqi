#!/usr/bin/env python3
"""后会友期 · 静态站点 + 极简访问统计。"""
import http.server
import json
import os
import socketserver
import threading
import time

PORT = int(os.environ.get("PORT", "8080"))
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("STATS_DIR", os.path.join(ROOT, "data"))
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
LOCK = threading.Lock()

EMPTY = {"views": 0, "starts": 0, "endings": {}, "days": {}}


def ensure_data_dir():
    """机器上没有挂载卷时，退回项目目录下的 data/，别让统计直接挂掉。"""
    global DATA_DIR, STATS_FILE
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        probe = os.path.join(DATA_DIR, ".probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except Exception as e:
        print("stats dir %s unusable (%s), falling back to ./data" % (DATA_DIR, e), flush=True)
        DATA_DIR = os.path.join(ROOT, "data")
        STATS_FILE = os.path.join(DATA_DIR, "stats.json")
        os.makedirs(DATA_DIR, exist_ok=True)


def load_stats():
    try:
        with open(STATS_FILE, encoding="utf-8") as f:
            st = json.load(f)
        for k, v in EMPTY.items():
            st.setdefault(k, v.copy() if isinstance(v, dict) else v)
        return st
    except Exception:
        return {k: (v.copy() if isinstance(v, dict) else v) for k, v in EMPTY.items()}


def save_stats(st):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = STATS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATS_FILE)
    except Exception as e:
        print("stats save failed:", e, flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._api = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/stats":
            today = time.strftime("%Y-%m-%d")
            with LOCK:
                st = load_stats()
            self._json({
                "views": st.get("views", 0),
                "starts": st.get("starts", 0),
                "endings": st.get("endings", {}),
                "today": (st.get("days") or {}).get(today, 0),
            })
            return
        if path == "/api/health":
            self._json({"ok": True})
            return
        super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/api/event":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        t = payload.get("type")
        today = time.strftime("%Y-%m-%d")
        with LOCK:
            st = load_stats()
            days = st.setdefault("days", {})
            if t == "view":
                st["views"] = st.get("views", 0) + 1
                days[today] = days.get(today, 0) + 1
            elif t == "start":
                st["starts"] = st.get("starts", 0) + 1
            elif t == "ending":
                key = str(payload.get("ending") or "unknown")[:24]
                e = st.setdefault("endings", {})
                e[key] = e.get(key, 0) + 1
            save_stats(st)
        self._json({"ok": True})

    def end_headers(self):
        if not getattr(self, "_api", False):
            self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    ensure_data_dir()
    print("serving on 0.0.0.0:%d  (stats: %s)" % (PORT, STATS_FILE), flush=True)
    with Server(("0.0.0.0", PORT), Handler) as httpd:
        httpd.serve_forever()
