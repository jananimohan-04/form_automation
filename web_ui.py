"""
web_ui.py
---------
JSON API backend for the React frontend (see frontend/). Paste any form URL,
then walk through the pipeline step by step:

    POST /api/detect  -> opens the URL, scrapes the schema, screenshots it
    POST /api/fill    -> fills every field with Faker-generated data
    POST /api/submit  -> submits, detects success/error, screenshots it
    GET  /api/state   -> current session state (for refresh/reconnect)
    POST /api/reset   -> closes the browser session, clears state

Each step reuses the same live browser session (via session_manager.py) so
"next step" continues from where the previous step left off, rather than
reloading the page from scratch.

In production this also serves the built React app (frontend/dist) as
static files, so `python web_ui.py` is the only command needed to run the
whole tool. During development, run the Vite dev server separately
(npm run dev in frontend/) — it proxies /api requests here.

Usage:
    python web_ui.py
Then open http://127.0.0.1:5123 in your browser.
"""

import os
import uuid

from flask import Flask, jsonify, request, send_from_directory, session

import config
from fill_data import (
    detect_message,
    fill_field,
    find_submit_button,
    get_http_status,
    wait_for_navigation_or_update,
)
from scrape_form import save_schema, scrape_form
from session_manager import get_session, reset_session
from utils import setup_logging

logger = setup_logging()

FRONTEND_DIST = os.path.join(config.BASE_DIR, "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")
app.secret_key = os.environ.get("FORM_AUTOMATION_SECRET", uuid.uuid4().hex)
app.config.update(SESSION_COOKIE_SAMESITE="Lax")


def _session_id():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _state_payload(fs):
    return {
        "stage": fs.stage,
        "schema": fs.schema,
        "filledValues": fs.filled_values,
        "result": fs.result,
        "error": fs.error,
    }


@app.after_request
def add_cors_headers(response):
    # Allows the Vite dev server (a different origin) to call this API
    # during development. In production the React build is served from
    # this same Flask app, so no cross-origin requests happen at all.
    origin = request.headers.get("Origin")
    if origin and origin.startswith("http://localhost:"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/state", methods=["GET"])
def api_state():
    fs = get_session(_session_id())
    return jsonify(_state_payload(fs))


@app.route("/api/detect", methods=["POST", "OPTIONS"])
def api_detect():
    if request.method == "OPTIONS":
        return "", 204

    fs = get_session(_session_id())
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please enter a URL."}), 400

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    fs.close()  # fresh browser for a new target
    fs.error = None

    try:
        driver = fs.ensure_driver()
        schema = scrape_form(driver, url)
        save_schema(schema)
        driver.save_screenshot(config.BEFORE_SCREENSHOT_PATH)

        fs.schema = schema
        fs.stage = "detected"
        logger.info(f"[web_ui] Detected {schema['field_count']} field(s) at {url}")
    except Exception as exc:
        logger.exception(f"[web_ui] Detection failed for {url}: {exc}")
        fs.error = f"Could not load or analyze that page: {exc}"
        fs.close()
        return jsonify(_state_payload(fs)), 502

    return jsonify(_state_payload(fs))


@app.route("/api/fill", methods=["POST", "OPTIONS"])
def api_fill():
    if request.method == "OPTIONS":
        return "", 204

    fs = get_session(_session_id())

    if fs.stage == "idle" or fs.schema is None or fs.driver is None:
        return jsonify({"error": "Detect a form first."}), 400

    try:
        driver = fs.driver
        fields = fs.schema.get("fields", [])
        filled = {}
        for field in fields:
            key = field.get("name") or field.get("id") or f"field_{fields.index(field)}"
            value = fill_field(driver, field)
            filled[key] = value
            logger.info(f"[web_ui] Filled '{key}' ({field.get('type')}) -> {value}")

        fs.filled_values = filled
        fs.stage = "filled"
        fs.error = None
    except Exception as exc:
        logger.exception(f"[web_ui] Fill failed: {exc}")
        fs.error = f"Error while filling the form: {exc}"
        return jsonify(_state_payload(fs)), 502

    return jsonify(_state_payload(fs))


@app.route("/api/submit", methods=["POST", "OPTIONS"])
def api_submit():
    if request.method == "OPTIONS":
        return "", 204

    fs = get_session(_session_id())

    if fs.stage != "filled" or fs.driver is None:
        return jsonify({"error": "Fill the form before submitting."}), 400

    driver = fs.driver
    result = {
        "submitted": False,
        "final_url": None,
        "final_title": None,
        "success_detected": False,
        "success_messages": [],
        "error_detected": False,
        "error_messages": [],
        "http_status_after": None,
    }

    try:
        submit_button = find_submit_button(driver)
        if submit_button is None:
            fs.error = "No submit button found on this form."
        else:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
            try:
                submit_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", submit_button)

            result["submitted"] = True
            wait_for_navigation_or_update(driver)

            driver.save_screenshot(config.AFTER_SCREENSHOT_PATH)

            result["final_url"] = driver.current_url
            result["final_title"] = driver.title
            result["http_status_after"] = get_http_status(driver.current_url)

            _, success_texts = detect_message(driver, config.SUCCESS_KEYWORDS)
            if success_texts:
                result["success_detected"] = True
                result["success_messages"] = success_texts

            _, error_texts = detect_message(driver, config.ERROR_KEYWORDS)
            if error_texts:
                result["error_detected"] = True
                result["error_messages"] = error_texts

        fs.result = result
        fs.stage = "submitted"
        logger.info(
            f"[web_ui] Submitted. success={result['success_detected']} error={result['error_detected']}"
        )
    except Exception as exc:
        logger.exception(f"[web_ui] Submit failed: {exc}")
        fs.error = f"Error during submission: {exc}"
        return jsonify(_state_payload(fs)), 502

    return jsonify(_state_payload(fs))


@app.route("/api/reset", methods=["POST", "OPTIONS"])
def api_reset():
    if request.method == "OPTIONS":
        return "", 204
    reset_session(_session_id())
    return jsonify({"ok": True})


@app.route("/api/screenshot/<name>")
def api_screenshot(name):
    if name not in ("before", "after"):
        return "", 404
    filename = "before_submit.png" if name == "before" else "after_submit.png"
    path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return "", 404
    return send_from_directory(config.OUTPUT_DIR, filename)


# --- Serve the built React app for every other route (production mode) ---

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if not os.path.isdir(FRONTEND_DIST):
        return (
            "Frontend build not found. Run `npm install && npm run build` "
            "inside the frontend/ directory first, or run the Vite dev "
            "server separately (npm run dev) and open its URL instead.",
            501,
        )
    full_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")


def _find_open_port(preferred, attempts=20):
    """Return the first bindable port at/after `preferred`.

    Windows can hold a just-closed socket in TIME_WAIT/CLOSE_WAIT for a while,
    which makes re-binding the same port right after a restart fail. Rather
    than force the user to pick a new port by hand each time, walk forward to
    the next free one automatically. Override with the PORT env var.
    """
    import socket

    env_port = os.environ.get("PORT")
    if env_port:
        return int(env_port)

    for candidate in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    return preferred  # let app.run surface the error if nothing was free


if __name__ == "__main__":
    port = _find_open_port(5175)
    print(f"\n  >>  Open the app at:  http://127.0.0.1:{port}\n", flush=True)
    app.run(debug=True, use_reloader=False, threaded=True, port=port)
