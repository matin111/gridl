from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "instagram_analyzer.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Integration marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n",
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n"
        "from growth.visual_intelligence import enrich_post_intelligence_with_vision\n",
        "visual import",
    )

    text = replace_once(
        text,
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n"
        "        post_intelligence = await enrich_post_intelligence_with_vision(post_intelligence)\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "live vision enrichment",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Visual Intelligence V11 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()
