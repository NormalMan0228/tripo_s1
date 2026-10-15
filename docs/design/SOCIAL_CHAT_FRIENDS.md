# Villagen social layer: design spec

Scope: (A) always-on MMO chat, (B) presence ("who is online", "who is in my village"), (C) friends, (D) one unified Social window. The client ships as a **PCK patch**: no edits to `game/project.godot` or `game/scripts/patch_boot.gd`, no autoloads, no `class_name`. The server deploys separately (staging `dev.<ip>.sslip.io` first). The judges' server stays untouched, so every new client feature is feature-detected.

---

## 0. Current status (현황), verified in the checkout

| Topic | Today | Evidence |
|---|---|---|
| Chat input | One LineEdit inside the full-screen "함께하기" modal. `modal_card` sets `controls_enabled=false`. `keep_editing_on_text_submit=true`, so focus stays after Enter | social.gd:292-378 (field ~369-378), main.gd:2965-3000 |
| HUD chat key | The SocialChip "chat" icon sends a fixed `안녕하세요! 👋` (the emoji is likely tofu in the bundled fonts) | social.gd:60 |
| Display | Every new line goes through the one-slot system toast (`app.message`). Lines overwrite each other and system notices. `seen_message` resets per main scene, so up to 20 old lines replay after every room trip | social.gd:170-173, main.gd:398-411, social.gd:26/99 |
| Rooms | studio.gd posts presence (home 4 Hz, workshop 3 s `keep_present`) and **ignores `messages`**. No chat indoors | studio.gd:1525-1600 |
| Server chat | `mp_messages(room,user_id,text,created)`. `room_for` = `party:<id>` if in a party, else `village:<host>`. The last 20 lines from the past hour ride in **every** presence reply with no cursor. 1 msg/s, 160 chars, `clean_text`, 24 h purge. Each line goes through `mutate()`, which writes a requests row and an audit row | multiplayer.py:33-36, 81-82, 168-170, 191-192, 332-345; app.py:107-122 |
| Presence | `mp_presence` row upserted per poll (`scene` village/home/away, `host_id`, `seen`). It is deleted on logout or offline. Only party members get an `online` flag, and nothing lists the server roster | multiplayer.py:26-29, 155-166, 176-179, 234-248 |
| My village | Only `village.players` (same scene, seen < 6 s). Guests inside the host's home are invisible to the outdoor list and the eject button | multiplayer.py:219, social.gd:355-359 |
| Friends/block/report | None, server or client (grep finds only NPC friendship) | — |
| Gating | Social turns on only when `/health multiplayer_protocol == 1` | app.py:269, main.gd:313, 759 |
| Input safety | `text_input_active()` blocks movement and hotkeys while a LineEdit is focused. ImeCaret re-`edit()`s any focused LineEdit each frame and releases it on Esc | main.gd:2702-2715, 2884; ime_caret.gd:77-118 |
| Ungated key reader | `field_objects.walker_moving()` reads `Input.get_vector` directly, so typing w/a/s/d in chat ends a swing seat or telescope view | field_objects.gd:283-284 (used at 1388, 1484) |
| Engine LineEdit | Enter emits `text_submitted`, then `unedit()`s if `!keep_editing_on_text_submit`, but **focus stays**, so ImeCaret would re-edit next frame. Esc `unedit()`s and `accept_event()`s, so the pause menu does not open | engine scene/gui/line_edit.cpp:924-946 |
| Input actions | `GameSettings.ACTIONS` → `apply_input()` adds missing InputMap actions at runtime. Enter/KP_Enter are RESERVED (not rebindable, free). `tests/settings_check.gd:88-93` asserts that project.godot declares every ACTIONS entry | game_settings.gd:102-123, 507-522 |
| Server capacity | One uvicorn worker, SQLite WAL with a single writer, 2 GB VM shared with 320 MB staging. Every 4 Hz poll is a `BEGIN IMMEDIATE` transaction that also runs the object list and npc_homes | ops/compose.yaml:13,56; multiplayer.py:234-248 |

Side bug to fix while touching input: `main.gd:2928-2930` (E/Space/Enter advances village dialogue) is unreachable, because `_unhandled_input` returns at 2869-2872 whenever `village_modal` is valid.

---

## 1. Architecture overview

```
 server (deploy first)                         client (PCK)
 ───────────────────────────                   ───────────────────────────────────────────
 multiplayer.py  presence/messages  ──reply──▶ social.gd (village/survival poll)  ─┐
   + Presence.since/place (opt-in)            studio.gd (room poll/heartbeat)     ─┤ ingest(reply)
   + chat block {cursor,lines}                                                      ▼
   + social block {v,requests,online}          SocialHub (session node under tree.root,
 friends.py   /v1/friends/* /v1/social/people     CraftTracker.of pattern): chat history,
              /v1/social/{blocks,report,         cursor, people cache, features, notices
              prefs,visit}                          │ signals line_added / people_changed / notice
 chat_filter.py  word filter                        ▼
 app.py health: social_features[]             per-scene widgets under the scene's `ui`:
                                              ChatBox (chat_box.gd), SocialWindow (social_window.gd),
                                              SocialNotice cards, SpeechBubble on walkers
```

Principles:
1. **No new steady-state requests.** Chat delivery and HUD badges ride the existing presence reply through a cursor. The roster (`GET /v1/social/people`) is fetched only while the Social window is open (every 5 s) or when `social.v` changes.
2. **State is session-wide; widgets are per-scene.** `SocialHub` lives under `tree.root`, keyed by `base_url|token`, like `CraftTracker.of` (craft_tracker.gd:51-72), so history and the cursor survive village↔room changes and `main.clear_ui()`. Widgets are rebuilt in each HUD build, so the existing fold, theme and `hide_hud` behaviour keeps working.
3. **Old server = graceful fallback.** Without `social_features`, the ChatBox still works on the legacy `messages` field: local room only, deduped by id, history seeded silently. The Friends, Online and global-chat UI are hidden.

---

## 2. Server design

