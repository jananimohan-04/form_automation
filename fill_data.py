"""
fill_data.py
------------
Reads form_schema.json produced by scrape_form.py, generates realistic fake
data for every field using Faker, fills the live form via Selenium, submits
it, and records the outcome (redirect URL, page title, success/error banners,
screenshots, exceptions).

Usage:
    python fill_data.py
"""

import json
import os
import random
import sys

import requests
from faker import Faker
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import config
from utils import build_driver, setup_logging

logger = setup_logging()
fake = Faker()


# ---------------------------------------------------------------------------
# Fake data generation
# ---------------------------------------------------------------------------

def generate_value(field):
    """Return a realistic fake value appropriate to the field's type/name/id/label."""
    field_type = (field.get("type") or "text").lower()
    name = (field.get("name") or "").lower()
    field_id = (field.get("id") or "").lower()
    label = (field.get("label") or "").lower()
    placeholder = (field.get("placeholder") or "").lower()
    hint = f"{name} {field_id} {label} {placeholder}"

    # Name/id/label/placeholder heuristics take priority over a generic
    # type="text" (many JS-framework forms don't set a real input type),
    # but an explicit non-text HTML type always wins for its own category.
    if field_type == "email" or "email" in hint:
        return fake.email()
    if field_type == "password":
        return fake.password(length=12)
    if field_type == "tel" or "phone" in hint or "mobile" in hint or "contact number" in hint:
        return fake.numerify("##########")
    if field_type == "url" or "website" in hint:
        return fake.url()
    if "zip" in hint or "postal" in hint or "pincode" in hint or "pin code" in hint:
        return fake.postcode()
    if "city" in hint:
        return fake.city()
    if "country" in hint:
        return fake.country()
    if "state" in hint or "province" in hint:
        return fake.state()
    if "company" in hint or "organi" in hint:
        return fake.company()
    if "address" in hint:
        return fake.address().replace("\n", ", ")
    if "username" in hint or "user name" in hint:
        return fake.user_name()
    if "first name" in hint or "firstname" in hint or "fname" in hint:
        return fake.first_name()
    if "last name" in hint or "lastname" in hint or "lname" in hint or "surname" in hint:
        return fake.last_name()
    if "full name" in hint or ("name" in hint and "user" not in hint):
        return fake.name()
    if "number" in hint and field_type == "text":
        # Ambiguous "number"-ish text field (mobile/phone already handled above)
        return fake.numerify("##########")

    if field_type == "number" or field_type == "range":
        return str(random.randint(1, 100))
    if field_type == "date":
        return fake.date(pattern="%Y-%m-%d")
    if field_type == "datetime-local":
        return fake.date_time().strftime("%Y-%m-%dT%H:%M")
    if field_type == "month":
        return fake.date(pattern="%Y-%m")
    if field_type == "week":
        return fake.date(pattern="%Y-W%U")
    if field_type == "time":
        return fake.time(pattern="%H:%M")
    if field_type == "color":
        return fake.hex_color()
    if field_type == "search":
        return fake.word()
    if field_type == "textarea":
        return fake.paragraph(nb_sentences=3)

    # Fallback for plain text/search/unrecognized types
    return fake.word()


def pick_option(options):
    """Pick a random option dict (with 'value'/'label') from a list, skipping empties."""
    usable = [o for o in options if (o.get("value") or o.get("label"))]
    return random.choice(usable) if usable else (random.choice(options) if options else None)


# ---------------------------------------------------------------------------
# Element lookup
# ---------------------------------------------------------------------------

def locate_element(driver, field):
    """
    Find the live element for a field, preferring name over id. Retries
    briefly to absorb transient timing issues (e.g. the page/tab was
    backgrounded between the detect and fill steps in the web UI and needs
    a moment to become responsive again).
    """
    name = field.get("name")
    field_id = field.get("id")
    tag = field.get("tag", "input")

    candidates = []
    if name:
        candidates.append((By.NAME, name))
    if field_id:
        candidates.append((By.ID, field_id))

    if not candidates:
        logger.warning(f"Could not locate element for field: {field.get('label') or name or field_id} ({tag})")
        return None

    for by, value in candidates:
        try:
            return WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            continue

    logger.warning(f"Could not locate element for field: {field.get('label') or name or field_id} ({tag})")
    return None


# ---------------------------------------------------------------------------
# Field filling strategies
# ---------------------------------------------------------------------------

DATE_HINT_WORDS = ("date", "dob", "birth", "dpd", "calendar")


def _looks_like_date_field(field):
    hint = f"{field.get('name') or ''} {field.get('id') or ''} {field.get('label') or ''}".lower()
    return any(word in hint for word in DATE_HINT_WORDS)


