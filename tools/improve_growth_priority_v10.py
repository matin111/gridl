from pathlib import Path

TARGET = Path('growth/priority_engine.py')


def main() -> None:
    source = TARGET.read_text(encoding='utf-8')
    old = '''def _content_priorities(content_audit: Mapping[str, Any] | None) -> list[GrowthPriority]:
    if not content_audit:
        return []

    analyzed_posts = max(int(content_audit.get("analyzed_posts", 0) or 0), 0)
    confidence = 90 if analyzed_posts >= 12 else 78 if analyzed_posts >= 6 else 62
    result: list[GrowthPriority] = []

    for index, issue in enumerate(content_audit.get("priority_issues", []) or []):
        affected_percent = _clamp(issue.get("affected_percent", 0))
        impact = _clamp(45 + affected_percent * 0.55)
        urgency = 90 if issue.get("priority") == "high" else 70
        problem = str(issue.get("issue", "مشکل محتوایی"))
        ease = 88 if any(word in problem for word in ("CTA", "کپشن", "هوک", "هشتگ")) else 68
        affected_posts = int(issue.get("affected_posts", 0) or 0)
        result.append(
            GrowthPriority(
                key=f"content:{index}:{problem[:24]}",
                title=problem,
                source="content_audit",
                problem=problem,
                evidence=(
                    f"{affected_posts} پست از {analyzed_posts} پست درگیر این مشکل هستند",
                    f"دامنه اثر مشاهده‌شده: {affected_percent}٪",
                ),
                recommendation=_content_recommendation(problem),
                impact=impact,
                confidence=confidence,
                ease=ease,
                urgency=urgency,
                score=_priority_score(
                    impact=impact,
                    confidence=confidence,
                    ease=ease,
                    urgency=urgency,
                ),
            )
        )
    return result
'''
    new = '''def _content_category(problem: str) -> str:
    if "CTA" in problem or "دعوت به اقدام" in problem:
        return "cta"
    if "هوک" in problem or "شروع کپشن" in problem:
        return "hook"
    if "کپشن" in problem:
        return "caption"
    if "هشتگ" in problem:
        return "hashtag"
    return "general"


def _content_priorities(content_audit: Mapping[str, Any] | None) -> list[GrowthPriority]:
    if not content_audit:
        return []

    analyzed_posts = max(int(content_audit.get("analyzed_posts", 0) or 0), 0)
    confidence = 90 if analyzed_posts >= 12 else 78 if analyzed_posts >= 6 else 62
    category_best: dict[str, GrowthPriority] = {}

    category_weight = {
        "cta": 1.00,
        "hook": 0.96,
        "caption": 0.90,
        "general": 0.82,
        "hashtag": 0.62,
    }

    for issue in content_audit.get("priority_issues", []) or []:
        affected_percent = _clamp(issue.get("affected_percent", 0))
        affected_posts = int(issue.get("affected_posts", 0) or 0)
        problem = str(issue.get("issue", "مشکل محتوایی"))
        category = _content_category(problem)

        # A pattern seen in fewer than 20% of posts is evidence, but not a daily priority.
        if analyzed_posts >= 5 and affected_percent < 20:
            continue

        base_impact = 35 + affected_percent * 0.65
        impact = _clamp(base_impact * category_weight[category])
        urgency = 88 if issue.get("priority") == "high" else 66
        if category == "hashtag":
            urgency = min(urgency, 48)
        ease = 90 if category in {"cta", "hook", "caption", "hashtag"} else 68

        candidate = GrowthPriority(
            key=f"content:{category}",
            title=problem,
            source="content_audit",
            problem=problem,
            evidence=(
                f"{affected_posts} پست از {analyzed_posts} پست درگیر این مشکل هستند",
                f"دامنه اثر مشاهده‌شده: {affected_percent}٪",
            ),
            recommendation=_content_recommendation(problem),
            impact=impact,
            confidence=confidence,
            ease=ease,
            urgency=urgency,
            score=_priority_score(
                impact=impact,
                confidence=confidence,
                ease=ease,
                urgency=urgency,
            ),
        )

        previous = category_best.get(category)
        if previous is None or (candidate.score, candidate.impact) > (previous.score, previous.impact):
            category_best[category] = candidate

    return list(category_best.values())
'''
    if old not in source:
        raise RuntimeError('target block not found')
    TARGET.write_text(source.replace(old, new, 1), encoding='utf-8')
    print('Growth Coach priority quality improved')


if __name__ == '__main__':
    main()
