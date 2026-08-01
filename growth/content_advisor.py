from __future__ import annotations

from dataclasses import dataclass
import re

from growth.domain_intelligence import DOMAIN_PROFILES, DomainDetector


@dataclass(slots=True)
class ContentAdvice:

    title: str

    hook: str

    scenario: list[str]

    caption: str

    cta: str

    hashtags: list[str]

    image_prompt: str

    cover_title: str

    publish_time: str

    why: str

    plan_b: str


class ContentAdvisor:

    def build(
        self,
        *,
        niche: str,
        audience: str,
        best_content_type: str,
        publish_time: str,
    ) -> ContentAdvice:

        if not niche:
            niche = "کسب و کار"

        if not audience:
            audience = "مخاطبان اینستاگرام"

        detected = DomainDetector().detect(biography=niche, display_name=niche)
        profile = DOMAIN_PROFILES[detected.domain]
        subject = profile.evergreen_topics[0]
        title = f"۳ نکته درباره {subject}"

        hook = (
            f"اگر {audience} با {profile.problems[0]} روبه‌رو هستند، "
            f"این نکته درباره {profile.terminology[0]} را از دست ندهند."
        )

        scenario = [
            "۳ ثانیه اول: سوال شوکه‌کننده",
            "مشکل اصلی را نشان بده",
            "نمونه واقعی نمایش بده",
            "راه‌حل را آموزش بده",
            f"CTA تخصصی: {profile.cta}",
        ]

        caption = (
            f"{profile.questions[0]}\n\n"
            f"برای تصمیم بهتر، {profile.terminology[0]} و {profile.problems[0]} را "
            f"جداگانه بررسی کن. این راهنما برای {audience} طراحی شده است.\n\n"
            f"{profile.cta}"
        )

        cta = profile.cta

        hashtags = list(profile.hashtags[:6]) + [
            "#" + re.sub(r"\s+", "_", topic) for topic in profile.evergreen_topics[:2]
        ]

        image_prompt = (
            "Premium instagram cover, modern purple branding, "
            "clean layout, studio lighting, empty title space, "
            f"visual language of {detected.domain} and {profile.terminology[0]}"
        )

        return ContentAdvice(
            title=title,
            hook=hook,
            scenario=scenario,
            caption=caption,
            cta=cta,
            hashtags=hashtags,
            image_prompt=image_prompt,
            cover_title=title,
            publish_time=publish_time,
            why="این موضوع با توجه به عملکرد پیج و نرخ تعامل انتخاب شده است.",
            plan_b="اگر این محتوا تعامل نگرفت، همان موضوع را به صورت ریلز آموزشی منتشر کن.",
        )
