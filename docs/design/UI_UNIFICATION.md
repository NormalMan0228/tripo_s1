# Villagen UI unification spec

Scope: game client only (`game/`). Everything here ships as a PCK patch. `game/project.godot` and `game/scripts/patch_boot.gd` stay untouched. There are no new autoloads and no `class_name`. New input actions are added at runtime through `GameSettings.apply_input` (game_settings.gd:507-522). Server work is limited to an optional `/health` feature flag for the friends/online tabs (section 7.4). The friends API itself is a separate spec.

Line numbers refer to the `merge-vg` worktree as read on 2026-10-15.

---

## 1. Decision: one visual language, two surfaces

The current majority convention becomes the rule. The exceptions are migrated to it.

| Surface | Look | Used for |
|---|---|---|
| **Paper** (parchment 9-slice `paper` / `hero`, `PAPER_INK` text, Jua titles) | content you read or manage | every game window (craft, wardrobe, storage, map, expedition, story, fish log, seed shop, interaction editor, admin), every drawer (bag in village, survival **and rooms**), the social window |
| **Night glass** (`night`, `night_plain`, `pill`, `INK`/`GOLD` text) | things over the world | HUD (frame, chips, minimap, objective, hotbar, prompt, toasts, chat box), dialogue, system screens (pause, settings, version gate, login) |

What changes because of this:
- The room dock stops being a flat dark `StyleBoxFlat` panel (studio.gd:319-355, 501-518) and becomes the same parchment drawer as the village bag (main.gd:999-1052).
- System menus stay night, but use the same shade, card builder, title style and close key as the paper windows.
- The painter workspace (painter/paint_widgets.gd) is the only allowed exception, because it is a full-screen tool. Its colours must still come from the tokens.

### 1.1 Tokens (rpg_ui.gd, next to lines 11-28)

Keep the existing constants and add the ones below. Every other file must use the tokens. A literal colour anywhere outside rpg_ui.gd and the painter is a lint failure (WP-17).

```
# colour
INK fff4d6, GOLD e9d29b, PAPER_INK 3c2e1e, PAPER_MUTED 7a6446, ACCENT b0452f, LEAF 4a7536, SOFT d8e3d4, OUTLINE (existing)
HOVER   := Color("ffe08a")          # replaces 28 literals in 12 files
TEAL    := Color("70afa3")          # party / whisper / teal ribbon
PAPER_LINE := Color("c9a46a")       # dividers (divider() default today, rpg_ui.gd:544)
ONLINE  := Color("8fd16a"), AWAY := Color("e9b552"), OFFLINE := Color(1,1,1,.35)
SHADE_IN := Color(0.03,0.05,0.06,.55), SHADE_OUT := Color(0.02,0.03,0.04,.86)  # main.gd:2979
# type scale (font, size)
T_WINDOW  = FONT_DISPLAY 26   (paper: PAPER_INK no outline; night: GOLD + outline)
T_SECTION = FONT_STRONG 17
T_BODY    = FONT_BODY 15
T_CAPTION = FONT_BODY 13 PAPER_MUTED / SOFT
T_SMALL   = FONT_BODY 12
# sizes
BTN_SM 32, BTN_MD 40, BTN_LG 44, BTN_MENU 52, SLOT 70 (hotbar), KEY 22 (keycap min), CLOSE 34
PAD 16, GAP 8 / 10 / 12, WINDOW_TOP 92, WINDOW_W {small 560, standard 760, wide 1040}, DRAWER_W 308
```

The following literals are mapped onto tokens:
- `e9b552` (craft_panel.gd:622, minimap, settings, studio) becomes `AWAY` or `GOLD`.
- `fff2cf` becomes `INK`.
- `c9d3c6` (pause, settings) becomes `SOFT`.
- The paper inks `3b2a1c`, `2f2a1f`, `5d4a35`, `7a5a2c`, `8a5a1c` (village_life.gd:298, 502-503; fishing.gd:555-565) become `PAPER_INK` or `PAPER_MUTED`.

### 1.2 Theme coverage
Today `night_theme()` (rpg_ui.gd:1094-1127) leaves ItemList, TabContainer/TabBar, OptionButton/PopupMenu and ScrollContainer unstyled, so parchment styles leak into night panels. `night_theme()` must style all of them, using the night frames already in `FRAMES`. After that, `studio.theme_style()` (studio.gd:319), `settings_menu._theme()` (settings_menu.gd:544) and `shape_panel.panel_theme()` (shape_panel.gd:32) are deleted. They are replaced by `RpgUi.theme()` (paper) or `RpgUi.night_theme()` (night).

---

## 2. Component API in rpg_ui.gd

All components are static functions and every window uses them. Existing helpers (`label`, `heading`, `caption`, `ribbon`, `divider`, `icon`, `meter`, `player_frame`, `hotbar`, `prompt`, `pin`, the fold system, `dialogue`, `field`, `menu_button`) stay as they are.

### 2.1 Windows
```gdscript
## One modal or non-modal window. kind: "paper"|"night". place: "top" (y=WINDOW_TOP) | "centre" | "bottom" (above hotbar).
## action: the GameSettings action that opens it ("craft","map",...) or "" -> close key shows Esc only.
static func window(host: Control, title: String, opts := {}) -> Dictionary
#  opts: {kind="paper", width=760, place="top", modal=true, action="", icon="", on_close=Callable(), scroll=true, id=""}
#  returns {root, shade, card, head, title, body, close, id}
static func close_window(w: Dictionary, animate := true) -> void
static func drawer(host: Control, title: String, opts := {}) -> Dictionary
#  non-modal side panel: {side="right"|"left", width=308, top=20, kind="paper", action="inventory"} -> same keys as window, slide_in from its side
static func shade(parent: Control) -> TextureRect     # the radial gradient now at main.gd:2972-2983, fades in 0.2 s
static func top_window() -> Dictionary                 # window stack, used by Esc routing and chat suppression
static var window_listeners: Array[Callable]           # called with (open_count, top_kind) when the stack changes
```
Window rules:
- One shade per screen. A window opened from another window, such as settings opened from pause, reuses the shade that is already there, so shades no longer stack (pause_menu.gd:72-75 plus 187-190 today).
- The title row is title (T_WINDOW), then optional extra head controls, then `close_key`. A `divider` sits under it. Every window opens with `pop_in` and `sfx("open")` and closes with `sfx("close")`.
- Each window registers itself in the stack with `id` and `action`. That is what lets the opening key toggle the window shut (section 4).

