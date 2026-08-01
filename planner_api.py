import json
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1/planner",
    tags=["AI Growth Planner"],
)


APP_API_TOKEN = os.getenv(
    "APP_API_TOKEN",
    "",
).strip()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")

OPENAI_PLANNER_MODEL = os.getenv(
    "OPENAI_PLANNER_MODEL",
    os.getenv(
        "OPENAI_TEXT_MODEL",
        os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        ),
    ),
).strip()


# =========================================================
# Schemas
# =========================================================

class PlannerProfileContext(BaseModel):
    username: str = Field(
        default="",
        max_length=150,
    )

    followers_count: int = Field(
        default=0,
        ge=0,
    )

    following_count: int = Field(
        default=0,
        ge=0,
    )

    media_count: int = Field(
        default=0,
        ge=0,
    )

    engagement_rate: float = Field(
        default=0.0,
        ge=0.0,
    )

    performance_score: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    best_publish_time: str = Field(
        default="",
        max_length=100,
    )

    best_content_type: str = Field(
        default="",
        max_length=100,
    )

    # Optional, additive signals supplied by newer Android clients. Older
    # clients can keep sending the original profile shape unchanged.
    detected_domain: str = Field(default="", max_length=200)
    products: list[str] = Field(default_factory=list)
    content_dna: dict[str, Any] = Field(default_factory=dict)
    recent_performance: list[dict[str, Any]] = Field(default_factory=list)


class PlannerRequest(BaseModel):
    goal: Literal[
        "افزایش فالوور",
        "افزایش فروش",
        "افزایش تعامل",
        "افزایش بازدید",
        "برندسازی",
        "آموزش",
    ] = "افزایش فالوور"

    days: Literal[
        7,
        14,
        30,
    ] = 7

    platform: str = Field(
        default="اینستاگرام",
        min_length=2,
        max_length=100,
    )

    business_field: str = Field(
        default="تولید محتوا",
        min_length=2,
        max_length=300,
    )

    target_audience: str = Field(
        default="مخاطبان عمومی",
        min_length=2,
        max_length=500,
    )

    tone: str = Field(
        default="حرفه‌ای و صمیمی",
        min_length=2,
        max_length=100,
    )

    additional_details: str = Field(
        default="",
        max_length=1500,
    )

    profile: PlannerProfileContext | None = None


class PlannerDay(BaseModel):
    day: int
    label: str
    title: str
    description: str
    goal: str
    content_type: str
    topic: str
    best_time: str
    tool: str
    tool_title: str
    action_title: str
    prompt: str
    cta: str
    hashtags: list[str]
    priority: str
    estimated_minutes: int
    completed: bool = False
    # A complete, independently publishable content package. These are
    # additive so the legacy Android mapping above remains wire-compatible.
    hook: str = ""
    short_script: str = ""
    caption: str = ""
    publish_time: str = ""
    engagement_task: str = ""
    kpi: str = ""
    actions: list[str] = Field(
        default_factory=lambda: [
            "copy_full_content",
            "create_content",
            "add_to_calendar",
        ]
    )


class PlannerResponse(BaseModel):
    success: bool
    title: str = ""
    subtitle: str = ""
    goal: str = ""
    platform: str = ""
    duration_days: int = 0
    current_day: int = 1
    progress_percent: int = 0
    days: list[PlannerDay] = []
    source: str = ""
    generated_at: str | None = None
    message: str | None = None


# =========================================================
# Authentication
# =========================================================

def verify_app_token(
    authorization: str | None,
) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است.",
        )

    expected_token = f"Bearer {APP_API_TOKEN}"

    if authorization != expected_token:
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز",
        )


# =========================================================
# OpenAI helpers
# =========================================================

