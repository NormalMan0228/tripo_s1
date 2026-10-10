"""Builds the shareable roadmap from docs/roadmap/roadmap.json.

Writes, side by side so GitHub shows them directly:
  docs/roadmap/README.md      the folder's front page (links to both)
  docs/roadmap/ROADMAP_KO.md  the text roadmap (task lists, dates, history)
  docs/roadmap/VISUAL_KO.md   the picture page
  docs/roadmap/roadmap.png    the picture

The version is the build's date and time in Korea (YYYY.MM.DD-HHMM). Edit roadmap.json, then:
  python tools/build_roadmap.py --note "무엇이 바뀌었는지 한 줄"
Each run with --note adds a history line; without it the latest line gets the new version.
"""
import argparse
import datetime
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs" / "roadmap"
SOURCE = FOLDER / "roadmap.json"
FONTS = Path("C:/Windows/Fonts")
KST = datetime.timezone(datetime.timedelta(hours=9))

STATUS = {
    "done": ("완료", "#5bb36f"),
    "in_progress": ("진행 중", "#e8a838"),
    "next": ("다음", "#4f93dc"),
    "later": ("이후", "#8b97a5"),
    "hold": ("보류", "#b07a7a"),
}
ORDER = ["done", "in_progress", "next", "later", "hold"]


def version_now() -> str:
    return datetime.datetime.now(KST).strftime("%Y.%m.%d-%H%M")


def load(note: str | None) -> dict:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    version = version_now()
    history = data.setdefault("history", [])
    if note:
        history.append({"version": version, "note": note})
    elif history:
        history[-1]["version"] = version
    else:
        history.append({"version": version, "note": "로드맵 갱신"})
    data["version"] = version
    SOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def counts(data: dict) -> dict:
    out = {key: 0 for key in ORDER}
    for phase in data["phases"]:
        for item in phase["items"]:
            out[item["status"]] += 1
    return out


# ------------------------------------------------------------------ text


def text_roadmap(data: dict) -> str:
    c = counts(data)
    total = sum(c.values())
    lines = [
        f"# {data['title']}",
        "",
        f"**버전 {data['version']}** (한국 시각) · {data['subtitle']}",
        "",
        f"> 그림으로 보기: [VISUAL_KO.md](VISUAL_KO.md) · 전체 {total}개 중 완료 {c['done']} · 진행 중 {c['in_progress']} · 다음 {c['next']} · 이후 {c['later']} · 보류 {c['hold']}",
        "",
    ]
    for label, url in data.get("links", []):
        lines.append(f"- [{label}]({url})")
    lines.append("")
    for number, phase in enumerate(data["phases"], 1):
        name, _ = STATUS[phase["status"]]
        period = "" if phase["period"] == name else f" · {phase['period']}"
        lines.append(f"## {phase['name']}  `{name}`{period}")
        lines.append("")
        for item in phase["items"]:
            word, _ = STATUS[item["status"]]
            mark = "x" if item["status"] == "done" else " "
            when = f" ({item['date']})" if item.get("date") else ""
            tag = "" if item["status"] == "done" else f" · *{word}*"
            lines.append(f"- [{mark}] {item['title']}{when}{tag}")
        lines.append("")
    lines += ["## 로드맵 변경 기록", "", "| 버전 (한국 시각) | 바뀐 점 |", "|---|---|"]
    for entry in reversed(data.get("history", [])):
        lines.append(f"| {entry['version']} | {entry['note']} |")
    lines += ["", "<sub>docs/roadmap/roadmap.json을 고친 뒤 `python tools/build_roadmap.py --note \"…\"`로 다시 만듭니다.</sub>", ""]
    return "\n".join(lines)


def visual_page(data: dict) -> str:
    return "\n".join([
        f"# {data['title']} (그림)",
        "",
        f"**버전 {data['version']}** (한국 시각) · 글로 보기: [ROADMAP_KO.md](ROADMAP_KO.md)",
        "",
        f"![Villagen 로드맵 {data['version']}](roadmap.png)",
        "",
        "초록 완료 · 주황 진행 중 · 파랑 다음 · 회색 이후 · 갈색 보류",
        "",
    ])


def index_page(data: dict) -> str:
    c = counts(data)
    return "\n".join([
        f"# {data['title']}",
        "",
        f"**버전 {data['version']}** (한국 시각)",
        "",
        f"- [그림으로 보기](VISUAL_KO.md)",
        f"- [글로 보기](ROADMAP_KO.md) — 완료 {c['done']} · 진행 중 {c['in_progress']} · 다음 {c['next']} · 이후 {c['later']}",
        "",
        f"![로드맵](roadmap.png)",
        "",
    ])


# ------------------------------------------------------------------ picture