### 2.2 Controls
```gdscript
static func close_key(parent: Node, callback: Callable, action := "") -> Button
#  the single close style: flat 34 px painted icon "close" (new assets/ui/icons/close.png), hover_motion 1.12,
#  tooltip "닫기 · Esc" or "닫기 · <key_text(action)>"; FOCUS_NONE
static func button(parent: Node, text: String, callback: Callable, variant := "normal", size := "md") -> Button
#  variant: normal|primary|gold|night|danger|ghost -> theme_type_variation; size sm32|md40|lg44|menu52
#  always: hover_motion + click/hover sfx, focus_mode ALL in menus, NONE on HUD
static func tab_strip(parent: Node, entries: Array, on_select: Callable, kind := "paper") -> HBoxContainer
#  toggle-button tabs (the settings_menu look, settings_menu.gd:~80-110), one ButtonGroup, keys PageUp/PageDown;
#  each entry {id, label, icon?, badge?}; returns strip with meta "select"(id)
static func list(parent: Node, kind := "paper") -> ItemList          # themed, fixed row height 34
static func person_row(parent: Node, p: Dictionary, actions: Array) -> HBoxContainer
#  p {username, character, online:"online"|"away"|"offline", where:""}: portrait_<character>.png 36 px in a round
#  frame + status dot (ONLINE/AWAY/OFFLINE) + name (T_BODY) + caption(where) + icon buttons [{icon, tip, call}]
static func badge(parent: Control, count: int) -> Label             # ACCENT pill top-right of a slot/button; hidden at 0
static func swatch(parent: Node, hex: String, selected: bool, callback: Callable) -> Button  # from main.swatch (main.gd:3018-3036)
static func section(parent: Node, title: String) -> VBoxContainer    # T_SECTION + divider + body
```

### 2.3 Key hints
```gdscript
static func key_text(action_or_key: String) -> String
#  an action id ("inventory") -> GameSettings.key_label(action); a literal ("Esc","Enter","1-9") passes through
static func keycap(parent: Node, key: String, size := 12) -> Label  # existing (rpg_ui.gd:562); `key` may now be an action id
static func key_hint(parent: Node, action_or_key: String, text: String) -> HBoxContainer  # [keycap] text
```
- Keycaps built from an action relabel themselves through `GameSettings.listeners` (game_settings.gd ~300 `_notify`). Each one holds meta `action` and refreshes when bindings change.
- Hotbar slot specs take `"action":"inventory"` in place of `"key":"I"`. `name_tip(b, label, key_text(action))` produces the tooltip `가방 · I`.
- No visible string may embed a key letter. `"I  가방"`, `"E · 탐험 시작"`, `"WASD 이동 E 상호작용…"` and `"Esc 닫기"` all become `key_hint` rows.

### 2.4 Toasts and prompt
```gdscript
static func toast_lane(host: Control, y := 94.0) -> VBoxContainer   # top-centre lane, pinned (0.5,0)
static func toast(lane: Control, text: String, kind := "info") -> void
#  kind info|success|warn|error|social; pill + kind icon (starseed glint for info), back-ease pop, "toast" chime
#  (none in survival / calm()), 4.5 s, max 3 stacked (oldest leaves), identical text within 2 s refreshes instead of stacking
static func prompt(ui, y)            # existing (rpg_ui.gd:764); the only E prompt in every scene, y = 560
```
`main.message` (main.gd:398-408), `studio.message` (studio.gd:602-629) and the craft window note pill (craft_window.gd:97-120) all become one-line calls to `toast`. The version-gate pills keep their own top lane at layer 90 and only take on the token colours.

---

## 3. Window migration list

