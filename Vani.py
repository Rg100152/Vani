"""
VANI - Single-File Text-to-Voice API & Web Application
Made by Raj Gautam

A self-contained Flask application that converts text to natural speech using
the official OpenAI Text-to-Speech API, with a premium web dashboard and REST API.

Requirements:
    pip install flask openai

Environment Variables:
    OPENAI_API_KEY      - Your OpenAI API key (required)
    VANI_API_KEY        - Optional bearer token to protect VANI's endpoints
    VANI_HOST           - Host to bind (default: 127.0.0.1)
    VANI_PORT           - Port to bind (default: 5060)
    VANI_OUTPUT_DIR     - Directory for generated audio (default: ./vani_output)
    VANI_MODEL          - TTS model (default: gpt-4o-mini-tts)
    VANI_VOICE          - Default voice (default: coral)
    VANI_RATE_LIMIT     - Requests per minute per IP (default: 10)

Run:
    python vani.py
"""

import os
import json
import uuid
import hmac
import time
import threading
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from collections import defaultdict
from typing import Optional, Tuple, Dict, Any

from flask import Flask, request, jsonify, render_template_string, send_file
from openai import OpenAI, OpenAIError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
VANI_API_KEY = os.environ.get("VANI_API_KEY")
HOST = os.environ.get("VANI_HOST", "127.0.0.1")
PORT = int(os.environ.get("VANI_PORT", "5060"))
OUTPUT_DIR = Path(os.environ.get("VANI_OUTPUT_DIR", "./vani_output")).resolve()
DEFAULT_MODEL = os.environ.get("VANI_MODEL", "gpt-4o-mini-tts")
DEFAULT_VOICE = os.environ.get("VANI_VOICE", "coral")
RATE_LIMIT_PER_MINUTE = int(os.environ.get("VANI_RATE_LIMIT", "10"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_FILE = OUTPUT_DIR / "_metadata.json"

# Verified against OpenAI Speech API docs [citation:18]
SUPPORTED_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]
SUPPORTED_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "onyx", "nova", "sage", "shimmer", "verse", "marin", "cedar",
]
SUPPORTED_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
MAX_INPUT_LENGTH = 4096  # OpenAI hard limit [citation:18]

