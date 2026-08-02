from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Mapping

MIN_VISUAL_POSTS = 6
MIN_GROUP_SIZE = 3


def _performance_value(post: Mapping[str, Any]) -> float:
    performance = post.get("performance") or {}
    try:
        return float(performance.get("score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _relative_difference(first: float, second: float) -> int:
    """Return a bounded, symmetric percentage difference.

    Using the smaller value as denominator made tiny performance values produce
    absurd differences such as 963%. This representation is always 0..100.
    """
    denominator = max(abs(first), abs(second), 1.0)
    return max(0, min(round(abs(first - second) / denominator * 100), 100))


def _completed_posts(post_intelligence: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not post_intelligence:
        return []
    posts = post_intelligence.get("posts")
    if not isinstance(posts, list):
        return []
    return [
        post for post in posts
        if isinstance(post, Mapping)
        and isinstance(post.get("visual"), Mapping)
        and (post.get("visual") or {}).get("status") == "completed"
    ]


def _group_comparison(
    posts: list[Mapping[str, Any]],
    *,
    feature: str,
    yes_label: str,
    no_label: str,
    minimum_per_group: int = MIN_GROUP_SIZE,
) -> dict[str, Any] | None:
    groups: dict[bool, list[float]] = defaultdict(list)
    post_ids: dict[bool, list[str]] = defaultdict(list)
    for post in posts:
        visual = post.get("visual") or {}
        value = visual.get(feature)
        if not isinstance(value, bool):
            continue
        groups[value].append(_performance_value(post))
        post_ids[value].append(str(post.get("post_id") or ""))

    if len(groups[True]) < minimum_per_group or len(groups[False]) < minimum_per_group:
        return None

    yes_average = mean(groups[True])
    no_average = mean(groups[False])
    difference_percent = _relative_difference(yes_average, no_average)
    if difference_percent < 20:
        return None

    better = yes_average > no_average
    return {
        "key": f"visual:{feature}",
        "type": "binary_visual_pattern",
        "title": yes_label if better else no_label,
        "finding": (
            f"پست‌های {yes_label} در نمونه بررسی‌شده میانگین عملکرد بالاتری داشتند"
            if better
            else f"پست‌های {no_label} در نمونه بررسی‌شده میانگین عملکرد بالاتری داشتند"
        ),
        "better_group": "yes" if better else "no",
        "better_average": round(yes_average if better else no_average, 2),
        "other_average": round(no_average if better else yes_average, 2),
        "difference_percent": difference_percent,
        "sample_size": len(groups[True]) + len(groups[False]),
        "group_sizes": {"yes": len(groups[True]), "no": len(groups[False])},
        "evidence_post_ids": post_ids[better],
        "confidence": "high" if min(len(groups[True]), len(groups[False])) >= 5 else "medium",
        "limitation": "این رابطه همبستگی در پست‌های بررسی‌شده است و علت قطعی عملکرد را ثابت نمی‌کند.",
    }


def _score_correlation_pattern(
    posts: list[Mapping[str, Any]],
    *,
    metric: str,
    title: str,
    minimum_group: int = MIN_GROUP_SIZE,
) -> dict[str, Any] | None:
    rows: list[tuple[float, float, str]] = []
    for post in posts:
        visual = post.get("visual") or {}
        value = visual.get(metric)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        rows.append((float(value), _performance_value(post), str(post.get("post_id") or "")))

    if len(rows) < minimum_group * 2:
        return None
    rows.sort(key=lambda row: row[0])
    split = len(rows) // 2
    low = rows[:split]
    high = rows[-split:]
    if len(low) < minimum_group or len(high) < minimum_group:
        return None

    low_performance = mean(row[1] for row in low)
    high_performance = mean(row[1] for row in high)
    difference_percent = _relative_difference(high_performance, low_performance)
    metric_gap = mean(row[0] for row in high) - mean(row[0] for row in low)
    if difference_percent < 20 or metric_gap < 10:
        return None

    # A negative relationship between a quality score and public performance is
    # too easily caused by post age, promotion, topic, or missing Insights. It is
    # not an actionable winning pattern, so keep it internal instead of showing
    # five misleading warnings to the user.
    if high_performance <= low_performance:
        return None

    return {
        "key": f"visual:{metric}",
        "type": "visual_score_pattern",
        "title": title,
        "finding": f"پست‌های با {title} بالاتر در این نمونه عملکرد بهتری داشتند",
        "direction": "positive",
        "high_group_average_metric": round(mean(row[0] for row in high), 2),
        "low_group_average_metric": round(mean(row[0] for row in low), 2),
        "high_group_average_performance": round(high_performance, 2),
        "low_group_average_performance": round(low_performance, 2),
        "difference_percent": difference_percent,
        "sample_size": len(rows),
        "evidence_post_ids": [row[2] for row in high],
        "confidence": "high" if len(rows) >= 10 else "medium",
        "limitation": "این الگو از مقایسه داخلی همین پیج به دست آمده و تضمین‌کننده عملکرد آینده نیست.",
    }


def discover_visual_patterns(post_intelligence: Mapping[str, Any] | None) -> dict[str, Any]:
    posts = _completed_posts(post_intelligence)
    if len(posts) < MIN_VISUAL_POSTS:
        return {
            "version": 11,
            "status": "insufficient_evidence",
            "analyzed_visual_posts": len(posts),
            "minimum_required_posts": MIN_VISUAL_POSTS,
            "patterns": [],
            "limitations": [
                f"برای کشف الگوی تصویری حداقل {MIN_VISUAL_POSTS} پست تحلیل‌شده لازم است.",
                "الگوها همبستگی هستند و رابطه علت و معلولی را اثبات نمی‌کنند.",
                "Reach، Saves، Shares و Retention فقط در صورت دسترسی به Insights قابل بررسی‌اند.",
            ],
        }

    patterns: list[dict[str, Any]] = []
    face_pattern = _group_comparison(
        posts,
        feature="face_detected",
        yes_label="دارای چهره",
        no_label="بدون چهره",
    )
    if face_pattern:
        patterns.append(face_pattern)

    for metric, title in (
        ("cover_score", "امتیاز کاور"),
        ("scroll_stop_score", "قدرت توقف اسکرول"),
        ("text_readability", "خوانایی متن"),
        ("contrast_score", "کنتراست"),
        ("composition_score", "ترکیب‌بندی"),
        ("brand_consistency_score", "هماهنگی برند"),
    ):
        pattern = _score_correlation_pattern(posts, metric=metric, title=title)
        if pattern:
            patterns.append(pattern)

    patterns.sort(
        key=lambda item: (
            1 if item.get("confidence") == "high" else 0,
            int(item.get("difference_percent", 0) or 0),
            int(item.get("sample_size", 0) or 0),
        ),
        reverse=True,
    )

    return {
        "version": 11,
        "status": "ready" if patterns else "insufficient_evidence",
        "analyzed_visual_posts": len(posts),
        "minimum_required_posts": MIN_VISUAL_POSTS,
        "patterns": patterns[:5],
        "limitations": [
            f"حداقل {MIN_GROUP_SIZE} نمونه در هر گروه برای مقایسه لازم است.",
            "فقط الگوهای مثبت و قابل اقدام نمایش داده می‌شوند.",
            "الگوها همبستگی هستند و رابطه علت و معلولی را اثبات نمی‌کنند.",
            "Reach، Saves، Shares و Retention فقط در صورت دسترسی به Insights قابل بررسی‌اند.",
        ],
    }