W = 1800
PAD = 56
LEFT = 430
BG = "#121c24"
CARD = "#1a2732"
INK = "#f3ead7"
MUTED = "#a9b4bf"
GOLD = "#f0c65a"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (["malgunbd.ttf"] if bold else ["malgun.ttf"]) + ["NotoSansKR-VF.ttf"]:
        path = FONTS / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def blend(hex_color: str, amount: float, base: str = CARD) -> tuple:
    a = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(base[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(round(b[k] + (a[k] - b[k]) * amount) for k in range(3))


def layout_chips(draw, items, width, f):
    """Rows of (x, item, chip width) that wrap inside `width`."""
    rows, row, x = [], [], 0
    for item in items:
        w = int(draw.textlength(item["title"], font=f)) + 58
        if row and x + w > width:
            rows.append(row)
            row, x = [], 0
        row.append((x, item, w))
        x += w + 12
    if row:
        rows.append(row)
    return rows


def picture(data: dict, path: Path) -> None:
    title_f, sub_f, phase_f, small_f, chip_f, pill_f = font(46, True), font(22), font(27, True), font(19), font(20), font(17, True)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    chip_area = W - PAD * 2 - LEFT - 28
    heights = []
    for phase in data["phases"]:
        rows = layout_chips(probe, phase["items"], chip_area, chip_f)
        heights.append(max(118, 30 + len(rows) * 52 + 18))
    top = 250
    height = top + sum(heights) + 14 * len(heights) + 120
    image = Image.new("RGB", (W, height), BG)
    d = ImageDraw.Draw(image)
    # Header
    d.text((PAD, 44), data["title"], fill=INK, font=title_f)
    d.text((PAD, 108), data["subtitle"], fill=MUTED, font=sub_f)
    badge = f"버전 {data['version']} (한국 시각)"
    bw = int(d.textlength(badge, font=pill_f)) + 36
    d.rounded_rectangle((W - PAD - bw, 50, W - PAD, 92), radius=21, fill=blend(GOLD, .22), outline=GOLD, width=2)
    d.text((W - PAD - bw + 18, 59), badge, fill=GOLD, font=pill_f)
    # Progress
    c = counts(data)
    total = max(1, sum(c.values()))
    bar = (PAD, 160, W - PAD, 182)
    d.rounded_rectangle(bar, radius=11, fill="#0c141a")
    x = bar[0]
    for key in ORDER:
        span = (bar[2] - bar[0]) * c[key] / total
        if span > 0:
            d.rounded_rectangle((x, bar[1], x + span, bar[3]), radius=11, fill=STATUS[key][1])
            x += span
    summary = "   ".join(f"{STATUS[k][0]} {c[k]}" for k in ORDER if c[k])
    d.text((PAD, 198), f"전체 {sum(c.values())}개 · {summary}", fill=MUTED, font=small_f)
    # Phases
    y = top
    current_marked = False
    for phase, h in zip(data["phases"], heights):
        word, color = STATUS[phase["status"]]
        if phase["status"] != "done" and not current_marked:
            current_marked = True
            d.line((PAD, y - 7, W - PAD, y - 7), fill=GOLD, width=3)
            tag = "지금 여기"
            tw = int(d.textlength(tag, font=pill_f)) + 28
            d.rounded_rectangle((W - PAD - tw, y - 22, W - PAD, y + 8), radius=15, fill=GOLD)
            d.text((W - PAD - tw + 14, y - 18), tag, fill=BG, font=pill_f)
            y += 14
        d.rounded_rectangle((PAD, y, W - PAD, y + h), radius=18, fill=CARD)
        d.rounded_rectangle((PAD, y, PAD + 10, y + h), radius=5, fill=color)
        d.text((PAD + 34, y + 24), phase["name"], fill=INK, font=phase_f)
        pw = int(d.textlength(word, font=pill_f)) + 28
        d.rounded_rectangle((PAD + 34, y + 70, PAD + 34 + pw, y + 100), radius=15, fill=blend(color, .3), outline=color, width=2)
        d.text((PAD + 48, y + 74), word, fill=INK, font=pill_f)
        if phase["period"] != word: d.text((PAD + 46 + pw, y + 74), phase["period"], fill=MUTED, font=small_f)
        cy = y + 26
        for row in layout_chips(d, phase["items"], chip_area, chip_f):
            for cx, item, cw in row:
                ic = STATUS[item["status"]][1]
                x0 = PAD + LEFT + 14 + cx
                d.rounded_rectangle((x0, cy, x0 + cw, cy + 40), radius=12, fill=blend(ic, .2), outline=blend(ic, .7), width=2)
                if item["status"] == "done":
                    d.line((x0 + 14, cy + 21, x0 + 20, cy + 27, x0 + 31, cy + 13), fill=ic, width=4, joint="curve")
                else:
                    d.ellipse((x0 + 15, cy + 13, x0 + 29, cy + 27), fill=ic)
                d.text((x0 + 42, cy + 8), item["title"], fill=INK, font=chip_f)
            cy += 52
        y += h + 14
    # Legend
    lx = PAD
    for key in ORDER:
        word, color = STATUS[key]
        d.ellipse((lx, y + 34, lx + 18, y + 52), fill=color)
        d.text((lx + 26, y + 30), word, fill=MUTED, font=small_f)
        lx += int(d.textlength(word, font=small_f)) + 70
    d.text((W - PAD - 520, y + 30), "github.com/NormalMan0228/tripo_s1 · docs/roadmap", fill=MUTED, font=small_f)
    image.save(path, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", help="이번 갱신에서 바뀐 점 한 줄 (변경 기록에 추가)")
    args = parser.parse_args()
    data = load(args.note)
    (FOLDER / "ROADMAP_KO.md").write_text(text_roadmap(data), encoding="utf-8")
    (FOLDER / "VISUAL_KO.md").write_text(visual_page(data), encoding="utf-8")
    (FOLDER / "README.md").write_text(index_page(data), encoding="utf-8")
    picture(data, FOLDER / "roadmap.png")
    print("roadmap", data["version"])


if __name__ == "__main__":
    main()