### 2.1 Feature advertisement
`app.py health_fields` (266-277) adds:
```json
"social_features": ["chat2", "people", "friends", "visit", "report"],
"global_chat": true
```
Keep `multiplayer_protocol: 1`, since clients require exactly 1 (main.gd:313, 759). New settings (server/config.py, env): `VILLAGEN_GLOBAL_CHAT` (default on for the school line), `VILLAGEN_SOCIAL_ROSTER` = `all|friends|off` (default `all`), `VILLAGEN_CHAT_FILTER_EXTRA` (optional path to an extra word list in data_dir).

### 2.2 Schema (additive; `CREATE TABLE IF NOT EXISTS` and guarded `ALTER`, as at multiplayer.py:96-101)
New module `server/friends.py` owns:
```sql
CREATE TABLE IF NOT EXISTS social_friends(          -- two directed rows per friendship
 user_id TEXT NOT NULL REFERENCES users(id), friend_id TEXT NOT NULL REFERENCES users(id),
 created REAL NOT NULL, PRIMARY KEY(user_id, friend_id));
CREATE TABLE IF NOT EXISTS social_requests(
 id TEXT PRIMARY KEY, from_id TEXT NOT NULL REFERENCES users(id), to_id TEXT NOT NULL REFERENCES users(id),
 state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);   -- pending|accepted|declined|cancelled
CREATE UNIQUE INDEX IF NOT EXISTS social_requests_open ON social_requests(from_id,to_id) WHERE state='pending';
CREATE INDEX IF NOT EXISTS social_requests_to ON social_requests(to_id,state);
CREATE TABLE IF NOT EXISTS social_blocks(
 user_id TEXT NOT NULL REFERENCES users(id), blocked_id TEXT NOT NULL REFERENCES users(id),
 created REAL NOT NULL, PRIMARY KEY(user_id, blocked_id));
CREATE TABLE IF NOT EXISTS social_prefs(
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 appear_offline INTEGER NOT NULL DEFAULT 0,
 requests TEXT NOT NULL DEFAULT 'everyone',      -- everyone|nobody
 drop_in TEXT NOT NULL DEFAULT 'off',            -- off|friends
 rev INTEGER NOT NULL DEFAULT 0,                 -- bumped on any friend/request/block change touching the user
 last_seen REAL, chat_muted_until REAL);
CREATE TABLE IF NOT EXISTS social_reports(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,  -- reporter
 to_id TEXT NOT NULL, message_id INTEGER, text TEXT, reason TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'open', created REAL NOT NULL);
```
In `multiplayer.py`, guarded ALTERs add `mp_messages.channel TEXT` and `mp_messages.to_id TEXT`, plus `CREATE INDEX IF NOT EXISTS mp_messages_to ON mp_messages(to_id,id)`.
`server/admin_cli.py:40-42 USER_COLUMNS` adds `'blocked_id'`. The other new columns already use names in that set (user_id, friend_id, from_id, to_id), so account deletion covers the new tables.

`last_seen` = `mp_presence.seen` while a row exists, else `social_prefs.last_seen`. The latter is written in `leave()` (multiplayer.py:155-166) just before the presence row is deleted, so presence polls need no extra writes. Clients show it coarsely (방금 / 오늘 / 어제 / N일 전).

### 2.3 Presence changes (multiplayer.py:68-77, 234-248)
`Presence` gains optional fields. The model is Strict, so the client sends them only when `chat2` is advertised:
- `since: int | None = Field(default=None, ge=-1, le=2**53)`: the chat cursor (-1 or 0 = "send history").
- `place: Literal['village','home','workshop','expedition'] | None`: finer location. `scene` stays for old servers.
Store `place` in a new guarded column `mp_presence.place TEXT`.

If `since` is present, the reply **replaces** `messages` with:
```json
"chat": {"cursor": 1234, "history": false,
         "lines": [{"id":1230,"channel":"local","user_id":"…","username":"mina","to_name":null,"text":"…","created":…}]},
"social": {"v": 17, "requests": 1, "friends_online": 3}
```
Old clients (no `since`) keep the exact current `messages` behaviour. The existing test `test_party_messages_are_private_and_idempotent` must still pass.

Delivery query, one indexed statement:
```sql
SELECT e.id,e.channel,e.user_id,u.username,e.text,e.created,t.username AS to_name
FROM mp_messages e JOIN users u ON u.id=e.user_id LEFT JOIN users t ON t.id=e.to_id
WHERE e.id>? AND e.created>?            -- now-3600
  AND (e.room IN (?,?,'global') OR (e.room='dm' AND (e.user_id=? OR e.to_id=?)))
  AND e.user_id NOT IN (SELECT blocked_id FROM social_blocks WHERE user_id=?)
ORDER BY e.id LIMIT 50
```
The rooms are the user's village room `village:<host>` (even when in a party, which fixes the party-vs-visitor split) and the party room if any. For `since <= 0`, take the last 30 (`ORDER BY id DESC LIMIT 30`, reversed) and set `history: true`. `social.v` = `social_prefs.rev`. `friends_online` = COUNT over `social_friends` ⋈ `mp_presence` (seen > now-15, not appear_offline). Both are cheap PK lookups and are computed only for opted-in clients.

### 2.4 Chat endpoint (multiplayer.py:332-345)
`Message` adds `channel: Literal['local','party','global','whisper'] | None = None` and `to: str | None` (a username pattern, for whisper). With no channel, the legacy `room_for` behaviour applies. Rules, in order:
1. `chat_muted_until > now` → 403 `chat_muted`.
2. `clean_text`, then `chat_filter.mask(text)` (2.5). Empty → 422 `message_empty`.
3. Rate: the existing 1 s gap (429 `message_rate_limited`); a burst of at most 5 per 10 s; `global` at most 1 per 5 s; the same text as the user's previous line within 30 s → 429 `message_repeated`.
4. Channel resolution: `local` → `village:<host_for>`; `party` → `party:<id>` or 409 `not_in_party`; `global` → `'global'` or 403 `global_chat_off`; `whisper` → room `'dm'`, `to_id` = target **only if accepted friends, not blocked either way, and target online**, else 404 `whisper_target_unavailable` (one code for every reason).
5. Insert with `channel`; purge rows older than 24 h (existing).
Whispers are limited to friends on purpose (student safety); this is a policy decision for the user.