def fill_combobox(driver, element, field):
    """
    Fill a react-select/downshift/MUI-Autocomplete-style "combobox": a plain
    text input (role="combobox") that opens a *filtered* options list rather
    than accepting free text. The available options aren't known up front
    (React renders them on demand), so instead of typing Faker-generated
    text — which would match nothing — this types one common letter at a
    time until the live options list is non-empty, then picks a real option
    from what actually rendered.
    """
    from selenium.webdriver.common.keys import Keys

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)

    option_xpath = "//*[@role='option'] | //*[contains(@id,'-option-')]"

    options = []
    for letter in "aeiosmn":
        element.send_keys(letter)
        try:
            WebDriverWait(driver, 1.5).until(
                lambda d: len(d.find_elements(By.XPATH, option_xpath)) > 0
            )
            options = driver.find_elements(By.XPATH, option_xpath)
            if options:
                break
        except TimeoutException:
            continue

    if options:
        chosen = random.choice(options)
        label = chosen.text.strip()
        try:
            chosen.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", chosen)
        return label or "(option selected)"

    # No option list ever appeared -> this wasn't really a filtered dropdown;
    # fall back to typing an ordinary fake value.
    value = generate_value(field)
    element.send_keys(value)
    element.send_keys(Keys.ENTER)
    return value


def fill_date_field(driver, element, field):
    """
    Fill a date input that may be backed by a calendar popup (react-datepicker
    and similar libraries render a floating panel on click/focus and ignore
    direct keystrokes). Try typing first; if a calendar-like popup appears,
    click a day cell in it instead of relying on the typed text.
    """
    value = generate_value(field)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)

    calendar_day_xpath = (
        "//*[contains(@class, 'datepicker') or contains(@class, 'calendar')]"
        "//*[contains(@class, 'day')"
        " and not(contains(@class, 'disabled'))"
        " and not(contains(@class, 'outside'))"
        " and not(contains(@class, 'header'))"
        " and not(contains(@class, 'name'))]"
    )
    try:
        WebDriverWait(driver, 1.5).until(
            EC.presence_of_element_located((By.XPATH, calendar_day_xpath))
        )
        days = driver.find_elements(By.XPATH, calendar_day_xpath)
        if days:
            chosen_day = random.choice(days)
            day_text = chosen_day.text.strip() or "(calendar day selected)"
            try:
                chosen_day.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", chosen_day)
            return day_text
    except TimeoutException:
        pass

    # No calendar popup detected -> treat as a normal typed date field.
    try:
        element.clear()
    except (ElementNotInteractableException, Exception):
        pass
    element.send_keys(value)
    return value


def fill_text_like(driver, element, field):
    if field.get("is_combobox"):
        return fill_combobox(driver, element, field)

    if _looks_like_date_field(field):
        return fill_date_field(driver, element, field)

    value = generate_value(field)
    try:
        element.clear()
    except (ElementNotInteractableException, Exception):
        pass
    element.send_keys(value)
    return value


def fill_select(driver, element, field):
    select = Select(element)
    options = field.get("options", [])

    # Prefer real choices over a leading placeholder/prompt option
    # (commonly value="" or the first option when more than one exists).
    non_placeholder = [
        o for i, o in enumerate(options)
        if not (i == 0 and len(options) > 1 and not (o.get("value") or "").strip())
    ]
    choice = pick_option(non_placeholder) or pick_option(options)
    if not choice:
        return None
    try:
        select.select_by_value(choice["value"])
    except Exception:
        select.select_by_visible_text(choice["label"])
    return choice.get("label") or choice.get("value")


