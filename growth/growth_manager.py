from __future__ import annotations

from dataclasses import dataclass
import re
from growth.growth_models import (
    GrowthManagerResponse,
    Recommendation,
    DailyTask,
    BioDoctor,
    ProfileDoctor,
    HighlightDoctor,
    ReadyToPublish,
    ContentDiagnosis,
    WeeklyRoadmapItem,
    GrowthForecast,
)
from growth.domain_intelligence import (
    DOMAIN_PROFILES,
    DomainDetector,
    content_dna,
    similarity,
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
    recent_media: list[object] | None = None


class GrowthManager:

    def __init__(self, ctx: GrowthContext):
        self.ctx = ctx
        self.media = ctx.recent_media or []
        captions = [str(getattr(item, "caption", "") or "") for item in self.media]
        hashtags = [tag for caption in captions for tag in caption.split() if tag.startswith("#")]
        links = [part for part in ctx.bio.split() if part.startswith(("http://", "https://"))]
        self.domain = DomainDetector().detect(
            biography=ctx.bio, username=ctx.username, display_name=ctx.full_name,
            captions=captions, hashtags=hashtags, external_links=links,
        )
        self.domain_profile = DOMAIN_PROFILES[self.domain.domain]
        self.dna = content_dna(self.media, ctx.best_time)

    def build(self) -> GrowthManagerResponse:
        score = self._growth_score()

        tasks = self._tasks()

        return GrowthManagerResponse(
            executive_summary=self._executive_summary(score),
            growth_score=score,
            daily_focus=self._daily_focus(),
            recommendations=self._recommendations(),
            daily_tasks=tasks,
            daily_missions=tasks,
            content_diagnosis=self._content_diagnosis(),
            weekly_roadmap=self._weekly_roadmap(),
            growth_forecast=self._growth_forecast(),
            bio=self._bio_doctor(),
            profile=self._profile_doctor(),
            highlights=self._highlight_doctor(),
            publish=self._ready_to_publish(),
        )

    def _executive_summary(self, score: int) -> str:
        if score >= 75:
            status = "پایه رشد پیج مناسب است"
        elif score >= 50:
            status = "پیج ظرفیت رشد دارد اما چند مانع قابل اصلاح دیده می‌شود"
        else:
            status = "پیج پیش از افزایش حجم محتوا به اصلاح پایه نیاز دارد"
        return (
            f"{status}. امتیاز رشد {score} از ۱۰۰ است؛ اولویت فعلی: "
            f"{self._daily_focus()}"
        )

    def _content_diagnosis(self) -> ContentDiagnosis:
        engagement = "healthy" if self.ctx.engagement_rate >= 3 else "needs_experiment"
        consistency = "healthy" if self.ctx.posting_consistency >= 65 else "needs_improvement"
        captions = "healthy" if self.ctx.caption_score >= 80 else "needs_improvement"
        return ContentDiagnosis(
            summary=(f"حوزه {self.domain.domain} (زیرحوزه {self.domain.subdomain}) با اطمینان "
                     f"{self.domain.confidence:.0%} تشخیص داده شد؛ خوشه برتر {self.dna['topic']} است."),
            strongest_format=self.ctx.best_content_type or "نامشخص",
            engagement_status=engagement,
            consistency_status=consistency,
            caption_status=captions,
        )

    def _weekly_roadmap(self) -> list[WeeklyRoadmapItem]:
        return [
            WeeklyRoadmapItem(week=1, objective="اصلاح پایه", missions=["به‌روزرسانی بیو", "تعیین سه ستون محتوا"], success_metric="تکمیل پروفایل و تقویم"),
            WeeklyRoadmapItem(week=2, objective="آزمایش محتوا", missions=["انتشار سه محتوای منظم", "آزمایش دو هوک"], success_metric="ثبت عملکرد سه محتوا"),
            WeeklyRoadmapItem(week=3, objective="تقویت تعامل", missions=["CTA مشخص در هر کپشن", "پاسخ به کامنت‌ها"], success_metric="بهبود تعامل نسبت به هفته دوم"),
            WeeklyRoadmapItem(week=4, objective="تکرار الگوی برتر", missions=["مقایسه فرمت‌ها", "بازطراحی بهترین موضوع"], success_metric="شناسایی یک الگوی تکرارپذیر"),
        ]

    def _growth_forecast(self) -> GrowthForecast:
        sample_confidence = "medium" if self.ctx.posts >= 12 else "low"
        return GrowthForecast(
            expected_outcome="در صورت اجرای منظم، امکان بهبود تدریجی تعامل و ثبات انتشار وجود دارد.",
            confidence=sample_confidence,
            assumptions=["اجرای کامل برنامه چهار هفته‌ای", "ثبات موضوع و کیفیت محتوا", "اندازه‌گیری هفتگی نتایج"],
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
        profile = self.domain_profile
        domain = self.domain.domain
        subject = profile.evergreen_topics[0]
        hooks = {
            "VPN": "چرا اینترنتت کند نیست؛ مسیرت اشتباه است.",
            "Restaurant": "این غذا را فقط آخر هفته می‌توانی سفارش بدهی.",
            "Clothing": "این اشتباه ساده، کل استایلت را نامتعادل نشان می‌دهد.",
            "AI": "این پرامپت، کاری را که یک ساعت طول می‌کشید در چند دقیقه انجام می‌دهد.",
            "Marketing": "اگر محتوا داری اما مشتری نه، این بخش قیف را جا انداخته‌ای.",
        }
        hook = hooks.get(domain, f"قبل از انتخاب {subject}، این نکته تخصصی را بدان.")
        entities = self.domain.entities
        product = (entities["products"] or list(profile.products) or [subject])[0]
        caption = (
            f"{hook}\n\nبرای {profile.audience[0]}، انتخاب درست «{product}» فقط به قیمت وابسته نیست. "
            f"{profile.problems[0]} را بررسی کن و بعد سراغ {profile.terminology[0]} برو. "
            f"این راه کوتاه، تصمیمی دقیق‌تر برای {subject} می‌سازد.\n\n{profile.cta}"
        )
        previous = [str(getattr(item, "caption", "") or "") for item in self.media]
        # Deterministic regeneration: use a different knowledge facet until the
        # proposed caption has less than 30% vocabulary overlap with every post.
        if any(similarity(caption, old) >= .30 for old in previous if old):
            caption = (f"راهنمای امروز: {profile.questions[0]}\n\nسه معیار را جداگانه بسنج: "
                       f"{profile.terminology[0]}، {profile.problems[-1]} و {profile.objections[0]}. "
                       f"نتیجه را با نیاز {profile.audience[0]} تطبیق بده.\n\n{profile.cta}")
        tags = list(dict.fromkeys(profile.hashtags))
        # 60% domain, 20% topic and 20% current-context tags.  "Trend" here is
        # constrained to the page's own terminology, never an unrelated trend.
        domain_tags = (tags * 2)[:6]
        topic_tags = ["#" + re.sub(r"\s+", "_", x) for x in profile.evergreen_topics[:2]]
        trend_tags = ["#" + re.sub(r"\s+", "", x) for x in profile.terminology[:2]]
        hashtags = list(dict.fromkeys(domain_tags + topic_tags + trend_tags))
        return ReadyToPublish(
            hook=hook,
            caption=caption,
            cta=profile.cta,
            hashtags=hashtags,
            publish_time=self.dna["publishing_hour"] or self.ctx.best_time,
            image_prompt=(
                f"Premium Instagram cover for {domain}, {subject}, clean layout, "
                f"visual details inspired by {profile.terminology[0]}, high contrast"
            ),
        )