### 2.5 Word filter (`server/chat_filter.py`, new)
- Normalisation for matching only: NFKC, lowercase, strip zero-width and bidi (already done), and remove spaces, punctuation and digits *between* Hangul or Latin letters, so "시 1 발" still matches. Hangul compatibility jamo are matched as-is (catches ㅅㅂ-style abbreviations).
- Lists: `server/data/chat_words_ko.txt` (a small, plain-text, reviewed list in the repo, which is not a binary) plus the optional operator file `VILLAGEN_CHAT_FILTER_EXTRA`. Loaded once and compiled into one regex.
- Action: mask the matched span in the **original** text with `*` (not ♡, which may be tofu). Count masks per user in `security_events`; 3 masked lines in 5 min → auto `chat_muted_until = now+300` with notice `chat_muted`.
- The same filter applies to party and global lines and to the report text snapshot. Usernames are out of scope.

### 2.6 Friends, blocks, prefs, reports, people (`server/friends.py`)
The constructor mirrors Multiplayer: `Friends(app, db, settings, clock, auth, mutate, multiplayer)`, wired in app.py right after `Multiplayer` (app.py:632). It reuses `host_for`/`leave` (exported at multiplayer.py:515-517) and needs `start_visit` exported (2.7). All mutations go through `mutate()` (`request_id` idempotency, audit).

| Method & path | Body | Result / errors |
|---|---|---|
| `GET /v1/social/people` | — | see the JSON below |
| `POST /v1/friends/requests` | `{request_id, username}` | `{state:'sent'|'accepted'|'friends'}`. Unknown name → 404 `user_not_found` (invites already reveal names); self → 422 `friend_self`. **Silent `sent`** without a row when blocked either way, when the target's prefs say `nobody`, or within 24 h of their decline. A reverse pending request auto-accepts. Limits: 20 new requests/day → 429 `friend_requests_limited`; 20 pending outgoing; 100 friends → 409 `friend_list_full` |
| `POST /v1/friends/requests/{id}/{accept|decline|cancel}` | `Mutation` | accept inserts two `social_friends` rows; bumps `rev` on both users; 404 `request_unavailable` |
| `POST /v1/friends/remove` | `{request_id, user_id}` | deletes both rows, bumps rev |
| `POST /v1/social/blocks` / `POST /v1/social/blocks/remove` | `{request_id, user_id}` | Block also removes the friendship and pending requests, revokes pending invites both ways, and ends the blocked user's visit to my village (`end_visit(...,'ended')`) |
| `POST /v1/social/report` | `{request_id, user_id, message_id?, reason: spam|abuse|other, note≤200}` | stores a text snapshot; at most 10 reports/day/user |
| `POST /v1/social/prefs` | `{request_id, appear_offline?, requests?, drop_in?}` | returns prefs |
| `POST /v1/social/visit` | `{request_id, user_id}` | `{state:'visiting'|'asked'}` (2.7) |
| (admin) `GET /v1/admin/reports`, `POST /v1/admin/chat/mute {user_id, minutes}` | role admin (as /v1/admin/grant, app.py:310) | optional, for the teacher/operator |

`GET /v1/social/people` reply:
```json
{"v":17, "online_count":23,
 "online":[{"id":"…","username":"mina","character":"explorer_b","friend":true,
            "where":{"place":"village","host_id":"…","host_name":"jun"}}],
 "my_village":{"host":{"id":"…","username":"me","online":true},
               "guests":[{"id":"…","username":"jun","scene":"home","floor":1,"since":…}],
               "invites_out":[{"id":"…","username":"sora","kind":"village","expires":…}]},
 "friends":[{"id":"…","username":"jun","character":"ranger","online":true,"last_seen":null,
             "where":{…},"joinable":true}],
 "requests":{"incoming":[{"id":"…","username":"…","created":…}],"outgoing":[…]},
 "blocked":[{"id":"…","username":"…"}],
 "prefs":{"appear_offline":false,"requests":"everyone","drop_in":"off"}}
```
Privacy rules:
- **Online list:** every online user except `appear_offline` users and blocked users (either direction). It shows username and avatar character only. `where` is included **only** for friends and for people in the same village (same `host_id`). With `SOCIAL_ROSTER=friends`, `online` lists friends only and `online_count` is still given. With `off`, the list is empty.
- **Friends:** `online`/`where`/`last_seen` are hidden (shown as offline) when the friend has `appear_offline`.
- **My village:** the host sees every guest from `mp_visits(host_id=me, expires>now)` joined with `mp_presence.scene/y` (indoors included, which fixes the eject gap). Guests see the host plus the other guests.
- "Online" = `mp_presence.seen > now-15` (survival polls every 2 s; the workshop heartbeat is 3 s, 1 s after this change).
- `place` resolution: `mp_presence.place` if sent; else `village`/`home` from `scene`; `away` + `active_coop` → `expedition`; else `away`.
- `joinable` = friend, online, `place in (village, home)` at their own home (`host_for == self`), and fewer than 2 guests.
- **Cost:** the shared part (online presence rows ⋈ users, ≤ a few hundred rows) is cached in-process for 3 s. This is safe with one worker; note the assumption in code. The per-user parts are PK lookups. This runs in `db.read()`, never inside the 4 Hz write transaction.

### 2.7 Visit from the list ("knock")
1. Refactor the village branch of `answer()` (multiplayer.py:302-311) into `start_visit(conn, guest_id, host_id)`. It keeps the same checks: host seen < 20 s and at home, `village_full`, upsert `mp_visits`, delete guest presence and notice.
2. `POST /v1/social/visit {user_id}`: if accepted friends, the host's `drop_in='friends'`, and the guest's own presence scene is `village` (the guest client handles a host change only in the village poll; see social.gd poll `old_host != host_id`), then `start_visit` → `{state:'visiting'}`. Otherwise insert `mp_invites(kind='knock', sender=guest, recipient=host, expires now+120)` → `{state:'asked'}`. Blocked → silent `asked`. At most 1 knock per pair per 60 s (429 `knock_limited`).
3. `answer()` for `kind='knock'`: accept → if the guest is in the village scene, `start_visit(guest, host)`; else insert a normal `village` invite host→guest, which the guest's client auto-accepts if it knocked within 10 min. Decline → nothing more.
4. `Invite.kind` stays `village|party` (knocks are created only by `/v1/social/visit`). Invite create and answer also reject blocked pairs silently (404 `invite_target_unavailable`, as for unknown names).

