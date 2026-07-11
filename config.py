"""Central configuration for the dynamic form automation tool."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SAMPLE_FILES_DIR = os.path.join(BASE_DIR, "sample_files")

SCHEMA_PATH = os.path.join(OUTPUT_DIR, "form_schema.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "automation.log")
BEFORE_SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, "before_submit.png")
AFTER_SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, "after_submit.png")
RESULT_PATH = os.path.join(OUTPUT_DIR, "submission_result.json")

DEFAULT_SAMPLE_FILE = os.path.join(SAMPLE_FILES_DIR, "sample.pdf")

# Default target if none is passed on the command line. Override with:
#   python scrape_form.py <url>
DEFAULT_URL = "https://www.selenium.dev/selenium/web/web-form.html"

# Selenium behaviour
PAGE_LOAD_TIMEOUT = 20
ELEMENT_WAIT_TIMEOUT = 10
HEADLESS = False

# Keywords used to detect success/failure banners after submission
SUCCESS_KEYWORDS = ["success", "thank", "submitted", "received", "confirmation", "complete"]
ERROR_KEYWORDS = ["error", "invalid", "required", "failed", "denied", "try again"]

for _dir in (OUTPUT_DIR, SAMPLE_FILES_DIR):
    os.makedirs(_dir, exist_ok=True)
