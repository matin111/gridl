import unittest

from growth.growth_manager import GrowthContext, GrowthManager


def context(**overrides):
    values = dict(
        username="coffee_shop",
        full_name="فروشگاه قهوه",
        followers=820,
        following=240,
        posts=27,
        engagement_rate=1.35,
        posting_consistency=38,
        caption_score=52,
        best_time="21:00",
        best_content_type="ریلز",
        bio="قهوه تازه برای خانه شما",
        analyzed_media_count=12,
        posts_per_week=1.4,
        average_views=610,
        average_likes=10,
        average_comments=1.2,
        public_performance_score=54,
    )
    values.update(overrides)
    return GrowthContext(**values)


class GrowthManagerV6Tests(unittest.TestCase):
    def test_complete_v6_contract_and_signal_grounding(self):
        result = GrowthManager(context()).build()

        self.assertEqual(result.version, 6)
        self.assertIn("12 محتوای", result.executive_summary)
        self.assertEqual(len(result.bio.ready_bios), 3)
        self.assertEqual(len(result.daily_tasks), 3)
        self.assertEqual(len(result.weekly_roadmap), 7)
        self.assertIsNotNone(result.content_diagnosis)
        self.assertIsNotNone(result.forecast)
        self.assertIn(result.forecast.confidence, {"low", "medium", "high"})
        self.assertIn("تضمین", result.forecast.caveat)
        for recommendation in result.recommendations:
            self.assertTrue(recommendation.teaching)
            self.assertTrue(recommendation.source_signals)
            self.assertTrue(all(signal.key and signal.value for signal in recommendation.source_signals))

    def test_bios_and_recommendations_are_profile_specific(self):
        result = GrowthManager(context(full_name="آکادمی زبان", bio="آموزش زبان")).build()

        self.assertTrue(all("آکادمی زبان" in bio for bio in result.bio.ready_bios))
        reasons = " ".join(item.reason for item in result.recommendations)
        self.assertIn("38/100", reasons)
        self.assertIn("1.35٪", reasons)

    def test_content_director_output_is_reused(self):
        director = {
            "topic": "راهنمای انتخاب قهوه",
            "content_type": "پست اسلایدی",
            "hook": "قهوه اشتباه نخرید",
            "scenario": [{"instruction": "سه معیار را نمایش بده"}],
            "caption": "این راهنما را ذخیره کن.",
            "cta": "ذخیره کن",
            "hashtags": ["#قهوه"],
            "publish_time": "19:30",
        }
        result = GrowthManager(context(content_director=director)).build()

        self.assertEqual(result.publish.topic, director["topic"])
        self.assertEqual(result.publish.hook, director["hook"])
        self.assertEqual(result.publish.scenario, ["سه معیار را نمایش بده"])
        self.assertEqual(result.publish.publish_time, "19:30")

    def test_growth_score_is_bounded_for_extreme_inputs(self):
        low = GrowthManager(context(engagement_rate=-10, posting_consistency=-5, caption_score=-2, public_performance_score=-1)).build()
        high = GrowthManager(context(engagement_rate=100, posting_consistency=200, caption_score=200, public_performance_score=200, posts_per_week=100)).build()

        self.assertGreaterEqual(low.growth_score, 0)
        self.assertLessEqual(high.growth_score, 100)


if __name__ == "__main__":
    unittest.main()
