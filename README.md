# Page Pulse

A small web tool that audits a URL and reports basic page-health and
SEO signals: HTTP status, response time, title, meta description,
H1 count, images missing alt text, and approximate word count.

**Live demo:** the frontend (`index.html`) is configured to call a
deployed backend at `https://page-pulse-1ni2.onrender.com` (set via
`API_BASE_URL` in `script.js`). To run fully locally instead, point
that constant at `http://127.0.0.1:8000` and follow the setup steps
below.

## Project structure

```
page-pulse/
├── backend/
│   ├── main.py            # FastAPI app, /api/audit route, validation, error handling
│   ├── parser.py          # HTML parsing logic (BeautifulSoup), separate from the route
│   ├── requirements.txt
│   ├── pytest.ini         # pytest config (test discovery)
│   └── tests/
│       └── test_parser.py # Unit tests for parser.py
├── index.html              # Page structure: URL input + Audit button
├── style.css               # Styling
├── script.js                # Calls the API, handles loading/error/report states
└── README.md
```

## Setup instructions

### 1. Install backend dependencies

**macOS / Linux**

```bash
cd page-pulse/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd page-pulse\backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (cmd.exe)**

```cmd
cd page-pulse\backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

This installs both the app's runtime dependencies (FastAPI, httpx,
BeautifulSoup4, Pydantic, Uvicorn) and `pytest` for the test suite.

### 2. Run the FastAPI backend locally

With the virtual environment activated (same on all platforms):

```bash
uvicorn main:app --reload --port 8000
```

The API is now running at `http://127.0.0.1:8000`. Sanity-check it directly:

```bash
curl -X POST http://127.0.0.1:8000/api/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### 3. Run the frontend locally

The frontend is static HTML/CSS/JS, so any simple static server works.
From the project root (where `index.html` lives):

```bash
python3 -m http.server 5500        # Windows: python -m http.server 5500
```

Then open `http://127.0.0.1:5500` in your browser.

> `script.js` currently points `API_BASE_URL` at the deployed backend
> (`https://page-pulse-1ni2.onrender.com`), so the page works
> out of the box even without running a local backend. To test
> against your local backend instead, change `API_BASE_URL` in
> `script.js` to `http://127.0.0.1:8000`. CORS is already enabled on
> the backend, so either setup works regardless of which port serves
> the frontend.

### 4. Run the test suite

From `backend/`, with the virtual environment activated and
dependencies installed:

```bash
pytest
```

or, more verbosely:

```bash
pytest tests/test_parser.py -v
```

The test suite only imports `parser.py` — it does not start the
FastAPI server, make network calls, or hit any live site (local or
deployed), so it runs the same way on macOS, Linux, and Windows.

## API contract

### `POST /api/audit`

**Request body**

```json
{ "url": "https://example.com" }
```

**Successful response** (`200 OK`)

```json
{
  "url": "https://example.com",
  "http_status": 200,
  "response_time_ms": 350,
  "title": "Example Domain",
  "meta_description": null,
  "h1_count": 1,
  "images_missing_alt": 0,
  "word_count": 100
}
```

| Field | Type | Notes |
|---|---|---|
| `url` | string | The (trimmed) URL that was audited |
| `http_status` | int | HTTP status code returned by the target page |
| `response_time_ms` | int | Time taken to fetch the page, in milliseconds |
| `title` | string \| null | Contents of `<title>`, or `null` if missing |
| `meta_description` | string \| null | Contents of `<meta name="description">`, or `null` if missing |
| `h1_count` | int | Number of `<h1>` elements on the page |
| `images_missing_alt` | int | Count of `<img>` elements with a missing, empty, or whitespace-only `alt` attribute |
| `word_count` | int | Approximate visible word count, excluding `<script>`/`<style>` content |

**Error responses** — all errors use the shape:

```json
{ "detail": "Human-readable error message" }
```

| Case | HTTP status | Example `detail` |
|---|---|---|
| Invalid URL (bad/missing scheme, no hostname, empty input) | `400` | "URL must start with http:// or https://" |
| Request timeout | `504` | "The request timed out. The site may be slow or unreachable." |
| Connection failure (DNS/refused/unreachable) | `502` | "Could not connect to that URL. Please check the address and try again." |
| Other network-level failure | `502` | "Failed to reach the page: <exception type>" |
| Non-HTML response | `415` | "That URL did not return an HTML page (content-type: ...)." |
| Upstream HTTP error (target site returned 4xx/5xx) | `502` | "The site responded with an error (HTTP 404)." |
| Parsing failure | `500` | "Failed to parse the page's HTML content." |

### `GET /`

Simple health check for the API itself. Returns:

```json
{ "status": "ok", "service": "Page Pulse API" }
```

## Design decisions

1. **Separation of HTTP/API concerns from HTML parsing.**
   `main.py` only handles request validation, fetching, and mapping
   failures to HTTP responses. All HTML parsing lives in `parser.py`,
   which takes raw HTML text and returns a plain dict of metrics with
   no knowledge of FastAPI, HTTP, or the network. This keeps the route
   function readable and makes the parsing logic independently
   testable — the test suite exercises `parser.py` directly, with no
   server or network involved.

2. **URL validation before making a network request.**
   `validate_url()` checks the scheme (`http`/`https`) and that a
   hostname is present *before* any network call is made, so
   obviously-bad input (e.g. `"not a url"`) fails fast with a clear
   `400` error instead of surfacing as an obscure network exception
   further down the stack.

3. **Explicit timeout and clear error mapping.**
   `httpx.AsyncClient` is configured with a 10-second timeout
   (`REQUEST_TIMEOUT_SECONDS`), so an unreachable or slow site returns
   a clean `504` instead of hanging the request indefinitely. Each
   `httpx` exception type (`TimeoutException`, `ConnectError`, generic
   `RequestError`) is caught separately and mapped to its own
   status code and human-readable message, rather than one generic
   "something went wrong."

4. **Content-Type validation before HTML parsing.**
   The backend only attempts to parse the response as HTML if the
   `Content-Type` header contains `text/html`. Non-HTML responses
   (JSON APIs, images, PDFs, etc.) return a `415` error instead of
   being fed into BeautifulSoup, which keeps parsing logic simple and
   avoids wasted work on content it was never designed to handle.

5. **Stateless architecture with no authentication or database.**
   Per the original requirements, this is a single request/response
   tool — no persistence, sessions, or user accounts. This keeps the
   surface area small and matches the scope of an audit tool that
   only needs to answer "what does this page look like right now."

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
- The footer ("Built for Digital Heroes Training Task", linking to
  `digitalheroesco.com`) is present and unchanged.

## Automated testing

`backend/tests/test_parser.py` covers `parser.py` directly:

- **Happy path** — a representative page with a title, meta
  description, multiple `<h1>` tags, a mix of images (valid alt,
  missing alt, empty alt, whitespace-only alt), and normal visible
  text, verifying every field `build_report()` returns.
- **Edge cases**, including:
  - A page with no title, no meta description, no H1s, and no images.
  - Multiple images with a mix of missing/empty/whitespace-only alt text.
  - Completely empty HTML input.
  - A page containing only `<script>`/`<style>` content, verifying
    that text is correctly excluded from the word count (tested both
    in isolation and alongside real visible text).
  - Whitespace-only `<title>` and `<meta name="description">` values,
    verifying they're treated the same as missing.

All tests build HTML strings in memory — none of them make a real
network request or start the FastAPI server, so they're fast and
deterministic.
