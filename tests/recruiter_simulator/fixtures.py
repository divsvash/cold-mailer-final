"""Fixtures for recruiter_simulator tests."""

CANDIDATE: dict = {
    "full_name": "Divyansh Sharma",
    "headline": "Software Engineer | AI/LLM Integration",
    "skills": [
        {"name": "Python",     "category": "language",  "level": "advanced",     "years": 2.0, "evidence": ["Buzz to Brand", "SkinSoul"]},
        {"name": "FastAPI",    "category": "backend",   "level": "advanced",     "years": 1.5, "evidence": ["Buzz to Brand", "AI Recruiter"]},
        {"name": "PostgreSQL", "category": "database",  "level": "intermediate", "years": 1.5, "evidence": ["Buzz to Brand", "AI Recruiter"]},
        {"name": "Redis",      "category": "backend",   "level": "intermediate", "years": 1.0, "evidence": ["SkinSoul", "AI Recruiter"]},
        {"name": "pgvector",   "category": "ai_ml",     "level": "intermediate", "years": 0.5, "evidence": ["AI Recruiter"]},
        {"name": "Docker",     "category": "devops",    "level": "intermediate", "years": 1.0, "evidence": ["Buzz to Brand"]},
        {"name": "AWS EC2",    "category": "devops",    "level": "beginner",     "years": 0.5, "evidence": ["Buzz to Brand"]},
    ],
    "projects": [
        {
            "name": "SkinSoul",
            "description": "AI skin analysis app.",
            "tech_stack": ["Python", "FastAPI", "Gemini Vision API", "Redis", "PostgreSQL", "pgvector"],
            "metrics": ["88% accuracy", "60% latency reduction", "1st place hackathon"],
            "highlights": ["Gemini Vision classification", "Prompt chaining"],
        },
        {
            "name": "AI Recruiter",
            "description": "Full-stack AI recruiter app.",
            "tech_stack": ["Python", "FastAPI", "PostgreSQL", "pgvector", "Redis", "Next.js"],
            "metrics": ["3x callback rate", "<100ms P95 latency"],
            "highlights": ["pgvector semantic matching"],
        },
    ],
    "experience": [
        {
            "title": "Software Engineering Intern", "company": "Buzz to Brand", "period": "Jun 2024 - Aug 2024",
            "bullets": ["Built FastAPI services handling 10K+ daily requests at <50ms P95 latency",
                        "Integrated Gemini API, reducing manual effort by 70%",
                        "Optimised PostgreSQL queries, cutting response time by 40%"],
            "tech_used": ["FastAPI", "Gemini API", "PostgreSQL", "Docker", "AWS EC2"],
        },
    ],
}

JOB_STRONG_MATCH: dict = {
    "must_have_skills": [
        {"name": "Python",     "category": "language"},
        {"name": "FastAPI",    "category": "backend"},
        {"name": "PostgreSQL", "category": "database"},
    ],
    "preferred_skills": [
        {"name": "Redis",    "category": "tool"},
        {"name": "pgvector", "category": "ai_ml"},
    ],
    "domain": "ai_ml", "seniority": "mid",
    "business_problems": [{"description": "Build LLM-integrated backend services", "priority": "primary"}],
    "culture": ["fast_paced", "startup_culture"],
}

JOB_PARTIAL_MATCH: dict = {
    "must_have_skills": [
        {"name": "Python",  "category": "language"},
        {"name": "Django",  "category": "backend"},   # candidate doesn't have
        {"name": "GraphQL", "category": "api"},        # candidate doesn't have
        {"name": "PostgreSQL", "category": "database"},
    ],
    "preferred_skills": [{"name": "Docker", "category": "devops"}],
    "domain": "enterprise_saas", "seniority": "mid",
    "business_problems": [{"description": "Build enterprise SaaS backend", "priority": "primary"}],
    "culture": [],
}

JOB_POOR_MATCH: dict = {
    "must_have_skills": [
        {"name": "Rust",             "category": "language"},
        {"name": "C++",              "category": "language"},
        {"name": "Embedded Systems", "category": "domain"},
    ],
    "preferred_skills": [{"name": "Assembly", "category": "language"}],
    "domain": "energy", "seniority": "senior",
    "business_problems": [{"description": "Develop firmware for industrial devices", "priority": "primary"}],
    "culture": [],
}

JOB_OVERLEVELED: dict = {
    "must_have_skills": [
        {"name": "Python", "category": "language"},
        {"name": "SQL",    "category": "language"},
    ],
    "preferred_skills": [],
    "domain": "devtools", "seniority": "junior",
    "business_problems": [{"description": "Support backend feature development", "priority": "primary"}],
    "culture": [],
}

JOB_STAFF_LEVEL: dict = {
    "must_have_skills": [
        {"name": "Python",  "category": "language"},
        {"name": "PyTorch", "category": "framework"},
    ],
    "preferred_skills": [],
    "domain": "ai_ml", "seniority": "staff",
    "business_problems": [{"description": "Lead ML platform strategy across multiple teams", "priority": "primary"}],
    "culture": [],
}

JOB_EMPTY: dict = {
    "must_have_skills": [], "preferred_skills": [],
    "domain": "unknown", "seniority": "unknown",
    "business_problems": [{"description": "General software engineering responsibilities", "priority": "primary"}],
    "culture": [],
}
