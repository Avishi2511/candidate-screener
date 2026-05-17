ROLE_CRITERIA = {
    "Backend Engineer": {
        "required_skills": ["Python", "FastAPI", "Django", "Go", "Node.js"],
        "max_notice_period_days": 60,
        "ctc_range_lpa": (10, 25),
        "open_to_remote": True,
    },
    "Frontend Engineer": {
        "required_skills": ["React", "Vue", "TypeScript"],
        "max_notice_period_days": 45,
        "ctc_range_lpa": (8, 20),
        "open_to_remote": True,
    },
}

DEFAULT_CRITERIA = {
    "required_skills": [],
    "max_notice_period_days": 90,
    "ctc_range_lpa": (0, 999),
    "open_to_remote": True,
}


def classify(skills: list[str], notice_period_days: int, expected_ctc_lpa: float, criteria: dict) -> tuple[str, str]:
    required_skills = criteria["required_skills"]
    max_notice = criteria["max_notice_period_days"]
    ctc_min, ctc_max = criteria["ctc_range_lpa"]

    skill_match = not required_skills or any(
        s.strip().lower() in [c.lower() for c in skills] for s in required_skills
    )
    notice_ok = notice_period_days <= max_notice
    ctc_ok = ctc_min <= expected_ctc_lpa <= ctc_max

    reasons = []
    if required_skills:
        matched = [s for s in required_skills if s.lower() in [c.lower() for c in skills]]
        reasons.append(f"Skill match: {', '.join(matched) if matched else 'none'}.")
    reasons.append(f"Notice {notice_period_days}d {'≤' if notice_ok else '>'} {max_notice}d limit.")
    reasons.append(f"Expected CTC {expected_ctc_lpa} LPA {'within' if ctc_ok else 'outside'} range {ctc_min}-{ctc_max}.")

    if skill_match and notice_ok and ctc_ok:
        return "qualified", " ".join(reasons)
    elif skill_match and (notice_ok or ctc_ok):
        return "maybe", " ".join(reasons)
    else:
        return "rejected", " ".join(reasons)