| # | Window (file:lines) | Today | Change |
|---|---|---|---|
| 1 | `main.modal_card` (main.gd:2965-3000) | radial shade, paper 760, text "닫기 · Esc" button | Thin wrapper: `w = RpgUi.window(ui, title, {action=…})`, `village_modal = w.root`, return `w.body`. `close_village_modal` calls `close_window`. The text close button becomes `close_key`. `modal_card` gains an `action` parameter. |
| 2 | `main.close_button` (main.gd:3003-3015) | 34 px SVG icon | Delegates to `RpgUi.close_key` (painted icon). |
| 3 | Expedition, story, wardrobe O, admin F9 (main.gd:3038-3510) | modal_card | Pass `action`: `""`, `""`, `"wardrobe"`, `""`. |
| 4 | Village life: map Tab, storage B, fish log, seed shop, observatory (village_life.gd:224-613) | modal_card | `action`: `"map"`, `"storage"`. Title of storage window: "마을 창고". Paper inks become tokens (village_life.gd:298, 502-503). |
| 5 | Seed picker (village_life.gd:251-318) | own night panel at (250,500), caption "Esc 닫기" | `RpgUi.window(kind="night", place="bottom", width=780, modal=false)`, keys 1-5 shown with `keycap`. It sits on the window stack, so the chat box is suppressed. |
| 6 | Craft window C (craft_window.gd:35-120) | copy of modal_card plus its own note pill | `RpgUi.window(action="craft")`. The note pill uses `toast` on its own lane inside the card. craft_panel `_button`/`_label`/`_option` (craft_panel.gd:853-889) become `RpgUi.button`/`label`. The step dot colour `e9b552` becomes `AWAY`. |
| 7 | Interaction editor (interaction_panel.gd:98-150, 528-540) | ColorRect .55, 1040x660, non-flat 40 px close | `RpgUi.window(width=1040, place="centre")`. The teal ribbon stays as a `head` decoration. Esc is handled by the stack, so the panel's own `_input` Esc code goes. |
| 8 | Shape panel (shape_panel.gd:32-80) | own theme, "✕" text close | `RpgUi.drawer(side="right", kind="night", width=324)` with `close_key`. `panel_theme()` is deleted (sliders move into the theme). |
| 9 | Village bag drawer I (main.gd:999-1052, 1091-1146) | parchment 308, title "나의 보관함" | `RpgUi.drawer(title="가방", action="inventory")`. Swatches use `RpgUi.swatch`. The inspector card stays at (20,206) but is hidden while the social drawer is open. |
| 10 | Survival bag drawer (main.gd:1997) | "탐험 가방" | Same `drawer` builder. The title stays "탐험 가방". |
| 11 | Room dock (studio.gd:501-560) | night flat dock 398 wide with custom TabContainer, "●" swatches, ColorPickerButton | `RpgUi.drawer(title="가방", action="inventory", width=308)`, paper look. Tabs use `tab_strip` (보관함, plus the dev tabs only in developer builds). Swatches use `RpgUi.swatch` with the village COLORS (main.gd:69). The ColorPickerButton stays under a "직접 고르기" ghost button. `studio.theme_style`/`button`/`key_cap`/`hud_button` (studio.gd:319-403) are deleted. |
| 12 | NPC storage chest (studio.gd:2805-2838) | night card over ColorRect .35, no close, "E 닫기" | `RpgUi.window(kind="paper", width=560, place="centre", title="보관 상자")` with `close_key` (Esc), plus a `key_hint("interact","닫기")` row. |
| 13 | Pause menu (pause_menu.gd:54-249) | ColorRect .66, night 420 | `RpgUi.window(kind="night", width=420, place="centre")` with the shared shade. Items stay `menu_button`. `ask()` uses `window(width=440)`. |
| 14 | Settings (settings_menu.gd:36-140, 505-575) | own theme, own shade, night up to 1000x660, tab buttons | `RpgUi.window(kind="night", width=min(1000,w-40))` reusing the pause shade. Tabs use `tab_strip(kind="night")`. Footer buttons use `RpgUi.button(size="lg")`. `_theme/_button/_paint/_box` are deleted. |
| 15 | Version gate blocking card (version_gate.gd:462-490) | ColorRect .8, night 470 | Shared `shade` (with a darker `SHADE_OUT` variant, `opts.dim=0.8`) plus `window(kind="night", modal=true)` on layer 90. Pills keep their lane but take token colours and `close_key`. |
| 16 | Survival return confirm (main.gd:2359-2377) | native ConfirmationDialog | `pause_menu.ask`-style `RpgUi.window(kind="night", width=440)` with primary/normal buttons. |
| 17 | 함께하기 modal (social.gd:292-380) | monolithic modal, chat transcript and LineEdit | Removed. Replaced by the social drawer (section 7) and the chat box (section 6). |
| 18 | Fishing catch card (fishing.gd:449-575) | paper card at (860,250), literal inks | Token colours only. Position unchanged. |
| 19 | Dialogue (rpg_ui.gd:1136-1426) | already shared | Registers on the window stack as kind `"dialogue"`, so chat and toasts hide consistently, and gets keyboard advance (section 4). |
| 20 | Login/title (main.gd:541-691) | night, menu_button | Token colours only; NightFields stay. |

Naming fixed in the same pass (labels go through `tr()`, so the i18n catalogues need the new keys):
- **가방** = I, personal items, in every scene. The room tab "보관함" is renamed to match.
- **창고** = B, the village storage. The `GameSettings.ACTIONS` label (game_settings.gd:114) changes from "보관함" to "창고", and the window becomes "마을 창고".
- "탐험 가방" (survival) and "보관 상자" (NPC chest) keep their names.

---

## 4. Open/close keys and key hints

### 4.1 One rule
1. **The key that opens a window closes it.** I, C, Tab, B, O, K and F9 all toggle.
2. **Esc closes the top of the stack**, in this order: chat focus, then the topmost window, then a drawer, then placement preview, then the pause menu.
3. **Enter** focuses chat when nothing else uses it. With chat focused, Enter sends and releases focus; an empty Enter just releases. While a dialogue is open, Enter advances it.
4. **E, Space and Enter** advance dialogue in both the village and rooms. **1-9** pick choices.
5. No hotkey fires while a text field has focus. This already holds through `text_input_active` (main.gd:2702) and the studio focus check (studio.gd:1664).

### 4.2 Key table (defaults; rebindable ones come from `GameSettings.ACTIONS`)
| Key | Action id | Village | Survival | Room | Notes |
|---|---|---|---|---|---|
| I | inventory | bag drawer | 탐험 가방 | bag drawer | toggle |
| C | craft | craft window | — | craft window | toggle (today Esc only) |
| Tab | map | map window | — | — | toggle (today it cannot close, main.gd:2869-2872) |
| B | storage | 마을 창고 | — | — | toggle |
| O | wardrobe | wardrobe | — | — | toggle |
| **K** | **social** (new) | social drawer | social drawer | social drawer | toggle; runtime-only action |
| Enter | (reserved) | chat focus/send | chat | chat | not rebindable (game_settings.gd:123) |
| E | interact | interact / advance dialogue | harvest | interact / advance | |
| Q F H Space | eat/campfire/heal/attack | — | as today | — | |
| R | rotate | placement | — | placement | |
| U | toggle_hud | fold all, chat included | same | same (new) | |
| M | toggle_sound | | | | |
| F3 / F9 | reserved | dev panel / admin | | | dev only |
| Esc | reserved | back-out chain | | | |

