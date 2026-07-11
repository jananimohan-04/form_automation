"""Shared helpers: WebDriver setup, logging, and DOM inspection utilities."""

import logging

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

import config


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("form_automation")


def build_driver(headless=None):
    """Create a configured Chrome WebDriver instance."""
    options = Options()
    if headless if headless is not None else config.HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    return driver


def _own_text(driver, label_element):
    """
    Return only the label's direct text nodes, excluding text belonging to
    nested controls (e.g. a <select>'s <option> text when the <select> is
    wrapped inside the <label>).
    """
    text = driver.execute_script(
        """
        const el = arguments[0];
        let result = '';
        for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                result += node.textContent;
            }
        }
        return result;
        """,
        label_element,
    )
    return text.strip() if text else ""


def find_label_for_element(driver, element):
    """
    Try multiple strategies to find a human-readable label for a form field:
      1. <label for="id">
      2. <label> wrapping the element (ancestor::label)
      3. aria-label attribute
      4. placeholder as a last resort
    """
    element_id = element.get_attribute("id")

    if element_id:
        try:
            label = driver.find_element(By.XPATH, f"//label[@for='{element_id}']")
            text = _own_text(driver, label)
            if text:
                return text
        except NoSuchElementException:
            pass

    try:
        label = element.find_element(By.XPATH, "ancestor::label")
        text = _own_text(driver, label)
        if text:
            return text
    except NoSuchElementException:
        pass

    aria_label = element.get_attribute("aria-label")
    if aria_label:
        return aria_label.strip()

    placeholder = element.get_attribute("placeholder")
    if placeholder:
        return placeholder.strip()

    return None


def is_required(element):
    if element.get_attribute("required") is not None:
        return True
    aria_required = element.get_attribute("aria-required")
    if aria_required and aria_required.lower() == "true":
        return True
    return False


def safe_get_attribute(element, name, default=None):
    value = element.get_attribute(name)
    return value if value is not None else default