def _find_elements_with_wait(driver, xpath, timeout=3):
    """find_elements() doesn't raise on an empty match, so a plain call can't
    distinguish 'genuinely no such elements' from 'page hasn't caught up
    yet'. Wait briefly for at least one match before giving up."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.XPATH, xpath)) > 0
        )
    except TimeoutException:
        pass
    return driver.find_elements(By.XPATH, xpath)


def fill_radio(driver, field):
    options = field.get("options", [])
    name = field.get("name")
    if not name or not options:
        return None
    radios = _find_elements_with_wait(driver, f"//input[@type='radio' and @name='{name}']")
    if not radios:
        return None
    chosen = random.choice(radios)
    try:
        chosen.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", chosen)
    return chosen.get_attribute("value")


def fill_checkbox_group(driver, field):
    name = field.get("name")
    options = field.get("options", [])
    selected_values = []

    if name:
        boxes = _find_elements_with_wait(driver, f"//input[@type='checkbox' and @name='{name}']")
    else:
        boxes = []

    if boxes:
        for box in boxes:
            if random.choice([True, False]):
                try:
                    box.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", box)
                selected_values.append(box.get_attribute("value"))
        return selected_values

    # Single standalone checkbox (no shared name group)
    element = locate_element(driver, field)
    if element and random.choice([True, False]):
        try:
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)
        selected_values.append(element.get_attribute("value"))
    return selected_values


def fill_file(driver, element, field):
    accept = (field.get("accept") or "").lower()
    file_path = config.DEFAULT_SAMPLE_FILE
    if not os.path.exists(file_path):
        logger.warning(f"Sample file not found at {file_path}; skipping file field.")
        return None
    element.send_keys(os.path.abspath(file_path))
    return os.path.abspath(file_path)


def fill_field(driver, field):
    """Dispatch a field to the correct fill strategy. Returns the value used (for logging)."""
    field_type = (field.get("type") or "text").lower()

    if field_type == "hidden":
        return "SKIPPED (hidden)"

    try:
        if field_type == "radio":
            return fill_radio(driver, field)

        if field_type == "checkbox":
            return fill_checkbox_group(driver, field)

        element = locate_element(driver, field)
        if element is None:
            return "SKIPPED (not found)"

        # Re-check disabled/readonly on the LIVE element rather than the
        # schema snapshot: some fields (e.g. a "City" dropdown gated on
        # "State" being chosen first) start disabled and become enabled
        # mid-fill as earlier fields are populated.
        if element.get_attribute("disabled") is not None:
            return "SKIPPED (disabled)"
        if element.get_attribute("readonly") is not None:
            return "SKIPPED (readonly)"

        if field_type == "select":
            return fill_select(driver, element, field)

        if field_type == "file":
            return fill_file(driver, element, field)

        # text, email, password, number, date, textarea, tel, url, etc.
        return fill_text_like(driver, element, field)

    except Exception as exc:
        logger.exception(f"Error filling field {field.get('name') or field.get('id')}: {exc}")
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Submission & validation
# ---------------------------------------------------------------------------

def find_submit_button(driver):
    candidates = [
        (By.XPATH, "//button[@type='submit']"),
        (By.XPATH, "//input[@type='submit']"),
        (By.XPATH, "//button[not(@type)]"),
        (By.XPATH, "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]"),
    ]
    for by, expr in candidates:
        elements = driver.find_elements(by, expr)
        if elements:
            return elements[0]
    return None


def detect_message(driver, keywords):
    for keyword in keywords:
        xpath = (
            f"//*[contains(translate(text(),"
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
        )
        elements = driver.find_elements(By.XPATH, xpath)
        texts = [e.text.strip() for e in elements if e.text.strip()]
        if texts:
            return keyword, texts[:5]
    return None, []


def get_http_status(url):
    try:
        response = requests.get(url, timeout=10)
        return response.status_code
    except requests.RequestException as exc:
        logger.warning(f"Could not retrieve HTTP status for {url}: {exc}")
        return None


def submit_form(driver):
    submit_button = find_submit_button(driver)
    if submit_button is None:
        logger.warning("No submit button found on the page.")
        return False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        submit_button.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", submit_button)
    return True


def wait_for_navigation_or_update(driver, timeout=5):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def load_schema(path=config.SCHEMA_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Schema file not found at {path}. Run scrape_form.py first."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    schema = load_schema()
    url = schema["url"]

    result = {
        "url": url,
        "http_status_before": None,
        "http_status_after": None,
        "submitted": False,
        "final_url": None,
        "final_title": None,
        "success_detected": False,
        "success_messages": [],
        "error_detected": False,
        "error_messages": [],
        "filled_values": {},
        "exceptions": [],
    }

    result["http_status_before"] = get_http_status(url)

    driver = None
    try:
        driver = build_driver()
        logger.info(f"Opening form page: {url}")
        driver.get(url)
        WebDriverWait(driver, config.ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        driver.save_screenshot(config.BEFORE_SCREENSHOT_PATH)
        logger.info(f"Saved before-submit screenshot to {config.BEFORE_SCREENSHOT_PATH}")

        fields = schema.get("fields", [])
        logger.info(f"Filling {len(fields)} field(s)...")

        for field in fields:
            key = field.get("name") or field.get("id") or f"field_{fields.index(field)}"
            value = fill_field(driver, field)
            result["filled_values"][key] = value
            logger.info(f"Filled '{key}' ({field.get('type')}) -> {value}")

        submitted = submit_form(driver)
        result["submitted"] = submitted

        if submitted:
            wait_for_navigation_or_update(driver)

        driver.save_screenshot(config.AFTER_SCREENSHOT_PATH)
        logger.info(f"Saved after-submit screenshot to {config.AFTER_SCREENSHOT_PATH}")

        result["final_url"] = driver.current_url
        result["final_title"] = driver.title
        result["http_status_after"] = get_http_status(driver.current_url)

        success_keyword, success_texts = detect_message(driver, config.SUCCESS_KEYWORDS)
        if success_texts:
            result["success_detected"] = True
            result["success_messages"] = success_texts

        error_keyword, error_texts = detect_message(driver, config.ERROR_KEYWORDS)
        if error_texts:
            result["error_detected"] = True
            result["error_messages"] = error_texts

        logger.info(
            f"Submission complete. success_detected={result['success_detected']} "
            f"error_detected={result['error_detected']}"
        )

    except Exception as exc:
        logger.exception(f"Fatal error during form filling/submission: {exc}")
        result["exceptions"].append(str(exc))
    finally:
        if driver is not None:
            driver.quit()

    with open(config.RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    logger.info(f"Submission result written to {config.RESULT_PATH}")

    return result


if __name__ == "__main__":
    run()
