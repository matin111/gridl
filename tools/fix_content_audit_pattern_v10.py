from __future__ import annotations

from pathlib import Path

TARGET = Path("growth/content_audit.py")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    source = replace_once(
        source,
        '    weak = [post for post in posts if int(post[field]) < 50]\n',
        '    # A score of exactly 50 is still borderline/weak for comparison.\n'
        '    weak = [post for post in posts if int(post[field]) <= 50]\n',
        "weak sample threshold",
    )

    source = replace_once(
        source,
        '    patterns = [signal for field in ("hook_score", "caption_score", "hashtag_score") if (signal := _correlation_signal(posts, field))]\n',
        '    patterns: list[dict[str, Any]] = []\n'
        '    for field in ("hook_score", "caption_score", "hashtag_score"):\n'
        '        signal = _correlation_signal(posts, field)\n'
        '        if signal is not None:\n'
        '            patterns.append(signal)\n',
        "pattern collection",
    )

    TARGET.write_text(source, encoding="utf-8")
    print("Content Audit V10 pattern regression fixed")


if __name__ == "__main__":
    main()
