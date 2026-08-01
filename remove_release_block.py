from pathlib import Path

p = Path("admin/settings.py")

s = p.read_text(encoding="utf-8")


start = """
    <section class="settings-card full">
      <div class="settings-card-head">
        <div>
          <h3 class="settings-card-title">وضعیت آخرین انتشار</h3>
"""

end = """
    <div class="settings-grid">
"""


if start not in s:
    print("start not found")
    exit()


a = s.index(start)
b = s.index(end, a)

s = s[:a] + s[b:]

p.write_text(s, encoding="utf-8")

print("release block removed")

