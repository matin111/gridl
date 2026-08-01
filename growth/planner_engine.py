from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlannerDay:
    title: str
    tasks: list[str]


class PlannerEngine:

    def build(
        self,
        *,
        best_time: str,
        best_content_type: str,
    ) -> list[PlannerDay]:

        return [

            PlannerDay(
                title="امروز",
                tasks=[
                    f"یک {best_content_type} در ساعت {best_time} منتشر کن.",
                    "به ۱۵ کامنت آخر پاسخ بده.",
                    "۵ استوری تعاملی منتشر کن.",
                    "هشتگ‌های پیشنهادی را استفاده کن.",
                ],
            ),

            PlannerDay(
                title="فردا",
                tasks=[
                    "یک محتوای آموزشی آماده کن.",
                    "کاور حرفه‌ای طراحی کن.",
                    "Insight پست قبلی را بررسی کن.",
                ],
            ),

            PlannerDay(
                title="این هفته",
                tasks=[
                    "۳ ریلز منتشر کن.",
                    "۲ پست اسلایدی منتشر کن.",
                    "نتایج رشد را تحلیل کن.",
                    "یک بایوی جدید را تست کن.",
                ],
            ),

        ]
