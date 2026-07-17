"""Fixtures for email_generator tests."""

CANDIDATE: dict = {
    "full_name": "Divyansh Sharma",
    "headline": "Software Engineer | AI/LLM Integration",
    "skills": [
        {"name": "Python",     "category": "language", "level": "advanced",     "years": 2.0, "evidence": ["Buzz to Brand"]},
        {"name": "FastAPI",    "category": "backend",  "level": "advanced",     "years": 1.5, "evidence": ["Buzz to Brand"]},
        {"name": "pgvector",   "category": "ai_ml",    "level": "intermediate", "years": 0.5, "evidence": ["AI Recruiter"]},
        {"name": "PostgreSQL", "category": "database", "level": "intermediate", "years": 1.5, "evidence": ["Buzz to Brand"]},
    ],
    "projects": [
        {
            "name": "AI Recruiter",
            "description": "Full-stack AI recruiter app with pgvector semantic matching.",
            "tech_stack": ["Python", "FastAPI", "PostgreSQL", "pgvector", "Redis"],
            "metrics": ["3x higher callback rate", "<100ms API P95 latency"],
            "highlights": ["pgvector cosine similarity for resume-job matching"],
        },
    ],
    "experience": [
        {
            "title": "Software Engineering Intern", "company": "Buzz to Brand", "period": "Jun 2024 - Aug 2024",
            "bullets": [
                "Built FastAPI services handling 10K+ daily requests with <50ms P95 latency",
                "Integrated Gemini API for content generation, reducing manual effort by 70%",
                "Optimised PostgreSQL queries, cutting response time by 40%",
            ],
            "tech_used": ["FastAPI", "PostgreSQL", "Docker", "AWS EC2"],
        },
    ],
    "contact": {"email": "divyansh@example.com"},
}

JOB_ANALYSIS: dict = {
    "must_have_skills": [
        {"name": "Python",  "category": "language"},
        {"name": "FastAPI", "category": "backend"},
    ],
    "preferred_skills": [{"name": "pgvector", "category": "ai_ml"}],
    "domain": "ai_ml", "seniority": "mid",
    "business_problems": [
        {"description": "Build LLM-integrated backend services for a new AI product", "priority": "primary"}
    ],
    "culture": ["fast_paced", "startup_culture"],
}

COMPANY_WITH_FULL_INFO: dict = {
    "name": "Vectorly",
    "one_liner": "Vectorly builds embedding-based developer search tools.",
    "recent_news": "Vectorly launched a new open-source code search API last month.",
    "role_title": "Backend Engineer",
    "recipient_name": "Alex",
    "recipient_role": "CTO",
}

COMPANY_MINIMAL_INFO: dict = {
    "name": "Vectorly",
}

PERSONALITY_PROMPT = """Write exactly like Divya. Tone: Natural. Ambitious. Technical.
Never exaggerate. Never invent experiences. Maximum 150 words."""

VALID_GENERATION_RESPONSE: dict = {
    "variants": [
        {
            "variant_type": "technical",
            "subject": "Backend Engineer @ Vectorly — FastAPI + pgvector background",
            "body": (
                "Hi Alex,\n\n"
                "Saw Vectorly launched a new open-source code search API last month — curious about the backend behind it. "
                "I've been building in a similar space: my AI Recruiter project uses pgvector for semantic matching with a FastAPI backend at under 100ms P95 latency. "
                "At Buzz to Brand I built FastAPI services handling 10K+ daily requests.\n\n"
                "Would love to chat about the Backend Engineer role — open to a short call?\n\nBest,\nDivyansh"
            ),
            "word_count": 75,
        },
        {
            "variant_type": "founder",
            "subject": "Backend help for Vectorly",
            "body": (
                "Hi Alex,\n\n"
                "Vectorly's open-source code search API launch caught my eye. "
                "I've shipped FastAPI services at 10K+ daily requests and built pgvector-based semantic search for my AI Recruiter project — "
                "could likely take backend ownership off your plate quickly.\n\n"
                "Open to a quick chat about the Backend Engineer role?\n\nBest,\nDivyansh"
            ),
            "word_count": 60,
        },
        {
            "variant_type": "concise",
            "subject": "Backend Engineer @ Vectorly",
            "body": (
                "Hi Alex,\n\n"
                "I've been building FastAPI + pgvector backends (AI Recruiter project, 10K+ daily requests at Buzz to Brand). "
                "Saw the Backend Engineer opening and the code search API launch — would love to chat if there's a fit.\n\nBest,\nDivyansh"
            ),
            "word_count": 45,
        },
    ]
}

VALID_RANKING_RESPONSE: dict = {
    "rankings": [
        {"variant_type": "technical", "expected_reply_rate": 0.42, "reasoning": "Specific technical overlap increases credibility."},
        {"variant_type": "founder",   "expected_reply_rate": 0.37, "reasoning": "Small-team framing resonates but less specific."},
        {"variant_type": "concise",   "expected_reply_rate": 0.33, "reasoning": "Shortest variant; high ratio but less context."},
    ]
}

# A response with one variant exceeding 150 words
RESPONSE_OVERLONG_TECHNICAL: dict = {
    **VALID_GENERATION_RESPONSE,
    "variants": [
        {**VALID_GENERATION_RESPONSE["variants"][0], "body": "word " * 160, "word_count": 160},
        VALID_GENERATION_RESPONSE["variants"][1],
        VALID_GENERATION_RESPONSE["variants"][2],
    ]
}

# A response with a hallucinated term (not in fact sheet)
RESPONSE_WITH_HALLUCINATION: dict = {
    **VALID_GENERATION_RESPONSE,
    "variants": [
        {
            **VALID_GENERATION_RESPONSE["variants"][0],
            "body": "Hi Alex,\n\nI noticed Vectorly raised a Series B from Sequoia. I built pgvector backends at Buzz to Brand.\n\nBest,\nDivyansh",
            "word_count": 30,
        },
        VALID_GENERATION_RESPONSE["variants"][1],
        VALID_GENERATION_RESPONSE["variants"][2],
    ]
}
