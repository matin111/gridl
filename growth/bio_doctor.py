from __future__ import annotations

from growth.growth_models import BioDoctor


class BioDoctorEngine:

    def analyze(
        self,
        username: str,
        full_name: str,
        bio: str,
        followers: int,
    ) -> BioDoctor:

        score = 100

        problems = []
        suggestions = []
        ready_bios = []

        bio = (bio or "").strip()

        if len(username) < 4:
            score -= 10
            problems.append("نام کاربری کوتاه است.")

        if "_" in username:
            score -= 3
            suggestions.append("در صورت امکان از نام کاربری ساده‌تر استفاده کن.")

        if len(full_name.strip()) < 3:
            score -= 10
            problems.append("نام پیج کامل نیست.")

        if len(bio) < 35:
            score -= 25
            problems.append("بایو کوتاه است.")

        if "👇" not in bio:
            score -= 5
            suggestions.append("یک CTA با 👇 اضافه کن.")

        if "@" not in bio and "http" not in bio:
            suggestions.append("راه ارتباطی یا لینک اضافه کن.")

        if followers < 1000:
            suggestions.append("فعلاً اعتمادسازی را به فروش ترجیح بده.")

        ready_bios.append(
            "کمک می‌کنم سریع‌تر رشد کنی 🚀\nآموزش + تجربه واقعی\n👇 همین حالا شروع کن"
        )

        ready_bios.append(
            "رشد پیج با هوش مصنوعی\nتحلیل + ایده + محتوا\n👇"
        )

        ready_bios.append(
            "تبدیل بازدیدکننده به مشتری\nروزانه آموزش کاربردی\n👇"
        )

        return BioDoctor(
            score=max(score, 0),
            problems=problems,
            suggestions=suggestions,
            ready_bios=ready_bios,
        )
