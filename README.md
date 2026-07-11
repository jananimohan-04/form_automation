# Dynamic Form Automation

A generic Selenium-based tool that scrapes **any** HTML form, generates a JSON
schema describing its fields, then fills and submits that form with realistic
fake data — without hardcoding any field names.

## Project Structure

```
dynamic-form-automation/
│
├── web_ui.py             # JSON API: /api/detect -> /api/fill -> /api/submit, serves the built React app
├── session_manager.py    # Keeps one live browser session per web UI visitor
├── frontend/             # React + Vite + Tailwind UI (the console you open in a browser)
│   ├── src/
│   │   ├── App.jsx           # Pipeline layout: three stages, one per panel
│   │   ├── api.js             # Thin fetch wrapper over the Flask JSON API
│   │   ├── theme.css          # Design tokens (light/dark) as CSS custom properties
│   │   ├── app.css            # Tailwind layers + component classes (.panel, .pill, .btn, ...)
│   │   └── components/        # Rail, Panel, Shot — shared building blocks
│   └── dist/              # Production build output, served by web_ui.py (git-ignored)
│
├── scrape_form.py        # Phase 1 & 2: scrapes the form, generates form_schema.json
├── fill_data.py          # Phase 3 & 4: fills the form with fake data, submits, validates
├── utils.py              # Shared Selenium/logging/label-detection helpers
├── config.py             # Paths, timeouts, keyword lists, default URL
│
├── output/
│   ├── form_schema.json       # Generated form structure (created by scrape_form.py)
│   ├── submission_result.json # Submission outcome (created by fill_data.py)
│   ├── before_submit.png
│   ├── after_submit.png
│   └── automation.log
│
├── sample_files/
│   └── sample.pdf         # Used to populate <input type="file"> fields
│
├── requirements.txt
└── README.md
```

## How it works

### Phase 1 — Scraping (`scrape_form.py`)
- Opens the target URL with Selenium.
- Locates every `<form>` on the page (falls back to scanning `<body>` if a
  page builds "forms" without a `<form>` tag).
- Walks every `input`, `select`, and `textarea` inside each form.
- For each field, extracts: `name`, `id`, tag, `type`, label (via
  `label[for]`, ancestor `<label>`, `aria-label`, or placeholder fallback),
  `placeholder`, `required`/optional status, current `value`, and — for
  radio groups, checkbox groups, and `<select>` — the list of available
  options.
- Radio and checkbox groups sharing a `name` are deduplicated into a single
  schema entry with an `options` array.
- Fields that are not actually visible on the page (e.g. inputs inside a
  `display:none` "Contact Us" popup/modal that only appears after a click,
  or a search box hidden behind a mobile-menu toggle) are excluded from the
  schema entirely — they exist in the DOM but aren't part of what a real
  user would see and fill in, and attempting to fill them raises Selenium's
  `ElementNotInteractableException`. Fields explicitly `type="hidden"` are
  still captured, since that's a normal, load-bearing part of many forms
  (CSRF tokens, etc.) rather than a visually-hidden decoy.

### Phase 2 — JSON Generation
- Emits `output/form_schema.json`:

```json
{
    "url": "https://example.com/form",
    "page_title": "Example Form",
    "field_count": 8,
    "has_submit_button": true,
    "fields": [
        {
            "name": "email",
            "id": "email",
            "tag": "input",
            "type": "email",
            "label": "Email Address",
            "placeholder": "Enter Email",
            "required": true,
            "value": null
        },
        {
            "name": "gender",
            "type": "radio",
            "options": [
                {"value": "male", "label": "Male", "checked": false},
                {"value": "female", "label": "Female", "checked": false}
            ]
        }
    ]
}
```

### Phase 3 — Automatic Filling (`fill_data.py`)
- Reads `form_schema.json`.
- Uses `Faker` (plus field name/label heuristics) to generate a plausible
  value per field type: `email`, `password`, `tel`, `url`, `number`, `date`,
  `datetime-local`, `month`, `week`, `time`, `color`, `textarea`, and generic
  `text` (with city/country/company/address/name heuristics based on the
  field's name or label).
- Dropdowns are filled via Selenium's `Select` (`select_by_value`, falling
  back to `select_by_visible_text`), radios/checkboxes are chosen/toggled
  randomly, file inputs receive the sample file's absolute path, and hidden
  fields are skipped.
- Elements are located by `name` first, then `id` — never by hardcoded
  selectors specific to one site.
- **JS-framework widgets** (React/Vue/MUI-style forms often replace native
  controls with custom ones) are detected and handled generically:
  - **Searchable dropdowns** (react-select, downshift, MUI Autocomplete —
    exposed as `<input role="combobox" aria-haspopup="true">`): clicked,
    typed into one letter at a time until a real options list renders, then
    a random rendered option is clicked. This also correctly re-checks
    `disabled` on the *live* element right before filling, so a field like a
    "City" dropdown that only becomes enabled after "State" is chosen still
    gets filled even though it was disabled at scrape time.
  - **Calendar-popup date fields** (react-datepicker and similar libraries
    that ignore direct keystrokes): clicked to open the popup, then a
    random enabled day cell is clicked. Detected by name/id/label containing
    "date", "dob", "birth", etc.; falls back to plain typing if no calendar
    popup actually appears.

