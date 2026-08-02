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
        '_CONTRAST_RE = re.compile(\n    r"(?:اما|ولی|درحالی|برخلاف|واقعیت|فکر می.?کنی|vs|versus)",\n    re.IGNORECASE,\n)\n',
        '_CONTRAST_RE = re.compile(\n'
        '    r"(?:(?<![\\w\\u0600-\\u06FF])(?:اما|ولی|درحالی|برخلاف|واقعیت|vs|versus)"\n'
        '    r"(?![\\w\\u0600-\\u06FF])|فکر می.?کنی)",\n'
        '    re.IGNORECASE,\n'
        ')\n',
        "contrast regex",
    )

    TARGET.write_text(source, encoding="utf-8")
    print("Content Audit V10 Persian contrast regex fixed")


if __name__ == "__main__":
    main()
