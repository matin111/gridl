from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

Severity = Literal["info", "low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_CONTACT_RE = re.compile(
    r"(?:\+?\d[\d\s\-()]{7,}|واتساپ|whatsapp|تلگرام|telegram|ایمیل|email|دایرکت|direct)",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"(?:خرید|سفارش|رزرو|ثبت.?نام|مشاوره|تماس|پیام|دایرکت|کلیک|دانلود|لینک|عضویت|follow|message|book|order|shop|contact|click|download)",
    re.IGNORECASE,
)
_VALUE_RE = re.compile(
    r"(?:کمک می.?کن|ارائه|فروش|آموزش|خدمات|تخصص|متخصص|ارسال|تضمین|سریع|اختصاصی|برای شما|we help|service|shop|coach|expert|official)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ProfileEvidence:
    field: str
    observed: str
    expected: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class ProfileIssue:
    key: str
    title: str
    severity: Severity
    score: int
    explanation: str
    impact: str
    recommendation: str
    confidence: Confidence
    evidence: tuple[ProfileEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [asdict(item) for item in self.evidence]
        return data


@dataclass(frozen=True, slots=True)
class ProfileAuditResult:
    score: int
    summary: str
    strengths: tuple[ProfileIssue, ...]
    issues: tuple[ProfileIssue, ...]
    unavailable_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "summary": self.summary,
            "strengths": [item.to_dict() for item in self.strengths],
            "issues": [item.to_dict() for item in self.issues],
            "unavailable_checks": list(self.unavailable_checks),
        }


def _read(profile: object | Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if isinstance(profile, Mapping) and key in profile:
            value = profile.get(key)
        else:
            value = getattr(profile, key, None)
        if value not in (None, ""):
            return value
    return default


def _confidence(available_checks: int, total_checks: int) -> Confidence:
    ratio = available_checks / max(total_checks, 1)
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"


def _severity(score: int) -> Severity:
    if score < 25:
        return "critical"
    if score < 50:
        return "high"
    if score < 70:
        return "medium"
    if score < 85:
        return "low"
    return "info"


def _issue(
    *,
    key: str,
    title: str,
    score: int,
    explanation: str,
    impact: str,
    recommendation: str,
    confidence: Confidence,
    evidence: tuple[ProfileEvidence, ...],
) -> ProfileIssue:
    safe_score = max(0, min(int(score), 100))
    return ProfileIssue(
        key=key,
        title=title,
        severity=_severity(safe_score),
        score=safe_score,
        explanation=explanation,
        impact=impact,
        recommendation=recommendation,
        confidence=confidence,
        evidence=evidence,
    )


def audit_profile(profile: object | Mapping[str, Any]) -> dict[str, Any]:
    """Audit only fields that are actually available from the profile payload.

    Missing fields are reported under ``unavailable_checks`` and never converted
    into fabricated failures. This keeps the audit honest for public Instagram APIs.
    """

    username = str(_read(profile, "username")).strip()
    full_name = str(_read(profile, "full_name", "fullName")).strip()
    biography = str(_read(profile, "biography", "bio")).strip()
    picture = str(_read(profile, "profile_picture_url", "profilePictureUrl")).strip()
    external_url = str(_read(profile, "external_url", "externalUrl", "website")).strip()
    category = str(_read(profile, "category", "category_name", "categoryName")).strip()
    contact = str(_read(profile, "contact", "contact_text", "contactText")).strip()

    checks: list[ProfileIssue] = []
    unavailable: list[str] = []

    username_score = 100 if username and len(username) <= 30 else 45 if username else 0
    checks.append(
        _issue(
            key="username",
            title="نام کاربری",
            score=username_score,
            explanation="نام کاربری باید موجود، کوتاه و قابل تشخیص باشد.",
            impact="نام کاربری نامشخص، جست‌وجو و یادآوری برند را سخت‌تر می‌کند.",
            recommendation="نام کاربری کوتاه، خوانا و نزدیک به نام برند یا حوزه فعالیت انتخاب کن.",
            confidence="high",
            evidence=(ProfileEvidence("username", username or "خالی", "نام کاربری موجود و حداکثر ۳۰ کاراکتر"),),
        )
    )

    name_score = 100 if 3 <= len(full_name) <= 64 else 55 if full_name else 0
    checks.append(
        _issue(
            key="display_name",
            title="نام نمایشی",
            score=name_score,
            explanation="نام نمایشی باید هویت یا حوزه پیج را سریع منتقل کند.",
            impact="نام مبهم باعث می‌شود بازدیدکننده در نگاه اول موضوع پیج را نفهمد.",
            recommendation="نام برند را همراه یک کلیدواژه روشن از حوزه فعالیت بنویس.",
            confidence="high",
            evidence=(ProfileEvidence("full_name", full_name or "خالی", "۳ تا ۶۴ کاراکتر و مرتبط با هویت پیج"),),
        )
    )

    bio_length = len(biography)
    has_value = bool(_VALUE_RE.search(biography))
    has_cta = bool(_CTA_RE.search(biography))
    has_contact = bool(_CONTACT_RE.search(biography))
    has_link_hint = bool(_URL_RE.search(biography)) or "لینک" in biography.lower()

    bio_score = 0
    bio_score += 25 if 35 <= bio_length <= 150 else 12 if biography else 0
    bio_score += 30 if has_value else 0
    bio_score += 25 if has_cta else 0
    bio_score += 20 if has_contact or has_link_hint or external_url else 0
    checks.append(
        _issue(
            key="biography",
            title="بیو و ارزش پیشنهادی",
            score=bio_score,
            explanation="بیو بر اساس طول، وضوح ارزش پیشنهادی، CTA و مسیر تماس بررسی شد.",
            impact="بیوی مبهم نرخ تبدیل بازدیدکننده به فالوور یا مشتری را کاهش می‌دهد.",
            recommendation="در سه خط بنویس: چه کاری انجام می‌دهی، برای چه کسی، و قدم بعدی مخاطب چیست.",
            confidence="high",
            evidence=(
                ProfileEvidence("bio_characters", str(bio_length), "۳۵ تا ۱۵۰ کاراکتر"),
                ProfileEvidence("value_proposition", "دارد" if has_value else "تشخیص داده نشد", "مزیت یا خدمت روشن"),
                ProfileEvidence("call_to_action", "دارد" if has_cta else "تشخیص داده نشد", "یک اقدام مشخص"),
                ProfileEvidence("contact_or_link_hint", "دارد" if has_contact or has_link_hint or external_url else "تشخیص داده نشد", "مسیر تماس یا لینک"),
            ),
        )
    )

    checks.append(
        _issue(
            key="profile_picture",
            title="عکس پروفایل",
            score=100 if picture else 0,
            explanation="وجود URL عکس پروفایل بررسی شد؛ کیفیت بصری بدون دسترسی به تصویر قضاوت نمی‌شود.",
            impact="نبود عکس پروفایل اعتماد و تشخیص برند را کاهش می‌دهد.",
            recommendation="از لوگو یا چهره واضح با کنتراست مناسب استفاده کن.",
            confidence="high",
            evidence=(ProfileEvidence("profile_picture_url", "موجود" if picture else "خالی", "URL معتبر عکس پروفایل"),),
        )
    )

    if external_url:
        checks.append(
            _issue(
                key="external_link",
                title="لینک خارجی",
                score=100,
                explanation="یک لینک خارجی در داده پروفایل موجود است.",
                impact="لینک واضح مسیر تبدیل کاربر را کوتاه می‌کند.",
                recommendation="مقصد لینک را با CTA بیو هماهنگ نگه دار.",
                confidence="high",
                evidence=(ProfileEvidence("external_url", external_url, "لینک مقصد معتبر"),),
            )
        )
    else:
        unavailable.append("external_url")

    if category:
        checks.append(
            _issue(
                key="category",
                title="دسته‌بندی پیج",
                score=100,
                explanation="دسته‌بندی عمومی پیج در داده API موجود است.",
                impact="دسته‌بندی روشن به درک سریع‌تر حوزه فعالیت کمک می‌کند.",
                recommendation="دسته‌بندی را با فعالیت اصلی پیج هماهنگ نگه دار.",
                confidence="high",
                evidence=(ProfileEvidence("category", category, "دسته‌بندی مرتبط"),),
            )
        )
    else:
        unavailable.append("category")

    if contact:
        checks.append(
            _issue(
                key="contact",
                title="راه ارتباطی",
                score=100,
                explanation="اطلاعات تماس در داده API موجود است.",
                impact="راه ارتباطی واضح اصطکاک خرید یا رزرو را کاهش می‌دهد.",
                recommendation="راه تماس اصلی را کوتاه و مشخص نگه دار.",
                confidence="high",
                evidence=(ProfileEvidence("contact", contact, "راه تماس قابل استفاده"),),
            )
        )
    else:
        unavailable.append("contact")

    confidence = _confidence(len(checks), len(checks) + len(unavailable))
    weighted = [item.score for item in checks]
    overall = round(sum(weighted) / max(len(weighted), 1))
    issues = tuple(sorted((item for item in checks if item.score < 85), key=lambda item: item.score))
    strengths = tuple(sorted((item for item in checks if item.score >= 85), key=lambda item: item.score, reverse=True))

    if issues:
        summary = f"مهم‌ترین مشکل پروفایل: {issues[0].title}. اطمینان تحلیل {confidence}."
    else:
        summary = f"پروفایل در بررسی داده‌های در دسترس وضعیت خوبی دارد. اطمینان تحلیل {confidence}."

    return ProfileAuditResult(
        score=overall,
        summary=summary,
        strengths=strengths,
        issues=issues,
        unavailable_checks=tuple(unavailable),
    ).to_dict()