K is free: it is not bound in project.godot or in ACTIONS.

### 4.3 Implementation points
- `main._unhandled_input` (main.gd:2865-2945). The early return while `village_modal` is valid (2869-2872) is replaced by `RpgUi.top_window()` routing:
  - If the top window's `action` matches the canonical key, close it.
  - If the top window is a dialogue and the key is E, Space or Enter, call `advance`. The unreachable branch at 2928-2930 is deleted.
  - Esc closes the top window.
  - The fishing E (2870) keeps its place in the branch.
- `studio._unhandled_key_input` (studio.gd:1641-1680) uses the same helper: `RpgUi.route_window_key(event) -> bool`. Enter for talk advance (1651) runs before chat focus.
- A new action is added as `["social","함께하기 · 친구",[KEY_K,KEY_NONE]]` in `GameSettings.ACTIONS`, plus `const RUNTIME_ACTIONS := ["social"]`.
  - `apply_input` already calls `InputMap.add_action` when the action is missing (game_settings.gd:510).
  - `tests/settings_check.gd:88-96` `check_project_defaults` skips `RUNTIME_ACTIONS`.
- Pause controls page (pause_menu.gd:200-226) gains rows for Enter 채팅, K 함께하기, U HUD, 1-9 선택지 and E/Space/Enter 대화 넘기기, all through `key_hint`.
- Hard-coded key text is removed at: main.gd:1214-1216 (hotbar), 1268-1273 (toolbar), 2766-2769 (objective text), 2859-2861 (survival hint), 1005 (drawer tooltip); studio.gd:457 and 1858-1860 (controls line), 495-496 (hotbar); village_life.gd:309.

---

## 5. HUD layout (design canvas 1280x800, `RpgUi.pin` anchors)

```
 (14,12) player frame [fold profile]         toast lane y=94 (max 3)            (1060,10) minimap / room: location card
 (14,108) -- (retired SocialChip) --                                            (994,246) objective [fold objective]

 SOCIAL DRAWER (K, paper, left)                                                  BAG DRAWER (I, paper, right)
 x14..354, y108..548                                                             x948..1256, y20..
 tabs: 우리 마을 | 파티 | 초대 (+친구 | 접속 중)                                     (inspector (20,206) hidden while
                                                                                  the social drawer is open)
                                  E prompt chip  y=560 (all scenes)
 CHAT BOX [fold chat]  x14..342 (328 w)
 header 30: [👥 K badge] 마을|파티 tabs, unread dot
 log 150: last 50 lines, fades after 8 s          HOTBAR y=700  village 6-7 slots (x347..933 with admin)
 input 40: NightField "Enter 로 대화"               survival: 가방 I, 먹기 Q, 모닥불 F, 붕대 H, 귀환
 bottom = 786                                      room: 가방 I, 제작 C, 함께하기 K, 마을로, 내 집/공방
```
- **Chat box**: bottom-left, `pin(c,0,1)`, 328x226 (header 30, log 150, input 40, gaps), from x 14 to 342.
  - It clears the 7-slot admin hotbar, which starts at x≈347 (rpg_ui.gd:697: 7·80-10+36 = 586 wide, centred).
  - `ChatBox.reflow()` runs on `size_changed` and on `ui_scale` changes. If its global rect overlaps the hotbar tray rect (at UI scale ≥ 1.2 the canvas narrows), it lifts so its bottom sits 8 px above the tray top.
- **Social entry**: the people button (icon `people`, keycap K, `badge` = pending invites plus unread party lines) sits in the chat header in every scene. This replaces the SocialChip (social.gd:42-77) and its survival position (470,74), which frees the top-left and the survival top-centre. The "인사" quick greeting becomes a small ghost button in the chat header that sends "안녕하세요!" with no emoji: the bundled fonts likely lack 👋.
- **Rooms** gain the player frame top-left. The PlacePanel (studio.gd:~460, now at (18,16)) becomes a night "location card" pinned top-right, in the minimap's spot, with the same style as the objective tracker. RoomNav (studio.gd:460-468, bottom-left) becomes hotbar slots ("마을로" with the `home` icon, plus "내 집"/"공방"), which frees the bottom-left for chat. PlacementTools (18,128) closes the social drawer while open.
- **Survival**: the text toolbar (main.gd:1251-1287) becomes `RpgUi.hotbar` icon slots. The fold id stays `"toolbar"` so saved fold settings still apply. The dead non-survival branch (main.gd:1274-1279) is deleted. The toast lane moves to y=94 like everywhere else; the day counter stays at the top centre. The world hint (main.gd:1308-1325) becomes `RpgUi.prompt` at y=560.
- **Dev panel** F3 moves from (20,520) to the right column under the objective tracker, at (994,430).
- **Visibility**:
  - Dialogue hides the HUD (main.gd:3322 `hide_hud`), and the chat box is hidden through the window stack.
  - Modal windows hide the chat box. The unread badge keeps counting and shows again on close.
  - Non-modal drawers (bag, social, shape) keep chat visible and live.
  - U folds the chat to its 42 px header chip.

---

## 6. Always-on chat box

### 6.1 Ownership: a persistent layer, not per scene
`game/scripts/social_hud.gd` (new) is a CanvasLayer at **layer 4**: above the HUD (1) and below pause (50), the gate (90) and the transition (100). It is created with `SocialHud.of(tree, api)` under `tree.root`, following the CraftTracker pattern (craft_tracker.gd:51-72). It ends on logout and on session loss, as `CraftTracker.end` does. Because it lives outside both scenes and outside `main.clear_ui` (main.gd:337-346), it survives the village to room switch.