### Phase 4 — Submission & Validation
- Screenshots are captured before (`before_submit.png`) and after
  (`after_submit.png`) submission.
- The submit control is located generically (`button[type=submit]`,
  `input[type=submit]`, or a button whose text contains "submit").
- After submitting, the script records: final URL, final page title,
  success/error banner text (matched via keyword lists in `config.py`), and
  best-effort HTTP status codes fetched via `requests` (Selenium itself
  cannot read HTTP status codes — see note below).
- Everything is written to `output/submission_result.json`, and the full run
  is logged to `output/automation.log`.

### HTTP Status Note
Selenium's WebDriver protocol has no API for reading the HTTP response
status code of a navigation. To approximate it, this tool issues a plain
`requests.get()` against the same URL (before scraping and after
submission) and records the resulting status code. This is a best-effort
signal, not the literal status of the Selenium-driven request — a page that
requires cookies/JS/auth may return a different status via `requests` than
what the browser actually received. For form submission success/failure,
rely primarily on the on-page success/error message detection.

## Setup

1. Requires Python 3.9+, Node.js 18+, and Google Chrome installed.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

`webdriver-manager` automatically downloads the matching ChromeDriver binary
— no manual driver setup required.

## Usage — Web UI (recommended)

A React-based console lets you paste in an unknown/anonymous form URL and
click through each stage, seeing the result of each step before moving to
the next. `web_ui.py` is a JSON API (`/api/detect`, `/api/fill`,
`/api/submit`, `/api/reset`, `/api/state`) that also serves the built React
app, so in normal use it's the only process you run.

**One-time setup** — build the frontend:

```bash
cd frontend
npm install
npm run build
cd ..
```

**Run it:**

```bash
python web_ui.py
```

Then open the URL it prints (e.g. **http://127.0.0.1:5175**) and:

1. **Paste the target URL** and click **"Detect Form"** — Chrome opens,
   navigates to the page, and the detected fields are shown in a table
   (name, type, label, required, options) along with a screenshot of the
   page as loaded.
2. Click **"Fill Form"** — the same browser window (still open on the same
   page) gets every field populated with Faker-generated data; the values
   used are listed on the page.
3. Click **"Submit Form"** — the form is submitted in that same browser
   window; the final URL, page title, detected success/error banner text,
   best-effort HTTP status, and an after-submission screenshot are shown.
4. Click **"Start Over With a New URL"** to close that browser session and
   test a different form.

The web UI keeps one live Selenium session per browser tab (via
`session_manager.py`), so each step always continues acting on the exact
page you just detected — it does not re-open or reload the page between
steps.

**Frontend development** (only needed if you're editing the UI itself): run
the Vite dev server separately for hot-reload —

```bash
cd frontend
npm run dev
```

— and open the Vite URL it prints (usually `http://127.0.0.1:5173`); it
proxies `/api` requests to the Flask server (`python web_ui.py` must also be
running). `frontend/vite.config.js` points the proxy at Flask's port —
update both if you change it.

## Usage — Command line (scripted / no browser UI)

1. **Scrape a form** (defaults to a public Selenium test form if no URL is
   given):

```bash
python scrape_form.py https://example.com/your-form-page
```

This produces `output/form_schema.json`.

2. **Fill and submit the form:**

```bash
python fill_data.py
```

This reads `output/form_schema.json`, fills and submits the form on the same
URL, and writes `output/submission_result.json` plus before/after
screenshots. Unlike the web UI, this opens a **new** browser session rather
than reusing the one from `scrape_form.py`.

## Configuration

Edit `config.py` to adjust:
- `DEFAULT_URL` — fallback target if no URL is passed to `scrape_form.py`.
- `HEADLESS` — run Chrome headless (`True`) or visibly (`False`).
- `PAGE_LOAD_TIMEOUT` / `ELEMENT_WAIT_TIMEOUT` — Selenium wait tuning.
- `SUCCESS_KEYWORDS` / `ERROR_KEYWORDS` — keywords used to detect
  success/failure banners on the post-submit page.

## Known Limitations

- Forms rendered inside cross-origin `<iframe>`s are not traversed.
- CAPTCHAs and other bot-detection mechanisms are not bypassed.
- Multi-step ("wizard") forms are treated as a single page; only fields
  present on initial load are captured.
- HTTP status codes are approximated via a separate `requests` call (see
  above) rather than read directly from the browser's navigation.
- The web UI (`web_ui.py`) keeps browser sessions in an in-memory dict
  keyed by a cookie — restarting the Flask process drops any in-progress
  session (you'll need to click "Detect" again). It's built for one
  operator driving one form at a time, not concurrent multi-user use.
- `web_ui.py` runs Flask's built-in development server (`debug=True`), which
  is intended for local use only — do not expose it on a public network
  without putting a production WSGI server and authentication in front of it.
- The combobox/calendar-widget handling (see Phase 3) is heuristic, not
  guaranteed: it recognizes the common conventions used by react-select-family
  libraries (`role="combobox"`) and react-datepicker-family libraries
  (a class name containing "datepicker"/"calendar"). A form built with a
  different custom widget library may not be recognized and will fall back
  to plain typing, which may not register on that widget.