def extract_openai_text(
    response_data: dict[str, Any],
) -> str:
    output_text = response_data.get(
        "output_text"
    )

    if (
        isinstance(output_text, str)
        and output_text.strip()
    ):
        return output_text.strip()

    output = response_data.get(
        "output"
    )

    if not isinstance(output, list):
        return ""

    text_parts: list[str] = []

    for output_item in output:
        if not isinstance(
            output_item,
            dict,
        ):
            continue

        content = output_item.get(
            "content"
        )

        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(
                content_item,
                dict,
            ):
                continue

            text = content_item.get(
                "text"
            )

            if (
                isinstance(text, str)
                and text.strip()
            ):
                text_parts.append(
                    text.strip()
                )

    return "\n".join(
        text_parts
    ).strip()


def planner_json_schema(
    days_count: int,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
            },
            "subtitle": {
                "type": "string",
            },
            "current_day": {
                "type": "integer",
                "minimum": 1,
                "maximum": days_count,
            },
            "days": {
                "type": "array",
                "minItems": days_count,
                "maxItems": days_count,
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "integer",
                        },
                        "label": {
                            "type": "string",
                        },
                        "title": {
                            "type": "string",
                        },
                        "description": {
                            "type": "string",
                        },
                        "goal": {
                            "type": "string",
                        },
                        "content_type": {
                            "type": "string",
                        },
                        "topic": {
                            "type": "string",
                        },
                        "best_time": {
                            "type": "string",
                        },
                        "tool": {
                            "type": "string",
                            "enum": [
                                "content_studio",
                                "image_generate",
                                "image_edit",
                                "hashtag",
                                "analyzer",
                                "planner",
                            ],
                        },
                        "tool_title": {
                            "type": "string",
                        },
                        "action_title": {
                            "type": "string",
                        },
                        "prompt": {
                            "type": "string",
                        },
                        "cta": {
                            "type": "string",
                        },
                        "hashtags": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 8,
                            "items": {
                                "type": "string",
                            },
                        },
                        "priority": {
                            "type": "string",
                            "enum": [
                                "high",
                                "medium",
                                "normal",
                            ],
                        },
                        "estimated_minutes": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 180,
                        },
                        "hook": {"type": "string"},
                        "short_script": {"type": "string"},
                        "caption": {"type": "string"},
                        "publish_time": {"type": "string"},
                        "engagement_task": {"type": "string"},
                        "kpi": {"type": "string"},
                    },
                    "required": [
                        "day",
                        "label",
                        "title",
                        "description",
                        "goal",
                        "content_type",
                        "topic",
                        "best_time",
                        "tool",
                        "tool_title",
                        "action_title",
                        "prompt",
                        "cta",
                        "hashtags",
                        "priority",
                        "estimated_minutes",
                        "hook",
                        "short_script",
                        "caption",
                        "publish_time",
                        "engagement_task",
                        "kpi",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "title",
            "subtitle",
            "current_day",
            "days",
        ],
        "additionalProperties": False,
    }


