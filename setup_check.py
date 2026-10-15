#!/usr/bin/env python3
"""
setup_check.py — run this first to verify everything is configured.

    python setup_check.py
"""
from __future__ import annotations
import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


def check(label: str, ok: bool, fix: str = "") -> bool:
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    if not ok and fix:
        print(f"       → {fix}")
    return ok


def main() -> None:
    from config import get_settings
    settings = get_settings()
    all_ok = True

    # ── Python ─────────────────────────────────────────────────────────────────
    print("\n🐍 Python")
    v = sys.version_info
    ok = check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        v >= (3, 12),
        "Install Python 3.12+ from python.org",
    )
    all_ok = all_ok and ok

    # ── Packages ───────────────────────────────────────────────────────────────
    print("\n📦 Required packages")
    packages = {
        "anthropic":            "pip install anthropic",
        "pydantic":             "pip install pydantic pydantic-settings",
        "sqlalchemy":           "pip install sqlalchemy aiosqlite",
        "beautifulsoup4":       "pip install beautifulsoup4",
        "pdfminer":             "pip install pdfminer.six",
        "httpx":                "pip install httpx",
        "tenacity":             "pip install tenacity",
        "google.oauth2":        "pip install google-auth google-auth-oauthlib",
        "googleapiclient":      "pip install google-api-python-client",
        "email_validator":      "pip install email-validator",
    }
    for pkg, install_cmd in packages.items():
        try:
            __import__(pkg.replace("-", "_").replace(".", "/").split("/")[0])
            check(pkg, True)
        except ImportError:
            check(pkg, False, install_cmd)
            all_ok = False

    # ── Environment variables ──────────────────────────────────────────────────
    print("\n🔑 Environment / .env")
    env_file = ROOT / ".env"
    check(".env file exists", env_file.exists(), "cp .env.example .env  then fill in your values")

    api_key = settings.ANTHROPIC_API_KEY
    ok = check(
        "ANTHROPIC_API_KEY set",
        bool(api_key) and api_key != "your_anthropic_api_key_here",
        "Get your key from console.anthropic.com and add to .env",
    )
    all_ok = all_ok and ok

    # ── Memory files ───────────────────────────────────────────────────────────
    print("\n🧠 Memory files")
    profile = settings.PROFILE_PATH
    ok = check(
        "memory/profile.json exists",
        profile.exists(),
        "Run: python -m agents.candidate_analyzer.main",
    )
    all_ok = all_ok and ok

    if profile.exists():
        import json
        try:
            data = json.loads(profile.read_text())
            name = data.get("full_name", "")
            skill_count = len(data.get("skills", []))
            project_count = len(data.get("projects", []))
            check(f"Profile loaded: {name} | {skill_count} skills | {project_count} projects", True)
        except Exception as exc:
            check(f"profile.json is valid JSON", False, f"Fix JSON syntax: {exc}")
            all_ok = False

    check("memory/resume.pdf exists",     settings.RESUME_PATH.exists(),
          "Place your resume PDF at memory/resume.pdf")
    check("memory/projects.md exists",    settings.PROJECTS_PATH.exists(),
          "Create memory/projects.md with your project details")
    check("memory/achievements.md exists",settings.ACHIEVEMENTS_PATH.exists(),
          "Create memory/achievements.md with your achievements")
    check("prompts/personality.md exists",settings.PERSONALITY_PATH.exists(),
          "Create prompts/personality.md with your voice/tone guide")

    # ── Gmail ──────────────────────────────────────────────────────────────────
    print("\n📬 Gmail")
    creds = settings.GMAIL_CREDENTIALS_PATH
    token = settings.GMAIL_TOKEN_PATH

    creds_ok = check(
        "credentials.json exists",
        creds.exists(),
        "Download from Google Cloud Console: APIs & Services → Credentials → OAuth 2.0 Client IDs → Desktop App",
    )
    token_ok = check(
        "token.json exists (OAuth done)",
        token.exists(),
        "Run once to authenticate: python -c \"from database.gmail_auth import get_gmail_service; get_gmail_service()\"",
    )

    if not creds_ok:
        print("""
  Gmail setup steps:
  1. Go to https://console.cloud.google.com
  2. Create project → Enable Gmail API
  3. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID → Desktop App
  4. Download JSON → save as credentials.json in career-agent/ root
  5. Run: python -c "from database.gmail_auth import get_gmail_service; get_gmail_service()"
  6. Complete browser OAuth flow → token.json is created automatically
""")

    # ── Quick import test ──────────────────────────────────────────────────────
    print("\n🔌 Import test")
    imports_ok = True
    for module, label in [
        ("agents.email_generator.engine",       "email_generator"),
        ("agents.recruiter_simulator.scoring",  "recruiter_simulator"),
        ("agents.candidate_analyzer.models",    "candidate_analyzer"),
        ("agents.job_fetcher.models",           "job_fetcher"),
        ("agents.job_analyzer.engine",          "job_analyzer"),
        ("database.gmail_service",              "database/gmail"),
    ]:
        try:
            __import__(module)
            check(label, True)
        except Exception as exc:
            check(label, False, str(exc))
            imports_ok = False
    all_ok = all_ok and imports_ok

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    if all_ok:
        print("✅  Everything looks good. Run:")
        print()
        print("    python send_emails.py \\")
        print('        --to "recruiter@company.com" \\')
        print('        --company "Company Name" \\')
        print('        --role "Role Title" \\')
        print('        --dry-run')
        print()
        print("    Remove --dry-run when you're ready to create the Gmail draft.")
    else:
        print("❌  Fix the issues above, then re-run: python setup_check.py")
    print()


if __name__ == "__main__":
    main()
