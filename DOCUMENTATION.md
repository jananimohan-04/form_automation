# Dynamic Form Automation — Full Documentation

A tool that opens **any** web form, figures out its fields on its own, fills
them with realistic fake data, submits it, and reports what happened — all
without anyone writing selectors for that specific site.

This document explains, in plain language: **what it does**, **how it works
step by step**, **every tool used and why**, and **how the code is organized**.

---

## 1. The one-sentence summary

> Paste a form URL → the tool reads the form → fills it with fake data →
> submits it → tells you if it worked, with screenshots.

The important part is the word **any**. Nothing about the field names is
hardcoded. Give it a login form, a pizza-order form, a job application — it
works the same way, because it inspects the live page every time instead of
relying on a script written for one website.

---

## 2. The process, in four phases

The whole tool is built around four phases. Think of it like a person filling
out a form they've never seen before.

### Phase 1 — Detect (read the form)

The tool opens the page in a real Chrome browser (driven by Selenium) and
walks through every input on it. For each field it records:

- **name / id** — how to find the field later
- **type** — text, email, password, number, date, radio, checkbox, dropdown,
  file, hidden, etc.
- **label** — the human-readable name next to the field ("Email Address")
- **placeholder**, **required or optional**, **disabled/readonly**
- **options** — the choices for radio buttons, checkboxes, and dropdowns

It figures out the label using several fallbacks (a `<label for="...">` tag,
a `<label>` wrapped around the field, an `aria-label`, or the placeholder), so
it still finds a sensible name even on messy pages.

**Two smart rules here:**