def build_planner_input(
    request: PlannerRequest,
) -> str:
    profile = request.profile

    profile_text = (
        "اطلاعات تحلیل‌شده‌ای از پیج وجود ندارد."
    )

    if profile is not None:
        profile_text = f"""
نام کاربری:
{profile.username or "نامشخص"}

تعداد دنبال‌کننده:
{profile.followers_count}

تعداد دنبال‌شونده:
{profile.following_count}

تعداد محتوا:
{profile.media_count}

نرخ تعامل تقریبی:
{profile.engagement_rate}

امتیاز عملکرد:
{profile.performance_score}

بهترین زمان انتشار فعلی:
{profile.best_publish_time or "نامشخص"}

بهترین نوع محتوا:
{profile.best_content_type or "نامشخص"}

دامنه تشخیص‌داده‌شده:
{profile.detected_domain or request.business_field}

محصولات یا خدمات:
{json.dumps(profile.products, ensure_ascii=False)}

Content DNA (لحن، ستون‌ها و الگوهای موفق):
{json.dumps(profile.content_dna, ensure_ascii=False)}

عملکرد محتوای اخیر:
{json.dumps(profile.recent_performance, ensure_ascii=False)}
""".strip()

    return f"""
برای کاربر یک برنامه رشد دقیق {request.days} روزه بساز.

هدف اصلی:
{request.goal}

پلتفرم:
{request.platform}

حوزه فعالیت:
{request.business_field}

مخاطب هدف:
{request.target_audience}

لحن برند:
{request.tone}

جزئیات تکمیلی:
{request.additional_details or "ندارد"}

اطلاعات تحلیل پیج:
{profile_text}

قوانین برنامه:
- دقیقاً {request.days} روز تولید کن.
- شماره day از ۱ شروع و پیوسته باشد.
- هر روز یک محتوای کامل و مستقل باشد که همان روز قابل انتشار است؛ هرگز یک محتوا را بین چند روز تقسیم نکن.
- topic، hook، short_script، caption و cta هر روز با تمام روزهای دیگر متفاوت باشد.
- فرمت‌ها را در هفته متنوع کن (ریلز، کاروسل، استوری تعاملی، فروش و اعتمادسازی).
- هیچ روزی صرفاً «نوشتن هوک»، «بهبود کپشن»، تحقیق، آماده‌سازی یا انتشار محتوای روز دیگر نباشد.
- حتی روز تحلیل عملکرد باید مرور کوتاه را همراه با بازآفرینی و انتشار کامل قوی‌ترین موضوع ارائه کند.
- موضوع هر روز مشخص، اختصاصی و قابل استفاده مستقیم باشد.
- hook شروع آماده محتوا، short_script متن/اسلایدهای آماده اجرا و caption کپشن نهایی انتشار باشد.
- engagement_task اقدام مشخص بعد از انتشار و kpi یک معیار قابل اندازه‌گیری همان محتوا باشد.
- از دامنه، محصولات، مخاطب، Content DNA و عملکرد اخیر بالا در تمام برنامه استفاده کن.
- prompt باید آماده ارسال به ابزار مرتبط باشد.
- tool فقط یکی از این مقادیر باشد:
  content_studio
  image_generate
  image_edit
  hashtag
  analyzer
  planner
- برای تولید کپشن، سناریو، ریلز یا پست از content_studio استفاده کن.
- برای ساخت تصویر کاملاً جدید از روی متن، پوستر جدید، کاور جدید یا تصویر تبلیغاتی بدون عکس ورودی از image_generate استفاده کن.
- برای تغییر یک عکس موجود، حذف پس‌زمینه، افزایش کیفیت، تغییر لباس، حذف اشیا یا ویرایش عکس واقعی محصول از image_edit استفاده کن.
- هرگز برای ساخت تصویر جدید از image_edit استفاده نکن.
- اگر فعالیت نیازمند عکس واقعی محصول کاربر است، از image_edit استفاده کن و در action_title بنویس «انتخاب عکس و شروع ویرایش».
- اگر فعالیت فقط با دستور متنی قابل ساخت است، از image_generate استفاده کن و در action_title بنویس «ساخت تصویر با هوش مصنوعی».
- برای ساخت هشتگ از hashtag استفاده کن.
- برای ارزیابی عملکرد از analyzer استفاده کن.
- best_time و publish_time باید برابر و زمان مشخص فارسی مانند «۲۰:۳۰» باشند.
- هشتگ‌ها با # شروع شوند.
- CTA کوتاه و طبیعی باشد.
- estimated_minutes واقع‌بینانه باشد.
- current_day برابر ۱ باشد.
- همه متن‌ها فارسی، طبیعی، کاربردی و غیرتکراری باشند.
""".strip()


