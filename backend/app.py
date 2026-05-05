from __future__ import annotations

import io
import json
import os
import shutil
import threading
import uuid
import zipfile
from functools import wraps
from pathlib import Path
from typing import Any, Dict

import pillow_heif  # type: ignore[import-untyped]

pillow_heif.register_heif_opener()

from flask import Flask, Response, jsonify, render_template, request, send_file  # type: ignore[import-untyped]

from config import Config
from functions import _out_name, add_watermark, collect_photos, folder_name_for_group, group_photos_by_time

_ROOT = Path(__file__).resolve().parent.parent

app = Flask(__name__, template_folder=str(_ROOT / "frontend"))

TEMP_BASE = _ROOT / "tmp"
TEMP_BASE.mkdir(exist_ok=True)

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()



def require_auth(f):  # type: ignore[no-untyped-def]
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app_user = os.environ.get("APP_USER")
        app_pass = os.environ.get("APP_PASS")
        if app_user and app_pass:
            auth = request.authorization
            if not auth or auth.username != app_user or auth.password != app_pass:
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": 'Basic realm="PhotoOrderer"'},
                )
        return f(*args, **kwargs)

    return decorated


@app.route("/")
@require_auth
def index() -> str:
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
@require_auth
def upload() -> Response:
    files = request.files.getlist("photos")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400  # type: ignore[return-value]

    session_id = str(uuid.uuid4())
    input_dir = TEMP_BASE / session_id / "input"
    input_dir.mkdir(parents=True)

    saved = 0
    for f in files:
        if f.filename:
            dest = input_dir / Path(f.filename).name
            f.save(dest)
            saved += 1

    if saved == 0:
        shutil.rmtree(TEMP_BASE / session_id, ignore_errors=True)
        return jsonify({"error": "No valid files"}), 400  # type: ignore[return-value]

    try:
        dates = json.loads(request.form.get("dates", "{}"))
    except (json.JSONDecodeError, ValueError):
        dates = {}
    if dates:
        (input_dir / "dates.json").write_text(json.dumps(dates))

    with _jobs_lock:
        _jobs[session_id] = {
            "status": "uploaded",
            "total": saved,
            "done": 0,
            "error": None,
        }

    return jsonify({"session_id": session_id, "count": saved})  # type: ignore[return-value]


def _run_job(session_id: str, mode: str) -> None:
    input_dir = TEMP_BASE / session_id / "input"
    output_dir = TEMP_BASE / session_id / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = Config(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        mode=mode,
    )

    dates_override: Dict[str, str] = {}
    try:
        dates_override = json.loads((input_dir / "dates.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass

    try:
        photos = collect_photos(input_dir)

        with _jobs_lock:
            _jobs[session_id].update({"status": "processing", "total": len(photos)})

        if mode == "watermark":
            for i, photo in enumerate(photos):
                add_watermark(str(photo), str(output_dir / _out_name(photo)), config, dates_override)
                with _jobs_lock:
                    _jobs[session_id]["done"] = i + 1

        else:
            groups = group_photos_by_time(photos, config, dates_override)
            done = 0
            for group in groups:
                group_dir = output_dir / folder_name_for_group(group, dates_override)
                group_dir.mkdir(parents=True, exist_ok=True)
                for photo in group:
                    out_path = group_dir / _out_name(photo)
                    if mode == "group":
                        shutil.copy2(str(photo), str(out_path))
                    else:
                        add_watermark(str(photo), str(out_path), config, dates_override)
                    done += 1
                    with _jobs_lock:
                        _jobs[session_id]["done"] = done

        with _jobs_lock:
            _jobs[session_id]["status"] = "done"

    except Exception as exc:
        with _jobs_lock:
            _jobs[session_id]["status"] = "error"
            _jobs[session_id]["error"] = str(exc)


@app.route("/process", methods=["POST"])
@require_auth
def process() -> Response:
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    mode = data.get("mode", "both")

    if mode not in ("watermark", "group", "both"):
        return jsonify({"error": "Invalid mode"}), 400  # type: ignore[return-value]

    with _jobs_lock:
        if session_id not in _jobs:
            return jsonify({"error": "Unknown session"}), 404  # type: ignore[return-value]
        _jobs[session_id]["status"] = "queued"

    threading.Thread(target=_run_job, args=(session_id, mode), daemon=True).start()
    return jsonify({"ok": True})  # type: ignore[return-value]


@app.route("/status/<session_id>")
@require_auth
def status(session_id: str) -> Response:
    with _jobs_lock:
        job = _jobs.get(session_id)
    if not job:
        return jsonify({"error": "Not found"}), 404  # type: ignore[return-value]
    return jsonify(job)  # type: ignore[return-value]


@app.route("/download/<session_id>")
@require_auth
def download(session_id: str) -> Response:
    with _jobs_lock:
        job = _jobs.get(session_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not ready"}), 404  # type: ignore[return-value]

    output_dir = TEMP_BASE / session_id / "output"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in output_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(output_dir))
    buf.seek(0)

    def _cleanup() -> None:
        shutil.rmtree(TEMP_BASE / session_id, ignore_errors=True)
        with _jobs_lock:
            _jobs.pop(session_id, None)

    threading.Thread(target=_cleanup, daemon=True).start()

    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="photos.zip")  # type: ignore[return-value]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