It owns:
- `seen_id` (the newest message id). The first ingest only seeds it, which fixes the replay of 20 old lines after login or a room return (social.gd:26, 170-173).
- Up to 50 lines of history, the unread count and the pending invites.
- `ingest(overview: Dictionary)`, called by `social.gd.poll` (main scene) and `studio.share_presence` (studio.gd:1525-1600). Rooms read `messages` for the first time this way.
- `send(text)`: POST /v1/social/messages through the same `api.mutation` path as `social.send_message` (social.gd:420-422), then a poll nudge.
- Visibility: shown only when `screen in [village, survival]` or in a room. It listens to `RpgUi.window_listeners` for suppression.

Chat lines no longer go through `main.message` (social.gd:173 is removed). System notices stay in the toast lane, and chat stays in the chat box.

### 6.2 `game/scripts/chat_box.gd` (new Control)
- **Header**: people button (K) with badge, tab_strip with 마을 and 파티 (파티 only when `data.party` exists; it filters by room when the server tags channels, otherwise the current room), the greeting ghost button and the fold toggle `RpgUi.fold_toggle(…, "chat", Vector2.LEFT)`.
- **Log**: a RichTextLabel with `bbcode_enabled`. User text is escaped (`[` becomes `[lb]`) before formatting:
  - Name in GOLD followed by the text in INK.
  - Your own name in HOVER.
  - System lines (joins, visit ended, invites) in SOFT with an icon. Invite lines carry `[url=accept:<id>]수락[/url] · [url=decline:<id>]거절[/url]`, which call the existing invite answer (social.gd:382-404).
  - Party lines in TEAL.
  - Scroll follows the end unless the user has scrolled up.
- **Idle fade**: 8 s after the last line or focus, the log panel style fades to alpha 0, leaving the text at 0.55 for 4 s and then 0. Hover, focus or a new line restores it within 0.15 s. The header stays at 0.85.
- **Input**: `RpgUi.field(parent, tr("Enter 로 대화"))` (rpg_ui.gd:1447, not latin). It is set to `keep_editing_on_text_submit = false`, `max_length = 160` and `focus_mode = FOCUS_CLICK`.
  - On Enter, `await get_tree().process_frame` first, so the Korean IME commits the last syllable.
  - If the text is non-empty, send it. Then clear the field and `release_focus()`.
  - The server's 429 `message_rate_limited` shows as a SOFT system line, not a toast.
- **Focus rules**:
  - Enter in `main._unhandled_input` (before the hotkey match) and in studio's handler calls `chat.focus()`, but only when no window, dialogue or placement is open.
  - Esc releases focus through ImeCaret (ime_caret.gd:114-118).
  - A left click in the world while chat is focused releases focus and is consumed, so no `click_furniture` runs (main.gd:2944). Studio does the same.
  - Any window opening releases focus.
- **Typing safety**: `field_objects.walker_moving()` (field_objects.gd:283-284) is gated on `app.text_input_active()`, so typing w/a/s/d does not end a seat or view (1388, 1484).

---

## 7. Social window entry

### 7.1 `game/scripts/social_window.gd` (new)
It is a left paper drawer (`RpgUi.drawer(side="left", width=340, top=108, action="social")`), opened by K or the chat header people button. It is non-modal, so movement and chat stay live.

Tabs (`tab_strip`) and their data:
- **우리 마을**: `data.village.players` (multiplayer.py:217-230) as `person_row`s. Host view adds a 방문 종료 action, the eject from social.gd:355-359.
- **파티**: `data.party.members`, with online state from `party_public` (multiplayer.py:176-179). Actions are 나가기 and 초대.
- **초대**: pending invites (수락/거절) plus an "이름으로 초대" form (a field plus 마을 초대 and 파티 초대 buttons). This replaces social.gd:309-320.
- **친구** and **접속 중**: shown only when `/health` lists `social_features` containing `"friends"`/`"people"`. Hidden on the judges' server. They are filled by the future `/v1/social/people` endpoint (separate server spec).

Rows use `portrait_<avatar.character>.png` (game/assets/ui) with a status dot. Per-friend SubViewports are not used.

### 7.2 Notifications
- A new invite adds a system line in the chat with accept/decline links and a `toast(kind="social")`.
- The people badge counts pending invites.
- The mailbox flag (field_objects.gd:1036-1046) stays.

### 7.3 Removal
`social.open_menu` (292-380), `menu_messages` and the HUD chip go. social.gd keeps only transport: polling, peers and nameplates, plus the visit-end text routed to `SocialHud` as system lines. The mailbox call `social.open_menu` (field_objects.gd:994) becomes `SocialHud.open_window()`.

### 7.4 Server (optional, additive)
`health_fields` (app.py:266-277) adds `"social_features": []`. `multiplayer_protocol` stays 1, because main.gd:313 and 759 require exactly 1. Nothing else is needed for WP-1 to WP-16.

---

## 8. Verification tooling
- **`tests/ui_gallery.gd`** gains:
  - New shots: `chat-idle`, `chat-focus`, `chat-faded`, `chat-ui140` (ui_scale 1.4), `social-window`, `social-invites`, `studio-bag`, `studio-hud`, `survival-hotbar`, `storage-chest`, `interaction-editor`, `seed-picker`.
  - A stub fixture with messages and invites in `tests/fixtures/ui_gallery.json` (tools/make_ui_gallery_fixture.py).
  - Before/after prefixes give the visual diff.
- **New `tests/ui_consistency_check.gd`** (headless):
  - Static part: scans `res://scripts/*.gd` and fails on `Color("ffe08a"|"e9b552"|"fff2cf"|"c9d3c6"|"3b2a1c"…)` outside rpg_ui.gd/painter/, on `ColorRect` used as a shade, on `StyleBoxFlat.new()` in migrated files, and on `"key":"<letter>"` hotbar specs. A shrinking allowlist is kept per WP.
  - Runtime part: opens every window and asserts one shade node, a close button with meta `rpg_close` whose tooltip ends with the key text, and theme type coverage.