_rate_buckets: Dict[str, list] = defaultdict(list)
_rate_lock = threading.Lock()
_metadata_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit(identifier: str) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[identifier]
        bucket[:] = [t for t in bucket if now - t < 60.0]
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            return False
        bucket.append(now)
        return True

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if VANI_API_KEY is None:
            return f(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401
        token = auth[7:]
        if not hmac.compare_digest(token.encode(), VANI_API_KEY.encode()):
            return jsonify({"error": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

def get_openai_client() -> Optional[OpenAI]:
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def load_metadata() -> Dict[str, Any]:
    if not METADATA_FILE.exists():
        return {"audios": []}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and "audios" in data else {"audios": []}
    except (json.JSONDecodeError, OSError):
        return {"audios": []}

def save_metadata(data: Dict[str, Any]) -> None:
    tmp = METADATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(METADATA_FILE)

def add_audio_record(record: Dict[str, Any]) -> None:
    with _metadata_lock:
        data = load_metadata()
        data["audios"].insert(0, record)
        save_metadata(data)

def get_audio_record(audio_id: str) -> Optional[Dict[str, Any]]:
    for a in load_metadata().get("audios", []):
        if a.get("id") == audio_id:
            return a
    return None

def remove_audio_record(audio_id: str) -> Optional[Dict[str, Any]]:
    with _metadata_lock:
        data = load_metadata()
        for i, a in enumerate(data.get("audios", [])):
            if a.get("id") == audio_id:
                removed = data["audios"].pop(i)
                save_metadata(data)
                return removed
        return None

# ---------------------------------------------------------------------------
# File safety
# ---------------------------------------------------------------------------

def safe_filename(audio_id: str, ext: str) -> str:
    if not all(c in "0123456789abcdef-" for c in audio_id):
        raise ValueError("Invalid audio ID format")
    if ext not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported audio format")
    return f"{audio_id}.{ext}"

def resolve_audio_path(audio_id: str, ext: str) -> Path:
    path = (OUTPUT_DIR / safe_filename(audio_id, ext)).resolve()
    if not str(path).startswith(str(OUTPUT_DIR)):
        raise ValueError("Path traversal detected")
    return path

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_tts_request(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    text = data.get("input") or data.get("text")
    if not text or not isinstance(text, str):
        return {}, "Field 'input' (or 'text') is required and must be a string."
    text = text.strip()
    if len(text) < 1:
        return {}, "Input text cannot be empty."
    if len(text) > MAX_INPUT_LENGTH:
        return {}, f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters."

    model = data.get("model", DEFAULT_MODEL)
    if model not in SUPPORTED_MODELS:
        return {}, f"Unsupported model '{model}'. Supported: {SUPPORTED_MODELS}"

    voice = data.get("voice", DEFAULT_VOICE)
    if voice not in SUPPORTED_VOICES:
        return {}, f"Unsupported voice '{voice}'. Supported: {SUPPORTED_VOICES}"

    response_format = data.get("response_format", "mp3")
    if response_format not in SUPPORTED_FORMATS:
        return {}, f"Unsupported response_format '{response_format}'. Supported: {SUPPORTED_FORMATS}"

    speed = data.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or speed < 0.25 or speed > 4.0:
        return {}, "Field 'speed' must be a number between 0.25 and 4.0."

    instructions = data.get("instructions")
    if instructions is not None:
        if not isinstance(instructions, str):
            return {}, "Field 'instructions' must be a string."
        if model in ("tts-1", "tts-1-hd"):
            return {}, "Field 'instructions' is only supported by gpt-4o-mini-tts."

    return {
        "input": text,
        "model": model,
        "voice": voice,
        "response_format": response_format,
        "speed": float(speed),
        "instructions": instructions,
    }, None

# ---------------------------------------------------------------------------
# Speech generation
# ---------------------------------------------------------------------------

def generate_speech(params: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[int]]:
    client = get_openai_client()
    if client is None:
        return None, "OPENAI_API_KEY is not configured on the server.", 503

    try:
        kwargs = {
            "model": params["model"],
            "voice": params["voice"],
            "input": params["input"],
            "response_format": params["response_format"],
            "speed": params["speed"],
        }
        if params["instructions"]:
            kwargs["instructions"] = params["instructions"]

        response = client.audio.speech.create(**kwargs)

        # The OpenAI SDK returns a binary response object; read the bytes
        audio_bytes = response.content if hasattr(response, "content") else response.read()

    except OpenAIError as e:
        err = str(e).lower()
        if "invalid api key" in err or "incorrect api key" in err:
            return None, "OpenAI API key is invalid.", 401
        if "quota" in err or "insufficient" in err:
            return None, "OpenAI quota exceeded. Check your billing.", 402
        if "rate limit" in err:
            return None, "OpenAI rate limit reached. Try again later.", 429
        return None, f"OpenAI API error: {str(e)}", 502
    except Exception as e:
        return None, f"Unexpected error: {str(e)}", 500

    if not audio_bytes:
        return None, "OpenAI returned an empty audio response.", 502

    audio_id = str(uuid.uuid4())
    ext = params["response_format"]
    filename = safe_filename(audio_id, ext)

    try:
        path = resolve_audio_path(audio_id, ext)
        with open(path, "wb") as f:
            f.write(audio_bytes)
    except (OSError, ValueError) as e:
        return None, f"Failed to save audio: {str(e)}", 500

    record = {
        "id": audio_id,
        "filename": filename,
        "model": params["model"],
        "voice": params["voice"],
        "input": params["input"],
        "response_format": ext,
        "speed": params["speed"],
        "instructions": params["instructions"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "url": f"/v1/audio/{audio_id}",
        "size_bytes": len(audio_bytes),
    }
    add_audio_record(record)
    return record, None, 201

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "VANI",
        "author": "Raj Gautam",
        "version": "1.0.0",
        "openai_configured": OPENAI_API_KEY is not None,
        "auth_required": VANI_API_KEY is not None,
        "default_model": DEFAULT_MODEL,
        "default_voice": DEFAULT_VOICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

@app.route("/v1/models")
@require_auth
def list_models():
    return jsonify({
        "object": "list",
        "data": [{"id": m, "object": "model", "owned_by": "openai"} for m in SUPPORTED_MODELS],
        "voices": SUPPORTED_VOICES,
        "formats": SUPPORTED_FORMATS,
    })

@app.route("/v1/audio/speech", methods=["POST"])
@require_auth
def create_speech():
    client_ip = request.remote_addr or "unknown"
    if not check_rate_limit(client_ip):
        return jsonify({"error": "Rate limit exceeded", "status": 429}), 429

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON in request body"}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    params, err = validate_tts_request(data)
    if err:
        return jsonify({"error": err}), 400

    record, err, status = generate_speech(params)
    if err:
        return jsonify({"error": err}), status

    return jsonify({
        "id": record["id"],
        "url": record["url"],
        "model": record["model"],
        "voice": record["voice"],
        "response_format": record["response_format"],
        "input_preview": record["input"][:120],
        "size_bytes": record["size_bytes"],
        "created_at": record["created_at"],
    }), 201

@app.route("/v1/audio", methods=["GET"])
@require_auth
def list_audio():
    data = load_metadata()
    return jsonify({
        "object": "list",
        "total": len(data.get("audios", [])),
        "data": data.get("audios", []),
    })

@app.route("/v1/audio/<audio_id>", methods=["GET"])
@require_auth
def get_audio(audio_id: str):
    record = get_audio_record(audio_id)
    if not record:
        return jsonify({"error": "Audio not found"}), 404
    try:
        path = resolve_audio_path(audio_id, record["response_format"])
    except ValueError:
        return jsonify({"error": "Invalid audio identifier"}), 400
    if not path.exists():
        return jsonify({"error": "Audio file missing from storage"}), 404
    mime = {
        "mp3": "audio/mpeg", "opus": "audio/opus", "aac": "audio/aac",
        "flac": "audio/flac", "wav": "audio/wav", "pcm": "audio/pcm",
    }.get(record["response_format"], "application/octet-stream")
    return send_file(path, mimetype=mime, as_attachment=False,
                     download_name=record["filename"])

@app.route("/v1/audio/<audio_id>", methods=["DELETE"])
@require_auth
def delete_audio(audio_id: str):
    record = remove_audio_record(audio_id)
    if not record:
        return jsonify({"error": "Audio not found"}), 404
    try:
        path = resolve_audio_path(audio_id, record["response_format"])
        if path.exists():
            path.unlink()
    except (OSError, ValueError):
        pass
    return jsonify({"deleted": True, "id": audio_id}), 200

@app.route("/v1/docs")
def docs():
    base = request.host_url.rstrip("/")
    return jsonify({
        "name": "VANI Text-to-Voice API",
        "author": "Raj Gautam",
        "version": "1.0.0",
        "base_url": base,
        "authentication": {
            "type": "Bearer token" if VANI_API_KEY else "none (local mode)",
            "header": "Authorization: Bearer <VANI_API_KEY>",
        },
        "endpoints": [
            {"method": "GET", "path": "/health", "desc": "Health check"},
            {"method": "GET", "path": "/v1/models", "desc": "List models, voices, formats"},
            {"method": "POST", "path": "/v1/audio/speech", "desc": "Generate speech"},
            {"method": "GET", "path": "/v1/audio", "desc": "List generated audio"},
            {"method": "GET", "path": "/v1/audio/<id>", "desc": "Retrieve audio file"},
            {"method": "DELETE", "path": "/v1/audio/<id>", "desc": "Delete audio"},
        ],
        "request_body": {
            "input": "string (required, max 4096 chars)",
            "model": f"string (default: {DEFAULT_MODEL})",
            "voice": f"string (default: {DEFAULT_VOICE})",
            "response_format": "string (default: mp3)",
            "speed": "number 0.25–4.0 (default: 1.0)",
            "instructions": "string (optional, gpt-4o-mini-tts only)",
        },
    })

# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VANI — Text to Voice by Raj Gautam</title>
<style>
:root {
  --bg: #0a0a12;
  --glass: rgba(30, 30, 55, 0.45);
  --glass-border: rgba(140, 120, 255, 0.18);
  --purple: #8b5cf6;
  --cyan: #22d3ee;
  --text: #e8e6f0;
  --text-dim: #9490a8;
  --danger: #f87171;
  --success: #34d399;
  --radius: 16px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --mono: 'SF Mono', 'Fira Code', Consolas, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font); background: var(--bg); color: var(--text);
  min-height: 100vh; line-height: 1.6; -webkit-font-smoothing: antialiased;
}
body::before {
  content: ''; position: fixed; inset: 0; z-index: -1;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(139,92,246,0.12), transparent),
    radial-gradient(ellipse 60% 50% at 80% 90%, rgba(34,211,238,0.08), transparent);
}
.app { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 0 32px; flex-wrap: wrap; gap: 16px;
}
.brand { display: flex; align-items: center; gap: 14px; }
.brand-mark {
  width: 44px; height: 44px; border-radius: 14px;
  background: linear-gradient(135deg, var(--purple), var(--cyan));
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 800; color: #0a0a12;
  box-shadow: 0 0 24px rgba(139,92,246,0.35);
}
.brand h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; }
.brand h1 span { color: var(--purple); }
.brand .author { font-size: 0.72rem; color: var(--text-dim); letter-spacing: 1px; text-transform: uppercase; }
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
  padding: 4px 12px; border-radius: 20px;
  background: var(--glass); border: 1px solid var(--glass-border);
  color: var(--text-dim);
}
.badge.online { color: var(--success); border-color: rgba(52,211,153,0.3); }
.badge.offline { color: var(--danger); border-color: rgba(248,113,113,0.3); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
.stat-card { background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius); padding: 20px 22px; }
.stat-card .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-dim); font-weight: 600; }
.stat-card .value { font-size: 1.8rem; font-weight: 700; margin-top: 6px; letter-spacing: -1px; }
.stat-card .value.purple { color: var(--purple); }
.stat-card .value.cyan { color: var(--cyan); }
.tabs { display: flex; gap: 4px; margin-bottom: 28px; border-bottom: 1px solid var(--glass-border); overflow-x: auto; }
.tab-btn {
  background: none; border: none; color: var(--text-dim);
  padding: 12px 22px; font-size: 0.9rem; font-weight: 600;
  cursor: pointer; border-bottom: 2px solid transparent;
  white-space: nowrap; transition: all 0.2s; font-family: var(--font);
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--purple); border-bottom-color: var(--purple); }
.panel { display: none; animation: fadeIn 0.25s ease; }
.panel.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.card { background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius); padding: 28px; margin-bottom: 24px; }
.card h2 { font-size: 1.15rem; font-weight: 700; margin-bottom: 20px; }
.card h2 .accent { color: var(--cyan); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.form-grid .full { grid-column: 1 / -1; }
@media (max-width: 640px) { .form-grid { grid-template-columns: 1fr; } }
label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--text-dim); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.4px; }
textarea, input, select {
  width: 100%; padding: 12px 14px; border-radius: 10px;
  background: rgba(10,10,20,0.6); border: 1px solid var(--glass-border);
  color: var(--text); font-family: var(--font); font-size: 0.92rem;
  transition: border-color 0.2s; outline: none;
}
textarea:focus, input:focus, select:focus { border-color: var(--purple); box-shadow: 0 0 0 3px rgba(139,92,246,0.15); }
textarea { resize: vertical; min-height: 120px; font-family: var(--mono); font-size: 0.85rem; }
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px 24px; border-radius: 10px; border: none;
  font-family: var(--font); font-weight: 600; font-size: 0.9rem;
  cursor: pointer; transition: all 0.2s;
}
.btn-primary { background: linear-gradient(135deg, var(--purple), #7c3aed); color: #fff; box-shadow: 0 4px 20px rgba(139,92,246,0.3); }
.btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 28px rgba(139,92,246,0.45); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; border: 1px solid var(--glass-border); color: var(--text-dim); }
.btn-ghost:hover { border-color: var(--purple); color: var(--text); }
.btn-danger { background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.3); color: var(--danger); }
.btn-sm { padding: 6px 14px; font-size: 0.8rem; border-radius: 8px; }
.spinner { width: 20px; height: 20px; border: 2px solid rgba(255,255,255,0.2); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
.audio-list { display: flex; flex-direction: column; gap: 12px; }
.audio-item {
  background: rgba(10,10,20,0.5); border: 1px solid var(--glass-border);
  border-radius: 12px; padding: 16px 18px;
}
.audio-item .meta { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.audio-item .meta .voice { font-size: 0.78rem; color: var(--cyan); font-weight: 600; }
.audio-item .meta .date { font-size: 0.72rem; color: var(--text-dim); }
.audio-item .preview { font-size: 0.82rem; color: var(--text-dim); line-height: 1.4; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.audio-item .actions { display: flex; gap: 8px; }
audio { width: 100%; margin-top: 10px; filter: invert(0.9) hue-rotate(180deg); }
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-dim); }
.code-block {
  background: rgba(5,5,15,0.8); border: 1px solid var(--glass-border);
  border-radius: 12px; padding: 16px; font-family: var(--mono);
  font-size: 0.82rem; overflow-x: auto; line-height: 1.5;
  white-space: pre-wrap; word-break: break-word; color: #c9c4e0;
}
.status-badge { display: inline-block; padding: 4px 12px; border-radius: 8px; font-size: 0.78rem; font-weight: 700; font-family: var(--mono); }
.status-200, .status-201 { background: rgba(52,211,153,0.15); color: var(--success); }
.status-400, .status-401, .status-404, .status-429 { background: rgba(248,113,113,0.15); color: var(--danger); }
.status-500, .status-502, .status-503 { background: rgba(251,191,36,0.15); color: #fbbf24; }
.docs h3 { font-size: 1rem; margin: 24px 0 10px; color: var(--cyan); }
.docs h3:first-child { margin-top: 0; }
.docs p, .docs li { font-size: 0.88rem; color: var(--text-dim); line-height: 1.7; }
.docs ul { padding-left: 20px; margin: 8px 0; }
.docs code { font-family: var(--mono); background: rgba(139,92,246,0.12); padding: 2px 7px; border-radius: 5px; font-size: 0.82rem; color: var(--purple); }
.docs pre { background: rgba(5,5,15,0.8); border: 1px solid var(--glass-border); border-radius: 10px; padding: 16px; overflow-x: auto; margin: 10px 0; font-family: var(--mono); font-size: 0.8rem; color: #c9c4e0; line-height: 1.5; }
.toast {
  position: fixed; bottom: 28px; right: 28px; z-index: 1000;
  padding: 14px 22px; border-radius: 12px; font-size: 0.88rem; font-weight: 600;
  background: var(--glass); backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  transform: translateY(80px); opacity: 0; transition: all 0.3s ease;
  pointer-events: none; max-width: 360px;
}
.toast.show { transform: translateY(0); opacity: 1; }
.toast.success { border-color: rgba(52,211,153,0.4); color: var(--success); }
.toast.error { border-color: rgba(248,113,113,0.4); color: var(--danger); }
.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 14px 0; border-bottom: 1px solid rgba(140,120,255,0.08); flex-wrap: wrap; gap: 8px; }
.setting-row:last-child { border-bottom: none; }
.setting-row .k { font-size: 0.88rem; color: var(--text-dim); }
.setting-row .v { font-size: 0.88rem; font-weight: 600; font-family: var(--mono); }
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.25); border-radius: 4px; }
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="brand">
      <div class="brand-mark">V</div>
      <div>
        <h1>VANI<span>.</span></h1>
        <div class="author">Text to Voice &middot; by Raj Gautam</div>
      </div>
    </div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <span class="badge" id="auth-badge">checking...</span>
      <span class="badge" id="status-badge"><span class="dot"></span> connecting...</span>
    </div>
  </header>

  <div class="stats">
    <div class="stat-card">
      <div class="label">Total Audio</div>
      <div class="value purple" id="stat-total">—</div>
    </div>
    <div class="stat-card">
      <div class="label">Default Model</div>
      <div class="value cyan" id="stat-model" style="font-size:1.1rem;margin-top:10px;">—</div>
    </div>
    <div class="stat-card">
      <div class="label">API Status</div>
      <div class="value" id="stat-api" style="font-size:1rem;margin-top:10px;">—</div>
    </div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" data-tab="generate">Generate</button>
    <button class="tab-btn" data-tab="library">Library</button>
    <button class="tab-btn" data-tab="playground">API Playground</button>
    <button class="tab-btn" data-tab="docs">Documentation</button>
    <button class="tab-btn" data-tab="settings">Settings</button>
  </div>

  <div class="panel active" id="panel-generate">
    <div class="card">
      <h2>Generate <span class="accent">Speech</span></h2>
      <div class="form-grid">
        <div class="full">
          <label for="gen-text">Text to Speak</label>
          <textarea id="gen-text" placeholder="Enter the text you want VANI to speak..." maxlength="4096"></textarea>
        </div>
        <div>
          <label for="gen-model">Model</label>
          <select id="gen-model"></select>
        </div>
        <div>
          <label for="gen-voice">Voice</label>
          <select id="gen-voice"></select>
        </div>
        <div>
          <label for="gen-format">Format</label>
          <select id="gen-format"></select>
        </div>
        <div>
          <label for="gen-speed">Speed (0.25–4.0)</label>
          <input type="number" id="gen-speed" value="1.0" min="0.25" max="4.0" step="0.05">
        </div>
        <div class="full">
          <label for="gen-instructions">Instructions (optional, gpt-4o-mini-tts only)</label>
          <input type="text" id="gen-instructions" placeholder="e.g., Speak in a cheerful, energetic tone">
        </div>
        <div class="full" style="display:flex;gap:12px;align-items:center;margin-top:8px;">
          <button class="btn btn-primary" id="gen-btn" onclick="generateSpeech()">Generate Speech</button>
          <span id="gen-status" style="font-size:0.85rem;color:var(--text-dim);"></span>
        </div>
      </div>
      <div id="gen-player" style="display:none;margin-top:20px;">
        <audio id="gen-audio" controls></audio>
      </div>
    </div>
  </div>

  <div class="panel" id="panel-library">
    <div class="card">
      <h2>Audio <span class="accent">Library</span></h2>
      <div id="library-list" class="audio-list"></div>
      <div class="empty-state" id="library-empty" style="display:none;">
        <div style="font-size:3rem;margin-bottom:12px;opacity:0.5;">🔊</div>
        <p>No audio generated yet. Start creating!</p>
      </div>
    </div>
  </div>

  <div class="panel" id="panel-playground">
    <div class="card">
      <h2>API <span class="accent">Playground</span></h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;" id="pg-grid">
        <div>
          <label>Endpoint</label>
          <div class="code-block" style="margin-bottom:14px;padding:10px 14px;">POST /v1/audio/speech</div>
          <label>Request Body (JSON)</label>
          <textarea id="pg-body" style="min-height:220px;" spellcheck="false">{
  "input": "Welcome to VANI, your text to voice platform by Raj Gautam.",
  "model": "gpt-4o-mini-tts",
  "voice": "coral",
  "response_format": "mp3",
  "instructions": "Speak in a warm, professional tone."
}</textarea>
          <div style="margin-top:14px;">
            <button class="btn btn-primary" onclick="playgroundSend()">Send Request</button>
          </div>
        </div>
        <div>
          <label>Response</label>
          <div id="pg-status" style="margin-bottom:10px;min-height:28px;"></div>
          <div class="code-block" id="pg-response" style="min-height:220px;">// Response will appear here</div>
        </div>
      </div>
    </div>
  </div>

  <div class="panel" id="panel-docs">
    <div class="card docs">
      <h2>Documentation</h2>
      <h3>Installation</h3>
      <pre>pip install flask openai
