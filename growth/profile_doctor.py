from __future__ import annotations

from growth.growth_models import ProfileDoctor


class ProfileDoctorEngine:

    def analyze(
        self,
        *,
        followers: int,
        following: int,
        posts: int,
        is_verified: bool,
        profile_picture_url: str | None = None,
    ) -> ProfileDoctor:

        score = 100

        problems = []
        suggestions = []

        if posts < 18:
            score -= 15
            problems.append("تعداد پست‌های پیج هنوز کم است.")
            suggestions.append("حداقل ۳۰ محتوای باکیفیت منتشر کن.")

        if followers < 1000:
            score -= 8
            suggestions.append(
                "در این مرحله روی اعتمادسازی، رضایت مشتری و تولید محتوای آموزشی تمرکز کن."
            )

        if following > followers * 2 and followers > 0:
            score -= 8
            problems.append("تعداد Following نسبت به Followers زیاد است.")

        if not is_verified:
            suggestions.append(
                "در صورت داشتن برند، احراز هویت اینستاگرام را بررسی کن."
            )

        if not profile_picture_url:
            score -= 12
            problems.append("تصویر پروفایل در دسترس نیست.")
            suggestions.append("از لوگو یا پرتره با کیفیت بالا استفاده کن.")

        suggestions.extend([
            "از رنگ ثابت برند در تمام کاورها استفاده کن.",
            "فونت پست‌ها را یکدست نگه دار.",
            "هایلایت‌ها را با کاورهای یکسان طراحی کن.",
            "سه پست اول پروفایل باید ارزش صفحه را منتقل کنند.",
        ])

        return ProfileDoctor(
            score=max(score, 0),
            problems=problems,
            suggestions=suggestions,
        )