- **New `tests/window_keys_check.gd`**: for each (key, window) pair it sends `InputEventKey` and asserts open, the same key closes, Esc closes, and Esc order with a drawer under a window.
- **New `tests/hud_layout_check.gd`**: for village, survival and studio at ui_scale 0.8, 1.0, 1.2 and 1.4 it collects the global rects of the player frame, chat box, hotbar tray, prompt, toast lane, minimap/location card and objective, and asserts no pairwise overlap among the visible ones.
- **New `tests/chat_box_check.gd`**:
  - Ingest seeds `seen_id`, so there is no replay.
  - Lines are appended in order and bbcode is escaped.
  - The village to studio to village switch keeps history.
  - Enter focuses, sends and releases focus; an empty Enter releases; Esc cancels.
  - A world click releases focus and does not click furniture.
  - The box is suppressed under a modal and during dialogue.
- **Existing tests to update**:
  - `hud_fold_check.gd` (175-243, SocialChip expectations) moves to the chat-header people button and fold `chat`.
  - `settings_check.gd` skips `RUNTIME_ACTIONS`.
  - `ime_typing.gd:201-214` switches to the chat box submit-then-unfocus flow. It is a real-IME windowed run with `tools/ime_type.ps1`, done manually by the user.
  - `npc_dialogue.gd` gains a keyboard-advance case.
  - `multiplayer.gd:84-86` reads the chat box instead of the toast.
- Windowed runs open on the BenQ screen (`tools/test_window_position.ps1`).


## Work packages

### WP-01 Tokens and complete night/paper theme coverage
- Goal: Add colour/type/size tokens to rpg_ui.gd and make night_theme() style ItemList, TabContainer/TabBar, OptionButton/PopupMenu and ScrollContainer, so local themes can be deleted later. No visual change to existing screens.
- Files: game/scripts/rpg_ui.gd
- Tests: compile_all.gd passes; new ui_consistency_check.gd theme part: both themes define stylebox/colour for every listed type; ui_gallery --prefix=ui-wp01- matches the baseline (village, bag, craft, pause-menu, settings-menu) by eye
- Risk: Low; additive constants and theme entries

### WP-02 Painted close icon, close_key, button, key_text/key_hint, action-aware keycaps and hotbar
- Goal: Add assets/ui/icons/close.png via tools/build_ui_icons.py; add RpgUi.close_key, button(variant,size), key_text, key_hint, badge, swatch; keycap/hotbar accept an action id and relabel on GameSettings listener changes. Village and room hotbars switch to action ids.
- Files: game/scripts/rpg_ui.gd, tools/build_ui_icons.py, game/assets/ui/icons/close.png, game/scripts/main.gd (1209-1217), game/scripts/studio.gd (495-497)
- Depends on: WP-01
- Tests: new keycap_rebind_check.gd: rebind inventory to J, the hotbar keycap shows J and the tooltip reads '가방 · J'; reset restores I; ui_gallery village/studio shots show identical hotbar; RpgUi.painted('close') resolves the PNG
- Risk: Low; hotbar spec change touches two callers

### WP-03 RpgUi.window/drawer/shade and window stack; modal_card and close_button become wrappers
- Goal: Implement window(), close_window(), drawer(), shade(), top_window(), window_listeners. main.modal_card/close_village_modal/close_button delegate to them with an 'action' argument; village_modal semantics stay for existing callers and tests.
- Files: game/scripts/rpg_ui.gd, game/scripts/main.gd (2953-3015), game/scripts/village_life.gd (modal_card callers pass action), game/scripts/social.gd (299 temporary)
- Depends on: WP-02
- Tests: ui_gallery: expedition, story, wardrobe, mailbox, seeds, admin, social shots unchanged except the close key icon; ui_consistency_check runtime part: each modal has one shade and a close button tooltip ending in its key; existing ui_gallery close_modal() still works
- Risk: Medium; every village modal goes through it. Keep the old function signatures.

### WP-04 Unified key routing: toggle-to-close, Esc stack, keyboard dialogue advance
- Goal: Replace the early return at main.gd:2869-2872 with RpgUi.route_window_key: the opening key closes its window, Esc closes the top window, and E/Space/Enter advance dialogue. Delete the unreachable branch 2928-2930. Use the same helper in studio._unhandled_key_input.
- Files: game/scripts/rpg_ui.gd, game/scripts/main.gd (2865-2945), game/scripts/studio.gd (1641-1680)
- Depends on: WP-03
- Tests: new window_keys_check.gd: I/C/Tab/B/O open and close by the same key, Esc order (window > drawer > placement > pause); npc_dialogue.gd extended: E and Enter advance village dialogue; fishing reel E still works with the map closed (field_objects/fishing tests)
- Risk: Medium; input regressions in fishing reel, seats and placement

### WP-05 Migrate craft window to RpgUi.window
- Goal: craft_window.gd uses RpgUi.window(action='craft') and toast for notes; craft_panel helpers use RpgUi.button/label; token colours.
- Files: game/scripts/craft_window.gd, game/scripts/craft_panel.gd (622, 853-889)
- Depends on: WP-04
- Tests: craft_panel_check.gd and craft_one_check.gd pass; ui_gallery craft shot: same layout, 34 px icon close; C toggles the window in village and room (window_keys_check)
- Risk: Low-medium; the craft flow is the presentation centrepiece, so check the progress view too

