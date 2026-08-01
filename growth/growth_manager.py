from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from growth.growth_models import (
    GrowthManagerResponse,
    Recommendation,
    DailyTask,
    BioDoctor,
    ProfileDoctor,
    HighlightDoctor,
    ReadyToPublish,
)


@dataclass(slots=True)
class GrowthContext:
    username: str
    full_name: str
    followers: int
    following: int
    posts: int
    engagement_rate: float
    posting_consistency: int
    caption_score: int
    best_time: str
    best_content_type: str
    bio: str
    is_verified: bool = False


class GrowthManager:

    def __init__(self, ctx: GrowthContext):
        self.ctx = ctx

    def build(self) -> GrowthManagerResponse:

        score = self._growth_score()

        return GrowthManagerResponse(
            growth_score=score,
            daily_focus=self._daily_focus(),
            recommendations=self._recommendations(),
            daily_tasks=self._tasks(),
            bio=self._bio_doctor(),
            profile=self._profile_doctor(),
            highlights=self._highlight_doctor(),
            publish=self._ready_to_publish(),
        )

    def _growth_score(self) -> int:

        score = 100

        score -= max(0, 60 - self.ctx.posting_consistency) // 2

        score -= max(0, 60 - self.ctx.caption_score) // 2

        if self.ctx.engagement_rate < 2:
            score -= 15

        if self.ctx.posts < 12:
            score -= 10

        return max(0, min(100, score))

    def _daily_focus(self) -> str:

        if self.ctx.posting_consistency < 50:
            return "امروز فقط روی نظم انتشار تمرکز کن."

        if self.ctx.caption_score < 60:
            return "امروز کپشن‌های قوی‌تر بنویس."

        if self.ctx.engagement_rate < 2:
            return "امروز هدف اصلی افزایش تعامل است."

        return "امروز روی تولید یک محتوای باکیفیت تمرکز کن."

    def _recommendations(self):

        items = []

        if self.ctx.posting_consistency < 50:
            items.append(
                Recommendation(
                    title="انتشار منظم",
                    reason="نظم انتشار پایین است.",
                    priority="high",
                    impact="very_high",
                    estimated_time="20 دقیقه",
                    action="شروع برنامه",
                    target_tool="planner",
                )
            )

        if self.ctx.caption_score < 60:
            items.append(
                Recommendation(
                    title="بهبود کپشن",
                    reason="کپشن‌ها نرخ تعامل را کاهش داده‌اند.",
                    priority="high",
                    impact="high",
                    estimated_time="10 دقیقه",
                    action="تولید کپشن",
                    target_tool="content_studio",
                )
            )

        if self.ctx.engagement_rate < 2:
            items.append(
                Recommendation(
                    title="افزایش تعامل",
                    reason="کامنت و ذخیره پایین است.",
                    priority="high",
                    impact="very_high",
                    estimated_time="15 دقیقه",
                    action="ساخت ریلز",
                    target_tool="content_studio",
                )
            )

        return items

    def _tasks(self):

        tasks = []

        tasks.append(
            DailyTask(
                title="بررسی بایو",
                description="بایو را با پیشنهادهای AI مقایسه و اصلاح کن.",
                priority="high",
            )
        )

        tasks.append(
            DailyTask(
                title="انتشار محتوا",
                description=f"یک {self.ctx.best_content_type} در ساعت {self.ctx.best_time} منتشر کن.",
                priority="high",
            )
        )

        tasks.append(
            DailyTask(
                title="پاسخ به کامنت‌ها",
                description="حداقل به ۱۰ کامنت اخیر پاسخ بده.",
                priority="medium",
            )
        )

        tasks.append(
            DailyTask(
                title="بررسی ترند",
                description="مرکز ترند را بررسی و یک ایده جدید ذخیره کن.",
                priority="medium",
            )
        )

        return tasks

    def _bio_doctor(self):

        score = 100
        problems = []
        suggestions = []
        ready = []

        bio = (self.ctx.bio or "").strip()

        if len(bio) < 30:
            score -= 25
            problems.append("بایو کوتاه است.")
            suggestions.append("ارزش پیشنهادی پیج را در یک جمله بنویس.")

        if "@" not in bio and "http" not in bio:
            score -= 10
            problems.append("راه ارتباطی یا لینک دیده نمی‌شود.")

        if "👇" not in bio:
            score -= 10
            suggestions.append("برای CTA از 👇 استفاده کن.")

        ready.append(
            "کمک می‌کنم سریع‌تر رشد کنی 🚀\nآموزش + تجربه واقعی\n👇 همین حالا شروع کن"
        )

        ready.append(
            "آموزش تخصصی اینستاگرام\nترفندهای رشد واقعی\n👇 همراه ما باش"
        )

        ready.append(
            "رشد پیج بدون آزمون و خطا\nمحتوا، تحلیل، ایده\n👇"
        )

        return BioDoctor(
            score=max(score,0),
            problems=problems,
            suggestions=suggestions,
            ready_bios=ready,
        )

    def _profile_doctor(self):

        score = 90
        problems = []
        suggestions = []

        if not self.ctx.is_verified:
            suggestions.append("در صورت امکان احراز هویت برند را انجام بده.")

        if self.ctx.followers < 500:
            suggestions.append("فعلاً روی اعتمادسازی تمرکز کن، نه فروش مستقیم.")

        if self.ctx.posts < 15:
            score -= 20
            problems.append("تعداد پست‌ها هنوز کم است.")
            suggestions.append("حداقل ۳۰ محتوای باکیفیت منتشر کن.")

        return ProfileDoctor(
            score=max(score,0),
            problems=problems,
            suggestions=suggestions,
        )

    def _highlight_doctor(self):

        return HighlightDoctor(
            score=60,
            missing=[
                "محصولات",
                "درباره ما",
                "رضایت مشتری",
                "سوالات متداول",
            ],
            suggestions=[
                "برای همه هایلایت‌ها کاور یکدست طراحی کن.",
                "ترتیب هایلایت‌ها را بر اساس نیاز کاربر بچین.",
            ],
        )

    def _ready_to_publish(self):

        return ReadyToPublish(
            hook="قبل از اینکه محتوای بعدی را منتشر کنی این نکته را ببین...",
            caption="یک کپشن آموزشی کوتاه با CTA مشخص بنویس.",
            cta="اگر این نکته مفید بود ذخیره کن.",
            hashtags=[
                "#رشد_اینستاگرام",
                "#تولید_محتوا",
                "#هوش_مصنوعی",
                "#رشدیار",
            ],
            publish_time=self.ctx.best_time,
            image_prompt=(
                "Instagram modern cover, clean, premium, purple branding, "
                "high contrast, social media post"
            ),
        )