export OPENAI_API_KEY="sk-..."
python vani.py</pre>
      <h3>Authentication</h3>
      <p>Set <code>VANI_API_KEY</code> to protect endpoints. Include <code>Authorization: Bearer YOUR_KEY</code> in requests.</p>
      <h3>Generate Speech</h3>
      <pre>curl -X POST http://127.0.0.1:5060/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_VANI_KEY" \
  -d '{"input":"Hello world","model":"gpt-4o-mini-tts","voice":"coral"}'</pre>
      <h3>List Audio</h3>
      <pre>curl http://127.0.0.1:5060/v1/audio \
  -H "Authorization: Bearer YOUR_VANI_KEY"</pre>
      <h3>Retrieve / Delete</h3>
      <pre>curl http://127.0.0.1:5060/v1/audio/AUDIO_ID -H "Authorization: Bearer KEY" --output out.mp3
curl -X DELETE http://127.0.0.1:5060/v1/audio/AUDIO_ID -H "Authorization: Bearer KEY"</pre>
      <h3>Supported Voices</h3>
      <p><code>alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar</code></p>
      <h3>Error Codes</h3>
      <ul>
        <li><code>400</code> — Validation error</li>
        <li><code>401</code> — Invalid/missing API key</li>
        <li><code>402</code> — OpenAI quota exceeded</li>
        <li><code>404</code> — Audio not found</li>
        <li><code>429</code> — Rate limit exceeded</li>
        <li><code>502</code> — OpenAI API error</li>
        <li><code>503</code> — OpenAI not configured</li>
      </ul>
    </div>
  </div>

  <div class="panel" id="panel-settings">
    <div class="card">
      <h2>Settings</h2>
      <div class="setting-row"><span class="k">OpenAI API Key</span><span class="v" id="set-openai">—</span></div>
      <div class="setting-row"><span class="k">VANI Auth</span><span class="v" id="set-auth">—</span></div>
      <div class="setting-row"><span class="k">Default Model</span><span class="v" id="set-model">—</span></div>
      <div class="setting-row"><span class="k">Default Voice</span><span class="v" id="set-voice">—</span></div>
      <div class="setting-row"><span class="k">Output Directory</span><span class="v" id="set-output" style="font-size:0.8rem;">—</span></div>
      <div class="setting-row"><span class="k">Author</span><span class="v">Raj Gautam</span></div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const state = { health: null, models: [], audios: [], authToken: null };