### 2.8 Polling budget and 2 GB VM
- Steady state adds **zero** requests. Chat and badges ride presence. `/people` costs 0.2 Hz per user, and only while the window is open.
- The opt-in delivery query replaces the legacy JOIN of 20 lines on every poll, which is cheaper than today.
- Global channel: 60 users × at most 1 line per 5 s is at most 12 inserts/s at the theoretical peak, each a `mutate()` transaction with 3 rows. Realistically < 1/s. It fits, but it is gated by `VILLAGEN_GLOBAL_CHAT` so the operator can switch it off.
- **Recommended in the same release (client side):** adaptive presence. When the space has no other players, no guests and no visit, poll at 1 Hz instead of 4 Hz (social.gd:10/110, studio.gd:34/1970), and switch back to 4 Hz as soon as a reply lists another player. For 60 mostly-alone students this cuts about 240 tx/s to about 70. Chat latency stays ≤ 1 s.
- Before enabling on the school server, extend `tools/test_multiplayer_load.py` to 60 pollers plus chat and `/people` against **staging**, and record the CPU-credit drain. The map notes that no current benchmark exists.

### 2.9 Server tests
New file `server/tests/test_friends.py` (reuses the `world` fixture and the `post` helper from test_multiplayer.py:15-36):
- request → accept → both lists; reverse request auto-accepts; decline → 24 h silent cooldown; cancel; remove; caps (20/day, 100 friends) using the clock fixture.
- block: removes the friendship, hides from `online`, silent friend request and invite, whisper → 404, block filters chat delivery both ways, ends a visit.
- privacy: a non-friend sees no `where`, except in the same village; `appear_offline` hides from online and shows offline to friends; `SOCIAL_ROSTER=friends`/`off`.
- my_village: a guest in the host's **home** scene is listed for the host.
- visit: drop_in friends → visiting; drop_in off → knock invite; knock accept with the guest in the village → visit started; with the guest away → village invite created; village_full; host away.
- people cache: two calls within 3 s hit the cache (clock-controlled), and a 4 s gap refreshes.

New file `server/tests/test_chat.py`:
- legacy path unchanged (no `since` → `messages`; no channel → room_for).
- cursor: since=0 → history ≤ 30 with `history:true`; since=n → only newer lines; local + party + global + own whispers merged and ordered; the 1 h window.
- channels: `not_in_party`, `global_chat_off` setting, a whisper to a non-friend/offline/blocked user → same 404; the other user sees `to_name`.
- rates: 1 s gap, burst 5/10 s, global 1/5 s, `message_repeated`.
- filter: masking with spaced or digit-split Hangul and with jamo; an auto-mute after 3 masked lines; `chat_muted`.
- report stores a snapshot; admin endpoints require role admin.

`server/tests/test_admin_cli.py`: deleting an account removes `social_blocks` rows that reference it as `blocked_id`.

---

## 3. Client design (PCK)

### 3.1 SocialHub (`game/scripts/social_hub.gd`, new; session node, not an autoload)
- `static func of(api) -> Node`, which creates it under `tree.root`, keyed by `base_url|token`, with `static func end(api)` called on logout and `session_lost`. This is the same pattern as craft_tracker.gd:51-72, and `main` calls it where it resets the social session (main.gd:757-760, `force_logout`).
- State: `features: PackedStringArray` (from `/health social_features`; empty = legacy), `cursor:int=0`, `lines: Array` (ring of 120, deduped by id), `unread: int`, `people: Dictionary`, `people_v:int`, `blocked: Dictionary`, `knocked: Dictionary` (host_id → time), `channel: String = "local"`.
- `ingest(reply: Dictionary)`. It is called by social.gd `poll()` (in place of the toast loop at 170-173) and by studio.gd `share_presence()` and `keep_present()` (the reply is currently ignored at 1596-1600).
  - With `chat2`: append `reply.chat.lines`, set `cursor`. History lines are added as `history=true` and emit no notices or bubbles.
  - Legacy: use `reply.messages`, dedupe by id. On the **first** reply of the session, mark all as history (fixes the replay).
  - `reply.social.v != people_v` → refresh `/people` once and emit `people_changed`. When `requests` grows, emit `notice("friend_request", …)`. When the invites list gains an id, emit `notice("invite", …)`.
- `presence_extra() -> Dictionary` returns `{since: cursor, place: …}` when `chat2` is advertised. social.gd `spot()` and studio.gd spot dictionaries merge it. If a 422 arrives with these fields, drop them, mirroring `rich_presence` at social.gd:153-155.
- `send(text, channel, to="")` POSTs `/v1/social/messages` with a `request_id` (api.gd mutation helper), adds a pending local echo line (greyed until the next cursor delivery), and maps errors to Korean `tr()` notices in the chat log (not the toast).
- Slash commands parsed client-side: `/w 이름 내용` or `/귓 이름 …` (whisper), `/r` (reply to the last whisperer), `/p`, `/v` (마을), `/g` (전체) to switch channel. `/` alone does nothing.
- `refresh_people()` GETs `/v1/social/people`; it is timed every 5 s by the SocialWindow while open.
- Signals: `line_added(entry)`, `people_changed()`, `notice(kind, data)`.

### 3.2 ChatBox (`game/scripts/chat_box.gd`, new Control)
Placement (design canvas 1280×800, anchored with `RpgUi.pin(box, 0, 1)` so ui_scale works):
- Village: x 14..374, bottom edge at y 690 (it stays **above** the hotbar row, which starts at y 700, so the growing hotbar never overlaps it), height 210 when active. SocialChip (y 108) and the drawer inspector (y 206, drawer only) stay clear. The F3 dev panel at (20,520) overlaps, which is acceptable for a dev tool.
- Survival: x 14..284, bottom 786 (toolbar starts at x 300; left panels end around y 560).
- Rooms: x 18..378, bottom at 800-66-10 (above RoomNav, studio.gd:460-468). It goes idle and mouse-transparent while `placement_mode`.
- Registered as fold id `"chat"` (`RpgUi.fold_shift`), so U folds it with the HUD. It is a child of `ui`, so `main.hide_hud()` hides it during NPC dialogue.

