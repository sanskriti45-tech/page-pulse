# Page Pulse

A small web tool that audits a URL and reports basic page-health and
SEO signals: HTTP status, response time, title, meta description,
H1 count, images missing alt text, and approximate word count.

## Project structure

```
page-pulse/
├── backend/
│   ├── main.py           # FastAPI app, /api/audit route, validation, error handling
│   ├── parser.py         # HTML parsing logic (BeautifulSoup), separate from the route
│   └── requirements.txt
├── frontend/
│   ├── index.html        # Page structure: URL input + Audit button
│   ├── style.css          # Styling
│   └── script.js         # Calls the API, handles loading/error/report states
└── README.md
```

## 1. Install & run the backend

```bash
cd page-pulse/backend
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API is now running at `http://127.0.0.1:8000`.
You can sanity-check it directly:

```bash
curl -X POST http://127.0.0.1:8000/api/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## 2. Run the frontend

The frontend is static HTML/CSS/JS, so any simple static server works.
From the `frontend/` folder:

```bash
cd page-pulse/frontend
python3 -m http.server 5500
```

Then open `http://127.0.0.1:5500` in your browser.

> The frontend calls the backend at `http://127.0.0.1:8000` (set in
> `script.js` via `API_BASE_URL`). Change that constant if you run the
> backend on a different host/port. CORS is already enabled on the
> backend for local development, so the two servers running on
> different ports can talk to each other.

## Design decisions

- **Separation of concerns**: `main.py` only handles HTTP/API
  concerns (validation, fetching, error mapping). All HTML parsing
  lives in `parser.py`, which takes raw HTML text and returns a plain
  dict of metrics. This keeps the route function readable and makes
  the parsing logic independently testable.
- **URL validation before fetching**: `validate_url()` checks the
  scheme (`http`/`https`) and that a hostname is present *before* any
  network call is made, so obviously-bad input fails fast with a
  clear 400 error instead of an obscure network exception.
- **Explicit timeout**: `httpx.AsyncClient` is configured with a
  10-second timeout, so an unreachable or slow site returns a clean
  504 error instead of hanging the request indefinitely.
- **Content-Type check before parsing**: the backend only attempts to
  parse the response as HTML if the `Content-Type` header contains
  `text/html`. Non-HTML responses (JSON APIs, images, PDFs, etc.)
  return a 415 error instead of being fed into BeautifulSoup.
- **Consistent error shape**: every error path (bad URL, timeout,
  connection failure, non-HTML, upstream HTTP error, parse failure)
  raises an `HTTPException` with a `detail` string, matching FastAPI's
  default `{"detail": "..."}` error body. The frontend only needs one
  code path to handle all error cases.
- **`images_missing_alt` definition**: an image counts as "missing
  alt" if the `alt` attribute is absent *or* present but empty/
  whitespace-only (e.g. `alt=""`), since both mean no meaningful
  alt text is available to assistive technology.
- **Word count**: `<script>` and `<style>` tag contents are removed
  before counting, since their text isn't visible page content. This
  is an approximation (whitespace-split), not a linguistically
  precise word count, which is appropriate for a quick audit tool.
- **No auth/database**: per the requirements, this is a stateless
  tool — each audit is a single request/response with no persistence
  or user accounts.

## Manual testing checklist

Run the backend and frontend as described above, then try each of
these in the URL field:

| # | Case | Input example | Expected result |
|---|------|----------------|------------------|
| 1 | Valid HTML URL | `https://example.com` | Report renders with status 200, a title, response time, word count, etc. |
| 2 | Invalid URL | `not a url` or `htp://bad` | Immediate 400 error: "URL must start with http:// or https://" (no network call made) |
| 3 | Timeout / unreachable URL | `https://10.255.255.1` (non-routable) or a domain that doesn't resolve, e.g. `https://this-domain-does-not-exist-xyz123.com` | Error message about timeout or being unable to connect — page doesn't crash or hang indefinitely |
| 4 | Non-HTML URL | `https://jsonplaceholder.typicode.com/todos/1` (returns JSON) or a direct image URL like `https://www.python.org/static/img/python-logo.png` | 415-style error: "did not return an HTML page" |
| 5 | Page with missing image alt text | Any page with `<img>` tags lacking `alt` (many older or image-heavy sites) | `images_missing_alt` shows a count > 0, styled as a warning |

For each case, also confirm:
- The **Audit** button is disabled and shows "Auditing..." while the request is in flight.
- The status/loading message clears once a result (success or error) is shown.
- Errors are shown in the red error box, not as a broken page or console-only failure.
