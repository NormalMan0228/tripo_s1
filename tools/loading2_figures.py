"""Figures for docs/performance/LOADING_2_KO.md (PNG, each kept under ~300 KB).

    .tools/art-venv/Scripts/python.exe tools/loading2_figures.py

Reads docs/performance/data/loading2_measurements.json (tools/summarize_loading.py --json of the
final interleaved runs), texture_caps.json, collision_equivalence.json and, for the picture
figures, the captures under artifacts/ (exterior views, the walkability grid). Writes
docs/performance/img/loading2_*.png. Charts are drawn with Pillow (no plotting library in the
art venv); Korean text uses Malgun Gothic from Windows.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "performance" / "data"
OUT = ROOT / "docs" / "performance" / "img"
ART = ROOT / "artifacts"
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3df"
BEFORE = "#b9b7b0"
AFTER = "#2a78d6"
# Categorical order of the reference palette (slots 1-8), fixed.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CHANGES = [("start -> title", "시작 → 타이틀"), ("title -> home", "타이틀 → 내 집"), ("home -> village", "내 집 → 마을"),
           ("village -> resident's house", "마을 → 주민 집"), ("resident's house -> village", "주민 집 → 마을"),
           ("village -> expedition", "마을 → 탐험"), ("expedition -> village", "탐험 → 마을")]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def save(image: Image.Image, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    image.save(path, optimize=True)
    if path.stat().st_size > 300_000:
        image.convert("P", palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")
    return path


def legend(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[tuple[str, str]]) -> None:
    for colour, label in items:
        draw.rounded_rectangle([x, y + 4, x + 14, y + 18], radius=3, fill=colour)
        draw.text((x + 20, y), label, fill=INK2, font=font(15))
        x += 28 + int(draw.textlength(label, font=font(15))) + 18


def paired_bars(title: str, subtitle: str, rows: list[tuple[str, float, float, list[float], list[float]]], unit: str,
                name: str, before_label: str = "이전 (e4ac621)", after_label: str = "이후") -> Path:
    """Horizontal before/after bars per row: (label, before, after, before range, after range)."""
    width, left, right = 1180, 300, 110
    bar, gap, group = 16, 2, 58
    height = 120 + group * len(rows) + 40
    image = Image.new("RGB", (width, height), SURFACE)
    draw = ImageDraw.Draw(image)
    draw.text((24, 18), title, fill=INK, font=font(24, True))
    draw.text((24, 52), subtitle, fill=INK2, font=font(15))
    legend(draw, 24, 80, [(BEFORE, before_label), (AFTER, after_label)])
    top = 116
    scale_max = max(max(r[1], r[2], *(r[3] or [0]), *(r[4] or [0])) for r in rows) * 1.08 or 1
    span = width - left - right
    for tick in range(0, 6):
        value = scale_max * tick / 5
        x = left + span * tick / 5
        draw.line([x, top - 6, x, height - 34], fill=GRID, width=1)
        draw.text((x - 14, height - 30), f"{value:.1f}" if scale_max < 20 else f"{value:.0f}", fill=MUTED, font=font(13))
    draw.text((width - right + 8, height - 30), unit, fill=MUTED, font=font(13))
    for index, (label, before, after, before_range, after_range) in enumerate(rows):
        y = top + index * group
        draw.text((24, y + 8), label, fill=INK, font=font(16))
        for k, (value, colour, spread) in enumerate([(before, BEFORE, before_range), (after, AFTER, after_range)]):
            by = y + k * (bar + gap)
            x1 = left + span * value / scale_max
            draw.rounded_rectangle([left, by, max(left + 4, x1), by + bar], radius=4, fill=colour)
            if spread and len(spread) > 1:
                lo, hi = left + span * min(spread) / scale_max, left + span * max(spread) / scale_max
                draw.line([lo, by + bar // 2, hi, by + bar // 2], fill=INK2, width=1)
            text = f"{value:.2f}" if scale_max < 20 else f"{value:.0f}"
            draw.text((max(left + 4, x1) + 6, by - 2), text, fill=INK2 if k == 0 else INK, font=font(14, k == 1))
    return save(image, name)


def stacked(title: str, subtitle: str, bars: list[tuple[str, dict]], order: list[tuple[str, str]], name: str) -> Path:
    width, left, right = 1100, 200, 40
    height = 150 + 70 * len(bars) + 30 * ((len(order) + 3) // 4)
    image = Image.new("RGB", (width, height), SURFACE)
    draw = ImageDraw.Draw(image)
    draw.text((24, 18), title, fill=INK, font=font(24, True))
    draw.text((24, 52), subtitle, fill=INK2, font=font(15))
    total_max = max(sum(values.get(key, 0) for key, _ in order) for _, values in bars) * 1.05
    span = width - left - right
    top = 92
    for index, (label, values) in enumerate(bars):
        y = top + index * 70
        draw.text((24, y + 10), label, fill=INK, font=font(16, True))
        x = left
        total = 0.0
        for slot, (key, _) in enumerate(order):
            value = values.get(key, 0.0)
            if value <= 0:
                continue
            w = span * value / total_max
            draw.rectangle([x, y, x + max(w - 2, 1), y + 40], fill=SERIES[slot])
            if w > 46:
                draw.text((x + 6, y + 10), f"{value / 1000:.1f}", fill="#ffffff", font=font(14, True))
            x += w
            total += value
        draw.text((x + 8, y + 10), f"{total / 1000:.1f} s", fill=INK, font=font(15, True))
    ly = top + len(bars) * 70 + 10
    for slot, (_, text) in enumerate(order):
        lx = 24 + (slot % 4) * 265
        yy = ly + (slot // 4) * 28
        draw.rounded_rectangle([lx, yy + 4, lx + 14, yy + 18], radius=3, fill=SERIES[slot])
        draw.text((lx + 20, yy), text, fill=INK2, font=font(14))
    return save(image, name)


def picture_row(title: str, pairs: list[tuple], labels: tuple[str, str], name: str, scale: float = 0.36) -> Path | None:
    """Rows of before/after pictures: (before, after, caption[, crop box as fractions])."""
    tiles = []
    for entry in pairs:
        a, b, caption = entry[:3]
        crop = entry[3] if len(entry) > 3 else None
        if not a.exists() or not b.exists():
            print("missing", a if not a.exists() else b)
            return None
        ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        if crop:
            w, h = ia.size
            box = (int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
            ia, ib = ia.crop(box), ib.crop(box)
        size = (int(ia.width * scale), int(ia.height * scale))
        tiles.append((ia.resize(size, Image.LANCZOS), ib.resize(size, Image.LANCZOS), caption))
    tw = max(t[0].width for t in tiles)
    width = 24 * 2 + tw * 2 + 12
    height = 70 + sum(t[0].height + 40 for t in tiles)
    image = Image.new("RGB", (width, height), SURFACE)
    draw = ImageDraw.Draw(image)
    draw.text((24, 16), title, fill=INK, font=font(20, True))
    draw.text((24, 46), labels[0], fill=INK2, font=font(15, True))
    draw.text((24 + tw + 12, 46), labels[1], fill=INK2, font=font(15, True))
    y = 70
    for a, b, caption in tiles:
        image.paste(a, (24, y))
        image.paste(b, (24 + tw + 12, y))
        draw.text((24, y + a.height + 6), caption, fill=MUTED, font=font(13))
        y += a.height + 40
    image = image.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.FLOYDSTEINBERG)
    return save(image, name)


def main() -> None:
    measured = json.loads((DATA / "loading2_measurements.json").read_text(encoding="utf-8"))
    base, final = measured["bas-gl"], measured["fin-gl"]

    def row(label: str, key: str, field: str = "seconds"):
        b, a = base["changes"][key], final["changes"][key]
        return (label, median(b[field]), median(a[field]), b[field], a[field])

    start_b, start_a = base["changes"]["start -> title"], final["changes"]["start -> title"]
    title_b = [x + y for x, y in zip(start_b["black_s"], start_b["seconds"])]
    title_a = [x + y for x, y in zip(start_a["black_s"], start_a["seconds"])]
    rows = [("검은 화면 (카드가 뜰 때까지)", median(start_b["black_s"]), median(start_a["black_s"]), start_b["black_s"], start_a["black_s"]),
            ("시작 → 타이틀 (검은 화면+카드)", median(title_b), median(title_a), title_b, title_a)]
    rows += [row(label, key) for key, label in CHANGES[1:]]
    paired_bars("장소를 옮길 때 기다리는 시간", "Compatibility 렌더러, 개발 실행(소스), 같은 PC에서 번갈아 3회씩 잰 중앙값(초) · 이동은 로딩 카드가 떠 있던 시간 · 가는 선 = 최소~최대",
                rows, "초", "loading2_times.png")

    rows = [(label, median(base["changes"][key]["over_50ms"]), median(final["changes"][key]["over_50ms"]),
             base["changes"][key]["over_50ms"], final["changes"][key]["over_50ms"]) for key, label in CHANGES]
    paired_bars("로딩 카드가 멈칫한 횟수", "카드가 떠 있는 동안 50 ms(초당 20장)보다 오래 걸린 프레임 수, 중앙값",
                rows, "회", "loading2_hitches.png")

    order = [("black", "검은 화면"), ("reading the game's scripts", "게임 스크립트 읽기"), ("waiting for file reads", "파일 읽기 대기"),
             ("GPU upload + engine", "GPU 업로드·엔진"), ("node assembly", "마을 조립"), ("pad levelling", "건물 터 고르기"),
             ("collision", "충돌 모양 만들기"), ("draw", "그리기(첫 그림 포함)")]

    def phases(summary: dict, key: str) -> dict:
        p = dict(summary["changes"][key]["phases"])
        p["draw"] = p.get("render", 0) + p.get("first render", 0)
        if key == "start -> title":
            p["black"] = median(summary["changes"][key]["black_s"]) * 1000
        return p
    stacked("시작 → 타이틀: 시간이 어디에 쓰였나", "Compatibility, 중앙값(ms 합계를 초로 표시). 카드가 완전히 덮은 동안만 나눔(페이드 0.8초 제외)",
            [("이전", phases(base, "start -> title")), ("이후", phases(final, "start -> title"))], order, "loading2_breakdown.png")

    memory = measured.get("memory", {})
    if memory:
        rows = [(label, memory[key][0], memory[key][1], [], []) for key, label in
                [("video_mb", "비디오 메모리 (타이틀 직후)"), ("ram_mb", "최대 RAM, 개발 실행"), ("exe_ram_mb", "최대 RAM, 내보낸 게임"),
                 ("pck_mb", "게임 파일 Villagen.pck")]]
        paired_bars("메모리와 설치 크기", "비디오 메모리: 개발 실행 중앙값 · RAM: 프로세스 최대 작업 집합 · pck: 내보낸 빌드", rows, "MB", "loading2_memory.png")

    exe = measured.get("exe")
    if exe:
        def warm(label: str, field: str) -> list[float]:
            return [r[field] for r in exe[label] if not r["cold"]]
        rows = [("검은 화면 (카드가 뜰 때까지)", median(warm("bas-exe", "card_s")), median(warm("fin-exe", "card_s")), warm("bas-exe", "card_s"), warm("fin-exe", "card_s")),
                ("타이틀이 보일 때까지", median(warm("bas-exe", "title_s")), median(warm("fin-exe", "title_s")), warm("bas-exe", "title_s"), warm("fin-exe", "title_s"))]
        paired_bars("내보낸 게임(Villagen.exe)의 시작", "플레이어가 받는 릴리스 빌드, 같은 PC에서 번갈아 3회씩 · 엔진 시작부터 잰 초",
                    rows, "초", "loading2_export.png")

    renderers = measured.get("renderers")
    if renderers:
        rows = [(label + (" (검은 화면 포함)" if key == "start -> title" else ""), renderers["gl"][key], renderers["fp"][key], [], [])
                for key, label in CHANGES]
        paired_bars("렌더러 비교: 장소 이동 시간 (이후 코드)", "Compatibility(지금 쓰는 것) 대 Forward+, 같은 코드·같은 PC, 중앙값",
                    rows, "초", "loading2_renderer_times.png", "Compatibility", "Forward+")

    picture_row("같은 자리, 두 렌더러 (정오, 기본 줌)",
                [(ART / f"exterior-final-gl-{s}-12.png", ART / f"exterior-final-fp-{s}-12.png", c)
                 for s, c in [("green", "광장 앞 (마을회관)"), ("cafe", "카페 앞"), ("stage", "무대")]],
                ("Compatibility (지금)", "Forward+"), "loading2_renderers.png")
    before = lambda spot: ART / f"exterior-texbefore-{spot}-12.png"
    after = lambda spot: ART / f"exterior-texafter-{spot}-12.png"
    picture_row("텍스처 상한 전후: 가장 가까운 줌, 1080p 화면 (잘라서 62 % 크기로)",
                [(before("cafe"), after("cafe"), "카페 앞: 가로등(4096→1024), 파라솔·탁자·의자(4096→2048/1024)", (0.0, 0.40, 0.30, 1.0)),
                 (before("cafe"), after("cafe"), "카페 앞: 간판(4096→1024), 꽃(4096→1024)", (0.36, 0.55, 0.78, 0.82)),
                 (before("camp"), after("camp"), "캠프: 주황 텐트(4096→2048), 덤불(4096→2048)", (0.0, 0.10, 0.55, 0.95))],
                ("이전 (원래 크기)", "이후 (상한 적용)"), "loading2_textures.png", scale=0.62)
    grid = ART / "walkability.png"
    if grid.exists():
        image = Image.open(grid).convert("RGB")
        width = image.width + 48
        canvas = Image.new("RGB", (width, image.height + 120), SURFACE)
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 14), "걸을 수 있는 곳: 원래 충돌 대 새 충돌 (0.5 m 격자, 위가 북쪽)", fill=INK, font=font(19, True))
        legend(draw, 24, 48, [("#a9c48f", "걸어서 닿는 땅"), ("#8d8b84", "건물·바위·물건"), ("#cfe3ea", "물"), ("#e34948", "새로 못 가게 된 칸"), ("#2a78d6", "새로 가게 된 칸")])
        canvas.paste(image, (24, 84))
        eq = json.loads((DATA / "collision_equivalence.json").read_text(encoding="utf-8"))
        note = f"격자 {eq['cells']:,}칸 중 닿는 칸 {eq['exact']['reachable']:,} → {eq['generated']['reachable']:,}: 못 가게 된 칸 {eq['reach_lost_count']}, 새로 가게 된 칸 {eq['reach_gained_count']} (모두 벽 가장자리 1~2칸)"
        draw.text((24, image.height + 92), note, fill=INK2, font=font(14))
        save(canvas.convert("P", palette=Image.ADAPTIVE, colors=64), "loading2_walkability.png")


if __name__ == "__main__":
    main()