async def generate_planner(
    request: PlannerRequest,
) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY روی سرور تنظیم نشده است."
        )

    if not OPENAI_PLANNER_MODEL:
        raise RuntimeError(
            "مدل Planner روی سرور تنظیم نشده است."
        )

    schema = planner_json_schema(
        request.days
    )

    payload = {
        "model": OPENAI_PLANNER_MODEL,
        "instructions": """
تو یک استراتژیست حرفه‌ای رشد و تولید محتوای فارسی هستی.

وظیفه تو ساخت برنامه‌ای اجرایی، دقیق و قابل استفاده مستقیم است.

قوانین:
- پاسخ فقط JSON معتبر مطابق Schema باشد.
- هیچ متن یا توضیحی بیرون JSON ننویس.
- پیشنهادها واقعی، متنوع و قابل اجرا باشند.
- اطلاعات یا آمار ساختگی تولید نکن.
- اگر اطلاعات پیج ناقص بود، برنامه را براساس حوزه فعالیت، هدف و مخاطب بساز.
""".strip(),
        "input": build_planner_input(
            request
        ),
        "temperature": 0.7,
        "max_output_tokens": (
            5000
            if request.days == 7
            else 9000
            if request.days == 14
            else 16000
        ),
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": (
                    f"growth_planner_"
                    f"{request.days}_days"
                ),
                "schema": schema,
                "strict": True,
            }
        },
    }

    timeout = httpx.Timeout(
        connect=30.0,
        read=300.0,
        write=60.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization":
                    f"Bearer {OPENAI_API_KEY}",
                "Content-Type":
                    "application/json",
                "Accept":
                    "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        detail = response.text[:2000]

        try:
            error_data = response.json()
            error_object = error_data.get(
                "error",
                {},
            )

            if isinstance(error_object, dict):
                error_message = error_object.get(
                    "message"
                )

                if error_message:
                    detail = str(
                        error_message
                    )

        except ValueError:
            pass

        raise RuntimeError(
            f"OpenAI Planner error "
            f"{response.status_code}: {detail}"
        )

    try:
        response_data = response.json()

    except ValueError as error:
        raise RuntimeError(
            "پاسخ سرویس Planner معتبر نیست."
        ) from error

    text = extract_openai_text(
        response_data
    )

    if not text:
        raise RuntimeError(
            "خروجی متنی Planner دریافت نشد."
        )

    try:
        parsed = json.loads(
            text
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "خروجی Planner قابل پردازش نیست."
        ) from error

    return parsed


def normalize_planner_days(
    raw_days: Any,
    days_count: int,
) -> list[PlannerDay]:
    if not isinstance(raw_days, list):
        raise RuntimeError(
            "فهرست روزهای برنامه معتبر نیست."
        )

    normalized: list[PlannerDay] = []
    unique_values: dict[str, set[str]] = {
        key: set() for key in ("topic", "hook", "caption", "cta")
    }
    incomplete_actions = (
        "write hook", "improve caption", "publish previous", "نوشتن هوک",
        "بهبود کپشن", "اصلاح کپشن", "فقط هوک", "انتشار محتوای",
    )

    for index, raw_day in enumerate(
        raw_days[:days_count],
        start=1,
    ):
        if not isinstance(raw_day, dict):
            continue

        hashtags = raw_day.get(
            "hashtags",
            [],
        )

        if not isinstance(hashtags, list):
            hashtags = []

        clean_hashtags = []

        for hashtag in hashtags:
            clean_hashtag = str(
                hashtag
            ).strip()

            if not clean_hashtag:
                continue

            if not clean_hashtag.startswith("#"):
                clean_hashtag = (
                    f"#{clean_hashtag}"
                )

            if clean_hashtag not in clean_hashtags:
                clean_hashtags.append(
                    clean_hashtag
                )

        def clean(key: str, fallback: str = "") -> str:
            return str(raw_day.get(key, fallback) or "").strip()

        package = {
            key: clean(key)
            for key in (
                "goal", "content_type", "topic", "hook", "short_script",
                "caption", "cta", "publish_time", "engagement_task", "kpi",
            )
        }
        package["publish_time"] = package["publish_time"] or clean("best_time")
        missing = [key for key, value in package.items() if not value]
        if missing:
            raise RuntimeError(
                f"روز {index} بسته محتوایی کامل ندارد: {', '.join(missing)}"
            )

        task_text = " ".join(
            clean(key).casefold()
            for key in ("title", "description", "goal", "topic", "action_title")
        )
        if any(phrase in task_text for phrase in incomplete_actions):
            raise RuntimeError(f"روز {index} یک اقدام ناقص از محتوای دیگر است.")

        for key in unique_values:
            comparable = package[key].casefold()
            if comparable in unique_values[key]:
                raise RuntimeError(f"مقدار {key} در روز {index} تکراری است.")
            unique_values[key].add(comparable)

        normalized.append(
            PlannerDay(
                day=index,
                label=str(
                    raw_day.get(
                        "label",
                        f"روز {index}",
                    )
                ).strip(),
                title=str(
                    raw_day.get(
                        "title",
                        "",
                    )
                ).strip(),
                description=str(
                    raw_day.get(
                        "description",
                        "",
                    )
                ).strip(),
                goal=package["goal"],
                content_type=package["content_type"],
                topic=package["topic"],
                best_time=package["publish_time"],
                tool=str(
                    raw_day.get(
                        "tool",
                        "content_studio",
                    )
                ).strip(),
                tool_title=str(
                    raw_day.get(
                        "tool_title",
                        "تولید محتوا",
                    )
                ).strip(),
                action_title=str(
                    raw_day.get(
                        "action_title",
                        "شروع",
                    )
                ).strip(),
                prompt=str(
                    raw_day.get(
                        "prompt",
                        "",
                    )
                ).strip(),
                cta=package["cta"],
                hashtags=clean_hashtags,
                priority=str(
                    raw_day.get(
                        "priority",
                        "normal",
                    )
                ).strip(),
                estimated_minutes=int(
                    raw_day.get(
                        "estimated_minutes",
                        30,
                    )
                ),
                completed=False,
                hook=package["hook"],
                short_script=package["short_script"],
                caption=package["caption"],
                publish_time=package["publish_time"],
                engagement_task=package["engagement_task"],
                kpi=package["kpi"],
            )
        )

    if len(normalized) != days_count:
        raise RuntimeError(
            "تعداد روزهای تولیدشده کامل نیست."
        )

    return normalized


# =========================================================
# Endpoints
# =========================================================

@router.get("/templates")
async def planner_templates(
    authorization: str | None = Header(
        default=None
    ),
) -> dict[str, Any]:
    verify_app_token(
        authorization
    )

    return {
        "success": True,
        "goals": [
            "افزایش فالوور",
            "افزایش فروش",
            "افزایش تعامل",
            "افزایش بازدید",
            "برندسازی",
            "آموزش",
        ],
        "durations": [
            {
                "days": 7,
                "title": "برنامه سریع ۷ روزه",
            },
            {
                "days": 14,
                "title": "برنامه حرفه‌ای ۱۴ روزه",
            },
            {
                "days": 30,
                "title": "برنامه کامل ۳۰ روزه",
            },
        ],
        "platforms": [
            "اینستاگرام",
            "تیک‌تاک",
            "تلگرام",
            "یوتیوب",
        ],
    }


@router.post(
    "",
    response_model=PlannerResponse,
)
async def create_planner(
    request: PlannerRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> PlannerResponse:
    verify_app_token(
        authorization
    )

    try:
        generated = await generate_planner(
            request
        )

        days = normalize_planner_days(
            raw_days=generated.get(
                "days"
            ),
            days_count=request.days,
        )

        return PlannerResponse(
            success=True,
            title=str(
                generated.get(
                    "title",
                    f"برنامه رشد {request.days} روزه",
                )
            ).strip(),
            subtitle=str(
                generated.get(
                    "subtitle",
                    (
                        f"برنامه اختصاصی برای "
                        f"{request.goal}"
                    ),
                )
            ).strip(),
            goal=request.goal,
            platform=request.platform,
            duration_days=request.days,
            current_day=max(
                1,
                min(
                    request.days,
                    int(
                        generated.get(
                            "current_day",
                            1,
                        )
                    ),
                ),
            ),
            progress_percent=0,
            days=days,
            source="openai",
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            message="برنامه رشد با موفقیت ساخته شد.",
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "PLANNER ERROR:",
            repr(error),
            flush=True,
        )

        traceback.print_exc()

        return PlannerResponse(
            success=False,
            goal=request.goal,
            platform=request.platform,
            duration_days=request.days,
            source="error",
            message=str(error),
        )


@router.post(
    "/regenerate",
    response_model=PlannerResponse,
)
async def regenerate_planner(
    request: PlannerRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> PlannerResponse:
    return await create_planner(
        request=request,
        authorization=authorization,
    )
