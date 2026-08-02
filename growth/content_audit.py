from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Iterable, Mapping

_HASHTAG_RE = re.compile(r"#[\w\u0600-\u06FF]+")
_QUESTION_RE = re.compile(r"[؟?]")
_NUMBER_RE = re.compile(r"(?:^|\s)[۰-۹0-9]+(?:\s|$)")
_CTA_RE = re.compile(
    r"(?:کامنت|نظر|ذخیره|ارسال|فالو|دایرکت|پیام|سفارش|خرید|رزرو|لینک|"
    r"comment|save|share|follow|message|order|buy|book|link)",
    re.IGNORECASE,
)
_WARNING_RE = re.compile(
    r"(?:اشتباه|هشدار|مراقب|هرگز|نکن|از دست نده|خطر|warning|mistake|never)",
    re.IGNORECASE,
)
_CONTRAST_RE = re.compile(
    r"(?:(?<![\w\u0600-\u06FF])(?:اما|ولی|درحالی|برخلاف|واقعیت|vs|versus)"
    r"(?![\w\u0600-\u06FF])|فکر می.?کنی)",
    re.IGNORECASE,
)
_RESULT_RE = re.compile(
    r"(?:نتیجه|قبل و بعد|در چند دقیقه|در چند روز|افزایش|کاهش|سریع.?تر|بهتر|"
    r"result|before and after|increase|decrease)",
    re.IGNORECASE,
)
_EDUCATION_RE = re.compile(
    r"(?:آموزش|راهنما|چطور|روش|نکته|مرحله|ترفند|how to|guide|tips?)",
    re.IGNORECASE,
)
_SALES_RE = re.compile(
    r"(?:خرید|سفارش|قیمت|تخفیف|فروش|رزرو|موجود|offer|sale|discount|price)",
    re.IGNORECASE,
)


