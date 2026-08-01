from __future__ import annotations

from dataclasses import dataclass


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

        title = f"۳ اشتباه رایج در {niche}"

        hook = (
            f"اگر {audience} این اشتباه را انجام دهند، "
            "رشد پیجشان متوقف می‌شود."
        )

        scenario = [
            "۳ ثانیه اول: سوال شوکه‌کننده",
            "مشکل اصلی را نشان بده",
            "نمونه واقعی نمایش بده",
            "راه‌حل را آموزش بده",
            "CTA واضح برای ذخیره و ارسال",
        ]

        caption = (
            f"اگر در حوزه {niche} فعالیت می‌کنی، "
            "این نکته می‌تواند نرخ تعاملت را افزایش دهد.\n\n"
            "امتحانش کن و نتیجه را بررسی کن."
        )

        cta = (
            "این پست را ذخیره کن و برای یک دوست ارسال کن."
        )

        hashtags = [
            "#رشد_اینستاگرام",
            "#تولید_محتوا",
            "#اکسپلور",
            "#هوش_مصنوعی",
            "#رشدیار",
        ]

        image_prompt = (
            "Premium instagram cover, modern purple branding, "
            "clean layout, studio lighting, empty title space, "
            "social media marketing"
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
