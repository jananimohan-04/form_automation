"""
Keeps one live Selenium WebDriver + form schema per browser session so the
web UI can walk through Detect -> Fill -> Submit against the *same* open
page, instead of restarting the browser for every step.

Session state is held in-memory (a dict keyed by a random session id stored
in the user's browser cookie). This is intentional: the tool automates one
form at a time for one operator, so a simple in-process store is enough and
avoids adding a database dependency.
"""

import threading

from utils import build_driver

_sessions = {}
_lock = threading.Lock()


class FormSession:
    def __init__(self):
        self.driver = None
        self.schema = None
        self.filled_values = {}
        self.result = None
        self.stage = "idle"  # idle -> detected -> filled -> submitted
        self.error = None

    def ensure_driver(self):
        if self.driver is None:
            self.driver = build_driver()
        return self.driver

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        self.schema = None
        self.filled_values = {}
        self.result = None
        self.stage = "idle"
        self.error = None


def get_session(session_id):
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = FormSession()
        return _sessions[session_id]


def reset_session(session_id):
    with _lock:
        if session_id in _sessions:
            _sessions[session_id].close()
            del _sessions[session_id]
