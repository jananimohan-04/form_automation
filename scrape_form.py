"""
scrape_form.py
--------------
Dynamically analyzes an HTML form on a target page and produces a JSON schema
describing every field (text, email, password, number, date, radio, checkbox,
select, textarea, file, hidden, etc.) without any hardcoded field names.

Usage:
    python scrape_form.py [url]

If no URL is given, config.DEFAULT_URL is used. The resulting schema is
written to output/form_schema.json.
"""

import json
import sys

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import config
from utils import build_driver, find_label_for_element, is_required, safe_get_attribute, setup_logging

logger = setup_logging()

FIELD_TAGS_XPATH = ".//input | .//select | .//textarea"


def find_forms(driver):
    """Return all <form> elements on the page. Falls back to <body> if none exist
    (some modern sites build 'forms' out of divs with no <form> tag)."""
    forms = driver.find_elements(By.TAG_NAME, "form")
    if forms:
        return forms
    logger.warning("No <form> tag found; falling back to scanning the full page body.")
    return [driver.find_element(By.TAG_NAME, "body")]


def get_radio_options(driver, container, name):
    """Collect all radio buttons sharing a name and their associated labels."""
    if name:
        radios = container.find_elements(By.XPATH, f".//input[@type='radio' and @name='{name}']")
    else:
        radios = []
    options = []
    for radio in radios:
        label = find_label_for_element(driver, radio) or safe_get_attribute(radio, "value", "")
        options.append(
            {
                "value": safe_get_attribute(radio, "value", ""),
                "label": label,
                "checked": radio.is_selected(),
            }
        )
    return options


def get_checkbox_options(driver, container, name):
    """Collect all checkboxes sharing a name (checkbox groups) and their labels."""
    if name:
        boxes = container.find_elements(By.XPATH, f".//input[@type='checkbox' and @name='{name}']")
    else:
        boxes = []
    options = []
    for box in boxes:
        label = find_label_for_element(driver, box) or safe_get_attribute(box, "value", "")
        options.append(
            {
                "value": safe_get_attribute(box, "value", ""),
                "label": label,
                "checked": box.is_selected(),
            }
        )
    return options


def get_select_options(element):
    select = Select(element)
    return [
        {"value": opt.get_attribute("value"), "label": opt.text.strip()}
        for opt in select.options
    ]


def describe_field(driver, element, seen_radio_groups, seen_checkbox_groups):
    """Build a dict describing a single form field, or None if it should be skipped."""
    tag = element.tag_name.lower()
    field_type = (safe_get_attribute(element, "type") or ("textarea" if tag == "textarea" else "text")).lower()
    if tag == "select":
        field_type = "select"

    name = safe_get_attribute(element, "name")
    field_id = safe_get_attribute(element, "id")

    # Buttons of type submit/button/reset/image aren't data fields.
    if field_type in ("submit", "button", "reset", "image"):
        return None

    # Skip fields that live inside a hidden container (display:none /
    # visibility:hidden ancestor) — e.g. a "Contact Us" modal/popup that
    # exists in the DOM at all times but is only shown after a click.
    # Hidden inputs (type="hidden") are intentionally NOT excluded here;
    # they're handled on their own merits further down.
    if field_type != "hidden" and not element.is_displayed():
        return None

    role = safe_get_attribute(element, "role")
    is_combobox = (
        field_type == "text"
        and role == "combobox"
        and safe_get_attribute(element, "aria-haspopup") in ("true", "listbox")
    )

    field = {
        "name": name,
        "id": field_id,
        "tag": tag,
        "type": field_type,
        "label": find_label_for_element(driver, element),
        "placeholder": safe_get_attribute(element, "placeholder"),
        "required": is_required(element),
        "disabled": element.get_attribute("disabled") is not None,
        "readonly": element.get_attribute("readonly") is not None,
        "value": safe_get_attribute(element, "value"),
        # A "searchable dropdown" widget (react-select, downshift, MUI
        # Autocomplete, etc.) exposed as a plain text input with
        # role="combobox". Needs click-type-Enter instead of a raw send_keys.
        "is_combobox": is_combobox,
    }

    if field_type == "radio":
        group_key = name or field_id
        if group_key in seen_radio_groups:
            return None
        seen_radio_groups.add(group_key)
        field["options"] = get_radio_options(driver, driver, name)

    elif field_type == "checkbox":
        group_key = name or field_id
        if group_key in seen_checkbox_groups and name:
            return None
        seen_checkbox_groups.add(group_key)
        options = get_checkbox_options(driver, driver, name) if name else [
            {
                "value": safe_get_attribute(element, "value", "on"),
                "label": field["label"],
                "checked": element.is_selected(),
            }
        ]
        field["options"] = options

    elif field_type == "select":
        field["options"] = get_select_options(element)
        field["multiple"] = safe_get_attribute(element, "multiple") is not None

    elif field_type == "hidden":
        # Just capture the value; hidden fields are not filled by the user.
        pass

    elif field_type == "file":
        field["accept"] = safe_get_attribute(element, "accept")
        field["multiple"] = safe_get_attribute(element, "multiple") is not None

    return field


def scrape_form(driver, url):
    logger.info(f"Opening target page: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, config.ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        logger.warning("Timed out waiting for page body; continuing anyway.")

    forms = find_forms(driver)
    logger.info(f"Found {len(forms)} form container(s) on the page.")

    all_fields = []
    seen_radio_groups = set()
    seen_checkbox_groups = set()

    for form_index, form in enumerate(forms):
        try:
            elements = form.find_elements(By.XPATH, FIELD_TAGS_XPATH)
        except NoSuchElementException:
            elements = []

        logger.info(f"Form #{form_index}: found {len(elements)} raw input/select/textarea elements.")

        for element in elements:
            try:
                field = describe_field(driver, element, seen_radio_groups, seen_checkbox_groups)
            except Exception as exc:
                logger.exception(f"Failed to describe an element: {exc}")
                continue
            if field is not None:
                field["form_index"] = form_index
                all_fields.append(field)

    submit_button_present = bool(
        driver.find_elements(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
    )

    schema = {
        "url": url,
        "page_title": driver.title,
        "field_count": len(all_fields),
        "has_submit_button": submit_button_present,
        "fields": all_fields,
    }
    return schema


def save_schema(schema, path=config.SCHEMA_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4, ensure_ascii=False)
    logger.info(f"Form schema written to {path}")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_URL
    driver = None
    try:
        driver = build_driver()
        schema = scrape_form(driver, url)
        save_schema(schema)
        logger.info(f"Scraping complete: {schema['field_count']} field(s) discovered.")
    except Exception as exc:
        logger.exception(f"Fatal error during scraping: {exc}")
        raise
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
