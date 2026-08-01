from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from instagram_analyzer import (
    InstagramAnalyzeRequest,
    analyze_instagram_profile,
    verify_app_token,
    build_content_director_context,
)


router = APIRouter(
    tags=["AIStudioPro V5"],
)


class DashboardRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=200,
    )

    media_count: int = Field(
        default=12,
        ge=3,
        le=30,
    )

    force_refresh: bool = Field(
        default=False,
    )

    variation_id: int = Field(
        default=0,
        ge=0,
    )


class DashboardHero(BaseModel):
    account_connected: bool
    title: str
    subtitle: str
    recommendation: str
    best_time: str
    performance_score: int
    account_name: str
    account_username: str
    platform: str


class DashboardStat(BaseModel):
    key: str
    title: str
    value: str
    description: str


class DashboardMission(BaseModel):
    time: str
    title: str
    subtitle: str
    priority: Literal[
        "high",
        "medium",
        "low",
    ]
    topic: str = ""
    hook: str = ""
    script: str = ""
    cta: str = ""
    caption: str = ""
    hashtags: list[str] = []
    xp_reward: int = 0
    action_key: str = "content_studio"


class DashboardSuggestion(BaseModel):
    title: str
    description: str
    priority: str


class DashboardInsight(BaseModel):
    title: str
    description: str


class DashboardQuickTool(BaseModel):
    key: str
    title: str
    subtitle: str
    chip: str


class DashboardResponse(BaseModel):
    success: bool
    hero: DashboardHero | None = None
    stats: list[DashboardStat] = []
    missions: list[DashboardMission] = []
    suggestions: list[DashboardSuggestion] = []
    insights: list[DashboardInsight] = []
    quick_tools: list[DashboardQuickTool] = []
    source: str
    message: str | None = None


def compact_number(
    value: float | int,
) -> str:
    number = float(value)

    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"

    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"

    if number >= 1_000:
        return f"{number / 1_000:.1f}K"

    if number.is_integer():
        return str(int(number))

    return f"{number:.2f}"


def readable_content_type(
    content_type: str | None,
) -> str:
    mapping = {
        "reel": "ریلز",
        "video": "ویدیو",
        "carousel": "پست اسلایدی",
        "image": "پست تصویری",
    }

    return mapping.get(
        content_type or "",
        "محتوای ترکیبی",
    )


def get_time_period(
    best_time: str | None,
) -> str:
    if not best_time:
        return "زمان مناسب"

    try:
        normalized_time = (
            str(best_time)
            .strip()
            .replace("۰", "0")
            .replace("۱", "1")
            .replace("۲", "2")
            .replace("۳", "3")
            .replace("۴", "4")
            .replace("۵", "5")
            .replace("۶", "6")
            .replace("۷", "7")
            .replace("۸", "8")
            .replace("۹", "9")
        )

        hour = int(normalized_time.split(":")[0])

    except (ValueError, IndexError):
        return "زمان مناسب"

    if 5 <= hour <= 11:
        return "صبح"

    if 12 <= hour <= 15:
        return "ظهر"

    if 16 <= hour <= 19:
        return "عصر"

    if 20 <= hour <= 23:
        return "شب"

    return "بامداد"


def create_missions(
    best_time: str,
    best_content_type: str,
    suggestions: list,
    *,
    followers_count: int = 0,
    engagement_rate: float = 0.0,
    posting_consistency_score: int = 0,
    caption_usage_score: int = 0,
    average_likes: float = 0.0,
    average_comments: float = 0.0,
    average_views: float = 0.0,
    next_reel=None,
    next_post=None,
    advisor_summary: str | None = None,
) -> list[DashboardMission]:
    """Build one executable V4 growth mission from the strongest available signals."""
    content_type = (
        best_content_type.strip()
        if best_content_type and best_content_type.strip()
        else "ریلز"
    )
    safe_time = (
        best_time.strip()
        if best_time and best_time.strip() and best_time != "اطلاعات کافی نیست"
        else "امروز"
    )
    time_period = get_time_period(best_time) if safe_time != "امروز" else ""

    followers = max(int(followers_count or 0), 0)
    engagement = max(float(engagement_rate or 0.0), 0.0)
    consistency = max(min(int(posting_consistency_score or 0), 100), 0)
    caption_score = max(min(int(caption_usage_score or 0), 100), 0)
    likes = max(float(average_likes or 0.0), 0.0)
    comments = max(float(average_comments or 0.0), 0.0)
    views = max(float(average_views or 0.0), 0.0)
    comment_ratio = comments / likes if likes > 0 else 0.0

    blueprint = next_reel or next_post
    bp_title = str(getattr(blueprint, "title", "") or "").strip()
    bp_hook = str(getattr(blueprint, "hook", "") or "").strip()
    bp_caption = str(getattr(blueprint, "caption", "") or "").strip()
    bp_cta = str(getattr(blueprint, "cta", "") or "").strip()
    bp_hashtags = list(getattr(blueprint, "hashtags", []) or [])
    bp_scenario = list(getattr(blueprint, "scenario", []) or [])

    if bp_title:
        topic = bp_title
    elif consistency < 50:
        topic = f"یک {content_type} ساده درباره مهم‌ترین مشکل مخاطبت"
    elif caption_score < 55:
        topic = f"یک {content_type} آموزشی با شروع کنجکاوکننده"
    elif likes >= 3 and comment_ratio < 0.03:
        topic = f"یک {content_type} سؤال‌محور درباره انتخاب مخاطب"
    elif views > 0 and views < max(100.0, followers * 0.5):
        topic = f"یک {content_type} نتیجه‌محور با نمایش نتیجه در ثانیه اول"
    else:
        topic = f"یک {content_type} کاربردی درباره مشکل اصلی مخاطبت"

    if bp_hook:
        hook = bp_hook
    elif consistency < 50:
        hook = "اگر برای تولید محتوا وقت کم داری، این روش ساده را امتحان کن."
    elif caption_score < 55:
        hook = "بیشتر پیج‌ها همین اشتباه را در شروع محتوا انجام می‌دهند."
    elif comment_ratio < 0.03:
        hook = "تو کدام گزینه را انتخاب می‌کنی؟ قبل از جواب این نکته را ببین."
    elif views > 0 and views < max(100.0, followers * 0.5):
        hook = "نتیجه را اول ببین؛ بعد در چند ثانیه می‌گویم چطور به آن رسیدم."
    else:
        hook = "قبل از اینکه محتوای بعدی را منتشر کنی، این نکته را بدان."

    if bp_scenario:
        script = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(bp_scenario))
    else:
        script = (
            "0 تا 3 ثانیه: هوک را مستقیم بگو و نتیجه را نشان بده.\n"
            "3 تا 10 ثانیه: مشکل اصلی مخاطب را خیلی کوتاه توضیح بده.\n"
            "10 تا 20 ثانیه: سه نکته یا مرحله عملی ارائه کن.\n"
            "20 تا 26 ثانیه: یک مثال یا نتیجه واقعی نشان بده.\n"
            "تا 30 ثانیه: CTA مشخص را بگو."
        )

    if bp_cta:
        cta = bp_cta
    elif comment_ratio < 0.03:
        cta = "نظر یا انتخابت را در کامنت بنویس."
    elif caption_score < 55:
        cta = "این محتوا را ذخیره کن و برای کسی که به آن نیاز دارد بفرست."
    else:
        cta = "ذخیره‌اش کن و برای قسمت بعد پیج را دنبال کن."

    caption = bp_caption or (
        f"{hook}\n\n"
        "این محتوا را کوتاه، واضح و کاربردی نگه دار. "
        "روی یک مشکل مشخص تمرکز کن و هر نکته را با مثال توضیح بده.\n\n"
        f"{cta}"
    )

    hashtags = [str(item).strip() for item in bp_hashtags if str(item).strip()][:12]
    if not hashtags:
        hashtags = [
            "#تولید_محتوا",
            "#رشد_اینستاگرام",
            "#آموزش_اینستاگرام",
            "#ریلز",
            "#کسب_و_کار_آنلاین",
        ]

    reasons: list[str] = []
    if consistency < 50:
        reasons.append(f"امتیاز نظم انتشار {consistency} از 100 است")
    if caption_score < 55:
        reasons.append(f"امتیاز کپشن {caption_score} از 100 است")
    if comment_ratio < 0.03:
        reasons.append("نسبت کامنت به لایک پایین است")
    if views > 0 and views < max(100.0, followers * 0.5):
        reasons.append("بازدید اخیر نسبت به اندازه پیج پایین است")
    if not reasons:
        reasons.append(f"فرمت {content_type} در داده‌های اخیر انتخاب مناسب‌تری است")

    if advisor_summary and advisor_summary.strip():
        coach_reason = advisor_summary.strip()
    else:
        coach_reason = "؛ ".join(reasons[:2]) + "."

    publish_line = (
        f"زمان پیشنهادی انتشار: ساعت {safe_time} در بازه {time_period}."
        if safe_time != "امروز"
        else "زمان پیشنهادی انتشار: امروز در یکی از ساعت‌های ثابت پیج."
    )

    xp_reward = 60 if consistency < 50 or caption_score < 55 else 50
    title = f"مأموریت رشد امروز: {topic}"
    subtitle = (
        f"چرا این مأموریت؟ {coach_reason}\n"
        f"موضوع: {topic}\n"
        f"هوک: {hook}\n"
        f"سناریو: {script}\n"
        f"CTA: {cta}\n"
        f"{publish_line}\n"
        f"پاداش: +{xp_reward} XP"
    )

    return [
        DashboardMission(
            time=safe_time,
            title=title,
            subtitle=subtitle,
            priority="high",
            topic=topic,
            hook=hook,
            script=script,
            cta=cta,
            caption=caption,
            hashtags=hashtags,
            xp_reward=xp_reward,
            action_key="content_studio",
        )
    ]

