# Villagen social API (server side of Social WP1 + WP2)

Reference for the client run (SocialHub, ChatBox, Social window). Server code: `server/chat.py`,
`server/chat_filter.py`, `server/friends.py`, `server/multiplayer.py`; tests: `server/tests/test_chat.py`,
`test_chat_filter.py`, `test_friends.py`, `test_admin_cli.py`. Design background:
`SOCIAL_CHAT_FRIENDS.md` and `DESIGN_CRITIC.md` (SERVER-M1 + SERVER-M2).

All times are server epoch seconds (float). All mutations take a `request_id` (UUID v4): a retry
with the same id and body returns the first answer; the same id with another body is
`409 request_id_reused`. Errors are `{"detail": "<code>"}`; 429 and some 403 answers carry a
`Retry-After` header (whole seconds). Every route needs `Authorization: Bearer <token>`.

---

## 1. Feature detection (`GET /health`)

```json
{"multiplayer_protocol": 1,
 "social_features": ["chat2", "place", "people", "friends", "visit", "report"],
 "global_chat": true,
 "social_roster": "all",
 "interaction_sync": 1,
 "chat_max_length": 160,
 "social_poll": {"presence_together": 0.25, "presence_alone": 1.0, "people": 5.0, "presence_budget": 60.0}}
```

| Flag | Client may then use |
|---|---|
| `chat2` | `since` in presence, the `chat`/`social` reply blocks, `channel`/`to` in messages |
| `place` | `place` and `floor` in presence |
| `people` | `GET /v1/social/people` |
| `friends` | `/v1/friends/*`, `/v1/social/blocks*`, `/v1/social/prefs` |
| `visit` | `POST /v1/social/visit`, knocks in the overview, `knock` in invite answers |
| `report` | `POST /v1/social/report` |
| `interaction_sync: 1` | `ix` in presence (Sockets WP17) |
| `global_chat` | the `global` channel is open (false: `403 global_chat_off`) |
| `social_roster` | `all`, `friends` (the online list shows friends and same-village players only) or `off` |
| `social_poll` | operator-tunable polling advice in seconds (section 9) |

`multiplayer_protocol` stays 1. A server without `social_features` (the judges' server, 0.11.x
servers) is the legacy path: no new fields are sent, the ChatBox uses `messages`.
Read `/health` at login, after a room return, and again after any 422 or version_gate, and keep the
result in the session (SocialHub) so rooms see it too.

---

## 2. Presence (`POST /v1/social/presence`), the 4 Hz poll

### 2.1 Request
Every field is optional. Old fields as before: `scene` (`village`|`home`|`away`), `x`,`z` (−100..100),
`y` (−20..40), `yaw`, `vx`,`vz` (−30..30), `t` (sender clock, 0..1e10).

| Field | Group (flag) | Type | Meaning |
|---|---|---|---|
| `since` | chat2 | int −1..2^53 | the newest chat line id this client holds; `0` (or −1) asks for history |
| `place` | place | `village`\|`home`\|`workshop`\|`room`\|`expedition` | where the player is; for lists only (`scene` still decides who is drawn) |
| `floor` | place | int 0..9 | home floor, shown in "내 마을" and friends lists |
| `ix` | interaction_sync | object | interaction state, stored and echoed, never interpreted (below) |

`ix` = `{"k": socket type [a-z][a-z0-9_]{0,23}, "p": "enter"|"hold"|"act"|"exit", "c": clip set [a-z0-9_]{0,48},
"t0": sender clock 0..1e10, "o": object ref [A-Za-z0-9_:#.-]{0,64} (obj:<id>, prop:<model>#<n>, fx:<id>, rf:<floor>:<i>),
"s": socket id [a-z0-9_]{0,32}, "h": height offset −0.3..0.3}`. Omit `ix` when not interacting: every poll
replaces the stored value, so an absent `ix` clears it.

### 2.2 The 422 rule (negotiation)
The model is strict (unknown fields are refused). For this route the 422 names the refused
top-level fields:
```json
{"detail": "invalid_request", "fields": ["ix"]}
```
Client rule: drop the group that owns each listed field (`since` → chat2 off for this session,
`place`/`floor` → place off, `ix` → ix off) and poll again at once. If `fields` is missing (an older
server) or lists only old fields, drop the newest group you sent first, then the 0.11.4 fields
(`vx`,`vz`,`t`) as today. Never send a group the server did not advertise.