Structure:
- `PanelContainer` (`RpgUi.panel_style("pill")`, background alpha animated) → VBox:
  1. Filter chips row: 전체 · 마을 · 파티 · 귓속말. Shown only when active.
  2. Log: `ScrollContainer` + VBox of `Label`s (one per line, autowrap, 14 pt body). Format `[채널] 이름: 내용`. Names in `RpgUi.GOLD`; channel colours as new `RpgUi.CHANNEL_COLORS`: 마을 = INK, 파티 = teal `7fd1c4`, 전체 = `c9b8ff`, 귓속말 = `f0a8c8`, 시스템 = `RpgUi.SOFT`. Blocked users' lines are never shown.
  3. Input row: channel chip button (cycles 마을/파티/전체; colour-coded; hidden channels drop out when unavailable) + `RpgUi.field(…, latin=false)` (NightField look, `max_length=160`, `keep_editing_on_text_submit=false`) + `RpgUi.keycap("Enter")`.
- **Idle mode** (not focused, not hovered): transparent background, input row hidden, a small `Enter 대화` keycap hint, only the last 6 lines. Each line holds full alpha for 8 s and fades to 0 by 12 s (one Tween per line). The log has `mouse_filter = IGNORE`, so world clicks pass through.
- **Active mode** (focused, or mouse hover over the box rect): background at alpha .85, all retained lines, scrollbar, auto-scroll to the bottom unless the user scrolled up (then a `▼ 새 메시지 N` pill appears).
- Unread: when the box is folded or hidden, a dot plus count appears on the SocialChip chat icon.

Focus and keys. This is the "never types into chat unless focused, never stuck" contract:
1. **Enter / KP_Enter opens chat.** In `main._unhandled_input`, before the `village_modal` early return? No: after it. Enter opens chat only when there is no `village_modal`, no PauseMenu, no `painter`/`interaction_panel`/`preview`, and `!text_input_active()`. Then `chat.focus()` (`grab_focus(); edit()`) and `set_input_as_handled()`. In studio `_unhandled_key_input` (1641-1680), the same check comes **after** the `talk_box` branch, so Enter still advances room dialogue. The SocialChip chat icon and a click on the idle hint also focus. Never a printable key, so T and / stay free and WASD can never type.
2. **Enter sends and returns to play.** In the `text_submitted` handler:
   1. If `DisplayServer.ime_get_text()` is non-empty (Windows Korean: the last syllable is committed after Enter), await up to 3 `process_frame`s until it is empty, then re-read `field.text`.
   2. If non-empty, `hub.send()`.
   3. `field.clear()`, then `field.release_focus()` **synchronously**. ImeCaret re-`edit()`s only the *focused* field (ime_caret.gd:80-88), and LineEdit's own `unedit()` leaves focus in place (engine line_edit.cpp:928), so the explicit release is required.
   An empty Enter just releases.
3. **Esc cancels.** LineEdit accepts `ui_cancel` and unedits (line_edit.cpp:940-946), and ImeCaret releases focus the next frame (ime_caret.gd:81-84, 114-118). The pause menu does not open. The typed draft is kept (MMO convention) unless empty.
4. **A world click releases.** In the `main._unhandled_input` mouse branch (~2944) and in studio's `_unhandled_input`: if the chat field has focus, `gui_release_focus()` and **consume** the click, so it does not also trigger `click_furniture`. This is needed because engine viewport.cpp:1941-1950 keeps focus on a world click.
5. **Any modal or dialogue opening releases** chat focus: in `modal_card`, `open_dialogue`, `open_craft`, the PauseMenu open hook, the painter and interaction_panel, and studio `open_talk`.
6. **No stuck keys.** On the field's `focus_exited`, call `Input.action_release()` for `move_forward/back/left/right` and `run`. This covers the unpatched-template IME stuck-key bug (tools/engine_patches/godot-4.7.2-ime-stuck-keys.patch is template-only). A key still physically held resumes on its next press.
7. Movement while typing is already blocked by `text_input_active()` (main.gd:2709) and studio's focus check (1664-1665). Also gate `field_objects.walker_moving()` (field_objects.gd:283) with `app.world_movement_allowed()`, so chat typing cannot end a seat or telescope view.
8. While focused, Tab / I / C and other hotkeys are ignored, because `_unhandled_input` returns on `text_input_active` (main.gd:2884).

### 3.3 Speech bubbles (`game/scripts/speech_bubble.gd`, new)
- `SpeechBubble.pop(walker: Node3D, text: String)` adds a pooled `Label3D` at y 2.45 (above the nameplate at 2.05), billboard, `width 260 px`, autowrap, max 60 chars plus `…`, outline, and a night-pill style `Sprite3D` back plate. It shows for `clamp(2.5 + 0.06*len, 3, 7)` s with a pop-in tween (modelled on shadow_figure.gd:315-323, 816-823).
- Shown for `local` and `party` lines whose `user_id` matches a drawn peer (social.gd `peers`, studio.gd `peers`) or self (`app.player` / `studio.hero`). No bubbles for global, whisper or history lines.
- Respects `art.gd plate_priority`. Cost is one Label3D per speaking walker, freed after hiding.

### 3.4 Social window (`game/scripts/social_window.gd`, new)
Look, unified with the parchment game windows:
- A parchment `RpgUi.panel_style("paper")` card 420 wide, pinned right (`RpgUi.pin(card, 1, 0)`, top 20) like the bag drawer (main.gd:999). Header: Jua `RpgUi.heading` "함께하기", a keycap `K`, and one icon close button (new `RpgUi.close_key(parent, "K")`, 34 px flat, tooltip `닫기 · K`). Opening hides the minimap and objective with the same `fold_shift` the drawer uses, and is mutually exclusive with the bag drawer.
- It is **non-modal**: it is not counted in `world_movement_allowed()`, so the player keeps walking and chatting. Esc closes it first in the main Esc chain (main.gd:2876-2882), before the drawer. In rooms it is built with `RpgUi.theme()`, as craft_window does, so it looks identical.