def _dashboard_variation_index(
    variation_id: int,
    username: str,
    force_refresh: bool,
) -> int:
    """
    یک شماره پایدار برای انتخاب الگوی پیشنهاد تولید می‌کند.

    وقتی variation_id از اندروید ارسال شود، همان مبنا قرار می‌گیرد.
    در حالت عادی نام کاربری باعث می‌شود خروجی هر پیج پایدار باشد.
    """
    clean_username = username.strip().lower()

    if variation_id > 0:
        seed = variation_id
    else:
        seed = sum(
            (index + 1) * ord(char)
            for index, char in enumerate(clean_username)
        )

    if force_refresh:
        seed += 17

    return abs(seed) % 6


def build_dynamic_dashboard_suggestions(
    *,
    username: str,
    best_time: str,
    best_content_type: str,
    engagement_rate: float,
    posts_per_week: float,
    posting_consistency_score: int,
    caption_usage_score: int,
    average_likes: float,
    average_comments: float,
    average_views: float,
    variation_id: int,
    force_refresh: bool,
) -> list[DashboardSuggestion]:
    """
    پیشنهادهای کاربردی و متنوع داشبورد را بر اساس داده واقعی پیج می‌سازد.
    """

    variation = _dashboard_variation_index(
        variation_id=variation_id,
        username=username,
        force_refresh=force_refresh,
    )

    publish_templates = [
        (
            "برنامه انتشار امروز",
            (
                f"امروز یک {best_content_type} آماده کن و نزدیک ساعت "
                f"{best_time} منتشر کن. برای این محتوا فقط روی یک پیام "
                "اصلی تمرکز کن."
            ),
        ),
        (
            "یک محتوای کوتاه منتشر کن",
            (
                f"یک {best_content_type} کوتاه بین ۱۵ تا ۲۵ ثانیه بساز. "
                f"انتشار را برای حدود ساعت {best_time} برنامه‌ریزی کن."
            ),
        ),
        (
            "محتوای امروز را از قبل آماده کن",
            (
                f"موضوع، هوک و دعوت به اقدام یک {best_content_type} را "
                f"قبل از ساعت {best_time} آماده کن تا انتشار منظم‌تر شود."
            ),
        ),
        (
            "امروز روی یک موضوع مشخص تمرکز کن",
            (
                f"برای {best_content_type} امروز فقط یک مشکل واقعی مخاطب "
                f"را توضیح بده و حدود ساعت {best_time} منتشر کن."
            ),
        ),
        (
            "یک محتوای قابل ذخیره بساز",
            (
                f"یک {best_content_type} آموزشی سه‌مرحله‌ای طراحی کن. "
                f"بهترین زمان فعلی پیج برای انتشار نزدیک {best_time} است."
            ),
        ),
        (
            "محتوای کاربردی امروز",
            (
                f"یک {best_content_type} با ساختار «مشکل، راه‌حل، اقدام» "
                f"بساز و انتشار آن را برای ساعت {best_time} قرار بده."
            ),
        ),
    ]

    interaction_templates = [
        (
            "تعامل بیشتری از مخاطب بگیر",
            (
                "در پایان محتوا یک سؤال ساده و مشخص بپرس که پاسخ آن "
                "برای مخاطب آسان باشد. سؤال‌های دوگزینه‌ای معمولاً "
                "کامنت بیشتری ایجاد می‌کنند."
            ),
        ),
        (
            "دعوت به اقدام را قوی‌تر کن",
            (
                "در پایان محتوا به‌جای جمله عمومی، یک اقدام مشخص بخواه؛ "
                "مثلاً «عدد ۱ را کامنت کن» یا «این پست را ذخیره کن»."
            ),
        ),
        (
            "کامنت گرفتن را هدف قرار بده",
            (
                f"میانگین فعلی کامنت حدود {average_comments:.0f} است. "
                "در محتوای بعدی نظر مخاطب را درباره یک انتخاب مشخص بپرس."
            ),
        ),
        (
            "مخاطب را وارد گفتگو کن",
            (
                "در کپشن یک تجربه کوتاه تعریف کن و در پایان از مخاطب "
                "بخواه تجربه مشابه خودش را در کامنت بنویسد."
            ),
        ),
        (
            "برای ذخیره‌شدن محتوا طراحی کن",
            (
                "محتوای بعدی را به شکل چک‌لیست، مراحل انجام کار یا "
                "اشتباهات رایج بساز تا ارزش ذخیره‌کردن داشته باشد."
            ),
        ),
        (
            "هوک و CTA را هماهنگ کن",
            (
                "هوک ابتدای محتوا باید همان وعده‌ای را بدهد که در پایان "
                "به آن پاسخ می‌دهی؛ سپس یک CTA کوتاه و مرتبط اضافه کن."
            ),
        ),
    ]

    content_templates = [
        (
            f"نسخه تازه‌ای از {best_content_type} بساز",
            (
                f"در داده‌های اخیر، {best_content_type} فرمت مناسب‌تری "
                "بوده است. همان موضوع موفق را با هوک و مثال جدید بازسازی کن."
            ),
        ),
        (
            "از بهترین فرمت پیج استفاده کن",
            (
                f"برای محتوای بعدی از فرمت {best_content_type} استفاده کن، "
                "اما موضوع یا زاویه روایت را تکرار نکن."
            ),
        ),
        (
            "یک محتوای سریالی شروع کن",
            (
                f"موضوع موفق پیج را به یک مجموعه سه‌قسمتی در قالب "
                f"{best_content_type} تبدیل کن تا مخاطب برای قسمت بعدی برگردد."
            ),
        ),
        (
            "محتوای آموزشی کوتاه بساز",
            (
                f"یک نکته کاربردی را در قالب {best_content_type} با "
                "سه بخش «اشتباه، اصلاح، نتیجه» توضیح بده."
            ),
        ),
        (
            "موضوع موفق را بازطراحی کن",
            (
                f"یکی از موضوعات قبلی را در قالب {best_content_type} "
                "با عنوان، کاور و شروع متفاوت دوباره تولید کن."
            ),
        ),
        (
            "یک محتوای مقایسه‌ای بساز",
            (
                f"در قالب {best_content_type} دو روش، ابزار یا نتیجه را "
                "مقایسه کن و در پایان از مخاطب بخواه یکی را انتخاب کند."
            ),
        ),
    ]

    publish_title, publish_description = publish_templates[variation]
    interaction_title, interaction_description = interaction_templates[
        (variation + 2) % len(interaction_templates)
    ]
    content_title, content_description = content_templates[
        (variation + 4) % len(content_templates)
    ]

    suggestions: list[DashboardSuggestion] = []

    if posting_consistency_score < 50 or posts_per_week < 2:
        suggestions.append(
            DashboardSuggestion(
                title=publish_title,
                description=publish_description,
                priority="high",
            )
        )
    else:
        suggestions.append(
            DashboardSuggestion(
                title=content_title,
                description=content_description,
                priority="high",
            )
        )

    if engagement_rate < 3 or average_comments < 2:
        suggestions.append(
            DashboardSuggestion(
                title=interaction_title,
                description=interaction_description,
                priority="high",
            )
        )
    else:
        suggestions.append(
            DashboardSuggestion(
                title="تعامل فعلی را حفظ کن",
                description=(
                    f"نرخ تعامل فعلی حدود {engagement_rate:.2f}٪ است. "
                    "ساختار محتوای موفق اخیر را حفظ کن، اما هوک و CTA "
                    "را برای محتوای بعدی تازه بنویس."
                ),
                priority="medium",
            )
        )

    if caption_usage_score < 60:
        suggestions.append(
            DashboardSuggestion(
                title="کپشن کامل‌تری بنویس",
                description=(
                    "کپشن بعدی را با یک جمله شروع‌کننده، دو نکته کاربردی "
                    "و یک دعوت به اقدام مشخص بنویس."
                ),
                priority="medium",
            )
        )
    elif average_views <= average_likes:
        suggestions.append(
            DashboardSuggestion(
                title="شروع ویدیو را جذاب‌تر کن",
                description=(
                    "در دو ثانیه اول نتیجه یا مشکل اصلی را نشان بده. "
                    "مقدمه طولانی را حذف کن تا احتمال ادامه تماشا بیشتر شود."
                ),
                priority="medium",
            )
        )
    else:
        suggestions.append(
            DashboardSuggestion(
                title=content_title,
                description=content_description,
                priority="medium",
            )
        )

    # حذف پیشنهاد تکراری احتمالی
    unique: list[DashboardSuggestion] = []
    seen_titles: set[str] = set()

    for item in suggestions:
        if item.title in seen_titles:
            continue

        seen_titles.add(item.title)
        unique.append(item)

    return unique[:3]



