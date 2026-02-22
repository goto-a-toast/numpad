#!/usr/bin/env python3
"""
スマホテンキーサーバー（HTML配信込み）
使い方: python3 numpad_server.py

スマホのブラウザで http://[PCのIP]:8766 を開くだけでOK！
"""

import asyncio
import websockets
import pyautogui
import json
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================================
# テンキーHTML（スマホに配信する画面）
# ============================================================
HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>テンキー</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Noto+Sans+JP:wght@400;700&display=swap');
  :root {
    --bg: #1a1a1f; --surface: #24242c; --accent: #00e5cc;
    --accent2: #ff6b35; --text: #e8e8f0; --text-dim: #6b6b80;
    --key-bg: #2a2a35; --shadow: 0 4px 12px rgba(0,0,0,0.5);
    /* レスポンシブ用：画面幅に応じてスケール */
    --base: min(90vw, 90vh, 600px);
    --gap: calc(var(--base) * 0.025);
    --radius: calc(var(--base) * 0.03);
    --key-font: calc(var(--base) * 0.09);
    --label-font: calc(var(--base) * 0.05);
    --display-font: calc(var(--base) * 0.1);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Noto Sans JP', sans-serif;
    height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: calc(var(--base) * 0.04); gap: calc(var(--base) * 0.03);
    overflow: hidden;
  }
  header {
    width: 100%; max-width: var(--base);
    display: flex; align-items: center; justify-content: space-between;
  }
  .title { font-family: 'Share Tech Mono', monospace; font-size: var(--label-font); color: var(--text-dim); letter-spacing: 0.15em; text-transform: uppercase; }
  .status { display: flex; align-items: center; gap: 6px; font-size: var(--label-font); color: var(--text-dim); }
  .status-dot { width: calc(var(--base)*0.02); height: calc(var(--base)*0.02); border-radius: 50%; background: #444; transition: background 0.3s; }
  .status-dot.connected { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
  .status-dot.error { background: var(--accent2); box-shadow: 0 0 6px var(--accent2); }
  .display {
    width: 100%; max-width: var(--base);
    background: var(--surface); border: 1px solid #3a3a48;
    border-radius: var(--radius); padding: calc(var(--base)*0.03) calc(var(--base)*0.04); text-align: right;
  }
  .display-label { font-size: calc(var(--label-font)*0.7); color: var(--text-dim); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 4px; }
  .display-value { font-family: 'Share Tech Mono', monospace; font-size: var(--display-font); color: var(--accent); letter-spacing: 0.05em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .numpad { width: 100%; max-width: var(--base); display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--gap); flex: 1; }
  .key {
    background: var(--key-bg); border: 1px solid #383848; border-radius: var(--radius); padding: 0;
    aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
    font-size: var(--key-font); font-family: 'Share Tech Mono', monospace; color: var(--text);
    cursor: pointer; user-select: none; transition: background 0.1s, transform 0.1s;
    box-shadow: var(--shadow); position: relative; overflow: hidden;
  }
  .key::after { content: ''; position: absolute; inset: 0; background: white; opacity: 0; transition: opacity 0.15s; border-radius: inherit; }
  .key:active::after { opacity: 0.08; }
  .key:active { transform: scale(0.94); }
  /* ダブルタップズーム完全無効化 */
  .key { touch-action: manipulation; }
  .key.op { color: var(--accent); border-color: rgba(0,229,204,0.2); }
  .key.enter { background: var(--accent); color: #000; border-color: var(--accent); font-size: calc(var(--key-font)*0.6); font-family: 'Noto Sans JP', sans-serif; font-weight: 700; }
  .key.clear { color: var(--accent2); border-color: rgba(255,107,53,0.2); font-size: calc(var(--key-font)*0.6); font-family: 'Noto Sans JP', sans-serif; }
  .key.zero { grid-column: span 2; aspect-ratio: auto; }
  .log { width: 100%; max-width: var(--base); font-family: 'Share Tech Mono', monospace; font-size: calc(var(--label-font)*0.8); color: var(--text-dim); text-align: center; }
</style>
</head>
<body>
<header>
  <span class="title">NumPad Remote</span>
  <div class="status">
    <div class="status-dot" id="statusDot"></div>
    <span id="statusText">接続中...</span>
  </div>
</header>
<div class="display">
  <div class="display-label">DISPLAY</div>
  <div class="display-value" id="displayValue">0</div>
</div>
<div class="numpad">
  <button class="key clear" data-key="clear" onclick="pressKey(this)">CLR</button>
  <button class="key op"    data-key="backspace" onclick="pressKey(this)">&#x232B;</button>
  <button class="key op"    data-key="/" onclick="pressKey(this)">/</button>
  <button class="key op"    data-key="*" onclick="pressKey(this)">x</button>
  <button class="key" data-key="7" onclick="pressKey(this)">7</button>
  <button class="key" data-key="8" onclick="pressKey(this)">8</button>
  <button class="key" data-key="9" onclick="pressKey(this)">9</button>
  <button class="key op" data-key="-" onclick="pressKey(this)">-</button>
  <button class="key" data-key="4" onclick="pressKey(this)">4</button>
  <button class="key" data-key="5" onclick="pressKey(this)">5</button>
  <button class="key" data-key="6" onclick="pressKey(this)">6</button>
  <button class="key op" data-key="+" onclick="pressKey(this)">+</button>
  <button class="key" data-key="1" onclick="pressKey(this)">1</button>
  <button class="key" data-key="2" onclick="pressKey(this)">2</button>
  <button class="key" data-key="3" onclick="pressKey(this)">3</button>
  <button class="key enter" data-key="enter" onclick="pressKey(this)" style="grid-row: span 2;">Enter</button>
  <button class="key zero" data-key="0" onclick="pressKey(this)">0</button>
  <button class="key" data-key="." onclick="pressKey(this)">.</button>
</div>
<div class="log" id="log">接続中...</div>
<script>
const serverHost = location.hostname;
const wsUrl = "ws://" + serverHost + ":__WS_PORT__";
let ws = null;
let displayBuffer = "";
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const displayValue = document.getElementById("displayValue");
const logEl = document.getElementById("log");

function setStatus(state, text) { statusDot.className = "status-dot " + state; statusText.textContent = text; }
function log(msg) { logEl.textContent = msg; }

function updateDisplay(key) {
  if (key === "clear") { displayBuffer = ""; }
  else if (key === "backspace") { displayBuffer = displayBuffer.slice(0, -1); }
  else if (key === "enter") { displayBuffer = ""; }
  else { displayBuffer += key; if (displayBuffer.length > 12) displayBuffer = displayBuffer.slice(-12); }
  displayValue.textContent = displayBuffer || "0";
}

function pressKey(btn) {
  const key = btn.dataset.key;
  updateDisplay(key);
  if (!ws || ws.readyState !== WebSocket.OPEN) { log("未接続"); return; }
  ws.send(JSON.stringify({ key: key }));
}

function connect() {
  setStatus("", "接続中...");
  ws = new WebSocket(wsUrl);
  ws.onopen = function() { setStatus("connected", "接続済み"); log("PCに接続しました"); };
  ws.onclose = function() { setStatus("error", "切断"); log("切断 - 再接続します..."); ws = null; setTimeout(connect, 3000); };
  ws.onerror = function() { setStatus("error", "エラー"); log("接続エラー"); };
}
connect();
</script>
</body>
</html>
"""

# ============================================================
# キーマッピング
# ============================================================
KEY_MAP = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    ".": ".", "+": "+", "-": "-", "*": "*", "/": "/",
    "enter": "enter", "backspace": "backspace", "clear": None,
}

# ============================================================
# WebSocket サーバー
# ============================================================
async def handle_client(websocket):
    addr = websocket.remote_address
    client_ip = addr[0] if addr else "unknown"
    print(f"✅ スマホ接続: {client_ip}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                key = data.get("key", "")
                print(f"  キー: {key}")
                if key in KEY_MAP:
                    mapped = KEY_MAP[key]
                    if mapped:
                        pyautogui.press(mapped)
                await websocket.send(json.dumps({"status": "ok", "key": key}))
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        print(f"❌ 切断: {client_ip}")

# ============================================================
# HTTP サーバー（HTMLを配信）
# ============================================================
def make_html_handler(ws_port):
    html = HTML.replace("__WS_PORT__", str(ws_port))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        def log_message(self, format, *args):
            pass
    return Handler

def start_http_server(port, ws_port):
    handler = make_html_handler(ws_port)
    server = HTTPServer(("0.0.0.0", port), handler)
    server.serve_forever()

# ============================================================
# メイン
# ============================================================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

async def main():
    ws_port = 8765
    http_port = 8766
    local_ip = get_local_ip()

    t = threading.Thread(target=start_http_server, args=(http_port, ws_port), daemon=True)
    t.start()

    print("=" * 50)
    print("  📱 スマホテンキーサーバー 起動！")
    print("=" * 50)
    print(f"  スマホのブラウザで開いてください：")
    print(f"")
    print(f"  👉  http://{local_ip}:{http_port}")
    print(f"")
    print(f"  ※ PCとスマホが同じWi-Fiに接続している必要があります")
    print(f"  Ctrl+C で終了")
    print("=" * 50)

    async with websockets.serve(handle_client, "0.0.0.0", ws_port):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nサーバーを終了しました。")