Tabs use the theme's TabContainer gold/paper frames (rpg_ui.gd:286-295):
1. **친구**
   - Requests strip at the top (incoming, with 수락/거절 buttons; outgoing, with 취소).
   - Friend rows sorted online first. Each row:
     - portrait thumb (`portrait_<avatar.character>.png`, 40 px round frame; no SubViewports)
     - status dot: LEAF = online in a village or home; amber = workshop or expedition; grey = offline
     - username (strong 15)
     - caption: "준님의 마을 · 집 안", "탐험 중" or "어제 접속"
     - icon HudSlot buttons (32 px): **놀러가기** (`/v1/social/visit`, enabled when `joinable` or the knock is allowed), **마을 초대** (existing `/v1/social/invites` by username, kind village; only when at home), **귓속말** (focuses chat with `/w name `), and `…` (PopupMenu: 파티 초대, 친구 삭제, 차단, 신고).
   - A `RpgUi.field` "이름으로 친구 신청" plus button.
   - A collapsed "차단 목록" section with 해제.
   - Footer toggles: 접속 숨기기, 친구 신청 받기, 친구가 바로 놀러 오기 (prefs).
2. **접속 중**: "지금 N명 접속 중" plus rows (portrait, name, a location only when the server provides it). Row actions: 친구 신청, 귓속말 (friends only), and `…` with 차단/신고.
3. **내 마을**
   - A host card.
   - Guests with location (마을 / 집 n층) and **내보내기** (existing `/v1/social/eject`, which now also works for guests indoors).
   - Pending village invites I sent.
   - The party block (members with online state, invite, leave, start an expedition), moved from the old 함께하기 modal.
   - When visiting: the host's name and 내 마을로 돌아가기 (existing return_home, social.gd:406-418).
- Refresh: `hub.refresh_people()` on open and every 5 s while open, plus on `people_changed`.
- Legacy server: only the 내 마을 tab, showing today's data (party, invites, eject, invite by name). The other tabs show "이 서버에서는 아직 친구 기능을 쓸 수 없어요".

### 3.5 Notifications (`game/scripts/social_notice.gd`, new)
- A small night-pill card stack under the toast lane (top-centre, y 140, at most 2 cards, 12 s each, with the `toast` sfx and `RpgUi.pop_in`). It is separate from the one-line system toast, so chat and notices no longer overwrite each other.
- Kinds:
  - incoming friend request: [수락] [보기]
  - village or party invite: [수락] [거절]. Today invites are invisible except for a counter (social.gd:84).
  - knock to the host: "○○님이 놀러 와도 되는지 물어요" [수락] [거절]
  - knock accepted or visit started
  - a friend came online: at most once per friend per 10 min, setting-toggleable, off by default to avoid noise
- System events also land in the chat log as SOFT lines: arrivals and departures in my village, friend requests accepted.

### 3.6 HUD entry points (consistent with the existing kit)
- **SocialChip** (social.gd:42-77, kept in place): the people icon opens the Social window (친구 tab) with a red badge = incoming requests + invites. The chat icon focuses the ChatBox (the fixed greeting is removed) and shows an unread dot. The status line shows `마을 · 친구 3명 접속`.
- A **new action `social`, default K**, added to `GameSettings.ACTIONS` (game_settings.gd:102-121), so it appears in settings rebinding and is created at runtime by `apply_input()`. Add `const RUNTIME_ACTIONS := ["social"]` and make `tests/settings_check.gd:88-93` skip these, because project.godot must not change. Chat stays on the reserved Enter key, shown as a fixed keycap.
- The hotbar is unchanged in the village, which keeps the 7-8 slot width fine. Rooms: add a `친구 K` slot to the 2-slot room hotbar (studio.gd:493-498) and add a SocialChip to the room HUD so both scenes have the same entry points.
- The pause menu "조작" page (pause_menu.gd:200-226) adds 대화 Enter, 친구 K, HUD 접기 U.
- Key hints use `GameSettings.key_label("social")`, not literals.

### 3.7 File-level change list (client)
| File | Change |
|---|---|
| `game/scripts/social_hub.gd` | NEW (3.1) |
| `game/scripts/chat_box.gd` | NEW (3.2) |
| `game/scripts/speech_bubble.gd` | NEW (3.3) |
| `game/scripts/social_window.gd` | NEW (3.4) |
| `game/scripts/social_notice.gd` | NEW (3.5) |
| `game/scripts/social.gd` | poll → `hub.ingest`; remove the toast loop 170-173; `spot()`/`heartbeat()` merge `hub.presence_extra()`; adaptive interval; peers get bubbles; `open_menu` → SocialWindow; the old modal content moves to the 내 마을 tab; chip icons rewired; remove the 👋 greeting |
| `game/scripts/studio.gd` | `share_presence`/`keep_present` → `hub.ingest`; workshop heartbeat 3 s → 1 s when `chat2`; build_ui adds ChatBox, SocialChip, 친구 hotbar slot; RoomNav stays bottom-left with the chat box above it; Enter/K routing after `talk_box`; world-click focus release; peers bubbles |
| `game/scripts/main.gd` | create `SocialHub.of(api)` after login, `end` on logout; read `social_features`; ChatBox in `build_village_hud` and `build_play_hud`; Enter/K in `_unhandled_input`; Esc chain closes the Social window; world click releases chat focus; release chat focus in `modal_card`/`open_dialogue`/`open_craft`; also fix the unreachable dialogue-advance branch (2928) by handling E/Space/Enter inside the `village_modal` early-return block when `village_modal.has_meta("advance")` |
| `game/scripts/field_objects.gd:283` | gate `walker_moving()` on `app.world_movement_allowed()`; mailbox (985-1046) reads hub invites |
| `game/scripts/rpg_ui.gd` | add `CHANNEL_COLORS`, `close_key()`, `side_card()`, `avatar_thumb(character)`, `status_dot()` |
| `game/scripts/game_settings.gd` | `["social","친구 · 접속",[KEY_K,KEY_NONE]]`, `RUNTIME_ACTIONS` |
| `game/scripts/pause_menu.gd` | controls rows |
| `game/tests/settings_check.gd` | skip `RUNTIME_ACTIONS` in the project.godot check |

