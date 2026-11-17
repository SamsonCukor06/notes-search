"""Notes Search as a desktop app.

Double-clicking the app runs this. It starts the search page (app.py, a Streamlit app) in a
background process on this computer only, then shows it in its own window. Each person's
notes, indexes and settings live in their own app-data folder:

    macOS:   ~/Library/Application Support/Notes Search
    Windows: %APPDATA%/Notes Search

Nothing is uploaded anywhere. Run from source with:  python desktop.py
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP_NAME = "Notes Search"
FROZEN = getattr(sys, "frozen", False)  # True inside the built app


def bundle_dir() -> Path:
    """Where app.py, .streamlit/ and the bundled search model are."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_env() -> dict:
    """Environment for the search page: the user's own data folder, offline model, app mode."""
    data = data_dir()
    models = data / "models"
    bundled = bundle_dir() / "models"
    if FROZEN and bundled.is_dir() and not models.exists():
        shutil.copytree(bundled, models)  # first launch: a writable copy of the bundled model
    env = dict(os.environ)
    env.update({
        "NOTES_SEARCH_APP": "1",
        "NOTES_SEARCH_DATA": str(data),
        "NOTES_SEARCH_RESULTS": str(data / "results"),
        "NOTES_SEARCH_MODELS": str(models),
    })
    if FROZEN:
        env["HF_HUB_OFFLINE"] = "1"  # the model ships with the app; never reach for the internet
    return env


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def exit_with_parent() -> None:
    """Stop this server when the app's window process ends, even if it quit abruptly (Cmd-Q
    can end the app without running its cleanup)."""
    import threading

    parent = os.getppid()

    def watch() -> None:
        while True:
            time.sleep(2)
            if os.getppid() != parent:  # the parent is gone; we were handed to launchd
                os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def run_server(port: int) -> None:
    """The background process: serve app.py on 127.0.0.1:port."""
    exit_with_parent()
    os.chdir(bundle_dir())  # so .streamlit/config.toml (theme, privacy settings) is used
    from streamlit.web import bootstrap

    flags = {
        "server.port": port, "server.address": "127.0.0.1", "server.headless": True,
        "server.fileWatcherType": "none", "browser.gatherUsageStats": False,
        "global.developmentMode": False, "server.maxUploadSize": 500,
    }
    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(str(bundle_dir() / "app.py"), False, [], flags)


LOADING_HTML = """
<html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#f6f4ee;
  font-family:-apple-system,system-ui,sans-serif;color:#6f6b63">
  <div style="text-align:center">
    <div style="display:inline-grid;place-items:center;width:64px;height:64px;border-radius:18px;
      background:#3d4fd6;color:#fff;font:40px Georgia,serif">∮</div>
    <p style="font-size:17px;margin-top:18px">Starting Notes Search…</p>
  </div>
</body></html>
"""


def main() -> None:
    if "--server" in sys.argv:
        run_server(int(sys.argv[sys.argv.index("--server") + 1]))
        return

    env = app_env()
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    cmd = [sys.executable, "--server", str(port)] if FROZEN else [sys.executable, __file__, "--server", str(port)]
    log_path = data_dir() / "server.log"
    log = open(log_path, "w")
    server = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)

    import webview

    window = webview.create_window(APP_NAME, html=LOADING_HTML, width=1120, height=880, min_size=(420, 560),
                                   background_color="#f6f4ee")

    def wait_then_show() -> None:
        deadline = time.time() + 120
        while time.time() < deadline:
            if server.poll() is not None:
                break  # the server stopped: show the error below
            try:
                with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as r:
                    if r.status == 200:
                        window.load_url(url)
                        return
            except OSError:
                time.sleep(0.4)
        window.load_html(f"<body style='font-family:system-ui;padding:40px'><h2>Notes Search couldn't start</h2>"
                         f"<p>Details are in {log_path}</p></body>")

    try:
        webview.start(wait_then_show, private_mode=False, storage_path=str(data_dir() / "webview"))
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


if __name__ == "__main__":
    main()