function $(id) { return document.getElementById(id); }
function toast(msg, type) {
  type = type || 'info';
  const el = $('toast');
  el.textContent = msg; el.className = 'toast ' + type;
  void el.offsetWidth; el.classList.add('show');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('show'), 3500);
}
function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
async function apiFetch(url, opts) {
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (state.authToken) headers['Authorization'] = 'Bearer ' + state.authToken;
  return fetch(url, Object.assign({}, opts, { headers }));
}
async function loadHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    state.health = data;
    const badge = $('status-badge');
    if (data.openai_configured) { badge.className = 'badge online'; badge.innerHTML = '<span class="dot"></span> API Ready'; }
    else { badge.className = 'badge offline'; badge.innerHTML = '<span class="dot"></span> No OpenAI Key'; }
    $('auth-badge').textContent = data.auth_required ? '🔒 Protected' : '🔓 Local Mode';
    $('stat-model').textContent = data.default_model || '—';
    $('stat-api').textContent = data.openai_configured ? '✅ Connected' : '❌ Not configured';
    $('set-openai').textContent = data.openai_configured ? '✅ Configured' : '❌ Missing';
    $('set-auth').textContent = data.auth_required ? '🔒 Enabled' : '🔓 Disabled';
    $('set-model').textContent = data.default_model || '—';
    $('set-voice').textContent = data.default_voice || '—';
    $('set-output').textContent = window.location.host;
    await loadModels();
    await loadAudios();
  } catch (e) {
    $('status-badge').className = 'badge offline';
    $('status-badge').innerHTML = '<span class="dot"></span> Offline';
  }
}
async function loadModels() {
  try {
    const res = await apiFetch('/v1/models');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    state.models = data.data || [];
    const voices = data.voices || [];
    const formats = data.formats || [];
    fill('gen-model', state.models.map(m => m.id), state.health ? state.health.default_model : 'gpt-4o-mini-tts');
    fill('gen-voice', voices, state.health ? state.health.default_voice : 'coral');
    fill('gen-format', formats, 'mp3');
  } catch (e) { /* auth required, silently skip */ }
}
function fill(id, options, selected) {
  const sel = $(id); sel.innerHTML = '';
  options.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o; opt.textContent = o;
    if (o === selected) opt.selected = true;
    sel.appendChild(opt);
  });
}
async function generateSpeech() {
  const text = $('gen-text').value.trim();
  if (!text) { toast('Please enter text', 'error'); return; }
  const btn = $('gen-btn'); const status = $('gen-status');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating...';
  status.textContent = 'Calling OpenAI...';
  const body = {
    input: text, model: $('gen-model').value, voice: $('gen-voice').value,
    response_format: $('gen-format').value, speed: parseFloat($('gen-speed').value) || 1.0,
  };
  const instr = $('gen-instructions').value.trim();
  if (instr && $('gen-model').value === 'gpt-4o-mini-tts') body.instructions = instr;
  try {
    const res = await apiFetch('/v1/audio/speech', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'HTTP ' + res.status);
    status.textContent = '✅ Audio generated';
    const player = $('gen-player'); const audioEl = $('gen-audio');
    audioEl.src = data.url + '?_=' + Date.now();
    player.style.display = 'block';
    audioEl.play().catch(() => {});
    toast('Speech generated successfully', 'success');
    await loadAudios();
  } catch (e) {
    status.textContent = '❌ ' + e.message;
    toast(e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Generate Speech';
  }
}
async function loadAudios() {
  try {
    const res = await apiFetch('/v1/audio');
    if (!res.ok) return;
    const data = await res.json();
    state.audios = data.data || [];
    $('stat-total').textContent = state.audios.length;
    renderLibrary();
  } catch (e) { /* ignore */ }
}
function renderLibrary() {
  const list = $('library-list'); const empty = $('library-empty');
  if (state.audios.length === 0) {
    list.innerHTML = ''; empty.style.display = 'block'; return;
  }
  empty.style.display = 'none';
  list.innerHTML = state.audios.map(a => {
    const date = a.created_at ? new Date(a.created_at).toLocaleString() : '—';
    const preview = a.input ? a.input.slice(0, 120) : '';
    return '<div class="audio-item">' +
      '<div class="meta"><span class="voice">' + escapeHtml(a.voice) + ' &middot; ' + escapeHtml(a.model) + '</span><span class="date">' + date + '</span></div>' +
      '<div class="preview">' + escapeHtml(preview) + '</div>' +
      '<audio controls preload="none" src="' + escapeHtml(a.url) + '"></audio>' +
      '<div class="actions" style="margin-top:10px;">' +
        '<a class="btn btn-ghost btn-sm" href="' + escapeHtml(a.url) + '" download>Download</a>' +
        '<button class="btn btn-danger btn-sm" onclick="deleteAudio(\'' + a.id + '\')">Delete</button>' +
      '</div></div>';
  }).join('');
}
async function deleteAudio(id) {
  if (!confirm('Delete this audio permanently?')) return;
  try {
    const res = await apiFetch('/v1/audio/' + id, { method: 'DELETE' });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || 'HTTP ' + res.status); }
    toast('Audio deleted', 'success');
    await loadAudios();
  } catch (e) { toast(e.message, 'error'); }
}
async function playgroundSend() {
  const statusEl = $('pg-status'); const respEl = $('pg-response');
  let body;
  try { body = JSON.parse($('pg-body').value); }
  catch (e) { statusEl.innerHTML = '<span class="status-badge status-400">Invalid JSON</span>'; respEl.textContent = e.message; return; }
  statusEl.innerHTML = '<span class="spinner"></span> Sending...';
  respEl.textContent = 'Waiting...';
  try {
    const res = await apiFetch('/v1/audio/speech', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    const text = await res.text();
    let json; try { json = JSON.parse(text); } catch (e) { json = { raw: text }; }
    statusEl.innerHTML = '<span class="status-badge status-' + res.status + '">HTTP ' + res.status + '</span>';
    respEl.textContent = JSON.stringify(json, null, 2);
    if (res.ok) { toast('Request successful', 'success'); await loadAudios(); }
  } catch (e) {
    statusEl.innerHTML = '<span class="status-badge status-500">Error</span>';
    respEl.textContent = e.message;
  }
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('panel-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'library') loadAudios();
  });
});
document.addEventListener('DOMContentLoaded', () => {
  try { const t = localStorage.getItem('vani_auth_token'); if (t) state.authToken = t; } catch (e) {}
  loadHealth();
  setInterval(loadHealth, 30000);
});
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD)

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/v1/") or request.path == "/health":
        return jsonify({"error": "Not found"}), 404
    return render_template_string(DASHBOARD), 200

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  VANI — Text to Voice Platform")
    print("  Made by Raj Gautam")
    print("=" * 60)
    print(f"  Dashboard:  http://{HOST}:{PORT}")
    print(f"  API:        http://{HOST}:{PORT}/v1")
    print(f"  Docs:       http://{HOST}:{PORT}/v1/docs")
    print(f"  Output:     {OUTPUT_DIR}")
    print(f"  OpenAI key: {'✅ configured' if OPENAI_API_KEY else '❌ MISSING'}")
    print(f"  Auth:       {'🔒 enabled' if VANI_API_KEY else '🔓 local mode'}")
    print(f"  Model:      {DEFAULT_MODEL} / voice: {DEFAULT_VOICE}")
    print("=" * 60)
    if not OPENAI_API_KEY:
        print("\n⚠️  Set OPENAI_API_KEY before generating speech.\n")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
