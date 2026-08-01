from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Insight:

    severity: str

    title: str

    reason: str

    impact: str

    solution: str

    estimated_days: int

    prediction: str


class InsightEngine:

    def analyze(
        self,
        *,
        engagement: float,
        posting_score: int,
        caption_score: int,
        followers: int,
    ) -> list[Insight]:

        insights = []

        if engagement < 2.5:

            insights.append(
                Insight(
                    severity="critical",
                    title="افت نرخ تعامل",
                    reason="کاربران کمتر از قبل لایک، کامنت و ذخیره می‌کنند.",
                    impact="کاهش شانس ورود به اکسپلور",
                    solution="سه ریلز آموزشی + دو پست تعاملی منتشر کن.",
                    estimated_days=7,
                    prediction="در صورت اجرای کامل، احتمال افزایش 15 تا 25 درصدی تعامل وجود دارد.",
                )
            )

        if posting_score < 70:

            insights.append(
                Insight(
                    severity="high",
                    title="بی‌نظمی در انتشار",
                    reason="الگوریتم انتشار منظم را ترجیح می‌دهد.",
                    impact="کاهش Reach",
                    solution="تقویم انتشار را فعال کن.",
                    estimated_days=5,
                    prediction="نرخ نمایش محتوا به مرور افزایش پیدا می‌کند.",
                )
            )

        if caption_score < 70:

            insights.append(
                Insight(
                    severity="medium",
                    title="کپشن ضعیف",
                    reason="دعوت به اقدام کافی وجود ندارد.",
                    impact="کاهش ذخیره و اشتراک‌گذاری",
                    solution="از CTA و Hook قوی استفاده کن.",
                    estimated_days=3,
                    prediction="افزایش نرخ ذخیره پست.",
                )
            )

        if followers < 1000:

            insights.append(
                Insight(
                    severity="low",
                    title="مرحله برندسازی",
                    reason="پیج هنوز در مرحله رشد اولیه است.",
                    impact="اعتماد مخاطب کمتر است.",
                    solution="روی آموزش رایگان و رضایت مشتری تمرکز کن.",
                    estimated_days=14,
                    prediction="رشد پایدارتر دنبال‌کنندگان.",
                )
            )

        return insights
