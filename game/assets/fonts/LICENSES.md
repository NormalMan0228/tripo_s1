# Bundled UI fonts

All fonts below are licensed under the SIL Open Font License 1.1 (full text in the
matching `OFL-*.txt`). They are subset to the characters the game uses
(`tools/build_ui_fonts.py`; every KS X 1001 Hangul syllable is kept for Korean
player text) and re-saved as WOFF. Subsetting is a modification permitted by the
OFL; the Reserved Font Names are unchanged because the files are not renamed for
redistribution as separate fonts.

| File | Font | Role | Source | Licence |
| --- | --- | --- | --- | --- |
| `Pretendard-Regular.woff`, `-SemiBold.woff`, `-Bold.woff` | Pretendard 1.3.9 (font version 1.309, Kil Hyung-jin) | Body, buttons, HUD numbers (tabular figures via `tnum`) | https://github.com/orioncactus/pretendard (`packages/pretendard/dist/public/static/`) | OFL 1.1 — `OFL-Pretendard.txt` |
| `Jua-Regular.woff` | Jua 1.001 (The Jua Project Authors) | Display titles, panel headers, name plates | https://github.com/google/fonts/tree/main/ofl/jua | OFL 1.1 — `OFL-Jua.txt` |
| `NotoSansSC-Regular.woff`, `-Bold.woff` | Noto Sans SC 2.004 (Adobe / Google), static 400 & 700 instances of the variable font | Simplified Chinese fallback | https://github.com/google/fonts/tree/main/ofl/notosanssc | OFL 1.1 — `OFL-NotoSansSC.txt` |

`ui_*.tres` are FontVariation resources wiring the fallback chain
Pretendard/Jua → Noto Sans SC → the OS font (Malgun Gothic, Microsoft YaHei, emoji).
