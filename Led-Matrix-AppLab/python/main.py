import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from arduino.app_utils import Bridge
except ImportError:  # Local laptop preview fallback.
    Bridge = None


def load_local_env() -> None:
    candidates = [
        Path(os.getcwd()) / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path("/app/.env"),
        Path("/home/arduino/ArduinoApps/led-matrix-voice-lab/.env"),
    ]
    env_path = next((path for path in candidates if path.exists()), None)
    if env_path is None:
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    except OSError:
        pass


load_local_env()

PORT = int(os.getenv("MATRIX_APP_PORT", "5002"))
MAX_TEXT_LENGTH = 80
last_text = "HELLO ARDUINO"
last_bridge_error = ""
last_scroll_enabled = True
last_speed_ms = 150


def clean_matrix_text(value: str) -> str:
    text = " ".join(value.strip().split())
    text = re.sub(r"[^A-Za-z0-9 .,!?@#:+\\-_/]", "", text)
    return text[:MAX_TEXT_LENGTH].upper()


def clamp_speed(value: object) -> int:
    try:
        speed = int(value)
    except (TypeError, ValueError):
        speed = 150
    return max(90, min(320, speed))


def bridge_call(method: str, value: object) -> tuple[bool, str]:
    if Bridge is None:
        return False, "Bridge is available only when this runs in Arduino App Lab on Arduino Uno Q."
    try:
        result = Bridge.call(method, str(value))
        return True, str(result)
    except Exception as exc:  # App Lab Bridge raises ValueError for missing RPC methods.
        return False, str(exc)


def send_display_state(text: str, scroll_enabled: bool, speed_ms: int) -> tuple[bool, str]:
    if Bridge is None:
        return False, "Bridge is available only when this runs in Arduino App Lab on Arduino Uno Q."
    calls = [
        bridge_call("set_scroll", "1" if scroll_enabled else "0"),
        bridge_call("set_speed", speed_ms),
        bridge_call("display_text", text),
    ]
    sent = all(ok for ok, _message in calls)
    messages = [message for _ok, message in calls if message]
    return sent, "; ".join(messages)


def send_settings(scroll_enabled: bool, speed_ms: int) -> tuple[bool, str]:
    if Bridge is None:
        return False, "Bridge is available only when this runs in Arduino App Lab on Arduino Uno Q."
    calls = [
        bridge_call("set_scroll", "1" if scroll_enabled else "0"),
        bridge_call("set_speed", speed_ms),
    ]
    sent = all(ok for ok, _message in calls)
    messages = [message for _ok, message in calls if message]
    return sent, "; ".join(messages)


class MatrixHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self.send_text(HTML, "text/html; charset=utf-8")
            return
        if self.path == "/health":
            self.send_json(
                {
                    "ok": True,
                    "matrix": "Arduino Uno Q built-in 13x8",
                    "bridge_available": Bridge is not None,
                    "last_text": last_text,
                    "scroll_enabled": last_scroll_enabled,
                    "speed_ms": last_speed_ms,
                    "last_bridge_error": last_bridge_error,
                }
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in {"/display", "/settings"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Could not read request."})
            return

        global last_text, last_bridge_error, last_scroll_enabled, last_speed_ms
        scroll_enabled = bool(data.get("scroll_enabled", last_scroll_enabled))
        speed_ms = clamp_speed(data.get("speed_ms", last_speed_ms))
        last_scroll_enabled = scroll_enabled
        last_speed_ms = speed_ms

        if self.path == "/settings":
            sent, bridge_message = send_settings(scroll_enabled, speed_ms)
            last_bridge_error = "" if sent else bridge_message
            self.send_json(
                {
                    "ok": True,
                    "sent_to_matrix": sent,
                    "scroll_enabled": scroll_enabled,
                    "speed_ms": speed_ms,
                    "bridge_message": bridge_message,
                }
            )
            return

        raw_text = data.get("text", "")
        text = clean_matrix_text(raw_text)
        if not text:
            text = " "

        last_text = text
        sent, bridge_message = send_display_state(text, scroll_enabled, speed_ms)
        last_bridge_error = "" if sent else bridge_message
        self.send_json(
            {
                "ok": True,
                "text": text,
                "sent_to_matrix": sent,
                "scroll_enabled": scroll_enabled,
                "speed_ms": speed_ms,
                "bridge_message": bridge_message,
            }
        )

    def send_json(self, data: dict) -> None:
        self.send_text(json.dumps(data), "application/json; charset=utf-8")

    def send_text(self, text: str, content_type: str) -> None:
        encoded = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), MatrixHandler)
    print(f"Arduino Uno Q LED Matrix Voice Lab is running on http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Arduino Uno Q LED Matrix Voice Lab</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      background: #f6f8fb;
      color: #132026;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(19, 32, 38, 0.04) 1px, transparent 1px),
        linear-gradient(180deg, rgba(19, 32, 38, 0.04) 1px, transparent 1px),
        linear-gradient(135deg, #fbfdff 0%, #edf5f2 100%);
      background-size: 28px 28px, 28px 28px, auto;
    }
    main {
      width: min(1080px, calc(100vw - 28px));
      min-height: 100vh;
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(310px, 0.86fr) minmax(320px, 1fr);
      align-items: center;
      gap: 30px;
      padding: 24px 0;
    }
    .controls, .preview {
      display: grid;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: clamp(2rem, 4.2vw, 4.1rem);
      line-height: 1.03;
      letter-spacing: 0;
      color: #0e2a31;
    }
    .subtitle {
      margin: 0;
      font-size: 1.05rem;
      line-height: 1.45;
      color: #41545c;
    }
    label {
      font-weight: 800;
      color: #21333a;
    }
    textarea {
      width: 100%;
      min-height: 120px;
      resize: vertical;
      padding: 16px;
      border: 2px solid #bdcbd1;
      border-radius: 8px;
      font: inherit;
      font-size: 1.12rem;
      background: #ffffff;
      color: #132026;
      box-shadow: 0 10px 22px rgba(23, 38, 46, 0.07);
    }
    .buttons {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    button {
      border: 0;
      border-radius: 8px;
      min-height: 54px;
      padding: 12px 14px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      color: #ffffff;
      background: #006d77;
      box-shadow: 0 8px 16px rgba(0, 109, 119, 0.17);
    }
    button.warn { background: #a74935; }
    button:hover { filter: brightness(1.05); }
    button:disabled {
      opacity: 0.58;
      cursor: wait;
    }
    .status {
      min-height: 52px;
      padding: 12px 14px;
      border-left: 5px solid #2e86ab;
      background: #eef8fc;
      color: #23343c;
      border-radius: 6px;
      font-weight: 700;
      line-height: 1.35;
    }
    .matrix-shell {
      background: #172028;
      border: 8px solid #27323c;
      border-radius: 8px;
      padding: clamp(12px, 2.4vw, 22px);
      box-shadow: 0 24px 46px rgba(19, 32, 38, 0.22);
      overflow: hidden;
    }
    .matrix {
      display: grid;
      grid-template-columns: repeat(13, minmax(14px, 1fr));
      grid-template-rows: repeat(8, minmax(14px, 1fr));
      gap: clamp(5px, 1vw, 10px);
      aspect-ratio: 13 / 8;
    }
    .dot {
      border-radius: 50%;
      background: #26333e;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
    }
    .dot.on {
      background: #3cb7ff;
      box-shadow: 0 0 10px rgba(60, 183, 255, 0.95), 0 0 20px rgba(60, 183, 255, 0.38);
    }
    .readout {
      min-height: 58px;
      padding: 12px 14px;
      border: 2px solid #c6d3d8;
      background: #ffffff;
      border-radius: 8px;
      font-size: clamp(1.15rem, 3vw, 1.8rem);
      font-weight: 900;
      color: #0e2a31;
      overflow-wrap: anywhere;
    }
    .toggles {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      color: #41545c;
      font-weight: 700;
    }
    input[type="range"] {
      width: min(240px, 100%);
      accent-color: #006d77;
    }
    @media (max-width: 820px) {
      main {
        grid-template-columns: 1fr;
        align-content: start;
      }
      .buttons {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="controls">
      <h1>Arduino Uno Q LED Matrix Voice Lab</h1>
      <p class="subtitle">Say a word or type it. The preview matches the Arduino Uno Q onboard 13 x 8 blue LED matrix.</p>
      <label for="textInput">Word to display</label>
      <textarea id="textInput" maxlength="80">HELLO ARDUINO</textarea>
      <div class="buttons">
        <button id="talkButton" title="Use microphone">Talk</button>
        <button id="sendButton" title="Display typed word">Display</button>
        <button id="clearButton" class="warn" title="Clear matrix">Clear</button>
      </div>
      <div class="status" id="status">Ready. The browser preview works here; on Arduino Uno Q the text is sent through Bridge.</div>
    </section>

    <section class="preview">
      <div class="matrix-shell" aria-label="Arduino Uno Q 13 by 8 LED matrix preview">
        <div class="matrix" id="matrix"></div>
      </div>
      <div class="readout" id="readout">HELLO ARDUINO</div>
      <div class="toggles">
        <label><input type="checkbox" id="scrollToggle" checked> Scroll preview</label>
        <label for="speed">Speed</label>
        <input type="range" id="speed" min="90" max="320" value="150">
      </div>
    </section>
  </main>

  <script>
    const COLS = 13;
    const ROWS = 8;
    const matrix = document.getElementById("matrix");
    const textInput = document.getElementById("textInput");
    const readout = document.getElementById("readout");
    const statusBox = document.getElementById("status");
    const talkButton = document.getElementById("talkButton");
    const sendButton = document.getElementById("sendButton");
    const clearButton = document.getElementById("clearButton");
    const scrollToggle = document.getElementById("scrollToggle");
    const speed = document.getElementById("speed");
    const dots = [];
    let columns = [];
    let offset = 0;
    let timer = null;
    let settingsTimer = null;

    const FONT = {
      " ": ["00000","00000","00000","00000","00000","00000","00000"],
      "0": ["01110","10001","10011","10101","11001","10001","01110"],
      "1": ["00100","01100","00100","00100","00100","00100","01110"],
      "2": ["01110","10001","00001","00010","00100","01000","11111"],
      "3": ["11110","00001","00001","01110","00001","00001","11110"],
      "4": ["00010","00110","01010","10010","11111","00010","00010"],
      "5": ["11111","10000","11110","00001","00001","10001","01110"],
      "6": ["00110","01000","10000","11110","10001","10001","01110"],
      "7": ["11111","00001","00010","00100","01000","01000","01000"],
      "8": ["01110","10001","10001","01110","10001","10001","01110"],
      "9": ["01110","10001","10001","01111","00001","00010","11100"],
      "A": ["01110","10001","10001","11111","10001","10001","10001"],
      "B": ["11110","10001","10001","11110","10001","10001","11110"],
      "C": ["01111","10000","10000","10000","10000","10000","01111"],
      "D": ["11110","10001","10001","10001","10001","10001","11110"],
      "E": ["11111","10000","10000","11110","10000","10000","11111"],
      "F": ["11111","10000","10000","11110","10000","10000","10000"],
      "G": ["01111","10000","10000","10011","10001","10001","01111"],
      "H": ["10001","10001","10001","11111","10001","10001","10001"],
      "I": ["01110","00100","00100","00100","00100","00100","01110"],
      "J": ["00111","00010","00010","00010","00010","10010","01100"],
      "K": ["10001","10010","10100","11000","10100","10010","10001"],
      "L": ["10000","10000","10000","10000","10000","10000","11111"],
      "M": ["10001","11011","10101","10101","10001","10001","10001"],
      "N": ["10001","11001","10101","10011","10001","10001","10001"],
      "O": ["01110","10001","10001","10001","10001","10001","01110"],
      "P": ["11110","10001","10001","11110","10000","10000","10000"],
      "Q": ["01110","10001","10001","10001","10101","10010","01101"],
      "R": ["11110","10001","10001","11110","10100","10010","10001"],
      "S": ["01111","10000","10000","01110","00001","00001","11110"],
      "T": ["11111","00100","00100","00100","00100","00100","00100"],
      "U": ["10001","10001","10001","10001","10001","10001","01110"],
      "V": ["10001","10001","10001","10001","10001","01010","00100"],
      "W": ["10001","10001","10001","10101","10101","10101","01010"],
      "X": ["10001","10001","01010","00100","01010","10001","10001"],
      "Y": ["10001","10001","01010","00100","00100","00100","00100"],
      "Z": ["11111","00001","00010","00100","01000","10000","11111"],
      ".": ["00000","00000","00000","00000","00000","01100","01100"],
      ",": ["00000","00000","00000","00000","01100","01100","01000"],
      "!": ["00100","00100","00100","00100","00100","00000","00100"],
      "?": ["01110","10001","00001","00010","00100","00000","00100"],
      ":": ["00000","01100","01100","00000","01100","01100","00000"],
      "-": ["00000","00000","00000","11111","00000","00000","00000"],
      "_": ["00000","00000","00000","00000","00000","00000","11111"],
      "/": ["00001","00010","00010","00100","01000","01000","10000"],
      "@": ["01110","10001","10111","10101","10111","10000","01110"],
      "#": ["01010","01010","11111","01010","11111","01010","01010"],
      "+": ["00000","00100","00100","11111","00100","00100","00000"]
    };

    for (let i = 0; i < ROWS * COLS; i += 1) {
      const dot = document.createElement("span");
      dot.className = "dot";
      matrix.appendChild(dot);
      dots.push(dot);
    }

    function cleanText(value) {
      return value.trim().replace(/\s+/g, " ").replace(/[^A-Za-z0-9 .,!?@#:+\-_/]/g, "").slice(0, 80).toUpperCase();
    }

    function buildColumns(text) {
      const result = Array(COLS).fill(0);
      for (const char of text || " ") {
        const glyph = FONT[char] || FONT["?"];
        for (let x = 0; x < 5; x += 1) {
          let column = 0;
          for (let y = 0; y < 7; y += 1) {
            if (glyph[y][x] === "1") column |= 1 << (y + 1);
          }
          result.push(column);
        }
        result.push(0);
      }
      return result.concat(Array(COLS).fill(0));
    }

    function draw() {
      for (let x = 0; x < COLS; x += 1) {
        const source = columns[(offset + x) % columns.length] || 0;
        for (let y = 0; y < ROWS; y += 1) {
          dots[y * COLS + x].classList.toggle("on", Boolean(source & (1 << y)));
        }
      }
    }

    function refreshPreview(reset = false) {
      const text = cleanText(textInput.value) || " ";
      readout.textContent = text.trim() || " ";
      columns = buildColumns(text);
      if (reset) offset = 0;
      draw();
    }

    function startScroll() {
      if (timer) window.clearInterval(timer);
      timer = window.setInterval(() => {
        if (scrollToggle.checked && columns.length) {
          offset = (offset + 1) % columns.length;
          draw();
        }
      }, Number(speed.value));
    }

    function currentSettings() {
      return {
        scroll_enabled: scrollToggle.checked,
        speed_ms: Number(speed.value)
      };
    }

    function scheduleHardwareSettingsSync() {
      if (settingsTimer) window.clearTimeout(settingsTimer);
      settingsTimer = window.setTimeout(syncHardwareSettings, 220);
    }

    async function syncHardwareSettings() {
      const settings = currentSettings();
      try {
        const response = await fetch("/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settings)
        });
        const data = await response.json();
        statusBox.textContent = data.sent_to_matrix
          ? `Hardware updated: scroll ${settings.scroll_enabled ? "on" : "off"}, speed ${settings.speed_ms} ms.`
          : `Preview updated. ${data.bridge_message}`;
      } catch (error) {
        statusBox.textContent = `Settings connection problem: ${error}`;
      }
    }

    async function sendDisplayText(text) {
      sendButton.disabled = true;
      talkButton.disabled = true;
      statusBox.textContent = "Sending to Arduino Uno Q matrix...";
      try {
        const response = await fetch("/display", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, ...currentSettings() })
        });
        const data = await response.json();
        textInput.value = data.text;
        refreshPreview(true);
        statusBox.textContent = data.sent_to_matrix
          ? `Displaying on Arduino Uno Q: ${data.text}`
          : `Previewing: ${data.text}. ${data.bridge_message}`;
      } catch (error) {
        statusBox.textContent = `App connection problem: ${error}`;
      } finally {
        sendButton.disabled = false;
        talkButton.disabled = false;
      }
    }

    function startListening() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        statusBox.textContent = "Speech recognition is not available here. Type the word and press Display.";
        return;
      }
      const recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      statusBox.textContent = "Listening...";
      recognition.onresult = (event) => {
        const spoken = event.results[0][0].transcript;
        textInput.value = spoken;
        sendDisplayText(spoken);
      };
      recognition.onerror = (event) => {
        statusBox.textContent = `Listening error: ${event.error}`;
      };
      recognition.start();
    }

    textInput.addEventListener("input", () => refreshPreview(true));
    sendButton.addEventListener("click", () => sendDisplayText(textInput.value));
    talkButton.addEventListener("click", startListening);
    clearButton.addEventListener("click", () => sendDisplayText(" "));
    speed.addEventListener("input", () => {
      startScroll();
      scheduleHardwareSettingsSync();
    });
    scrollToggle.addEventListener("change", () => {
      draw();
      scheduleHardwareSettingsSync();
    });
    refreshPreview(true);
    startScroll();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