No change to `game/project.godot` or `patch_boot.gd`. Verify with `tools/game_patch.py` (it must report no settings or boot change).

### 3.8 Client tests
- `game/tests/chat_box_check.gd` (new, headless, stub hub):
  - Enter focuses; pressing W while focused does not move the player and types `w`.
  - Enter sends and releases focus (`gui_get_focus_owner()==null` the next frame, and ImeCaret does not re-edit).
  - Empty Enter releases; Esc releases and the pause menu stays closed.
  - A world click releases and does not call `click_furniture`; opening the craft window or a dialogue releases.
  - After focus exit, every move action reports not pressed.
  - Enter during room `talk_box` advances the talk and does not open chat.
- `game/tests/social_hub_check.gd`: cursor handling, dedupe, history lines not bubbled or notified, legacy fallback (first-reply replay suppressed), 422 fallback drops `since`/`place`, survives a village→room→village change (same node, same cursor).
- `game/tests/ime_typing.gd` (extend 201-214): with the real IME via `tools/ime_type.ps1`, type 한글 + Enter in the **HUD chat**, check the full last syllable is sent and focus released, then W walks and stops on key-up. Run on both patched and unpatched templates.
- `game/tests/multiplayer.gd` (84-86): two clients exchange a local line and a whisper; a bubble appears over the peer.
- `game/tests/ui_gallery.gd`: new shots for chat idle and active (village, survival, room), the Social window 3 tabs, the notification card, and the room HUD with chip.
- `game/tests/hud_fold_check.gd`: the `chat` fold id; SocialChip still under `ui` (239).

---

## 4. Rollout
1. Server work (WP1, WP2) goes to **staging**. Run the pytest suite and the 60-user load test there.
2. Client PCK against staging with the DEV client (3 people).
3. School server deploy. The client feature-detects, so the judges' server keeps its legacy behaviour, and the ChatBox and 내 마을 tab still work there.
4. Update the roadmap (`roadmap.json` + tools/build_roadmap.py) and write a Korean test doc with figures for the in-engine verification. Note for the parent agent: the user's memory rule requires a PNG layout figure with any plan shown to them, showing the HUD placement of the chat box, SocialChip and Social window on the 1280×800 canvas.

## 5. Decisions the user should confirm
1. Global ("전체") channel on the school server: on, with filter + rate limits + mute (default proposed), or off.
2. Roster visibility: everyone sees every online username (`all`, proposed), or friends only.
3. Whispers friends-only (proposed) or to anyone online.
4. Friends' drop-in default: `off` (knock required, proposed) or `friends`.
5. Social window as a non-modal right-side parchment panel (proposed, keeps walking and chatting) vs a centred modal like the current one.


## Work packages

### WP1 Server chat v2: channels, cursor delivery, history, filter, rate limits
- Goal: Add opt-in Presence.since/place, a chat block with cursor and history, Message.channel/to (local/party/global/whisper), mp_messages.channel/to_id columns, chat_filter.py with a Korean word list, burst/global/repeat limits, chat_muted, and a health social_features flag, while keeping the legacy messages path byte-compatible for old clients.
- Files: server/multiplayer.py, server/chat_filter.py, server/data/chat_words_ko.txt, server/app.py, server/config.py, server/tests/test_chat.py, server/tests/test_multiplayer.py
- Tests: legacy presence without since still returns messages (room_for) and test_party_messages_are_private_and_idempotent passes; since=0 returns <=30 history lines with history:true; since=n returns only newer lines across local+party+global+own whispers; whisper to non-friend/offline/blocked -> identical 404 whisper_target_unavailable; rate: 1 s gap, 5 per 10 s burst, global 1 per 5 s, message_repeated; filter masks spaced/digit-split Hangul and jamo; 3 masked lines -> chat_muted; global_chat setting off -> 403 global_chat_off; health lists social_features
- Risk: Strict Presence/Message models: new fields must be sent only when advertised, or old servers 422; delivery query must stay index-backed inside the 4 Hz write transaction.

