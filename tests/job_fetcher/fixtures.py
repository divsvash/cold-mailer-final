"""Fixtures for job_fetcher tests — realistic API response payloads."""
import json

GREENHOUSE_RESPONSE: dict = {
    "jobs": [
        {
            "id": 4023881007, "title": "Senior Software Engineer, Backend",
            "location": {"name": "San Francisco, CA"},
            "absolute_url": "https://boards.greenhouse.io/stripe/jobs/4023881007",
            "content": "<p>We are looking for a Senior Software Engineer.</p><ul><li>5+ years backend</li></ul>",
            "updated_at": "2024-10-15T12:00:00.000Z",
            "departments": [{"id": 10, "name": "Engineering"}],
            "offices": [{"id": 20, "name": "San Francisco"}],
        },
        {
            "id": 4023882008, "title": "Product Manager, Developer Platform",
            "location": {"name": "Remote"},
            "absolute_url": "https://boards.greenhouse.io/stripe/jobs/4023882008",
            "content": "<p>Lead the developer platform product strategy.</p>",
            "updated_at": "2024-10-12T09:30:00.000Z",
            "departments": [{"id": 11, "name": "Product"}],
            "offices": [{"id": 21, "name": "Remote"}],
        },
    ]
}
GREENHOUSE_RESPONSE_JSON = json.dumps(GREENHOUSE_RESPONSE)
GREENHOUSE_EMPTY_RESPONSE = {"jobs": []}
GREENHOUSE_MALFORMED_RESPONSE = "not-json-{"

LEVER_RESPONSE: list = [
    {
        "id": "abc-111-def", "text": "Staff Infrastructure Engineer",
        "hostedUrl": "https://jobs.lever.co/vercel/abc-111-def",
        "applyUrl": "https://jobs.lever.co/vercel/abc-111-def/apply",
        "categories": {"commitment": "Full-time", "department": "Infrastructure", "location": "Remote (US)"},
        "description": "<p>Vercel is building the frontend cloud.</p>",
        "descriptionPlain": "Vercel is building the frontend cloud.",
        "lists": [{"text": "Requirements", "content": "<li>8+ years in infrastructure</li>"}],
        "createdAt": 1697356800000,
    },
    {
        "id": "abc-222-ghi", "text": "Senior Frontend Engineer",
        "hostedUrl": "https://jobs.lever.co/vercel/abc-222-ghi",
        "applyUrl": "https://jobs.lever.co/vercel/abc-222-ghi/apply",
        "categories": {"commitment": "Full-time", "department": "Engineering", "location": "San Francisco, CA"},
        "description": "<p>Join the DX team to build Next.js.</p>",
        "descriptionPlain": "Join the DX team to build Next.js.",
        "lists": [], "createdAt": 1697270400000,
    },
]
LEVER_RESPONSE_JSON = json.dumps(LEVER_RESPONSE)
LEVER_EMPTY_RESPONSE: list = []
LEVER_WRONG_SHAPE_RESPONSE = json.dumps({"error": "not a list"})

YC_NEXT_DATA_RESPONSE = """<!DOCTYPE html>
<html><head><title>Jobs at YC Companies</title></head><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"jobs":[
  {"id":"yc-job-501","title":"Founding Engineer","company":{"name":"Stealth AI Startup"},
   "location":"San Francisco, CA","description":"<p>Join us to build the future.</p>",
   "createdAt":1697443200000,"url":"/jobs/yc-job-501"},
  {"id":"yc-job-502","title":"Growth Engineer","company":{"name":"Moonshot Health"},
   "location":"Remote","description":"<p>Build and run growth experiments.</p>",
   "createdAt":1697356800000,"url":"/jobs/yc-job-502"}
]}},"page":"/jobs"}
</script></body></html>"""

YC_EMPTY_HTML_RESPONSE = "<!DOCTYPE html><html><body><p>No jobs found.</p></body></html>"