### WP-06 Migrate interaction editor, NPC storage chest, seed picker, shape panel
- Goal: Move the four bespoke windows onto window()/drawer(), with one close style, token colours and keycaps for hints. Delete shape_panel.panel_theme.
- Files: game/scripts/interaction_panel.gd (98-150, 528-540), game/scripts/studio.gd (2805-2838), game/scripts/village_life.gd (251-318), game/scripts/shape_panel.gd (32-80)
- Depends on: WP-04
- Tests: interaction_check.gd passes; ui_gallery new shots interaction-editor, storage-chest, seed-picker; seed keys 1-5 still pick; Esc closes each
- Risk: Low

### WP-07 System menus on the shared window and shade
- Goal: pause_menu, settings_menu, version_gate blocking card and the survival return confirm use window(kind='night'); one shade when settings opens from pause; delete settings_menu._theme/_button/_paint/_box; tab_strip for settings tabs.
- Files: game/scripts/pause_menu.gd, game/scripts/settings_menu.gd, game/scripts/version_gate.gd (462-490), game/scripts/main.gd (2359-2377), game/scripts/rpg_ui.gd (tab_strip)
- Depends on: WP-03
- Tests: settings_check.gd passes; ui_gallery pause-menu, settings-menu, settings (title) shots; a check that only one shade node exists with pause plus settings open; version gate screens via existing gate tests
- Risk: Medium; version_gate is on layer 90 and must keep working on blocked clients

### WP-08 Shared toast lane with stacking
- Goal: Add RpgUi.toast_lane/toast (max 3, kinds, merge of identical text within 2 s). main.message, studio.message and the craft note call it; delete main.make_toast/show_toast/hide_toast and the studio StatusToast.
- Files: game/scripts/rpg_ui.gd, game/scripts/main.gd (398-472), game/scripts/studio.gd (442-449, 602-629), game/scripts/craft_window.gd
- Depends on: WP-01
- Tests: new toast_check.gd: 4 pushes show 3, the oldest leaves; an identical push refreshes the timer; survival is silent; ui_gallery village/studio toasts look identical
- Risk: Low; I18n.server still applied in main.message

### WP-09 One prompt chip everywhere
- Goal: Survival world_hint (main.gd:1308-1325, 2859-2861) and the studio hint_chip/key_cap (studio.gd:451-457, 1814-1877) become RpgUi.prompt/set_prompt at y=560 with key_text; the controls line becomes key_hint rows in the pause controls page.
- Files: game/scripts/main.gd, game/scripts/studio.gd, game/scripts/pause_menu.gd (200-226)
- Depends on: WP-02
- Tests: ui_gallery survival and studio show the keycap prompt; a rebind of interact to G shows G in all three scenes (keycap_rebind_check)
- Risk: Low

### WP-10 Survival icon hotbar
- Goal: Replace the 680 px text toolbar with RpgUi.hotbar slots (가방 I, 먹기 Q, 모닥불 F, 붕대 H, 귀환), keep fold id 'toolbar', move the survival toast to y=94 and delete the dead branch main.gd:1274-1279.
- Files: game/scripts/main.gd (1230-1306), game/assets/ui/icons (eat/fire/heal/return icons if missing)
- Depends on: WP-02, WP-08
- Tests: combat_play.gd / survival tests pass; hud_fold_check 'toolbar' fold still works; ui_gallery survival, survival-bag
- Risk: Low-medium; survival tests may look up toolbar buttons by text

### WP-11a Room HUD frame: player frame, location card, RoomNav into hotbar
- Goal: Rooms get RpgUi.player_frame top-left; PlacePanel becomes a night location card pinned top-right; RoomNav buttons become hotbar slots so the bottom-left is free; studio.hud_button/key_cap deleted.
- Files: game/scripts/studio.gd (422-500)
- Depends on: WP-02
- Tests: home_roundtrip.gd, home_visit.gd, interior_tour.gd pass; ui_gallery studio shot; hud_layout_check studio has no overlaps
- Risk: Medium; room navigation tests may click RoomNav by name, so keep node names on the slots

### WP-11b Room bag becomes the parchment drawer
- Goal: Replace the night Dock with RpgUi.drawer(title '가방', action inventory) and tab_strip; RpgUi.swatch with the village palette; delete studio.theme_style/label/button/option duplicates.
- Files: game/scripts/studio.gd (319-403, 501-560)
- Depends on: WP-11a, WP-03
- Tests: avatar_rooms_check.gd and the furniture placement tests pass; ui_gallery studio-bag; ui_consistency_check: no StyleBoxFlat in studio.gd
- Risk: Medium; the dock carries placement, paint and dev tabs

### WP-12 SocialHud persistent layer and read-only chat box
- Goal: Add social_hud.gd (CanvasLayer 4 under tree.root, CraftTracker pattern) and chat_box.gd (log with fade, bbcode escaping, system lines). social.gd.poll and studio.share_presence call ingest(); seen_id seeded on first ingest; chat lines no longer go to the toast.
- Files: game/scripts/social_hud.gd (new), game/scripts/chat_box.gd (new), game/scripts/social.gd (142-191), game/scripts/studio.gd (1525-1600), game/scripts/main.gd (social wiring 235-237, logout/session end)
- Depends on: WP-08
- Tests: new chat_box_check.gd: ordering, escaping, no replay after a village to studio to village switch, hidden on title/login; multiplayer.gd (84-86) reads the chat box; ui_gallery chat-idle, chat-faded
- Risk: Medium; layer must be ended on logout or it leaks across accounts

### WP-13 Chat input: Enter focus/send/release, IME-safe, world-click release
- Goal: Add a NightField to the chat box with keep_editing false; Enter focuses (when no window, dialogue or placement is open), sends and releases; empty Enter and Esc release; a world click releases and is consumed; suppressed under modals and dialogue via window_listeners; gate field_objects.walker_moving on text input.
- Files: game/scripts/chat_box.gd, game/scripts/main.gd (_unhandled_input 2865-2945), game/scripts/studio.gd (1641-1680, 1997-1999), game/scripts/field_objects.gd (283-284)
- Depends on: WP-12, WP-04
- Tests: chat_box_check.gd input part (synthetic key events); ime_typing.gd social case rewritten for the submit-then-unfocus flow (windowed, real IME via tools/ime_type.ps1); typing 'wasd' while seated on a swing does not stand up
- Risk: Medium-high; Korean IME last-syllable and stuck-key bugs on unpatched templates

