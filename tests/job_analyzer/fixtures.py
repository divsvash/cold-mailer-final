"""Fixtures for job_analyzer tests."""

SENIOR_BACKEND_JD = """
Senior Backend Engineer — Payments Infrastructure

Requirements:
- 5+ years of backend engineering experience
- Strong proficiency in Python or Go
- Deep experience with PostgreSQL and distributed transactions
- Experience with AWS (ECS, RDS, SQS)

Nice to have:
- Experience in fintech or payments
- Familiarity with Kafka or other event streaming systems

What you'll work on:
- Redesigning our double-entry ledger for 10x scale
- Reducing payment settlement latency from 24h to near real-time
"""

JUNIOR_FRONTEND_JD = """
Frontend Engineer (New Grad) — Consumer App Team

Qualifications:
- BS in Computer Science or related field
- Solid understanding of JavaScript and React
- Familiarity with HTML/CSS

Bonus points:
- Experience with TypeScript
- Exposure to design systems (Figma)

You'll be working on:
- Building new lesson player features used by students daily
- Improving app load time and accessibility (WCAG compliance)
"""

VALID_JU_INPUT = {
    "must_have_skills": [
        {"name": "Python", "category": "language"},
        {"name": "PostgreSQL", "category": "database"},
    ],
    "preferred_skills": [
        {"name": "Kafka", "category": "tool"},
    ],
    "domain": "fintech",
    "seniority": "senior",
    "business_problems": [
        {"description": "Redesign the double-entry ledger for 10x scale", "priority": "primary"},
    ],
    "culture": ["fast_paced"],
}

INVALID_DOMAIN_INPUT = {**VALID_JU_INPUT, "domain": "not_a_valid_domain_xyz"}
MISSING_SENIORITY_INPUT = {k: v for k, v in VALID_JU_INPUT.items() if k != "seniority"}