### 2.3 Reply
Unchanged keys: `self_id, host_id, host_name, visiting, party, invites, pending_rewards, visit_ended,
village, space, npc_homes`. Changes:
- `messages` (legacy, the last 20 lines of the old room) is **only sent without `since`**.
- `knocks` appears only when someone knocks on your village (2.4); `invites` never contains knocks
  (a released game would show one as a party invitation).
- `space.players[*].ix` appears only for players who sent one.
- Blocked players (either direction) are left out of `space.players`, `messages` and `chat`.
- With `since`: `chat` and `social` (below).

```json
"chat": {"cursor": 1234, "history": false, "more": false,
         "lines": [{"id": 1230, "channel": "local", "user_id": "…", "username": "mina",
                    "text": "안녕", "created": 1781234567.2},
                   {"id": 1233, "channel": "whisper", "user_id": "…", "username": "jun",
                    "to_id": "…", "to_name": "mina", "text": "…", "created": …}],
         "removed": [1201]},
"social": {"v": 17, "requests": 1, "knocks": 0, "friends_online": 3,
           "poll": {"together": 0.61, "alone": 2.45}, "muted_until": 1781234999.0}
```

Chat block rules:
- `cursor`: send it back as `since` next time. It is the newest line id on the server, so after a
  room change the old lines of the new room are not replayed. If you want the new room's recent
  lines (joined a party, started a visit), send `since: 0` once.