### WP-14 HUD layout: chat placement, reflow, fold, SocialChip retirement
- Goal: Pin the chat box bottom-left (328x226), reflow above the hotbar on overlap at any ui_scale, fold id 'chat' with U, move the F3 dev panel to (994,430), retire SocialChip into the chat header (people button K, badge, greeting without emoji).
- Files: game/scripts/chat_box.gd, game/scripts/social.gd (42-91), game/scripts/main.gd (1175-1228, dev panel), game/scripts/rpg_ui.gd (FOLD_TIPS), game/tests/hud_fold_check.gd (175-243)
- Depends on: WP-13, WP-10, WP-11a
- Tests: new hud_layout_check.gd at ui_scale 0.8/1.0/1.2/1.4 in village, survival and studio with an admin hotbar; hud_fold_check updated: U folds the chat to its chip and restores it; ui_gallery chat-ui140
- Risk: Low-medium

### WP-15 Social drawer (K) replacing the 함께하기 modal
- Goal: Add social_window.gd as a left paper drawer with tabs 우리 마을 / 파티 / 초대 (+ 친구 / 접속 중 behind /health social_features), person_row with portraits and status dots, and invite lines with accept/decline links in chat. Add the 'social' runtime action (K) with RUNTIME_ACTIONS and adjust settings_check. Delete social.open_menu and point the mailbox at the new window.
- Files: game/scripts/social_window.gd (new), game/scripts/social.gd (292-404), game/scripts/rpg_ui.gd (person_row, tab_strip), game/scripts/game_settings.gd (102-123), game/tests/settings_check.gd (88-96), game/scripts/field_objects.gd (994), server/app.py (266-277, optional social_features: [])
- Depends on: WP-14, WP-03
- Tests: new social_window_check.gd with the stub API: rows, eject, invite by name, accept from the chat link; settings_check passes with K absent from project.godot; K toggles the drawer in all three scenes (window_keys_check); ui_gallery social-window, social-invites; server test: /health has social_features and multiplayer_protocol still 1
- Risk: Medium; the guest-in-home eject gap stays until a server change

### WP-16 Naming and key-hint sweep, controls page
- Goal: Apply the names 가방 (I) / 창고 (B) / 탐험 가방 / 보관 상자 and add the i18n keys; replace every remaining hard-coded key string with key_hint/key_text; the pause controls page lists Enter, K, U, F3, 1-9 and dialogue advance.
- Files: game/scripts/main.gd (1005, 2766-2769), game/scripts/game_settings.gd (114), game/scripts/village_life.gd (309, 466), game/scripts/pause_menu.gd (200-226), game/scripts/i18n.gd / translation catalogues
- Depends on: WP-09, WP-15
- Tests: ui_consistency_check static part: no key-letter literals in UI strings (allowlist empty); ui_gallery --languages=ko,en,zh
- Risk: Low; translation catalogue gaps show Korean

### WP-17 Colour literal cleanup and lint allowlist to zero
- Goal: Replace the hard-coded colours (ffe08a x28, e9b552, fff2cf, c9d3c6, paper inks in village_life.gd and fishing.gd, minimap, studio) with tokens; the painter maps its palette to tokens but keeps its tool theme.
- Files: game/scripts/*.gd (12 files with ffe08a), game/scripts/fishing.gd (449-575), game/scripts/minimap.gd, game/scripts/painter/paint_widgets.gd (11-61)
- Depends on: WP-01
- Tests: ui_consistency_check passes with an empty allowlist; full ui_gallery before/after review
- Risk: Low

## Risks

- Korean IME on unpatched export templates: an always-on chat field that gains and loses focus often makes the lost-syllable (#123269) and stuck-WASD bugs more likely. A PCK cannot ship the engine patches (tools/engine_patches). The deferred-submit plus explicit release_focus mitigates this, but it must be verified with a real IME run (ime_typing.gd), which the user runs.
- Input routing rewrite (WP-04) touches every village key path: fishing reel E inside a modal, seat stand on E/Esc, placement R/wheel, admin F9. A regression here breaks core play, so window_keys_check and the existing field/fishing/seat tests must run on every step.
- A SocialHud CanvasLayer under tree.root outlives scenes. If it is not ended on logout or session loss (CraftTracker.end pattern), chat history and invites leak to the next account on the same PC.
- settings_check.gd asserts that project.godot declares every ACTIONS entry. The K action must be marked runtime-only and the test changed. Forgetting this fails CI, and editing project.godot instead would force a full reinstall.
- ui_scale 120-140% narrows the design canvas, so the chat box and hotbar can overlap. The reflow rule and hud_layout_check are needed at every scale, including the 7-slot admin hotbar.
- Renaming labels (가방/창고/보관함) changes tr() keys. The en/zh catalogues fall back to Korean until updated, and tests that find buttons by text may break.
- Room HUD changes (RoomNav into the hotbar, dock into a parchment drawer) can break room tests that look up nodes by name ('RoomNav', 'Dock', 'DockToggle'). Keep the node names or update the tests in the same WP.
- Friends and online tabs depend on server endpoints that do not exist. Without the /health social_features flag they must stay hidden; on the judges' untouched server they must never appear.
- Chat moves out of the toast: players who fold the chat (U) only see the unread badge. This is a UX change to confirm with the user.
- Per-presence-reply ingest in rooms adds parsing work at 4 Hz. It stays cheap (at most 20 lines) but must not rebuild the RichTextLabel when no new id arrived.