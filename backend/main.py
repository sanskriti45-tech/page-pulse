"""
main.py

FastAPI app for Page Pulse. This file owns HTTP/API concerns:
- request/response schemas
- URL validation
- fetching the target page with httpx
- turning failures into clean, user-friendly JSON errors

The actual HTML parsing is delegated to parser.py.
"""

import time
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parser import build_report

# --- App setup -------------------------------------------------------

app = FastAPI(title="Page Pulse API")

# Allow the frontend (served from a different origin/port during local
# development, e.g. a simple static file server on :5500 or :8080) to
# call this API. This is intentionally permissive since Page Pulse has
# no auth/user data - it's a small local dev tool.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Reasonable timeout so a slow/unreachable site can't hang a request
# forever. Applied to connect + read + write + pool phases.
REQUEST_TIMEOUT_SECONDS = 10.0

# A normal-looking browser User-Agent. Some sites block requests that
# don't send one at all.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PagePulse/1.0; "
        "+https://example.com/page-pulse)"
    )
}


# --- Request / response schemas --------------------------------------

class AuditRequest(BaseModel):
    url: str


class AuditResponse(BaseModel):
    url: str
    http_status: int
    response_time_ms: int
    title: str | None
    meta_description: str | None
    h1_count: int
    images_missing_alt: int
    word_count: int


# --- Helpers -----------------------------------------------------------

def validate_url(raw_url: str) -> str:
    """
    Validate that raw_url is a well-formed http/https URL with a
    hostname. Returns the (trimmed) URL if valid, otherwise raises
    an HTTPException with a friendly message.
    """
    url = raw_url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="Please provide a URL to audit.")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="URL must start with http:// or https://",
        )

    if not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="That doesn't look like a valid URL. Please check it and try again.",
        )

    return url


# --- Route -------------------------------------------------------------

@app.post("/api/audit", response_model=AuditResponse)
async def audit_url(payload: AuditRequest):
    url = validate_url(payload.url)

    # --- Fetch the page, timing the request ---
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=REQUEST_HEADERS,
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="The request timed out. The site may be slow or unreachable.",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to that URL. Please check the address and try again.",
        )
    except httpx.RequestError as exc:
        # Catch-all for other httpx-level problems (DNS failure,
        # malformed redirect chain, etc.) so we never crash with a
        # raw stack trace.
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach the page: {exc.__class__.__name__}",
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # --- HTTP error responses from the target site ---
    # We still try to report *something* useful for 4xx/5xx pages
    # rather than treating them as our own server error, but we
    # only continue to parse them if they're actually HTML.
    content_type = response.headers.get("content-type", "")

    if "text/html" not in content_type.lower():
        raise HTTPException(
            status_code=415,
            detail=(
                f"That URL did not return an HTML page "
                f"(content-type: {content_type or 'unknown'})."
            ),
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"The site responded with an error (HTTP {response.status_code}).",
        )

    # --- Parse HTML and build the report ---
    try:
        metrics = build_report(response.text)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse the page's HTML content.",
        )

    return AuditResponse(
        url=url,
        http_status=response.status_code,
        response_time_ms=elapsed_ms,
        title=metrics["title"],
        meta_description=metrics["meta_description"],
        h1_count=metrics["h1_count"],
        images_missing_alt=metrics["images_missing_alt"],
        word_count=metrics["word_count"],
    )


@app.get("/")
async def root():
    """Simple health check / landing route for the API itself."""
    return {"status": "ok", "service": "Page Pulse API"}