- **Invisible fields are skipped.** Many sites have hidden pop-up forms ("Contact
  Us" modals) sitting in the page code even when you can't see them. The tool
  checks whether each field is actually visible and ignores the ones that
  aren't — so it doesn't try to fill a form the user never opened.
- **Real `<form>` tags are preferred**, but if a page has none (common with
  modern JavaScript sites), it scans the whole page body as a fallback.

The result is saved as a clean JSON file, `form_schema.json`.

### Phase 2 — JSON (write down what it found)

Phase 1's findings are written to a JSON file describing the form's structure.
This is the "map" of the form. Example:

```json
{
  "url": "https://example.com/form",
  "field_count": 3,
  "fields": [
    { "name": "email",  "type": "email", "required": true },
    { "name": "gender", "type": "radio", "options": ["Male", "Female", "Other"] },
    { "name": "country","type": "select","options": ["India", "USA", "UK"] }
  ]
}
```

Having this as a separate file means Phase 3 doesn't need to re-read the page —
it just reads the map.

### Phase 3 — Fill (type in realistic data)

The tool reads the JSON map and, for every field, generates a **realistic**
fake value using the **Faker** library, matched to the field's type:

| Field type | What it gets |
|---|---|
| email | a real-looking email (`hlane@example.com`) |
| password | a strong random password |
| phone / mobile | a 10-digit number |
| number / range | a random number |
| date | a real date (or clicks a calendar — see below) |
| city / country / company / address | a matching fake value |
| name / first / last | a fake person's name |
| dropdown | a random real option from the list |
| radio / checkbox | a random choice / toggle |
| file upload | the included `sample.pdf` |
| hidden / disabled / readonly | skipped (correctly left alone) |

It doesn't just look at the `type` attribute — it also reads the field's
**id, name, label, and placeholder** to make a smart guess. That's how it
knows a field labeled "Mobile Number" (even if its type is plain `text`)
should get a phone number, not a random word.

**Handling modern JavaScript widgets** (this is what makes it robust on real
sites):

- **Searchable dropdowns** (the React "combobox" style, like a State/City
  selector) can't just be typed into. The tool clicks them, types a letter
  to make the real options appear, and clicks a genuine option.
- **Calendar date pickers** (that ignore typing) are opened with a click, and
  the tool clicks a day cell in the calendar.
- **Fields that unlock later** (a "City" dropdown that only enables after you
  pick a "State") are re-checked live, so they get filled once they become
  available.

### Phase 4 — Submit & Verify (send it and check)

Finally, the tool:

1. Takes a **"before" screenshot**.
2. Finds the submit button generically (a `<button type=submit>`, an
   `<input type=submit>`, or a button whose text says "submit").
3. Clicks it.
4. Takes an **"after" screenshot**.
5. Reads the resulting page and records:
   - the final URL and page title
   - any **success message** ("Thank you", "submitted", "received"…)
   - any **error message** ("invalid", "required", "failed"…)
   - a best-effort HTTP status code

Everything is saved to `submission_result.json` and logged to
`automation.log`.

> **Note on HTTP status:** Selenium (the browser tool) genuinely cannot read
> the HTTP status code of a page load — that's a limitation of the browser
> automation protocol itself, not this tool. So the tool makes a separate
> plain request to approximate it. For "did the form actually work?", the
> on-page success/error message detection is the reliable signal.

---

## 3. The two ways to run it

### A) The Web UI (recommended) — a React console

A polished browser interface where you paste a URL and click through the three
stages, seeing the result of each before moving on. Behind the scenes it's a
**React** app talking to a **Flask** JSON API that drives the same Selenium
browser session across all three steps (so "Fill" acts on the exact page
"Detect" opened — the browser stays open between steps).

```bash
# one-time: build the UI
cd frontend && npm install && npm run build && cd ..

# run it
python web_ui.py
# then open the printed URL, e.g. http://127.0.0.1:5175
```

### B) The command line — two scripts

For scripting or when you don't want a UI:

```bash
python scrape_form.py https://example.com/your-form   # Phase 1 & 2 -> form_schema.json
python fill_data.py                                    # Phase 3 & 4 -> submission_result.json
```

---

## 4. Everything used, and why

### Backend (Python)

| Tool | What it's for | Why this one |
|---|---|---|
| **Selenium** | Drives a real Chrome browser — clicks, types, reads the live page | The standard for browser automation; needed because modern forms rely on JavaScript that a plain HTTP request can't run |
| **webdriver-manager** | Auto-downloads the matching ChromeDriver | Removes a fiddly manual setup step — no driver install needed |
| **Faker** | Generates realistic fake data (names, emails, addresses…) | Purpose-built for exactly this; far better than random strings |
| **Flask** | The web server / JSON API behind the UI | Lightweight, minimal, perfect for a small local API |
| **requests** | Fetches the HTTP status code separately | Simple, standard HTTP library (Selenium can't get status codes) |
| **beautifulsoup4 / lxml** | HTML parsing helpers | Standard, dependable HTML tooling |

### Frontend (the UI)

| Tool | What it's for | Why this one |
|---|---|---|
| **React** | Builds the interactive step-by-step interface | Industry-standard UI library; clean state management for the wizard flow |
| **Vite** | Bundles and serves the React app | Fast, modern build tool with a simple dev server |
| **Tailwind CSS** | Styling via utility classes | Fast to build a consistent, professional look |
| **lucide-react** | Clean line icons (spinners, checkmarks, arrows) | Lightweight, tasteful icon set |

### Supporting pieces

- **ChromeDriver** — the bridge Selenium uses to control Chrome (auto-managed).
- **A sample PDF** — a tiny valid PDF included for testing file-upload fields.

---

## 5. File-by-file breakdown

```
dynamic-form-automation/
│
├── web_ui.py            # Flask JSON API + serves the built React app
├── session_manager.py   # Keeps one live browser session per user across steps
│
├── scrape_form.py       # Phase 1 & 2: reads the form, writes form_schema.json
├── fill_data.py         # Phase 3 & 4: fills, submits, verifies
├── utils.py             # Shared helpers: browser setup, logging, label-finding
├── config.py            # Settings: paths, timeouts, success/error keywords
│
├── frontend/            # The React UI
│   ├── src/
│   │   ├── App.jsx           # The 3-stage layout and flow logic
│   │   ├── api.js            # Talks to the Flask API
│   │   ├── theme.css         # Colors for light & dark mode
│   │   ├── app.css           # Button/panel/pill styles
│   │   └── components/       # Rail (sidebar steps), Panel (cards), Shot (screenshots)
│   └── dist/            # The built UI that Flask serves
│
├── output/             # Everything the tool produces
│   ├── form_schema.json      # The form "map" (Phase 2)
│   ├── submission_result.json# The final report (Phase 4)
│   ├── before_submit.png     # Screenshot before submitting
│   ├── after_submit.png      # Screenshot after submitting
│   └── automation.log        # Step-by-step log of everything
│
├── sample_files/sample.pdf  # For file-upload fields
├── requirements.txt         # Python dependencies
├── README.md                # Quick start
└── DOCUMENTATION.md         # This file
```

**How the files work together:**

```
        ┌──────────────┐        ┌──────────────┐
        │  React UI    │───────▶│   web_ui.py  │   (the Flask API)
        │ (frontend/)  │  JSON  │              │
        └──────────────┘        └──────┬───────┘
                                       │ calls
                       ┌───────────────┼────────────────┐
                       ▼               ▼                ▼
                 scrape_form.py    fill_data.py    session_manager.py
                 (detect + map)   (fill + submit)  (keeps browser open)
                       │               │
                       └──────┬────────┘
                              ▼
                   utils.py + config.py   (shared browser setup & settings)
                              │
                              ▼
                       Selenium → Chrome → the target website
```

---

## 6. What makes it "work on unknown forms"

This is the core skill the tool demonstrates. It never says "find the field
called `email`." Instead, every run it:

1. **Discovers** fields by walking the live page.
2. **Infers** what each field is from its type, id, name, label, and placeholder.
3. **Adapts** its filling strategy to the field (type into a textbox, click a
   calendar, choose from a real dropdown, toggle a checkbox…).
4. **Reports** honestly — including which fields it skipped and why.

That's why the same code handles a Selenium demo form, a DemoQA React form
with cascading State/City dropdowns and a calendar, and a WordPress page with a
hidden pop-up — with no per-site changes.

---

## 7. Known limits (honest boundaries)

- Forms inside cross-origin `<iframe>`s aren't traversed.
- CAPTCHAs and bot-detection aren't bypassed (by design).
- Multi-step "wizard" forms: only the fields visible on first load are read.
- HTTP status is approximate (see the note in Phase 4).
- The web UI holds sessions in memory — restarting the server clears them.
- The JavaScript-widget handling recognizes the common libraries
  (react-select, react-datepicker); a very unusual custom widget may fall back
  to plain typing.