- `history: true` (since ≤ 0, or a cursor newer than the server's, e.g. after a restore): the newest
  ≤ 30 lines of your rooms from the last hour. Seed the log silently (no notices, bubbles or unread).
- `more: true`: more than 50 new lines were waiting; poll again soon with the new cursor.
- Lines come from: your village room (the village you are in, also while in a party), your party,
  `global` (when on), whispers to you and whispers you sent. Never older than 1 hour.
- `channel`: `local` (village/visit), `party`, `global`, `whisper`. Lines from 0.11.x clients
  arrive as `local` or `party`.
- `removed`: ids an operator deleted in the last 15 minutes; drop them from the log if shown.
- Your own line arrives too: replace your pending echo by `id` (the send reply has the id).

Social block: `v` changes on any friend/request/block/knock/privacy change touching you, so
refetch `/v1/social/people` only when `v` changes (or every 5 s while the window is open).
`requests` = incoming friend requests, `knocks` = knocks waiting at your village,
`friends_online` = friends online and visible, `muted_until` only while muted.
`poll` = the presence intervals (seconds) the server wants now: `together` when another player is
in your space (or a party run, an invite, a knock or anyone's interaction is under way), `alone`
otherwise. Follow it on every reply (section 9).

### 2.4 Knocks in the overview (`GET /v1/social`, presence, invite answers)
```json
"knocks": [{"id": "…", "sender_id": "…", "sender": "jun", "expires": …}]
```
Answer with the existing `POST /v1/social/invites/{id}/accept|decline` (`Mutation` body). The reply
is the overview plus `"knock": "visiting"` (the guest was in their village and walked straight in)
or `"knock": "invited"` (the guest is indoors or away: a normal village invitation host → guest was
created; the guest's client should accept it automatically if it knocked within 10 minutes).
Errors as for invitations (`invitation_expired`, `village_full`, `host_offline`,
`return_home_before_inviting`, `party_expedition_active`).

---

## 3. Chat (`POST /v1/social/messages`)

```json
{"request_id": "…", "text": "1..160 chars", "channel": "local|party|global|whisper", "to": "username"}
```
No `channel` = the 0.11.x behaviour (the party room when in a party, else the village room).
`to` only for whispers. Reply:
```json
{"ok": true, "id": 1235, "channel": "local", "text": "아 * * 진짜", "masked": true, "muted_until": 1781235300.0}
```
`text` is what everybody sees (after cleaning and masking); `muted_until` only when this line
triggered the automatic mute. Checks, in order:

| # | Check | Answer |
|---|---|---|
| 1 | cleaned text empty (controls, bidi, zero-width removed) | 422 `message_empty` |
| 2 | same `request_id` again | the first reply (or 409 `request_id_reused`) |
| 3 | a word on the block list (`!` entries; none by default) | 422 `message_blocked` |
| 4 | muted (auto or operator) | 403 `chat_muted` + Retry-After |
| 5 | `party` without a party | 409 `not_in_party` |
| 6 | `global` switched off | 403 `global_chat_off` |
| 7 | whisper target not a friend / offline / appearing offline / blocked / unknown / self | 404 `whisper_target_unavailable` (always the same) |
| 8 | under 1 s since your last line, or 5 lines in 10 s | 429 `message_rate_limited` + Retry-After |
| 9 | the same text as one of your last 3 lines within 30 s | 429 `message_repeated` |
| 10 | `global` within 5 s of your last global line | 429 `global_chat_slow` + Retry-After |
| 11 | more than 600 lines a minute from one address (a school shares one) | 429 `chat_ip_limited` |
| 12 | more than 20 global lines in 10 s on the whole server | 429 `global_chat_busy` |

The filter masks listed words with `*` (also split by spaces, digits, dots, full-width or jamo:
"시 1 발", "ㅅ.ㅂ", "f u c k"), phone numbers and links. Three masked lines (words, not phone
numbers or links) within 5 minutes mute the player for 5 minutes. Runs of more than 12 identical
characters are cut to 12. Lists: `server/data/chat_words.txt` (syntax in its header) plus the
operator's `VILLAGEN_CHAT_FILTER_EXTRA` file (relative to the data directory), read at start-up.
A chat line writes no `requests` or `audit` row: the line itself (with its `request_id`) is the
idempotency record.

Client slash commands are client-side only (`/w 이름 내용`, `/r`, `/p`, `/v`, `/g`).

---

## 4. People (`GET /v1/social/people`)

Fetch when the social window opens, every `social_poll.people` (5) seconds while it is open, and
when `social.v` changes. At most 60 calls a minute per player (429 `people_rate_limited`).

```json
{"v": 17, "online_count": 23, "roster": "all",
 "online": [{"id": "…", "username": "mina", "avatar": {…Avatar…}, "avatar_version": 2,
             "friend": true, "place": "village",
             "where": {"place": "village", "host_id": "…", "host_name": "jun", "floor": 1}}],
 "my_village": {"host": {"id": "…", "username": "me", "online": true}, "visiting": false, "guest_limit": 2,
                "guests": [{"id": "…", "username": "jun", "online": true, "place": "home", "floor": 0}],
                "invites_out": [{"id": "…", "user_id": "…", "username": "sora", "kind": "village", "expires": …}],
                "knocks": [{"id": "…", "user_id": "…", "username": "dan", "expires": …}]},
 "friends": [{"id": "…", "username": "jun", "avatar": {…}, "avatar_version": 0, "online": true,
              "where": {…}, "last_seen": null, "since": …, "joinable": true, "drop_in": false}],
 "requests": {"incoming": [{"id": "…", "user_id": "…", "username": "…", "created": …}], "outgoing": […]},
 "blocked": [{"id": "…", "username": "…"}],
 "prefs": {"appear_offline": false, "roster": "everyone", "requests": "everyone", "drop_in": "off"},
 "limits": {"friends": 100, "requests_per_day": 20}}
```

Rules:
- "Online" = a presence poll within 15 s. The shared online list is cached for 3 s on the server,
  so a player appears or disappears within about 3 s.
- `online` (at most 200, friends first, then your village, then by name) lists everyone online
  except you, blocked players (either way) and `appear_offline` players. Players with
  `roster: friends`, and everybody when the server says `social_roster: friends`, appear only to
  friends and to players in the same village; `social_roster: off` empties the list.
  `online_count` counts every online player not appearing offline.
- Fields for students are minimal: name, look, a place category (`village`, `home`, `workshop`,
  `room`, `expedition`, `away` = an older game outside the village). `where` (whose village,
  floor) only for friends and players in your village. Never addresses, never ids of other
  players' villages for strangers.
- Friends appearing offline show `online: false, last_seen: null`. Otherwise `last_seen` is the last
  poll time (show it coarsely: 방금 / 오늘 / 어제 / N일 전).
- `joinable`: the friend is online in their own village or home with fewer than 2 guests (you are
  not already there). `drop_in`: the friend lets friends walk straight in (else a visit knocks).
- `my_village`: the host and every guest, indoors too (`place: home` with `floor`), so 내보내기
  (`/v1/social/eject`) works for guests inside the house. `invites_out` and `knocks` only for the host.

---

## 5. Friends

| Route | Body | Reply | Errors |
|---|---|---|---|
| `POST /v1/friends/requests` | `{request_id, username}` or `{request_id, user_id}` | `{state: "sent", id}` / `{state: "accepted"}` (they had asked you) / `{state: "friends"}` | 404 `user_not_found`, 422 `friend_self`, 409 `user_blocked` (you blocked them), 429 `friend_requests_limited` (20 a day), 409 `friend_requests_pending_full` (20 open), 409 `friend_list_full` (100) |
| `POST /v1/friends/requests/{id}/accept\|decline\|cancel` | `{request_id}` | `{ok, state}` | 404 `request_unavailable`, 409 `friend_list_full` |
| `POST /v1/friends/remove` | `{request_id, user_id}` | `{ok}` | — |

A request is **silently** kept from the other player (the sender still sees it as outgoing) when
either has blocked the other, when the receiver's `requests` pref is `nobody`, or within 24 h
after the receiver declined the sender. Requests expire after 30 days. Accept/decline is only for
the receiver, cancel only for the sender.

## 6. Blocks, privacy, reports

| Route | Body | Reply | Notes |
|---|---|---|---|
| `POST /v1/social/blocks` | `{request_id, user_id}` | `{ok}` | 404 `user_not_found`, 422 `block_self`, 409 `block_list_full` (200). Ends the friendship, open requests, pending invitations and knocks both ways, and a visit either way (the guest's next poll has `visit_ended.reason: "ended"`) |
| `POST /v1/social/blocks/remove` | `{request_id, user_id}` | `{ok}` | |
| `POST /v1/social/prefs` | `{request_id, appear_offline?: bool, roster?: "everyone"\|"friends", requests?: "everyone"\|"nobody", drop_in?: "off"\|"friends"}` | the prefs | 422 on other values |
| `POST /v1/social/report` | `{request_id, user_id, message_id?, reason: "spam"\|"abuse"\|"other", note?: ≤200}` | `{ok, id}` | 422 `report_self`, 429 `report_limited` (10 a day); the same report again within a day returns the first id |

Blocks hide both players from each other everywhere: chat (both ways, legacy messages too),
`space.players`, the online list, friends lists, `my_village` guests and knocks; invitations from
either side answer `404 invite_target_unavailable` (the unknown-name answer), knocks answer a
silent `asked`. A party is not broken up by a block (the shared expedition goes on), but the party
lines of a blocked member are hidden.

A report stores the reported line's text (as everyone saw it) and up to 10 lines the reported
player wrote in the last hour where the reporter could read them, for the operator.

## 7. Visits from the lists (`POST /v1/social/visit`)

`{request_id, user_id}` → `{state: "visiting"}` or `{state: "asked", expires}`.
- `visiting`: you are friends, the host's `drop_in` is `friends`, and you are in your village
  scene (polled within 20 s). The visit starts like an accepted invitation; your next village poll
  shows the new `host_id`. Already there: also `visiting`.
- `asked`: a knock (an invitation of kind `knock`, guest → host, 2 minutes). The host sees it in
  `knocks` and `social.knocks`. Blocked pairs and hosts whose `requests` is `nobody` (for
  non-friends) get a silent `asked` without a knock.
- Errors: 409 `host_offline` (not online and visible, or away visiting someone), 422 `visit_self`,
  404 `user_not_found`, 409 `party_expedition_active`, 409 `village_full`, 429 `knock_limited`
  (one knock per host per 60 s, at most 5 open), Retry-After.

## 8. Operators

HTTP (account role `admin`, else 403 `admin_only`):
- `GET /v1/admin/reports?state=open|closed|all&limit=50` → `{reports: [{id, reporter, reported, message_id, text, context, reason, note, state, created, …}]}`
- `POST /v1/admin/reports/{id}/close` `{request_id}`
- `POST /v1/admin/chat/mute` `{request_id, user_id, minutes}` (0 lifts the mute; at most 7 days)
- `POST /v1/admin/chat/delete` `{request_id, message_ids: [..≤100]}` → `{ok, removed}`; clients drop them via `chat.removed`.

Inside the server container (`docker compose … exec -T api python -m server.admin_cli …`):
```
chat list [--username NAME] [--grep TEXT] [--limit 50]
chat delete MESSAGE_ID [MESSAGE_ID ...]
chat mute USERNAME MINUTES          (0 = lift)
reports list [--all] [--limit 50]
reports close REPORT_ID [...]
delete-accounts ...                  (now also removes social rows, blocked_id included)
```

Settings (environment): `VILLAGEN_GLOBAL_CHAT` (on|off, default on), `VILLAGEN_SOCIAL_ROSTER`
(all|friends|off, default all), `VILLAGEN_CHAT_FILTER_EXTRA` (word file in the data directory),
`VILLAGEN_CHAT_IP_PER_MINUTE` (600), `VILLAGEN_CHAT_RETENTION_HOURS` (24),
`VILLAGEN_PRESENCE_TOGETHER` (0.25), `VILLAGEN_PRESENCE_ALONE` (1), `VILLAGEN_PEOPLE_SECONDS` (5),
`VILLAGEN_PRESENCE_BUDGET` (60 polls/s, section 9.2).

## 9. Polling guidance

### 9.1 What the client does
| Poll | When | Interval |
|---|---|---|
| presence (village, home) | always while in those scenes | `social.poll.together` with another player in the space, a party run, a pending invite/knock or an `ix` phase other than hold; else `social.poll.alone`. Before the first chat2 reply: `/health social_poll` (0.25 / 1.0). Switch to `together` at once when a reply lists another player |
| presence (workshop, other rooms) | heartbeat | `social.poll.alone` (1 s at rest); the reply carries chat, so the room chat works |
| presence (survival) | as today | 2 s |
| `/v1/social/people` | social window open, or `social.v` changed | `social_poll.people` (5 s); never in the background |
| `/v1/social` | the old menu only | on open |
| chat send | on Enter | the reply has the line id; drop the pending echo when that id arrives |

`remote_motion.gd` adapts its delay between 0.12 and 0.5 s from the arrival spacing, so the
advised `together` interval up to 0.5 s keeps walkers smooth; above that (a crowded server) peers
step more coarsely but stay correct. Chat latency is about one poll interval.

### 9.2 Backpressure
The server counts presence polls. Every 2 s it moves a slow-down factor (1..4) towards
`polls per second / VILLAGEN_PRESENCE_BUDGET` (square-root steps) and advises
`social_poll × factor` in every chat2 reply. Default budget: **60 polls/s**. Small groups keep
4 Hz; a full class is slowed until the server carries about 60 polls a second. Released clients
ignore the advice (they poll at their fixed 4 Hz).

### 9.3 Load test (tools/test_multiplayer_load.py)
Isolated server on 127.0.0.1:8867 (production command line: one uvicorn worker, WAL SQLite, no
access log), temporary data deleted afterwards, 8 load-generator processes (a single asyncio
process topped out at ~55 req/s and was the bottleneck in a first attempt). PC: Ryzen 9 3900X,
Windows 10. 60 players: 15 villages of three (host and one guest outdoors, one guest indoors),
9 alone in their village, 3 in the workshop, 3 on survival expeditions (input 5 Hz); chat one
line per player every 20 s on average (15 % everyone, 10 % whispers, 2 % swearing); 20 social
windows open. 120 s measured after a 10 s warm-up. CPU = the server process, % of one core.

| Run | Server | Clients | Presence together / alone (s) | Served req/s | CPU | CPU ms/req | Presence p50 / p95 ms | Chat delivery p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|
| A | before (6028e2c) | 60 × 0.11.x | 0.25 / 0.25 | 168 of ~240 (saturated) | 146 % | 8.7 | 56 / 975 | – |
| B | this branch | 60 × 0.11.x | 0.25 / 0.25 | 233 | 98 % | 4.2 | 13 / 79 | – |
| C | this branch | 60 × chat2 | 0.25 / 0.25 | 242 | 90 % | 3.7 | 11 / 52 | 158 / 601 |
| D | this branch | 60 × chat2 | 0.25 / 1 | 169 | 57 % | 3.4 | 10 / 34 | 216 / 956 |
| F | this branch | 60 × chat2 | 0.5 / 1 | 110 | 34 % | 3.1 | 9 / 19 | 331 / 953 |
| G | this branch | 60 × chat2 | 1 / 2 | 68 | 22 % | 3.2 | 8 / 14 | 627 / 1811 |
| E | this branch | 120 × chat2 | 0.5 / 1 | 221 | 102 % | 4.6 | 16 / 94 | 361 / 993 |
| H | this branch | 60 × chat2 following `social.poll` (budget 60) | advised (settled ≈ 0.6 / 2.4) | 83 (presence 60.3) | 25 % | 3.1 | 9 / 20 | 475 / 2275 |

Other figures: memory 88–112 MB RSS (A: 94–97 MB); WAL peak 4–5.6 MB; database file growth
about 93 KB per minute at ~3 chat lines/s (runs F, G, measured after full checkpoints), bounded by
the 24 h chat retention; chat adds no `requests`/`audit` rows (run A: +449 of each in two minutes,
kept forever before this branch). In-process profile of one village poll: 14.3 ms → 5.6 ms CPU;
the handler alone 8.5 → 1.9 ms (connection pooling removed ~4 ms of schema re-parsing per poll,
direct JSON ~2.9 ms). Remaining per-request floor: the middleware stack (a second session lookup
in `boundary`, BaseHTTPMiddleware), about 2 ms on this PC; not changed here (app.py core).
Per-request costs: `/v1/social` 13.7 → 2.7 ms, presence away 6.8 → 2.9 ms, presence in a
village with 12 objects 9.2 → 4.4 ms.

### 9.4 t4g.small estimate
Two Graviton2 vCPUs; the API is one Python process (about one vCPU usable); the CPU-credit
baseline is 20 % per vCPU = 0.4 vCPU sustained. Assume a request costs about 1.7× this PC
(single-thread ratio, not measured on the VM):
- C, everyone at 4 Hz: about 150 % of a vCPU, more than one process can give: it saturates like
  run A did here. **Not viable for 60 players.**
- D (4 Hz together, 1 Hz alone): about 100 %: at the limit.
- F (2 Hz / 1 Hz): about 60 %: fine for lessons (burst credits or a few cents in unlimited mode).
- G (1 Hz / 0.5 Hz): about 37 %: within the baseline.
- H, the default budget of 60 polls/s with clients following the advice: the server settled at
  60.3 presence polls/s, 25 % of a core here, about 43 % of a vCPU estimated, near the baseline,
  while small groups keep 4 Hz. 120 players would be slowed further (up to 4×).
Confirm on staging with this tool pointed at the VM-like box (it runs anywhere with the server
venv) and watch CloudWatch CPUCreditBalance during a lesson; lower `VILLAGEN_PRESENCE_BUDGET`
if the balance falls.

## 10. Storage, retention and load safety

New tables: `social_friends` (two rows per friendship), `social_requests`, `social_blocks`,
`social_prefs` (prefs, `rev`, `last_seen`, `chat_muted_until`), `social_reports`,
`mp_message_removals`. New columns: `mp_presence.place/floor/ix`, `mp_messages.channel/to_id/request_id`.
New indexes: `mp_messages(user_id,id)`, `mp_messages(created)`, unique `mp_messages(user_id,request_id)`,
`requests(operation,created)`, `audit(action,created)`, `mp_invites(expires)`, `mp_invites(sender_id,state)`,
`coop_members(user_id)` and the social tables' own. All `CREATE … IF NOT EXISTS` and guarded `ALTER`s:
an existing world upgrades in place, twice is harmless, nothing is rewritten.

Bounded tables (pruned at most every 10 minutes, ≤ 5000 rows per table per run, from the chat and
presence routes):

| Table | Kept |
|---|---|
| `mp_messages` | 24 h (`VILLAGEN_CHAT_RETENTION_HOURS`); delivered at most 1 h |
| `requests` rows of social operations | 2 days (idempotency only); money/crafting rows untouched |
| `audit` rows of social operations | 30 days; legacy per-line chat rows 1 day; chat v2 writes none |
| `mp_invites` (incl. knocks) | 7 days after expiry |
| `mp_visit_notices` | 1 day |
| `social_requests` | open ones expire after 30 days; answered ones are deleted 30 days later |
| `social_reports` | closed 90 days, any 180 days |
| `mp_message_removals` | 15 minutes |
| `security_events` (`chat_masked`, `chat_auto_mute`) | 90 days (existing rule) |

Load-safety rules in the code: the chat delivery and the roster never run inside the presence
write transaction (`Database.write_then_read`: the poll's writes commit, then the reply is read
from a snapshot); delivery is one `UNION ALL` of index ranges per room (`mp_messages(room,id)`,
`(user_id,id)`); history ≤ 30, delivery ≤ 50 per reply; online list ≤ 200 per reply and rebuilt
at most every 3 s (in-process, single uvicorn worker: move it to SQLite before adding workers);
`/people` 60/min per player; the global channel's server-wide ceiling.

Database (server/database.py, affects every route): connections are pooled (`Database.POOL_SIZE`
= 8 idle; opening one re-parses the whole schema, which cost more CPU than the queries of a
poll), `journal_size_limit` keeps the WAL at ≤ 16 MB once checkpointed, and the presence commit
uses `synchronous=NORMAL` (`write_then_read(durable=False)`: positions are rewritten by the next
poll; after a power cut the last moment of presence writes may be missing, never half applied).
Every other transaction keeps the default full durability. Large replies (presence, people) are
encoded with `JSONResponse` directly instead of FastAPI's generic encoder (same bytes).