### WP2 Server friends, blocks, prefs, reports, people roster, knock/drop-in visits
- Goal: New server/friends.py with social_friends/social_requests/social_blocks/social_prefs/social_reports tables, endpoints /v1/friends/*, /v1/social/{people,blocks,report,prefs,visit}, start_visit refactor and the 'knock' invite kind in multiplayer.py, block enforcement in invites/chat/roster, mp_presence.place column, last_seen written in leave(), 3 s in-process roster cache, optional admin mute/report review, and 'blocked_id' in admin_cli USER_COLUMNS.
- Files: server/friends.py, server/multiplayer.py, server/app.py, server/admin_cli.py, server/tests/test_friends.py, server/tests/test_admin_cli.py, tools/test_multiplayer_load.py
- Depends on: WP1
- Tests: request/accept/decline/cancel/remove; reverse request auto-accepts; 24 h silent cooldown after decline; 20/day and 100-friend caps; block removes friendship, silences requests and invites, hides from online, ends visit; privacy: non-friends get no 'where' except same village; appear_offline; SOCIAL_ROSTER=friends/off; my_village lists a guest inside the host's home scene; visit: drop_in friends -> visiting; off -> knock invite; knock accept with guest in village starts visit, else creates village invite; village_full/host_offline; admin_cli delete-accounts removes social_blocks rows by blocked_id; load test: 60 pollers + chat + /people on staging, record CPU
- Risk: Extra queries must stay out of the 4 Hz write transaction; the module cache assumes a single uvicorn worker; start_visit refactor must not change existing invite semantics.

### WP3 Client SocialHub session node and presence ingestion
- Goal: New game/scripts/social_hub.gd (CraftTracker.of pattern under tree.root) holding chat history, cursor, features, people cache, blocked set and notices; social.gd and studio.gd feed every presence reply into hub.ingest, merge hub.presence_extra() into spots, drop the toast relay, fix the history replay, add adaptive 1 Hz idle polling and a 1 s workshop heartbeat that reads replies; main.gd creates/ends the hub and reads social_features.
- Files: game/scripts/social_hub.gd, game/scripts/social.gd, game/scripts/studio.gd, game/scripts/main.gd, game/tests/social_hub_check.gd
- Depends on: WP1
- Tests: cursor advances, lines deduped, history lines emit no notices or bubbles; legacy server: first reply seeded silently, no replay after a village->room->village trip; 422 with since/place -> fields dropped and polling continues; adaptive interval: 1 Hz alone, 4 Hz once another player is listed; hub survives scene changes and ends on logout/session_lost
- Risk: Two pollers (social.gd, studio.gd) must not double-ingest or race the cursor; the hub must be keyed per session to avoid leaking across accounts.

### WP4 Always-on ChatBox, input routing, IME safety and speech bubbles
- Goal: New chat_box.gd (idle fade log + focus-only input, channel chip, slash commands, unread badge) placed bottom-left in village (bottom y 690), survival (x<=284) and rooms (above RoomNav), with fold id 'chat'. Enter focuses; Enter sends, then release_focus synchronously after waiting out IME composition; Esc cancels; a world click releases and is consumed; modals and dialogues release; focus_exited releases move actions; field_objects.walker_moving gated. New speech_bubble.gd for local/party lines over peers and self in village and rooms. Fix the unreachable village dialogue keyboard advance.
- Files: game/scripts/chat_box.gd, game/scripts/speech_bubble.gd, game/scripts/main.gd, game/scripts/studio.gd, game/scripts/social.gd, game/scripts/field_objects.gd, game/scripts/rpg_ui.gd, game/tests/chat_box_check.gd, game/tests/ime_typing.gd, game/tests/multiplayer.gd
- Depends on: WP3
- Tests: Enter focuses; W while focused types and does not move; Enter sends and focus is released next frame (ImeCaret does not re-edit); empty Enter releases; Esc releases without opening the pause menu; world click releases focus and does not trigger click_furniture; opening craft/dialogue/modal releases focus; move actions not pressed after focus exit; room talk_box: Enter advances talk, not chat; real Korean IME (tools/ime_type.ps1): last syllable sent, then W walks and stops on key-up, on patched and unpatched templates; peer bubble appears for a local line, not for global/whisper/history
- Risk: Korean IME commit order on Windows (last syllable after Enter) and the template-only stuck-key engine bug; ImeCaret's force-edit behaviour can fight focus release if release is deferred.

### WP5 Unified Social window (친구 / 접속 중 / 내 마을), notifications and HUD entry points
- Goal: New social_window.gd: a non-modal parchment right-side card with three tabs built from RpgUi (portrait thumbs, status dots, icon actions: visit, invite, whisper, more menu with party invite, remove, block, report; add-by-name; requests strip; blocked list; privacy toggles; my-village guests with eject incl. indoors; party block migrated from the old 함께하기 modal). New social_notice.gd card stack for friend requests, invites and knocks with inline accept. SocialChip rewired (people → window with badge, chat → focus chat). Room HUD gets a SocialChip and a 친구 K hotbar slot. New 'social' action (K) via GameSettings.ACTIONS + RUNTIME_ACTIONS; settings_check relaxed; pause controls page updated; RpgUi gains close_key/side_card/avatar_thumb/status_dot/CHANNEL_COLORS. Legacy servers show only 내 마을.
- Files: game/scripts/social_window.gd, game/scripts/social_notice.gd, game/scripts/social.gd, game/scripts/studio.gd, game/scripts/main.gd, game/scripts/rpg_ui.gd, game/scripts/game_settings.gd, game/scripts/pause_menu.gd, game/scripts/field_objects.gd, game/tests/settings_check.gd, game/tests/ui_gallery.gd, game/tests/hud_fold_check.gd
- Depends on: WP2, WP3, WP4
- Tests: ui_gallery shots: chat idle/active (village, survival, room), three Social tabs, notice card, room HUD with SocialChip; K opens/closes in village and rooms; Esc closes window before drawer/pause; movement continues while open; window refreshes /people every 5 s only while open; badge updates from social.v without /people polling; legacy server: only 내 마을 tab with party/invites/eject; settings_check passes without project.godot changes; K appears in rebinding UI; tools/game_patch.py reports no settings/boot change
- Risk: HUD real estate (minimap/objective fold interplay, room RoomNav) and keeping the parchment look identical in rooms, where studio has its own flat theme.

## Risks

- Strict pydantic models (extra='forbid'): new Presence/Message fields break against old servers unless sent only when /health social_features advertises them; the client must also fall back on a 422.
- Single uvicorn worker + SQLite single writer on a shared 2 GB t4g.small: 4 Hz presence for ~60 students is already ~240 write tx/s; the global channel and roster must stay out of the poll transaction, and adaptive 1 Hz idle polling plus a staging load test are strongly advised before school rollout.
- Korean IME: engine fixes (lost syllables #123269, stuck WASD after composition) ship only in custom export templates, not a PCK; the always-on box toggles focus far more often, so the submit-wait-then-release logic and Input.action_release on focus exit must be verified with tools/ime_type.ps1 on unpatched templates.
- ImeCaret force-edits any focused LineEdit every frame; if release_focus is deferred, chat can re-enter edit mode and lock movement until Esc.
- The in-process roster cache assumes workers=1; raising uvicorn workers later would make roster/online counts inconsistent without moving the cache to SQLite.
- Student privacy/safety is a policy choice (server-wide roster, global chat, whisper scope, drop-in default); defaults proposed here must be confirmed by the user and possibly the school.
- Word-filter false positives and negatives in Korean (spacing and jamo tricks); the list needs review and an operator-editable extra file; auto-mute could frustrate legitimate users.
- Two client pollers (social.gd in main, studio.gd in rooms) feeding one SocialHub can double-ingest or race the cursor during scene changes.
- settings_check.gd currently requires project.godot to declare every ACTIONS entry; adding K without the RUNTIME_ACTIONS exemption would push someone to edit project.godot and force a full reinstall.
- Knock/drop-in host changes are only handled by the village poll; starting a visit while the guest is in a room or on an expedition must be avoided (fall back to an invite), or the guest client reaches an inconsistent state.