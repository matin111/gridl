"""Deterministic, domain-aware content intelligence for Analyzer V7.

The engine deliberately uses only observed profile/post text.  This makes the
fallback content director useful even when an LLM is unavailable and prevents
unrelated marketing vocabulary leaking into every recommendation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DomainProfile:
    keywords: tuple[str, ...]
    audience: tuple[str, ...]
    problems: tuple[str, ...]
    questions: tuple[str, ...]
    objections: tuple[str, ...]
    terminology: tuple[str, ...]
    evergreen_topics: tuple[str, ...]
    products: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ()
    cta: str = "نظرت را در کامنت بنویس."


def _p(keywords, audience, problems, terms, topics, hashtags, cta, products=(), services=()):
    return DomainProfile(tuple(keywords), tuple(audience), tuple(problems),
                         (f"چطور {topics[0]} را بهتر انتخاب کنیم؟",),
                         ("قیمت", "اعتماد", "کیفیت"), tuple(terms), tuple(topics),
                         tuple(products), tuple(services), tuple(hashtags), cta)


# More than twenty built-in profiles; each contains vocabulary and editorial
# knowledge rather than a generic social-media template.
DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "VPN": _p(("vpn", "فیلترشکن", "wireguard", "openvpn", "v2ray", "outline", "cisco", "ip ثابت", "پروکسی"), ("کاربران اینترنت", "گیمرها"), ("قطعی", "پینگ بالا", "حریم خصوصی"), ("WireGuard", "OpenVPN", "Cisco", "V2Ray", "Outline", "Dedicated IP"), ("انتخاب پروتکل", "کاهش پینگ", "امنیت اتصال"), ("#VPN", "#WireGuard", "#OpenVPN", "#CiscoVPN", "#DedicatedIP", "#GamingVPN", "#NetflixVPN", "#Privacy"), "نوع دستگاهت را کامنت کن تا پروتکل مناسب را پیشنهاد بدهیم.", ("IP ثابت", "Gaming VPN", "Netflix VPN"), ("اتصال امن", "کاهش پینگ")),
    "Restaurant": _p(("restaurant", "رستوران", "غذا", "منو", "کباب", "پیتزا", "فود"), ("خانواده‌ها", "علاقه‌مندان غذا"), ("انتخاب غذا", "رزرو", "تازگی"), ("منو", "سرآشپز", "مواد تازه"), ("پشت صحنه آشپزخانه", "غذای ویژه", "معرفی منو"), ("#Restaurant", "#Food", "#Chef", "#FreshFood", "#رستوران", "#غذای_تازه"), "برای رزرو میز همین حالا پیام بده.", services=("سرو غذا", "رزرو میز")),
    "Coffee": _p(("coffee", "cafe", "کافه", "قهوه", "اسپرسو", "لاته"), ("قهوه‌دوستان",), ("تلخی", "انتخاب دانه"), ("Arabica", "Espresso", "Roast"), ("دم‌آوری", "شناخت دانه"), ("#Coffee", "#Espresso", "#SpecialtyCoffee", "#کافه", "#قهوه"), "قهوه محبوبت را کامنت کن.", ("قهوه", "دانه قهوه")),
    "Real Estate": _p(("real estate", "املاک", "ملک", "آپارتمان", "ویلا", "رهن"), ("خریداران ملک", "سرمایه‌گذاران"), ("قیمت‌گذاری", "سند"), ("رهن", "سند", "متراژ"), ("راهنمای خرید", "بررسی محله"), ("#RealEstate", "#Property", "#املاک", "#خرید_خانه"), "برای دریافت فایل‌های مناسب بودجه‌ات دایرکت بده.", services=("خرید ملک", "فروش ملک")),
    "Clothing": _p(("clothing", "fashion", "لباس", "پوشاک", "مانتو", "استایل", "مزون"), ("علاقه‌مندان مد",), ("انتخاب سایز", "ست کردن"), ("استایل", "سایزبندی", "پارچه"), ("راهنمای استایل", "ست فصل", "جنس پارچه"), ("#Fashion", "#Style", "#Clothing", "#استایل", "#پوشاک", "#مانتو"), "برای راهنمای سایز، قد و سایزت را دایرکت کن.", ("مانتو", "لباس", "اکسسوری")),
    "Beauty": _p(("beauty", "زیبایی", "آرایش", "پوست", "میکاپ", "سالن"), ("علاقه‌مندان زیبایی",), ("نوع پوست", "ماندگاری"), ("Skin care", "Makeup"), ("روتین پوست", "آموزش آرایش"), ("#Beauty", "#Skincare", "#Makeup", "#زیبایی", "#مراقبت_پوست"), "نوع پوستت را کامنت کن تا روتین مناسب بگیری.", services=("میکاپ", "مراقبت پوست")),
    "Doctor": _p(("doctor", "پزشک", "دکتر", "کلینیک", "درمان"), ("بیماران",), ("علائم مبهم", "پیشگیری"), ("تشخیص", "درمان", "پیشگیری"), ("نشانه‌های مهم", "پیشگیری"), ("#Doctor", "#Health", "#پزشک", "#سلامت"), "برای ارزیابی تخصصی وقت مشاوره بگیر.", services=("ویزیت", "مشاوره پزشکی")),
    "Dentist": _p(("dentist", "دندانپزشک", "دندان", "ارتودنسی", "ایمپلنت"), ("مراجعان دندانپزشکی",), ("درد دندان", "ترس درمان"), ("Implant", "Orthodontics"), ("بهداشت دهان", "مراقبت پس از درمان"), ("#Dentist", "#DentalCare", "#دندانپزشکی", "#ایمپلنت"), "برای معاینه و انتخاب درمان وقت بگیر.", services=("ایمپلنت", "ارتودنسی")),
    "Lawyer": _p(("lawyer", "وکیل", "حقوقی", "دادگاه", "قرارداد"), ("افراد نیازمند مشاوره حقوقی",), ("ریسک قرارداد", "اختلاف"), ("قرارداد", "دادخواست"), ("نکات قرارداد", "حقوق روزمره"), ("#Lawyer", "#Legal", "#وکیل", "#حقوق"), "موضوع حقوقی‌ات را برای رزرو مشاوره ارسال کن.", services=("مشاوره حقوقی", "وکالت")),
    "Education": _p(("education", "آموزش", "مدرس", "دوره", "کلاس"), ("دانش‌آموزان", "دانشجویان"), ("یادگیری کند", "تمرین"), ("Course", "Learning"), ("درس کوتاه", "تمرین کاربردی"), ("#Education", "#Learning", "#آموزش", "#یادگیری"), "برای دریافت تمرین این درس کلمه «تمرین» را کامنت کن.", services=("دوره آموزشی",)),
    "Programming": _p(("programming", "developer", "برنامه نویسی", "پایتون", "python", "کدنویسی"), ("برنامه‌نویسان",), ("باگ", "مسیر یادگیری"), ("Python", "API", "Git"), ("حل باگ", "پروژه عملی"), ("#Programming", "#Python", "#Developer", "#برنامه_نویسی"), "کد را ذخیره کن و خروجی پروژه‌ات را بفرست.", services=("آموزش برنامه‌نویسی",)),
    "Crypto": _p(("crypto", "کریپتو", "رمزارز", "بیت کوین", "bitcoin", "ترید"), ("سرمایه‌گذاران رمزارز",), ("نوسان", "امنیت کیف پول"), ("Blockchain", "Wallet", "Bitcoin"), ("امنیت دارایی", "مفاهیم بلاکچین"), ("#Crypto", "#Bitcoin", "#Blockchain", "#رمزارز"), "تحلیل خودت را بنویس؛ این محتوا توصیه مالی نیست.", services=("آموزش رمزارز",)),
    "Gaming": _p(("gaming", "game", "گیم", "بازی", "گیمر"), ("گیمرها",), ("لگ", "انتخاب بازی"), ("FPS", "Console", "PC"), ("ترفند بازی", "بررسی بازی"), ("#Gaming", "#Gamer", "#VideoGames", "#گیم"), "اسم بازی بعدی برای بررسی را کامنت کن.", products=("بازی",)),
    "AI": _p(("artificial intelligence", "هوش مصنوعی", "chatgpt", "machine learning", "midjourney", "ai"), ("سازندگان محتوا", "کسب‌وکارها"), ("انتخاب ابزار", "پرامپت ضعیف"), ("ChatGPT", "LLM", "Prompt", "Machine Learning"), ("آموزش پرامپت", "مقایسه ابزارها", "اتوماسیون"), ("#AI", "#ArtificialIntelligence", "#ChatGPT", "#MachineLearning", "#هوش_مصنوعی"), "کلمه «پرامپت» را کامنت کن تا نمونه را بفرستیم.", ("ابزار هوش مصنوعی",), ("اتوماسیون",)),
    "Travel": _p(("travel", "سفر", "تور", "گردشگری", "هتل"), ("مسافران",), ("بودجه سفر", "برنامه‌ریزی"), ("Tour", "Hotel", "Visa"), ("راهنمای مقصد", "سفر اقتصادی"), ("#Travel", "#Tourism", "#سفر", "#گردشگری"), "مقصد بعدی‌ات را کامنت کن.", services=("تور", "رزرو سفر")),
    "Photography": _p(("photography", "photographer", "عکاسی", "عکاس", "دوربین"), ("عکاسان",), ("نور کم", "کادربندی"), ("ISO", "Shutter", "Lens"), ("نورپردازی", "ترکیب‌بندی"), ("#Photography", "#Photographer", "#عکاسی", "#دوربین"), "این تنظیمات را ذخیره و در عکاسی بعدی امتحان کن.", services=("عکاسی",)),
    "Fitness": _p(("fitness", "بدنسازی", "ورزش", "تمرین", "باشگاه"), ("ورزشکاران",), ("فرم اشتباه", "ثبات تمرین"), ("Workout", "Strength", "Recovery"), ("فرم حرکت", "برنامه تمرین"), ("#Fitness", "#Workout", "#بدنسازی", "#تمرین"), "هدفت را کامنت کن تا تمرین مناسب را معرفی کنیم.", services=("برنامه تمرینی",)),
    "Nutrition": _p(("nutrition", "تغذیه", "رژیم", "کالری", "پروتئین"), ("افراد جویای تغذیه سالم",), ("رژیم ناپایدار", "محاسبه کالری"), ("Protein", "Calories", "Macro"), ("بشقاب سالم", "اصول رژیم"), ("#Nutrition", "#HealthyFood", "#تغذیه", "#رژیم"), "هدفت را برای دریافت پیشنهاد عمومی بنویس.", services=("مشاوره تغذیه",)),
    "Marketing": _p(("marketing", "مارکتینگ", "بازاریابی", "اینستاگرام", "تولید محتوا", "سوشال مدیا"), ("صاحبان کسب‌وکار",), ("تعامل کم", "استراتژی مبهم"), ("CTA", "Funnel", "Conversion"), ("استراتژی محتوا", "قیف فروش"), ("#Marketing", "#ContentMarketing", "#SocialMedia", "#بازاریابی_محتوا", "#رشد_اینستاگرام"), "پست را ذخیره کن و هدف پیجت را کامنت کن.", services=("استراتژی محتوا", "مدیریت شبکه اجتماعی")),
    "Agency": _p(("agency", "آژانس", "استودیو", "طراحی سایت", "برندینگ"), ("برندها",), ("انتخاب پیمانکار", "بازگشت سرمایه"), ("Branding", "Campaign", "Brief"), ("مطالعه موردی", "فرآیند پروژه"), ("#Agency", "#Branding", "#CreativeAgency", "#آژانس"), "برای دریافت نمونه‌کار و برآورد پروژه پیام بده.", services=("برندینگ", "طراحی کمپین")),
    "Podcast": _p(("podcast", "پادکست", "اپیزود", "شنوتو", "spotify"), ("شنوندگان پادکست",), ("کشف اپیزود", "زمان شنیدن"), ("Episode", "Spotify", "Audio"), ("خلاصه اپیزود", "گفتگو با مهمان"), ("#Podcast", "#Podcasting", "#پادکست", "#اپیزود"), "اپیزود کامل را بشنو و برداشتت را بنویس.", products=("اپیزود",)),
    "News": _p(("news", "خبر", "اخبار", "رسانه", "گزارش"), ("دنبال‌کنندگان خبر",), ("خبر جعلی", "کمبود زمینه"), ("Report", "Source", "Breaking"), ("توضیح خبر", "راستی‌آزمایی"), ("#News", "#BreakingNews", "#خبر", "#اخبار"), "نظر تحلیلی‌ات را با ذکر دلیل بنویس.", services=("خبررسانی",)),
    "Tech": _p(("tech", "technology", "تکنولوژی", "گجت", "موبایل", "لپ تاپ"), ("علاقه‌مندان فناوری",), ("انتخاب دستگاه", "ارزش خرید"), ("Hardware", "Software", "Benchmark"), ("بررسی محصول", "مقایسه فناوری"), ("#Tech", "#Technology", "#Gadgets", "#تکنولوژی"), "مدل موردنظرت برای مقایسه را کامنت کن.", products=("گجت",)),
    "Ecommerce": _p(("ecommerce", "فروشگاه", "خرید آنلاین", "ارسال", "سبد خرید"), ("خریداران آنلاین",), ("اعتماد خرید", "ارسال"), ("Checkout", "Shipping", "Store"), ("راهنمای خرید", "معرفی محصول"), ("#Ecommerce", "#OnlineShopping", "#فروشگاه_آنلاین", "#خرید_آنلاین"), "برای سفارش روی لینک فروشگاه بزن.", services=("فروش آنلاین",)),
}


@dataclass(slots=True)
class DomainResult:
    domain: str
    subdomain: str
    confidence: float
    entities: dict[str, list[str]] = field(default_factory=dict)


class DomainDetector:
    """Weighted phrase matching across all public profile evidence."""

    def detect(self, *, biography="", username="", display_name="", captions: Iterable[str] = (), hashtags: Iterable[str] = (), external_links: Iterable[str] = ()) -> DomainResult:
        identity = f"{username} {display_name} {biography}".lower()
        posts = " ".join(captions).lower()
        extras = " ".join((*hashtags, *external_links)).lower()
        scores: dict[str, float] = {}
        hits: dict[str, list[str]] = {}
        for domain, profile in DOMAIN_PROFILES.items():
            found = []
            score = 0.0
            for keyword in profile.keywords:
                key = keyword.lower()
                if key in identity:
                    score += 4
                    found.append(keyword)
                if key in posts:
                    score += min(3, posts.count(key))
                    found.append(keyword)
                if key in extras:
                    score += 2
                    found.append(keyword)
            scores[domain] = score
            hits[domain] = list(dict.fromkeys(found))
        domain = max(scores, key=scores.get)
        best = scores[domain]
        if best == 0:
            domain = "Ecommerce"
        total = sum(scores.values())
        confidence = round(min(.99, .25 + best / max(8, total + 4)), 2) if best else .2
        subdomain = hits.get(domain, [])[0] if hits.get(domain) else DOMAIN_PROFILES[domain].evergreen_topics[0]
        return DomainResult(domain, subdomain, confidence, extract_entities(f"{identity} {posts}", DOMAIN_PROFILES[domain]))


def extract_entities(text: str, profile: DomainProfile) -> dict[str, list[str]]:
    candidates = (*profile.products, *profile.services, *profile.terminology)
    present = [item for item in candidates if item.lower() in text.lower()]
    hashtags = re.findall(r"#[\w\u0600-\u06ff]+", text)
    cities = re.findall(r"(?:تهران|مشهد|شیراز|اصفهان|تبریز|دبی|Dubai|Tehran)", text, re.I)
    platforms = [x for x in ("Instagram", "Netflix", "Spotify", "Android", "iOS", "Cisco") if x.lower() in text.lower()]
    return {"products": [x for x in present if x in profile.products], "services": [x for x in present if x in profile.services], "brands": platforms, "cities": list(dict.fromkeys(cities)), "countries": [], "technologies": [x for x in present if x in profile.terminology], "platforms": platforms, "competitors": [], "audience": list(profile.audience), "hashtags": hashtags}


CLUSTERS = {
    "Offers": ("تخفیف", "فروش", "offer", "قیمت"), "Tutorials": ("آموزش", "چطور", "راهنما", "ترفند"),
    "Problems": ("مشکل", "اشتباه", "چرا", "خطا"), "Comparisons": ("مقایسه", "بهتر", "vs"),
    "Reviews": ("بررسی", "نقد", "review"), "Announcements": ("جدید", "اعلام", "رونمایی"),
    "Seasonal": ("نوروز", "تابستان", "زمستان", "یلدا"), "Questions": ("؟", "سوال"),
    "Entertainment": ("سرگرمی", "طنز", "fun"),
}


def cluster_posts(posts: Iterable[object]) -> dict[str, float]:
    totals, counts = defaultdict(float), Counter()
    for post in posts:
        caption = str(getattr(post, "caption", "") or "").lower()
        cluster = next((name for name, keys in CLUSTERS.items() if any(k in caption for k in keys)), "Education")
        engagement = float(getattr(post, "like_count", 0) or 0) + 2 * float(getattr(post, "comment_count", 0) or 0) + .1 * float(getattr(post, "view_count", 0) or 0)
        totals[cluster] += engagement
        counts[cluster] += 1
    return {name: round(totals[name] / counts[name], 2) for name in counts}


def content_dna(posts: Iterable[object], fallback_time: str) -> dict[str, str]:
    posts = list(posts)
    clusters = cluster_posts(posts)
    topic = max(clusters, key=clusters.get) if clusters else "Education"
    ranked = sorted(posts, key=lambda p: (getattr(p, "like_count", 0) or 0) + 2 * (getattr(p, "comment_count", 0) or 0), reverse=True)
    best = ranked[0] if ranked else None
    caption = str(getattr(best, "caption", "") or "")
    published = str(getattr(best, "published_at", "") or "")
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        day, hour = dt.strftime("%A"), dt.strftime("%H:00")
    except ValueError:
        day, hour = "نامشخص", fallback_time
    return {"topic": topic, "hook": caption.splitlines()[0][:100] if caption else "", "cta": caption.splitlines()[-1][:100] if caption else "", "caption_style": "کوتاه" if len(caption) < 180 else "داستانی", "hashtag_style": "تخصصی", "publishing_hour": hour, "publishing_day": day}


def similarity(a: str | Iterable[str], b: str | Iterable[str]) -> float:
    tokenize = lambda value: set(re.findall(r"[\w\u0600-\u06ff]+", " ".join(value) if not isinstance(value, str) else value.lower()))
    left, right = tokenize(a), tokenize(b)
    return len(left & right) / max(1, len(left | right))
