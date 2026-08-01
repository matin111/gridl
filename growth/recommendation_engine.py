from __future__ import annotations

from growth.growth_models import Recommendation


class RecommendationEngine:

    def build(
        self,
        *,
        engagement: float,
        posting_score: int,
        caption_score: int,
        followers: int,
    ) -> list[Recommendation]:

        items: list[Recommendation] = []

        if engagement < 2.5:
            items.append(
                Recommendation(
                    title="افزایش نرخ تعامل",
                    reason="نرخ تعامل کمتر از حد مطلوب است.",
                    priority="high",
                    impact="very_high",
                    estimated_time="20 دقیقه",
                    action="ساخت ریلز آموزشی",
                    target_tool="content_studio",
                )
            )

        if posting_score < 70:
            items.append(
                Recommendation(
                    title="منظم کردن انتشار",
                    reason="بی‌نظمی باعث افت رشد شده است.",
                    priority="high",
                    impact="high",
                    estimated_time="10 دقیقه",
                    action="برنامه‌ریزی انتشار",
                    target_tool="planner",
                )
            )

        if caption_score < 70:
            items.append(
                Recommendation(
                    title="بهبود کپشن",
                    reason="کپشن‌ها قدرت کافی برای جذب مخاطب ندارند.",
                    priority="medium",
                    impact="high",
                    estimated_time="8 دقیقه",
                    action="تولید کپشن",
                    target_tool="caption",
                )
            )

        if followers < 1000:
            items.append(
                Recommendation(
                    title="اعتمادسازی",
                    reason="در این مرحله باید اعتبار پیج را افزایش دهی.",
                    priority="medium",
                    impact="medium",
                    estimated_time="15 دقیقه",
                    action="ساخت محتوای آموزشی",
                    target_tool="content_studio",
                )
            )

        if not items:
            items.append(
                Recommendation(
                    title="ادامه روند فعلی",
                    reason="عملکرد پیج مناسب است.",
                    priority="low",
                    impact="medium",
                    estimated_time="5 دقیقه",
                    action="بررسی ترندهای جدید",
                    target_tool="trend",
                )
            )

        return items
