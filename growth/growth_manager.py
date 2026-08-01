from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from growth.growth_models import (
    BioDoctor, ContentDiagnosis, DailyTask, GrowthForecast,
    GrowthManagerResponse, HighlightDoctor, ProfileDoctor, ReadyToPublish,
    Recommendation, RoadmapDay, SignalEvidence,
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
    profile_picture_url: str | None = None
    analyzed_media_count: int = 0
    posts_per_week: float = 0
    average_views: float = 0
    average_likes: float = 0
    average_comments: float = 0
    public_performance_score: int = 0
    content_director: dict[str, Any] | None = None


class GrowthManager:
    """Deterministic V6 coach. Every prescribed action carries measured evidence."""

    def __init__(self, ctx: GrowthContext):
        self.ctx = ctx

    def _signal(self, key: str, label: str, value: object) -> SignalEvidence:
        return SignalEvidence(key=key, label=label, value=str(value))

    def _core_signals(self) -> list[SignalEvidence]:
        return [
            self._signal("engagement_rate", "نرخ تعامل تخمینی", f"{self.ctx.engagement_rate:.2f}٪"),
            self._signal("posting_consistency", "امتیاز نظم انتشار", f"{self.ctx.posting_consistency}/100"),
            self._signal("caption_score", "امتیاز استفاده از کپشن", f"{self.ctx.caption_score}/100"),
            self._signal("analyzed_media_count", "اندازه نمونه", f"{self.ctx.analyzed_media_count} محتوا"),
        ]

    def _growth_score(self) -> int:
        engagement = min(self.ctx.engagement_rate / 5 * 100, 100)
        activity = min(self.ctx.posts_per_week / 4 * 100, 100)
        score = (
            self.ctx.public_performance_score * .25 + engagement * .25
            + self.ctx.posting_consistency * .20 + self.ctx.caption_score * .15
            + activity * .15
        )
        return max(0, min(100, round(score)))

    def build(self) -> GrowthManagerResponse:
        score = self._growth_score()
        return GrowthManagerResponse(
            executive_summary=self._summary(score), growth_score=score,
            score_explanation="امتیاز از عملکرد عمومی (۲۵٪)، تعامل (۲۵٪)، نظم (۲۰٪)، کپشن (۱۵٪) و تعداد انتشار (۱۵٪) محاسبه شده است.",
            daily_focus=self._daily_focus(), recommendations=self._recommendations(),
            daily_tasks=self._tasks(), bio=self._bio_doctor(),
            profile=self._profile_doctor(), highlights=self._highlight_doctor(),
            content_diagnosis=self._content_diagnosis(), weekly_roadmap=self._roadmap(),
            forecast=self._forecast(), publish=self._ready_to_publish(),
        )

    def _summary(self, score: int) -> str:
        weakest = min((self.ctx.posting_consistency, "نظم انتشار"), (self.ctx.caption_score, "کپشن"), (min(round(self.ctx.engagement_rate * 20), 100), "تعامل"))[1]
        return f"پیج @{self.ctx.username} با امتیاز رشد {score} از ۱۰۰، بیشترین فرصت فوری را در {weakest} دارد؛ این جمع‌بندی بر پایه {self.ctx.analyzed_media_count} محتوای اخیر و نرخ تعامل {self.ctx.engagement_rate:.2f}٪ است، نه تضمین رشد آینده."

    def _daily_focus(self) -> str:
        if self.ctx.posting_consistency < 60:
            return f"امروز یک {self.ctx.best_content_type} برای ساعت {self.ctx.best_time} آماده کن؛ امتیاز نظم تو {self.ctx.posting_consistency}/100 است."
        if self.ctx.caption_score < 70:
            return f"کپشن محتوای بعدی را با سؤال و CTA بازنویسی کن؛ امتیاز کپشن {self.ctx.caption_score}/100 است."
        return f"فرمت موفق {self.ctx.best_content_type} را در ساعت {self.ctx.best_time} تکرار و نتیجه را ثبت کن."

    def _recommendations(self) -> list[Recommendation]:
        candidates: list[tuple[int, Recommendation]] = []
        if self.ctx.posting_consistency < 75:
            s = [self._signal("posting_consistency", "نظم انتشار", f"{self.ctx.posting_consistency}/100"), self._signal("posts_per_week", "انتشار هفتگی", f"{self.ctx.posts_per_week:.1f}")]
            candidates.append((100-self.ctx.posting_consistency, Recommendation(title="تثبیت سه نوبت انتشار", reason=f"نظم {self.ctx.posting_consistency}/100 و میانگین {self.ctx.posts_per_week:.1f} انتشار در هفته ثبت شده است.", priority="critical" if self.ctx.posting_consistency < 40 else "high", impact="افزایش قابلیت مقایسه و شانس توزیع پایدار", estimated_time="۲۰ دقیقه", action="سه نوبت هفته را در تقویم ثبت کن", target_tool="planner", teaching="برنامه ثابت، اثر موضوع و زمان انتشار را قابل اندازه‌گیری می‌کند؛ تغییر هم‌زمان چند متغیر یادگیری را دشوار می‌کند.", source_signals=s)))
        if self.ctx.caption_score < 80:
            s = [self._signal("caption_score", "امتیاز کپشن", f"{self.ctx.caption_score}/100"), self._signal("average_comments", "میانگین کامنت", f"{self.ctx.average_comments:.1f}")]
            candidates.append((90-self.ctx.caption_score, Recommendation(title="بازنویسی کپشن با یک CTA", reason=f"امتیاز کپشن {self.ctx.caption_score}/100 و میانگین کامنت {self.ctx.average_comments:.1f} است.", priority="high", impact="افزایش احتمال کامنت و ذخیره", estimated_time="۱۲ دقیقه", action="کپشن آماده V6 را شخصی‌سازی کن", target_tool="content_studio", teaching="یک سؤال ساده اصطکاک پاسخ را کم می‌کند؛ چند CTA هم‌زمان معمولاً تصمیم مخاطب را سخت می‌کند.", source_signals=s)))
        if self.ctx.engagement_rate < 3:
            s = [self._signal("engagement_rate", "نرخ تعامل", f"{self.ctx.engagement_rate:.2f}٪"), self._signal("best_content_type", "فرمت برتر", self.ctx.best_content_type)]
            candidates.append((round((3-self.ctx.engagement_rate)*20), Recommendation(title=f"آزمون هوک در {self.ctx.best_content_type}", reason=f"نرخ تعامل {self.ctx.engagement_rate:.2f}٪ است و فرمت برتر {self.ctx.best_content_type} تشخیص داده شد.", priority="high", impact="بهبود توقف اسکرول و تعامل", estimated_time="۳۰ دقیقه", action="دو هوک برای یک موضوع بساز", target_tool="content_studio", teaching="با ثابت نگه‌داشتن موضوع و تغییر هوک می‌توان فهمید افت از بسته‌بندی محتواست یا خود موضوع.", source_signals=s)))
        if not candidates:
            candidates.append((1, Recommendation(title="تکرار کنترل‌شده فرمت برتر", reason=f"تعامل {self.ctx.engagement_rate:.2f}٪ و نظم {self.ctx.posting_consistency}/100 نیاز به حفظ روند دارند.", priority="medium", impact="حفظ رشد همراه با یادگیری", estimated_time="۲۰ دقیقه", action="یک نسخه تازه از موضوع موفق بساز", target_tool="content_studio", teaching="تکرار ساختار موفق با موضوع تازه، ریسک آزمایش را کم می‌کند.", source_signals=self._core_signals()[:2])))
        return [item for _, item in sorted(candidates, key=lambda x: x[0], reverse=True)]

    def _tasks(self) -> list[DailyTask]:
        recs = self._recommendations()
        tasks = [DailyTask(title="مأموریت ۱: اقدام اولویت‌دار", description=recs[0].action, priority="high", success_metric="اقدام در ابزار مقصد ثبت شود", teaching=recs[0].teaching, source_signals=recs[0].source_signals)]
        tasks.append(DailyTask(title="مأموریت ۲: انتشار قابل سنجش", description=f"یک {self.ctx.best_content_type} در {self.ctx.best_time} منتشر کن و آمار ۲۴ ساعت را ثبت کن.", priority="high", success_metric="ثبت بازدید، لایک و کامنت پس از ۲۴ ساعت", teaching="ثبت نتیجه، پیشنهاد بعدی را از حدس به آزمایش داده‌محور تبدیل می‌کند.", source_signals=[self._signal("best_content_type", "فرمت برتر", self.ctx.best_content_type), self._signal("best_time", "زمان پیشنهادی", self.ctx.best_time)]))
        tasks.append(DailyTask(title="مأموریت ۳: گفت‌وگوی هدفمند", description="به ۱۰ کامنت اخیر پاسخ بده و در یک استوری سؤال دوگزینه‌ای بپرس.", priority="medium", success_metric="۱۰ پاسخ و یک استوری تعاملی", teaching="گفت‌وگوی مستقیم هم شناخت درد مخاطب می‌سازد و هم ایده محتوای بعدی را آشکار می‌کند.", source_signals=[self._signal("average_comments", "میانگین کامنت", f"{self.ctx.average_comments:.1f}")]))
        return tasks

    def _bio_doctor(self) -> BioDoctor:
        bio = self.ctx.bio.strip(); has_cta = any(x in bio for x in ("👇", "دایرکت", "لینک", "خرید", "رزرو")); has_value = len(bio) >= 35
        score = max(0, 100-(30 if not has_value else 0)-(20 if not has_cta else 0))
        name = self.ctx.full_name or self.ctx.username; niche = name
        signals = [self._signal("bio_length", "طول بایو", f"{len(bio)} نویسه"), self._signal("bio_cta", "CTA بایو", "دارد" if has_cta else "ندارد")]
        return BioDoctor(score=score, problems=(["ارزش پیشنهادی روشن نیست"] if not has_value else [])+(["دعوت به اقدام مشخص نیست"] if not has_cta else []), suggestions=["مخاطب، نتیجه و اقدام بعدی را در سه خط جدا بنویس."], ready_bios=[f"{niche} برای آدم‌های نتیجه‌گرا ✨\nآموزش‌های کوتاه و قابل اجرا\nبرای شروع دایرکت بده 👇", f"کمک می‌کنم در {niche} انتخاب بهتری داشته باشی\nتجربه واقعی + نکته کاربردی\nراهنمای رایگان در لینک 👇", f"هر هفته ایده تازه درباره {niche}\nساده، شفاف و بدون حاشیه\nسؤالت را دایرکت کن 👇"], teaching="سه خط بایو باید به‌ترتیب «برای چه کسی»، «چه نتیجه‌ای» و «قدم بعدی چیست» را پاسخ دهد.", source_signals=signals)

    def _profile_doctor(self) -> ProfileDoctor:
        ratio = self.ctx.following/max(self.ctx.followers, 1); problems=[]; suggestions=[]; score=100
        if not self.ctx.profile_picture_url: score-=25; problems.append("تصویر پروفایل در داده عمومی در دسترس نیست"); suggestions.append("لوگو یا چهره خوانا را در اندازه کوچک آزمایش کن.")
        if ratio > 2: score-=15; problems.append("Following بیش از دو برابر Followers است"); suggestions.append("به‌جای دنبال‌کردن انبوه، جذب مخاطب هدف را با محتوا بسنج.")
        if self.ctx.posts < 12: score-=15; problems.append("کمتر از ۱۲ پست در پروفایل ثبت شده است"); suggestions.append("سه پست سنجاق‌شده برای معرفی، اثبات و شروع آماده کن.")
        if not suggestions: suggestions.append("سه پست سنجاق‌شده را برای معرفی، اثبات و اقدام بعدی بازبینی کن.")
        return ProfileDoctor(score=max(score,0), problems=problems, suggestions=suggestions, teaching="کاربر در چند ثانیه اول از تصویر، نام و سه پست سنجاق‌شده درباره اعتبار صفحه تصمیم می‌گیرد.", source_signals=[self._signal("followers_following", "نسبت Following به Followers", f"{ratio:.2f}"), self._signal("media_count", "تعداد پست", self.ctx.posts), self._signal("profile_picture", "تصویر پروفایل", "دارد" if self.ctx.profile_picture_url else "نامشخص")])

    def _highlight_doctor(self) -> HighlightDoctor:
        return HighlightDoctor(score=60, missing=["شروع از اینجا", "نمونه/نتیجه", "سؤالات متداول"], suggestions=["به‌دلیل نبود داده عمومی هایلایت، این موارد را دستی بررسی کن؛ کاورها را یکدست و هر هایلایت را کوتاه نگه دار."])

    def _content_diagnosis(self) -> ContentDiagnosis:
        problems=[]
        if self.ctx.posting_consistency < 70: problems.append(f"نظم انتشار {self.ctx.posting_consistency}/100 است.")
        if self.ctx.caption_score < 70: problems.append(f"امتیاز کپشن {self.ctx.caption_score}/100 است.")
        if self.ctx.engagement_rate < 2.5: problems.append(f"نرخ تعامل تخمینی {self.ctx.engagement_rate:.2f}٪ است.")
        return ContentDiagnosis(score=max(0,min(100,round((self.ctx.public_performance_score+self.ctx.posting_consistency+self.ctx.caption_score)/3))), summary=f"در نمونه {self.ctx.analyzed_media_count}تایی، {self.ctx.best_content_type} فرمت برتر و {self.ctx.best_time} زمان پیشنهادی است.", problems=problems or ["افت بحرانی در سیگنال‌های قابل مشاهده دیده نشد."], opportunities=[f"یک سری سه‌قسمتی با فرمت {self.ctx.best_content_type} بساز.", "موضوع موفق را با دو هوک متفاوت آزمایش کن."], teaching="تشخیص محتوا بر داده عمومی است؛ ذخیره، اشتراک‌گذاری و نگهداشت در دسترس نیستند و باید از Insights اضافه شوند.", source_signals=self._core_signals()+[self._signal("best_content_type", "فرمت برتر", self.ctx.best_content_type)])

    def _roadmap(self) -> list[RoadmapDay]:
        actions=[("خط مبنا", ["آمار فعلی را ثبت کن", "سه موضوع مخاطب را بنویس"], "ثبت یک برگه خط مبنا"), ("پروفایل", ["یکی از سه بایو را شخصی‌سازی کن", "سه پست سنجاق‌شده را مرتب کن"], "بایوی سه‌خطی فعال"), ("تولید", [f"یک {self.ctx.best_content_type} با دو هوک بساز"], "دو نسخه هوک آماده"), ("انتشار", [f"نسخه اول را در {self.ctx.best_time} منتشر کن"], "آمار ساعت اول ثبت شود"), ("تعامل", ["به کامنت‌ها پاسخ بده", "استوری سؤال‌دار منتشر کن"], "حداقل ۱۰ گفت‌وگو"), ("آزمایش", ["هوک دوم را با موضوع مشابه منتشر کن"], "نتیجه قابل مقایسه"), ("بازبینی", ["بازدید و تعامل دو محتوا را مقایسه کن", "برنده هفته بعد را انتخاب کن"], "یک تصمیم مبتنی بر داده")]
        return [RoadmapDay(day=i, title=t, actions=a, success_metric=m, teaching="هر روز فقط یک متغیر اصلی را تغییر بده تا علت نتیجه قابل تشخیص باشد.") for i,(t,a,m) in enumerate(actions,1)]

    def _forecast(self) -> GrowthForecast:
        n=self.ctx.analyzed_media_count; confidence_score=min(85, 30+n*4+(10 if self.ctx.posts_per_week>0 else 0)); confidence="high" if confidence_score>=75 else "medium" if confidence_score>=50 else "low"
        low=max(3, round((100-self._growth_score())*.08)); high=max(low+3, round((100-self._growth_score())*.18))
        return GrowthForecast(expected_improvement=f"در صورت اجرای کامل برنامه، بهبود نسبی حدود {low} تا {high} درصدی در شاخص‌های قابل مشاهده محتمل است.", confidence=confidence, confidence_score=confidence_score, basis=f"{n} محتوای عمومی، نرخ تعامل {self.ctx.engagement_rate:.2f}٪ و نظم {self.ctx.posting_consistency}/100", caveat="این پیش‌بینی تضمین رشد فالوئر یا فروش نیست؛ تغییر الگوریتم، کیفیت اجرا و داده‌های خصوصی Insights می‌توانند نتیجه را تغییر دهند.", source_signals=self._core_signals())

    def _ready_to_publish(self) -> ReadyToPublish:
        cd=self.ctx.content_director or {}; topic=str(cd.get("topic") or f"۳ اشتباه رایج مخاطبان {self.ctx.full_name or self.ctx.username}"); hook=str(cd.get("hook") or f"اگر این ۳ اشتباه را انجام می‌دهی، نتیجه محتوایت را خودت محدود می‌کنی."); scenario=cd.get("scenario") or ["۰–۳ ثانیه: نتیجه نهایی و هوک را نشان بده.", "۳–۱۵ ثانیه: سه اشتباه را با مثال کوتاه بگو.", "۱۵–۲۵ ثانیه: راه‌حل هر اشتباه را نمایش بده.", "پایان: یک سؤال مشخص بپرس."]
        if scenario and isinstance(scenario[0], dict): scenario=[str(x.get("instruction") or x.get("title") or "") for x in scenario]
        return ReadyToPublish(topic=topic, content_type=str(cd.get("content_type") or self.ctx.best_content_type), hook=hook, scenario=scenario, caption=str(cd.get("caption") or f"این سه اشتباه باعث می‌شود محتوای خوب کمتر دیده شود.\n\nکدام مورد را بیشتر انجام می‌دادی؟ شماره‌اش را کامنت کن تا برای همان مورد راه‌حل دقیق‌تر بسازم."), cta=str(cd.get("cta") or "شماره اشتباه رایج خودت را کامنت کن و پست را ذخیره کن."), hashtags=list(cd.get("hashtags") or ["#تولید_محتوا", "#آموزش_اینستاگرام", "#رشدیار"]), publish_time=str(cd.get("publish_time") or self.ctx.best_time), image_prompt="Persian Instagram cover, clean high-contrast typography, three mistakes concept, brand-consistent colors", teaching=f"فرمت {self.ctx.best_content_type} و زمان {self.ctx.best_time} از عملکرد اخیر انتخاب شده‌اند؛ موضوع را با تجربه واقعی حوزه خودت شخصی‌سازی کن.", source_signals=[self._signal("best_content_type", "فرمت برتر", self.ctx.best_content_type), self._signal("best_time", "زمان پیشنهادی", self.ctx.best_time), self._signal("caption_score", "امتیاز کپشن", f"{self.ctx.caption_score}/100")])