def _read(item: object | Mapping[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        value = item.get(key, default)
    else:
        value = getattr(item, key, default)
    return default if value is None else value


def _score_performance(item: object | Mapping[str, Any]) -> float:
    return (
        float(_read(item, "like_count", 0) or 0)
        + 2.5 * float(_read(item, "comment_count", 0) or 0)
        + 0.02 * float(_read(item, "view_count", 0) or 0)
    )


def _first_meaningful_line(caption: str) -> str:
    for line in caption.splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            return value[:180]
    return ""


def _hook_type(hook: str) -> str:
    if not hook:
        return "missing"
    if _QUESTION_RE.search(hook):
        return "question"
    if _WARNING_RE.search(hook):
        return "warning"
    if _CONTRAST_RE.search(hook):
        return "contrast"
    if _RESULT_RE.search(hook):
        return "result"
    if _NUMBER_RE.search(hook):
        return "number"
    return "statement"


def _hook_score(hook: str) -> int:
    if not hook:
        return 0
    score = 35
    hook_type = _hook_type(hook)
    score += {
        "question": 25,
        "warning": 22,
        "contrast": 22,
        "result": 24,
        "number": 18,
        "statement": 0,
    }.get(hook_type, 0)
    length = len(hook)
    if 12 <= length <= 90:
        score += 20
    elif length <= 130:
        score += 10
    if hook.endswith((".", "!", "؟", "?")):
        score += 5
    return max(0, min(score, 100))


def _caption_score(caption: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    if not caption.strip():
        return 0, ["کپشن خالی است"]

    length = len(caption.strip())
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", caption) if part.strip()]
    score = 25

    if 80 <= length <= 1200:
        score += 25
        reasons.append("طول کپشن برای انتقال پیام مناسب است")
    elif length < 40:
        reasons.append("کپشن بسیار کوتاه است")
    else:
        score += 10
        reasons.append("طول کپشن قابل قبول اما قابل بهینه‌سازی است")

    if len(paragraphs) >= 2:
        score += 20
        reasons.append("پاراگراف‌بندی خوانایی را بهتر کرده است")
    else:
        reasons.append("پاراگراف‌بندی مشخصی دیده نشد")

    if _CTA_RE.search(caption):
        score += 20
        reasons.append("دعوت به اقدام تشخیص داده شد")
    else:
        reasons.append("دعوت به اقدام مشخص تشخیص داده نشد")

    if _EDUCATION_RE.search(caption) or _RESULT_RE.search(caption):
        score += 10
        reasons.append("نشانه‌ای از ارزش آموزشی یا نتیجه‌محور وجود دارد")

    return min(score, 100), reasons


def _hashtag_score(caption: str) -> tuple[int, list[str], list[str]]:
    hashtags = _HASHTAG_RE.findall(caption)
    normalized = [tag.casefold() for tag in hashtags]
    unique = list(dict.fromkeys(normalized))
    reasons: list[str] = []

    if not hashtags:
        return 20, ["هشتگی در کپشن تشخیص داده نشد"], []

    score = 45
    count = len(hashtags)
    if 3 <= count <= 12:
        score += 30
        reasons.append("تعداد هشتگ‌ها متعادل است")
    elif count > 20:
        reasons.append("تعداد هشتگ‌ها زیاد است")
    else:
        score += 12
        reasons.append("تعداد هشتگ‌ها قابل قبول است")

    duplicates = count - len(unique)
    if duplicates == 0:
        score += 15
        reasons.append("هشتگ تکراری داخل همین کپشن وجود ندارد")
    else:
        score -= min(duplicates * 8, 30)
        reasons.append(f"{duplicates} هشتگ تکراری داخل کپشن دیده شد")

    if any("_" in tag for tag in hashtags):
        score += 10
        reasons.append("هشتگ‌های چندکلمه‌ای تخصصی استفاده شده‌اند")

    return max(0, min(score, 100)), reasons, hashtags


def _content_pillar(caption: str) -> str:
    if _SALES_RE.search(caption):
        return "sales"
    if _EDUCATION_RE.search(caption):
        return "education"
    if _QUESTION_RE.search(caption):
        return "engagement"
    return "general"


@dataclass(frozen=True, slots=True)
class PostAudit:
    post_id: str
    media_type: str
    permalink: str | None
    published_at: str | None
    hook_text: str
    hook_type: str
    hook_score: int
    caption_score: int
    cta_present: bool
    hashtag_score: int
    hashtags: tuple[str, ...]
    content_pillar: str
    performance_score: float
    strengths: tuple[str, ...]
    issues: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("hashtags", "strengths", "issues", "limitations"):
            data[key] = list(data[key])
        return data


def audit_post(item: object | Mapping[str, Any]) -> dict[str, Any]:
    caption = str(_read(item, "caption", "") or "").strip()
    hook = _first_meaningful_line(caption)
    hook_score = _hook_score(hook)
    caption_score, caption_reasons = _caption_score(caption)
    hashtag_score, hashtag_reasons, hashtags = _hashtag_score(caption)
    cta_present = bool(_CTA_RE.search(caption))

    strengths: list[str] = []
    issues: list[str] = []

    if hook_score >= 70:
        strengths.append("شروع کپشن از نظر متنی قدرت توقف اسکرول خوبی دارد")
    elif hook_score < 50:
        issues.append("شروع کپشن عمومی یا ضعیف است؛ سؤال، تضاد، هشدار یا نتیجه روشن ندارد")

    if caption_score >= 70:
        strengths.append("ساختار کپشن قابل استفاده و نسبتاً خواناست")
    else:
        issues.extend(reason for reason in caption_reasons if "نشده" in reason or "کوتاه" in reason)

    if hashtag_score >= 70:
        strengths.append("ساختار هشتگ‌های این کپشن متعادل است")
    else:
        issues.extend(reason for reason in hashtag_reasons if "زیاد" in reason or "تکراری" in reason or "تشخیص داده نشد" in reason)

    if not cta_present:
        issues.append("CTA مشخصی برای کامنت، ذخیره، ارسال، خرید یا پیام وجود ندارد")

    limitations = (
        "قدرت سه ثانیه اول ویدئو بدون فایل ویدئو یا Retention قابل اندازه‌گیری نیست",
        "کیفیت کاور فقط از URL تصویر قابل قضاوت نیست و در این مرحله امتیاز داده نشده است",
        "Save و Share فقط در صورت ارائه API قابل تحلیل هستند",
    )

    return PostAudit(
        post_id=str(_read(item, "id", "") or ""),
        media_type=str(_read(item, "media_type", "unknown") or "unknown"),
        permalink=str(_read(item, "permalink", "") or "") or None,
        published_at=str(_read(item, "published_at", "") or "") or None,
        hook_text=hook,
        hook_type=_hook_type(hook),
        hook_score=hook_score,
        caption_score=caption_score,
        cta_present=cta_present,
        hashtag_score=hashtag_score,
        hashtags=tuple(hashtags),
        content_pillar=_content_pillar(caption),
        performance_score=round(_score_performance(item), 2),
        strengths=tuple(dict.fromkeys(strengths)),
        issues=tuple(dict.fromkeys(issues)),
        limitations=limitations,
    ).to_dict()


def _correlation_signal(posts: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    strong = [post for post in posts if int(post[field]) >= 70]
    # A score of exactly 50 is still borderline/weak for comparison.
    weak = [post for post in posts if int(post[field]) <= 50]
    if len(strong) < 2 or len(weak) < 2:
        return None
    strong_perf = median(float(post["performance_score"]) for post in strong)
    weak_perf = median(float(post["performance_score"]) for post in weak)
    if weak_perf <= 0:
        lift = None
    else:
        lift = round((strong_perf - weak_perf) / weak_perf * 100, 1)
    return {
        "metric": field,
        "strong_sample": len(strong),
        "weak_sample": len(weak),
        "strong_median_performance": round(strong_perf, 2),
        "weak_median_performance": round(weak_perf, 2),
        "estimated_lift_percent": lift,
        "confidence": "high" if len(strong) + len(weak) >= 10 else "medium",
    }


def audit_content(media: Iterable[object | Mapping[str, Any]]) -> dict[str, Any]:
    posts = [audit_post(item) for item in media]
    if not posts:
        return {
            "score": 0,
            "analyzed_posts": 0,
            "posts": [],
            "patterns": [],
            "priority_issues": [],
            "best_posts": [],
            "weakest_posts": [],
            "limitations": ["هیچ محتوایی برای تحلیل دریافت نشد"],
        }

    averages = {
        "hook": round(sum(post["hook_score"] for post in posts) / len(posts)),
        "caption": round(sum(post["caption_score"] for post in posts) / len(posts)),
        "hashtag": round(sum(post["hashtag_score"] for post in posts) / len(posts)),
        "cta_coverage": round(sum(1 for post in posts if post["cta_present"]) / len(posts) * 100),
    }
    overall = round(
        averages["hook"] * 0.35
        + averages["caption"] * 0.35
        + averages["hashtag"] * 0.15
        + averages["cta_coverage"] * 0.15
    )

    patterns: list[dict[str, Any]] = []
    for field in ("hook_score", "caption_score", "hashtag_score"):
        signal = _correlation_signal(posts, field)
        if signal is not None:
            patterns.append(signal)

    issue_counts: dict[str, int] = {}
    for post in posts:
        for issue in post["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    priority_issues = [
        {
            "issue": issue,
            "affected_posts": count,
            "affected_percent": round(count / len(posts) * 100),
            "priority": "high" if count / len(posts) >= 0.6 else "medium",
        }
        for issue, count in sorted(issue_counts.items(), key=lambda pair: pair[1], reverse=True)[:5]
    ]

    ranked = sorted(posts, key=lambda post: float(post["performance_score"]), reverse=True)
    return {
        "score": overall,
        "analyzed_posts": len(posts),
        "averages": averages,
        "posts": posts,
        "patterns": patterns,
        "priority_issues": priority_issues,
        "best_posts": ranked[:3],
        "weakest_posts": list(reversed(ranked[-3:])),
        "content_mix": {
            pillar: sum(1 for post in posts if post["content_pillar"] == pillar)
            for pillar in ("education", "sales", "engagement", "general")
        },
        "limitations": [
            "این تحلیل فقط از کپشن و آمار عمومی پست‌ها استفاده می‌کند",
            "Retention، Save، Share و کیفیت بصری فقط با داده واقعی API یا فایل رسانه قابل بررسی هستند",
            "رابطه عملکرد و ساختار محتوا همبستگی است و به‌تنهایی علت قطعی را ثابت نمی‌کند",
        ],
    }