@router.post(
    "/v1/dashboard",
    response_model=DashboardResponse,
)
async def build_online_dashboard(
    request: DashboardRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> DashboardResponse:
    verify_app_token(authorization)

    analysis = await analyze_instagram_profile(
        request=InstagramAnalyzeRequest(
            username=request.username,
            media_count=request.media_count,
        ),
        authorization=authorization,
    )

    if not analysis.success:
        raise HTTPException(
            status_code=502,
            detail=(
                analysis.message
                or "تحلیل پیج برای داشبورد ناموفق بود."
            ),
        )

    profile = analysis.profile
    analytics = analysis.analytics

    if profile is None or analytics is None:
        raise HTTPException(
            status_code=502,
            detail=(
                "اطلاعات کافی برای ساخت داشبورد "
                "دریافت نشد."
            ),
        )

    best_time = (
        analytics.suggested_publish_time
        or "اطلاعات کافی نیست"
    )

    time_period = get_time_period(best_time)


    best_content_type = readable_content_type(
        analytics.best_content_type
    )

    dynamic_suggestions = build_dynamic_dashboard_suggestions(
        username=profile.username,
        best_time=best_time,
        best_content_type=best_content_type,
        engagement_rate=analytics.estimated_engagement_rate,
        posts_per_week=analytics.posts_per_week,
        posting_consistency_score=analytics.posting_consistency_score,
        caption_usage_score=analytics.caption_usage_score,
        average_likes=analytics.average_likes,
        average_comments=analytics.average_comments,
        average_views=analytics.average_views,
        variation_id=request.variation_id,
        force_refresh=request.force_refresh,
    )

    first_suggestion = (
        dynamic_suggestions[0]
        if dynamic_suggestions
        else None
    )

    recommendation = (
        first_suggestion.description
        if first_suggestion
        else (
            f"امروز روی {best_content_type} تمرکز کن و "
            f"حدود ساعت {best_time} ({time_period}) منتشر کن."
        )
    )

    stats = [
        DashboardStat(
            key="followers",
            title="دنبال‌کننده",
            value=compact_number(
                profile.followers_count
            ),
            description="تعداد فعلی دنبال‌کنندگان",
        ),
        DashboardStat(
            key="performance_score",
            title="امتیاز عملکرد",
            value=str(
                max(
                    0,
                    min(
                        int(analytics.public_performance_score),
                        100,
                    ),
                )
            ),
            description="بر اساس اطلاعات عمومی پیج",
        ),
        DashboardStat(
            key="best_time",
            title="بهترین زمان",
            value=best_time,
            description="بر اساس محتواهای موفق اخیر",
        ),
        DashboardStat(
            key="engagement_rate",
            title="نرخ تعامل",
            value=(
                f"{analytics.estimated_engagement_rate:.2f}٪"
            ),
            description="نرخ تعامل تخمینی عمومی",
        ),
        DashboardStat(
            key="average_likes",
            title="میانگین لایک",
            value=compact_number(
                analytics.average_likes
            ),
            description=(
                f"بر اساس "
                f"{analytics.analyzed_media_count} محتوا"
            ),
        ),
        DashboardStat(
            key="average_comments",
            title="میانگین کامنت",
            value=compact_number(
                analytics.average_comments
            ),
            description="میانگین کامنت محتواهای اخیر",
        ),
        DashboardStat(
            key="average_views",
            title="میانگین بازدید",
            value=compact_number(
                analytics.average_views
            ),
            description="میانگین بازدید ویدیوهای اخیر",
        ),
        DashboardStat(
            key="posts_per_week",
            title="انتشار هفتگی",
            value=f"{analytics.posts_per_week:.2f}",
            description="میانگین تعداد محتوا در هفته",
        ),
    ]

    suggestions = dynamic_suggestions

    insights = [
        DashboardInsight(
            title="فرمت محتوای برتر",
            description=(
                f"در میان محتواهای بررسی‌شده، "
                f"{best_content_type} عملکرد بهتری داشته است."
            ),
        ),
        DashboardInsight(
            title="نظم انتشار",
            description=(
                "امتیاز نظم انتشار پیج "
                f"{analytics.posting_consistency_score} "
                "از ۱۰۰ است."
            ),
        ),
        DashboardInsight(
            title="استفاده از کپشن",
            description=(
                "امتیاز استفاده از کپشن در محتواهای اخیر "
                f"{analytics.caption_usage_score} از ۱۰۰ است."
            ),
        ),
    ]

    quick_tools = [
        DashboardQuickTool(
            key="content",
            title="مدیریت محتوا",
            subtitle=(
                f"ساخت کپشن و سناریوی {best_content_type}"
            ),
            chip="AI",
        ),
        DashboardQuickTool(
            key="trend",
            title="ترندهای روز",
            subtitle=(
                f"پیدا کردن موضوع مناسب برای "
                f"{best_content_type}"
            ),
            chip="داغ",
        ),
        DashboardQuickTool(
            key="suggestion",
            title="پیشنهاد هوشمند",
            subtitle=(
                first_suggestion.title
                if first_suggestion
                else "برنامه اختصاصی رشد پیج"
            ),
            chip="آنلاین",
        ),
        DashboardQuickTool(
            key="hashtag",
            title="هشتگ هوشمند",
            subtitle=(
                f"هشتگ مناسب محتوای "
                f"{best_content_type}"
            ),
            chip="رشد",
        ),
    ]

    return DashboardResponse(
        success=True,
        hero=DashboardHero(
            account_connected=True,
            title="سلام 👋",
            subtitle=(
                "تحلیل آنلاین بر اساس اطلاعات واقعی "
                f"@{profile.username}"
            ),
            recommendation=recommendation,
            best_time=best_time,
            performance_score=max(
                0,
                min(
                    int(analytics.public_performance_score),
                    100,
                ),
            ),
            account_name=(
                profile.full_name
                or profile.username
            ),
            account_username=profile.username,
            platform="اینستاگرام",
        ),
        stats=stats,
        missions=create_missions(
            best_time=best_time,
            best_content_type=best_content_type,
            suggestions=dynamic_suggestions,
            followers_count=profile.followers_count,
            engagement_rate=analytics.estimated_engagement_rate,
            posting_consistency_score=(
                analytics.posting_consistency_score
            ),
            caption_usage_score=analytics.caption_usage_score,
            average_likes=analytics.average_likes,
            average_comments=analytics.average_comments,
            average_views=analytics.average_views,
            next_reel=getattr(analysis, "next_reel", None),
            next_post=getattr(analysis, "next_post", None),
            advisor_summary=getattr(analysis, "advisor_summary", None),
        ),
        suggestions=suggestions[:3],
        insights=insights,
        quick_tools=quick_tools,
        source="instagram_ai_growth_coach_v5",
        message=None,
    )


# ---------------------------------------------------------------------------
# Analyze V5
# ---------------------------------------------------------------------------

class AnalyzeV5Request(DashboardRequest):
    """Structured profile-analysis request used by Analyze, Dashboard and Studio."""


class AuditMetric(BaseModel):
    key: str
    title: str
    score: int
    status: Literal["excellent", "good", "warning", "critical"]
    description: str
    recommendation: str


class AuditSection(BaseModel):
    key: str
    title: str
    score: int
    summary: str
    metrics: list[AuditMetric] = []


class GrowthScoreV5(BaseModel):
    score: int
    grade: str
    level: str
    profile_score: int
    content_score: int
    engagement_score: int
    consistency_score: int
    trend_score: int


class AnalyzeRecommendationV5(BaseModel):
    id: str
    priority: Literal["critical", "high", "medium", "low"]
    title: str
    reason: str
    impact: str
    estimated_minutes: int
    difficulty: Literal["easy", "medium", "hard"]
    action_key: str


class NextActionV5(BaseModel):
    order: int
    title: str
    description: str
    action_key: str
    xp_reward: int


class ContentDirectorScenarioStepV5(BaseModel):
    order: int
    time_range: str
    title: str
    instruction: str
    visual_direction: str
    on_screen_text: str


class ContentDirectorV5(BaseModel):
    topic: str
    content_type: str
    goal: str
    hook: str
    scenario: list[ContentDirectorScenarioStepV5] = []
    caption: str
    cta: str
    hashtags: list[str] = []
    publish_time: str
    recommendation_reason: str
    predicted_growth: str
    plan_b: str
    after_publish_actions: list[str] = []
    confidence_score: int
    source_signals: list[str] = []


class AnalyzeV5Response(BaseModel):
    success: bool
    username: str
    full_name: str
    profile_picture_url: str | None = None
    followers_count: int
    following_count: int
    media_count: int
    analyzed_media_count: int
    growth_score: GrowthScoreV5
    profile_audit: AuditSection
    content_audit: AuditSection
    engagement_audit: AuditSection
    posting_audit: AuditSection
    trend_audit: AuditSection
    recommendations: list[AnalyzeRecommendationV5] = []
    next_actions: list[NextActionV5] = []
    content_director: ContentDirectorV5
    dashboard_data: DashboardResponse
    # Additive V6 data; all V5/Android response fields remain unchanged.
    growth_manager: dict[str, Any] | None = None
    evidence_findings: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "instagram_analyze_v5"
    message: str | None = None


def _clamp_score(value: float | int) -> int:
    return max(0, min(int(round(float(value or 0))), 100))


def _metric_status(score: int) -> Literal["excellent", "good", "warning", "critical"]:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 45:
        return "warning"
    return "critical"


def _grade(score: int) -> tuple[str, str]:
    if score >= 90:
        return "A+", "عالی"
    if score >= 80:
        return "A", "خیلی خوب"
    if score >= 70:
        return "B", "خوب"
    if score >= 60:
        return "C", "متوسط"
    if score >= 45:
        return "D", "نیازمند بهبود"
    return "E", "ضعیف"


def _metric(
    key: str,
    title: str,
    score: int,
    description: str,
    recommendation: str,
) -> AuditMetric:
    safe_score = _clamp_score(score)
    return AuditMetric(
        key=key,
        title=title,
        score=safe_score,
        status=_metric_status(safe_score),
        description=description,
        recommendation=recommendation,
    )


def _section(key: str, title: str, metrics: list[AuditMetric]) -> AuditSection:
    score = _clamp_score(sum(item.score for item in metrics) / max(len(metrics), 1))
    weakest = min(metrics, key=lambda item: item.score) if metrics else None
    summary = (
        f"مهم‌ترین فرصت بهبود: {weakest.title}. {weakest.recommendation}"
        if weakest
        else "اطلاعات کافی برای تحلیل وجود ندارد."
    )
    return AuditSection(key=key, title=title, score=score, summary=summary, metrics=metrics)


def _build_recommendations(
    sections: list[AuditSection],
    best_content_type: str,
    best_time: str,
) -> list[AnalyzeRecommendationV5]:
    candidates: list[tuple[int, AuditMetric]] = []
    for section in sections:
        for item in section.metrics:
            candidates.append((item.score, item))
    candidates.sort(key=lambda pair: pair[0])

    result: list[AnalyzeRecommendationV5] = []
    for index, (_, item) in enumerate(candidates[:5], start=1):
        priority: Literal["critical", "high", "medium", "low"]
        if item.score < 35:
            priority = "critical"
        elif item.score < 55:
            priority = "high"
        elif item.score < 75:
            priority = "medium"
        else:
            priority = "low"
        result.append(
            AnalyzeRecommendationV5(
                id=f"rec_{item.key}_{index}",
                priority=priority,
                title=f"بهبود {item.title}",
                reason=item.description,
                impact="افزایش کیفیت محتوا و شانس رشد پیج",
                estimated_minutes=10 + index * 5,
                difficulty="easy" if index <= 2 else "medium",
                action_key="content_studio" if item.key in {"caption", "content", "views", "engagement"} else "profile_analyzer",
            )
        )

    result.insert(
        0,
        AnalyzeRecommendationV5(
            id="rec_publish_next",
            priority="high",
            title=f"یک {best_content_type} جدید آماده کن",
            reason=f"فرمت برتر پیج {best_content_type} است و زمان مناسب فعلی {best_time} تشخیص داده شد.",
            impact="افزایش احتمال بازدید و تعامل محتوای بعدی",
            estimated_minutes=30,
            difficulty="medium",
            action_key="content_studio",
        ),
    )
    return result[:6]


def _build_next_actions(best_content_type: str, best_time: str) -> list[NextActionV5]:
    return [
        NextActionV5(order=1, title=f"ساخت {best_content_type}", description="موضوع، هوک و سناریوی پیشنهادی را در استودیو آماده کن.", action_key="content_studio", xp_reward=40),
        NextActionV5(order=2, title="بهینه‌سازی کپشن", description="یک CTA روشن برای ذخیره، ارسال یا کامنت اضافه کن.", action_key="smart_content", xp_reward=20),
        NextActionV5(order=3, title="انتشار در زمان مناسب", description=f"محتوا را نزدیک ساعت {best_time} منتشر کن.", action_key="planner", xp_reward=25),
        NextActionV5(order=4, title="پاسخ به تعامل‌ها", description="پس از انتشار به کامنت‌ها و پیام‌های مرتبط پاسخ بده.", action_key="engagement", xp_reward=15),
    ]


def _content_topic_from_context(context: dict, content_type: str) -> str:
    biography = str(context.get("biography") or "").strip()
    recent_media = context.get("recent_media") or []
    captions = [str(item.get("caption") or "").strip() for item in recent_media if str(item.get("caption") or "").strip()]
    if captions:
        strongest = max(
            recent_media,
            key=lambda item: float(item.get("like_count") or 0) + float(item.get("comment_count") or 0) * 3 + float(item.get("view_count") or 0) * 0.02,
        )
        caption = str(strongest.get("caption") or "").strip().replace("\n", " ")
        if caption:
            return f"بازطراحی موضوع موفق اخیر: {caption[:90]}"
    if biography:
        return f"یک نکته کاربردی و قابل ذخیره درباره {biography[:80]}"
    return f"یک {content_type} درباره مهم‌ترین مشکل واقعی مخاطب"


def _build_content_director(
    context: dict,
    *,
    best_content_type: str,
    best_time: str,
    growth_score: int,
) -> ContentDirectorV5:
    analytics = context.get("analytics") or {}
    followers = max(int(context.get("followers_count") or 0), 0)
    engagement = max(float(analytics.get("estimated_engagement_rate") or 0.0), 0.0)
    consistency = _clamp_score(analytics.get("posting_consistency_score") or 0)
    caption_score = _clamp_score(analytics.get("caption_usage_score") or 0)
    avg_views = max(float(analytics.get("average_views") or 0.0), 0.0)
    avg_likes = max(float(analytics.get("average_likes") or 0.0), 0.0)
    avg_comments = max(float(analytics.get("average_comments") or 0.0), 0.0)
    comment_ratio = avg_comments / max(avg_likes, 1.0)

    topic = _content_topic_from_context(context, best_content_type)
    is_video = best_content_type in {"ریلز", "ویدیو", "محتوای ترکیبی"}
    content_type = "ریلز ۲۵ تا ۳۵ ثانیه‌ای" if is_video else best_content_type

    if avg_views > 0 and avg_views < max(100.0, followers * 0.45):
        goal = "افزایش بازدید و نگه‌داشت مخاطب"
        hook = "نتیجه را اول ببین؛ بعد در چند ثانیه می‌گویم چطور به آن رسیدم."
    elif comment_ratio < 0.03:
        goal = "افزایش کامنت و تعامل واقعی"
        hook = "تو کدام گزینه را انتخاب می‌کنی؟ قبل از جواب این نکته را ببین."
    elif caption_score < 55:
        goal = "افزایش ذخیره و ارسال محتوا"
        hook = "بیشتر افراد این اشتباه ساده را انجام می‌دهند؛ راه درستش این است."
    else:
        goal = "افزایش اعتماد و تبدیل بازدیدکننده به دنبال‌کننده"
        hook = "قبل از محتوای بعدی، این نکته کاربردی را از دست نده."

    scenario = [
        ContentDirectorScenarioStepV5(order=1, time_range="۰ تا ۳ ثانیه", title="توقف اسکرول", instruction="هوک را بدون مقدمه بگو و نتیجه یا تضاد اصلی را همان ابتدا نشان بده.", visual_direction="نمای نزدیک، حرکت کوتاه دوربین یا نمایش مستقیم نتیجه نهایی.", on_screen_text=hook[:70]),
        ContentDirectorScenarioStepV5(order=2, time_range="۳ تا ۸ ثانیه", title="تعریف مسئله", instruction="مشکل اصلی مخاطب را در یک جمله روشن و قابل هم‌ذات‌پنداری توضیح بده.", visual_direction="نمونه اشتباه یا وضعیت قبل را نمایش بده.", on_screen_text="این اشتباه باعث افت نتیجه می‌شود"),
        ContentDirectorScenarioStepV5(order=3, time_range="۸ تا ۲۰ ثانیه", title="راه‌حل مرحله‌ای", instruction="سه نکته کوتاه و عملی ارائه کن؛ هر نکته باید قابل اجرا باشد.", visual_direction="برای هر نکته کات جدا، عددگذاری و متن بزرگ استفاده کن.", on_screen_text="۱. ساده کن  ۲. مثال بزن  ۳. اقدام بخواه"),
        ContentDirectorScenarioStepV5(order=4, time_range="۲۰ تا ۲۷ ثانیه", title="اثبات و نتیجه", instruction="یک نمونه، نتیجه یا مقایسه قبل و بعد نشان بده تا وعده هوک کامل شود.", visual_direction="مقایسه دو قاب یا نمایش خروجی نهایی.", on_screen_text="نتیجه: واضح‌تر، سریع‌تر، مؤثرتر"),
        ContentDirectorScenarioStepV5(order=5, time_range="۲۷ تا ۳۲ ثانیه", title="دعوت به اقدام", instruction="فقط یک اقدام مشخص از مخاطب بخواه.", visual_direction="نگاه مستقیم به دوربین و نمایش CTA در مرکز تصویر.", on_screen_text="ذخیره کن و نظرت را بنویس"),
    ]

    if comment_ratio < 0.03:
        cta = "انتخابت را در کامنت بنویس: گزینه ۱ یا گزینه ۲؟"
    elif caption_score < 55:
        cta = "این محتوا را ذخیره کن و برای کسی که به آن نیاز دارد بفرست."
    else:
        cta = "برای قسمت بعد پیج را دنبال کن و این پست را ذخیره کن."

    caption = (
        f"{hook}\n\n"
        f"در این محتوا درباره «{topic}» صحبت کردیم. "
        "برای گرفتن نتیجه بهتر، پیام را ساده نگه دار، یک مثال واقعی نشان بده و در پایان فقط یک اقدام مشخص بخواه.\n\n"
        f"{cta}"
    )

    hashtags = ["#تولید_محتوا", "#رشد_اینستاگرام", "#آموزش_اینستاگرام", "#ریلز", "#ایده_محتوا", "#بازاریابی_محتوا", "#کسب_و_کار_آنلاین", "#استراتژی_محتوا"]

    signals = []
    if consistency < 55:
        signals.append(f"نظم انتشار {consistency} از ۱۰۰ است")
    if caption_score < 55:
        signals.append(f"امتیاز استفاده از کپشن {caption_score} از ۱۰۰ است")
    if comment_ratio < 0.03:
        signals.append("نسبت کامنت به لایک پایین است")
    if avg_views > 0 and avg_views < max(100.0, followers * 0.45):
        signals.append("میانگین بازدید نسبت به اندازه پیج پایین است")
    if not signals:
        signals.append(f"{best_content_type} بهترین فرمت محتوای اخیر تشخیص داده شده است")

    recommendation_reason = "؛ ".join(signals[:3]) + "."
    confidence = _clamp_score(55 + min(int(analytics.get("analyzed_media_count") or 0), 12) * 3 + (10 if best_time != "امروز" else 0))

    if growth_score < 45:
        predicted_growth = "با اجرای منظم این برنامه، انتظار می‌رود ابتدا نرخ تعامل و کیفیت بازدید بهتر شود؛ رشد دنبال‌کننده تدریجی خواهد بود."
    elif growth_score < 70:
        predicted_growth = "این محتوا شانس متوسط رو به بالایی برای افزایش ذخیره، کامنت و بازدید نسبت به میانگین فعلی پیج دارد."
    else:
        predicted_growth = "با توجه به عملکرد فعلی، این محتوا شانس بالایی برای عبور از میانگین بازدید و تعامل اخیر پیج دارد."

    plan_b = (
        "اگر در ۶۰ تا ۹۰ دقیقه اول بازدید ضعیف بود، کاور و جمله اول کپشن را اصلاح کن، "
        "در استوری با یک سؤال دوگزینه‌ای معرفی‌اش کن و همان محتوا را حذف و دوباره منتشر نکن."
    )
    after_publish_actions = [
        "در ۱۵ دقیقه اول به اولین کامنت‌ها سریع و کامل پاسخ بده.",
        "۳۰ تا ۶۰ دقیقه بعد محتوا را با یک سؤال مشخص در استوری معرفی کن.",
        "پس از ۲۴ ساعت بازدید، ذخیره، ارسال و کامنت را با میانگین پیج مقایسه کن.",
        "اگر ذخیره یا ارسال بالا بود، همان موضوع را به یک مجموعه سه‌قسمتی تبدیل کن.",
    ]

    return ContentDirectorV5(
        topic=topic,
        content_type=content_type,
        goal=goal,
        hook=hook,
        scenario=scenario,
        caption=caption,
        cta=cta,
        hashtags=hashtags,
        publish_time=best_time,
        recommendation_reason=recommendation_reason,
        predicted_growth=predicted_growth,
        plan_b=plan_b,
        after_publish_actions=after_publish_actions,
        confidence_score=confidence,
        source_signals=signals,
    )


async def _build_dashboard_from_analysis(
    request: AnalyzeV5Request,
    authorization: str | None,
    analysis,
) -> DashboardResponse:
    profile = analysis.profile
    analytics = analysis.analytics
    best_time = analytics.suggested_publish_time or "اطلاعات کافی نیست"
    best_content_type = readable_content_type(analytics.best_content_type)
    dynamic_suggestions = build_dynamic_dashboard_suggestions(
        username=profile.username,
        best_time=best_time,
        best_content_type=best_content_type,
        engagement_rate=analytics.estimated_engagement_rate,
        posts_per_week=analytics.posts_per_week,
        posting_consistency_score=analytics.posting_consistency_score,
        caption_usage_score=analytics.caption_usage_score,
        average_likes=analytics.average_likes,
        average_comments=analytics.average_comments,
        average_views=analytics.average_views,
        variation_id=request.variation_id,
        force_refresh=request.force_refresh,
    )
    first = dynamic_suggestions[0] if dynamic_suggestions else None
    return DashboardResponse(
        success=True,
        hero=DashboardHero(
            account_connected=True,
            title="سلام 👋",
            subtitle=f"تحلیل آنلاین بر اساس اطلاعات واقعی @{profile.username}",
            recommendation=first.description if first else f"امروز روی {best_content_type} تمرکز کن.",
            best_time=best_time,
            performance_score=_clamp_score(analytics.public_performance_score),
            account_name=profile.full_name or profile.username,
            account_username=profile.username,
            platform="اینستاگرام",
        ),
        stats=[
            DashboardStat(key="followers", title="دنبال‌کننده", value=compact_number(profile.followers_count), description="تعداد فعلی دنبال‌کنندگان"),
            DashboardStat(key="performance_score", title="امتیاز عملکرد", value=str(_clamp_score(analytics.public_performance_score)), description="بر اساس اطلاعات عمومی پیج"),
            DashboardStat(key="best_time", title="بهترین زمان", value=best_time, description="بر اساس محتواهای موفق اخیر"),
            DashboardStat(key="engagement_rate", title="نرخ تعامل", value=f"{analytics.estimated_engagement_rate:.2f}٪", description="نرخ تعامل تخمینی عمومی"),
        ],
        missions=create_missions(
            best_time=best_time,
            best_content_type=best_content_type,
            suggestions=dynamic_suggestions,
            followers_count=profile.followers_count,
            engagement_rate=analytics.estimated_engagement_rate,
            posting_consistency_score=analytics.posting_consistency_score,
            caption_usage_score=analytics.caption_usage_score,
            average_likes=analytics.average_likes,
            average_comments=analytics.average_comments,
            average_views=analytics.average_views,
            next_reel=getattr(analysis, "next_reel", None),
            next_post=getattr(analysis, "next_post", None),
            advisor_summary=getattr(analysis, "advisor_summary", None),
        ),
        suggestions=dynamic_suggestions[:3],
        insights=[
            DashboardInsight(title="فرمت محتوای برتر", description=f"{best_content_type} در میان محتواهای اخیر عملکرد بهتری داشته است."),
            DashboardInsight(title="نظم انتشار", description=f"امتیاز نظم انتشار {analytics.posting_consistency_score} از ۱۰۰ است."),
        ],
        quick_tools=[
            DashboardQuickTool(key="content", title="مدیریت محتوا", subtitle=f"ساخت کپشن و سناریوی {best_content_type}", chip="AI"),
            DashboardQuickTool(key="trend", title="ترندهای روز", subtitle="موضوع مناسب برای محتوای بعدی", chip="داغ"),
            DashboardQuickTool(key="hashtag", title="هشتگ هوشمند", subtitle="هشتگ متناسب با موضوع", chip="رشد"),
        ],
        source="instagram_ai_growth_coach_v5",
        message=None,
    )


@router.post("/v2/analyze/profile", response_model=AnalyzeV5Response)
async def analyze_profile_v5(
    request: AnalyzeV5Request,
    authorization: str | None = Header(default=None),
) -> AnalyzeV5Response:
    verify_app_token(authorization)
    analysis = await analyze_instagram_profile(
        request=InstagramAnalyzeRequest(username=request.username, media_count=request.media_count),
        authorization=authorization,
    )
    if not analysis.success:
        raise HTTPException(status_code=502, detail=analysis.message or "تحلیل پیج ناموفق بود.")
    profile = analysis.profile
    analytics = analysis.analytics
    if profile is None or analytics is None:
        raise HTTPException(status_code=502, detail="اطلاعات کافی برای تحلیل دریافت نشد.")

    bio = (getattr(profile, "biography", None) or "").strip()
    full_name = (profile.full_name or "").strip()
    followers = max(int(profile.followers_count or 0), 0)
    following = max(int(getattr(profile, "following_count", 0) or 0), 0)
    media_count = max(int(getattr(profile, "media_count", 0) or 0), 0)
    analyzed_count = max(int(analytics.analyzed_media_count or 0), 0)
    engagement = max(float(analytics.estimated_engagement_rate or 0.0), 0.0)
    avg_views = max(float(analytics.average_views or 0.0), 0.0)
    avg_likes = max(float(analytics.average_likes or 0.0), 0.0)
    avg_comments = max(float(analytics.average_comments or 0.0), 0.0)

    bio_score = _clamp_score(25 + min(len(bio), 100) * 0.55 + (20 if any(x in bio for x in ["خرید", "لینک", "دایرکت", "مشاوره", "ثبت سفارش"]) else 0))
    identity_score = _clamp_score(45 + (25 if full_name else 0) + (15 if getattr(profile, "profile_picture_url", None) else 0))
    branding_score = _clamp_score(50 + (20 if full_name and full_name.lower() != profile.username.lower() else 0) + (10 if bio else 0))
    caption_score = _clamp_score(analytics.caption_usage_score)
    consistency_score = _clamp_score(analytics.posting_consistency_score)
    view_score = _clamp_score((avg_views / max(followers, 1)) * 100)
    interaction_score = _clamp_score(min(100.0, engagement * 8.0))
    comment_score = _clamp_score((avg_comments / max(avg_likes, 1)) * 400)
    frequency_score = _clamp_score(min(float(analytics.posts_per_week or 0.0), 5.0) * 20)
    trend_score = _clamp_score(55 + (15 if analytics.best_content_type in {"reel", "video"} else 0) + min(analyzed_count, 10) * 2)

    profile_audit = _section("profile", "تحلیل پروفایل", [
        _metric("bio", "بیو", bio_score, "وضوح پیام، طول مناسب و وجود CTA بررسی شد.", "در بیو مشخص کن چه کمکی می‌کنی و یک اقدام روشن قرار بده."),
        _metric("identity", "هویت صفحه", identity_score, "نام نمایشی و تصویر پروفایل بررسی شد.", "نام و تصویر را به شکلی انتخاب کن که سریع قابل تشخیص باشند."),
        _metric("branding", "برندینگ", branding_score, "هماهنگی نام، نام کاربری و توضیح صفحه بررسی شد.", "یک کلمه کلیدی اصلی را در نام یا بیو تکرار کن."),
    ])
    content_audit = _section("content", "تحلیل محتوا", [
        _metric("content", "کیفیت کلی محتوا", _clamp_score(analytics.public_performance_score), "عملکرد عمومی محتواهای اخیر بررسی شد.", "موضوعات موفق را به مجموعه‌های چندقسمتی تبدیل کن."),
        _metric("caption", "کپشن", caption_score, "میزان استفاده از کپشن در محتواهای اخیر بررسی شد.", "کپشن را با هوک کوتاه و یک CTA اصلی تمام کن."),
        _metric("views", "قدرت بازدید", view_score, "بازدید میانگین نسبت به اندازه پیج سنجیده شد.", "سه ثانیه اول ریلز و کاور را قوی‌تر کن."),
    ])
    engagement_audit = _section("engagement", "تحلیل تعامل", [
        _metric("engagement", "نرخ تعامل", interaction_score, f"نرخ تعامل تخمینی {engagement:.2f}٪ است.", "از سؤال‌های دوگزینه‌ای و CTA کامنت استفاده کن."),
        _metric("comments", "کیفیت کامنت", comment_score, "نسبت کامنت به لایک بررسی شد.", "در پایان محتوا سؤال ساده و قابل پاسخ بپرس."),
        _metric("likes", "میانگین لایک", _clamp_score((avg_likes / max(followers, 1)) * 800), "میانگین لایک نسبت به دنبال‌کننده‌ها سنجیده شد.", "موضوع و هوک محتوا را بر اساس درد مخاطب انتخاب کن."),
    ])
    posting_audit = _section("posting", "تحلیل انتشار", [
        _metric("consistency", "نظم انتشار", consistency_score, "فاصله زمانی انتشارهای اخیر بررسی شد.", "حداقل دو تا سه محتوای منظم در هفته منتشر کن."),
        _metric("frequency", "تعداد انتشار", frequency_score, f"میانگین انتشار هفتگی {analytics.posts_per_week:.2f} است.", "برای هفته آینده از قبل سه موضوع آماده کن."),
        _metric("publish_time", "زمان انتشار", 80 if analytics.suggested_publish_time else 40, f"زمان پیشنهادی فعلی {analytics.suggested_publish_time or 'نامشخص'} است.", "محتوا را نزدیک زمان پیشنهادی منتشر و نتیجه را ثبت کن."),
    ])
    trend_audit = _section("trend", "تحلیل روند و فرمت", [
        _metric("trend", "تناسب با فرمت برتر", trend_score, f"فرمت برتر فعلی {readable_content_type(analytics.best_content_type)} تشخیص داده شد.", "در کنار فرمت برتر، هوک و ساختار سریالی استفاده کن."),
        _metric("sample_size", "اعتبار نمونه", _clamp_score(analyzed_count * 10), f"{analyzed_count} محتوا بررسی شده است.", "برای تحلیل دقیق‌تر تعداد بیشتری از محتواهای اخیر را بررسی کن."),
    ])

    profile_score = profile_audit.score
    content_score = content_audit.score
    engagement_score = engagement_audit.score
    posting_score = posting_audit.score
    trend_final = trend_audit.score
    final_score = _clamp_score(profile_score * 0.15 + content_score * 0.30 + engagement_score * 0.25 + posting_score * 0.15 + trend_final * 0.15)
    grade, level = _grade(final_score)
    best_time = analytics.suggested_publish_time or "امروز"
    best_content_type = readable_content_type(analytics.best_content_type)
    sections = [profile_audit, content_audit, engagement_audit, posting_audit, trend_audit]
    dashboard = await _build_dashboard_from_analysis(request, authorization, analysis)
    content_director_context = build_content_director_context(analysis)
    content_director = _build_content_director(
        content_director_context,
        best_content_type=best_content_type,
        best_time=best_time,
        growth_score=final_score,
    )

    return AnalyzeV5Response(
        success=True,
        username=profile.username,
        full_name=profile.full_name or profile.username,
        profile_picture_url=getattr(profile, "profile_picture_url", None),
        followers_count=followers,
        following_count=following,
        media_count=media_count,
        analyzed_media_count=analyzed_count,
        growth_score=GrowthScoreV5(
            score=final_score,
            grade=grade,
            level=level,
            profile_score=profile_score,
            content_score=content_score,
            engagement_score=engagement_score,
            consistency_score=posting_score,
            trend_score=trend_final,
        ),
        profile_audit=profile_audit,
        content_audit=content_audit,
        engagement_audit=engagement_audit,
        posting_audit=posting_audit,
        trend_audit=trend_audit,
        recommendations=_build_recommendations(sections, best_content_type, best_time),
        next_actions=_build_next_actions(best_content_type, best_time),
        content_director=content_director,
        dashboard_data=dashboard,
        growth_manager=analysis.growth_manager,
        evidence_findings=analysis.evidence_findings,
        source="instagram_analyze_v5",
        message=None,
    )
