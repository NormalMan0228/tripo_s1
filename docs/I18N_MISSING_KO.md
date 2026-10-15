# 번역 누락 점검

`python tools/i18n_check.py --report docs/I18N_MISSING_KO.md`로 재생성합니다.

- 검사: `game/**/*.gd` 333개, 번역 문자열 1668개(중복 제외).
- 카탈로그에 없는 키: **166개**.
- 기존 키의 `en` 또는 `zh` 값 누락: **0개**.

`tr`, `TranslationServer.translate`, `I18n.t/server`, `t.call`, 로컬 `t/_t`, `DayFolk.line` 및 이 함수들에 인수를 직접 전달하는 래퍼를 검사합니다. 래퍼는 파일별로 탐지하며 `preload` 별칭과 래퍼 간 전달도 추적합니다. 조건식의 문자열 분기와 리터럴 결합도 포함합니다. 주석·기호·서식 전용 값은 제외하고 변수·조회 결과 등 동적 인수는 추론하지 않습니다. 카탈로그의 기존 텍스트 키는 사용 여부와 관계없이 두 언어의 빈 값도 검사합니다.

| 누락 | 위치 (파일:줄) | 키 |
| --- | --- | --- |
| 키 없음 | `game/maps/survival/survival_map.gd:1000` | "옛 돌문" |
| 키 없음 | `game/maps/survival/survival_map.gd:1009` | "노을 기중기" |
| 키 없음 | `game/maps/survival/survival_map.gd:1016` | "서리 등불탑" |
| 키 없음 | `game/scripts/build/build_rules.gd:36` | "자기 위에 있는 물건 위로는 올릴 수 없어요." |
| 키 없음 | `game/scripts/build/build_rules.gd:37` | "벽에 걸기에는 너무 높아요. 조금 아래로 내려 주세요." |
| 키 없음 | `game/scripts/build/build_rules.gd:38` | "여기서는 벽이나 천장에 걸 수 없어요." |
| 키 없음 | `game/scripts/build/build_rules.gd:39` | "걸 벽을 골라 주세요." |
| 키 없음 | `game/scripts/build/build_rules.gd:40` | "이 방에는 더 놓을 수 없어요. 일부를 가방에 넣어 주세요." |
| 키 없음 | `game/scripts/build/build_rules.gd:41` | "마을에는 더 놓을 수 없어요. 일부를 가방에 넣어 주세요." |
| 키 없음 | `game/scripts/chat_box.gd:88` | "보낼 곳 바꾸기" |
| 키 없음 | `game/scripts/chat_box.gd:135` | "Enter 로 대화" |
| 키 없음 | `game/scripts/chat_box.gd:252` | "귓속말 · %s" |
| 키 없음 | `game/scripts/chat_box.gd:287` | "[귓] " |
| 키 없음 | `game/scripts/craft_panel.gd:179` | "확인을 기다리는 제작 %d건 · 운영자가 확인하면 맡긴 별씨가 돌아와요" |
| 키 없음 | `game/scripts/craft_panel.gd:488` | "%s는 바늘이 실제 시각에 맞춰 움직이도록 만들어요. 바늘은 공방이 무료로 달아 드려요." |
| 키 없음 | `game/scripts/craft_panel.gd:589` | "그림이 나왔어요!" |
| 키 없음 | `game/scripts/craft_panel.gd:608`<br>`game/tests/craft_panel_check.gd:157` | "확인이 필요해요" |
| 키 없음 | `game/scripts/craft_panel.gd:609` | "공방이 Tripo에 보낸 요청이 닿았는지 확인하지 못했어요. 운영자가 확인하면 맡긴 별씨가 돌아와요. 그동안 새 물건을 만들 수 있어요." |
| 키 없음 | `game/scripts/craft_panel.gd:699` | "AI가 그림을 그리고 있어요…" |
| 키 없음 | `game/scripts/craft_panel.gd:699` | "공방에서 3D로 빚고 있어요…" |
| 키 없음 | `game/scripts/craft_panel.gd:729` | "설계" |
| 키 없음 | `game/scripts/craft_panel.gd:730` | "그림" |
| 키 없음 | `game/scripts/craft_panel.gd:731` | "3D 부품" |
| 키 없음 | `game/scripts/craft_words.gd:24` | "만들 물건을 2~1500자로 적어 주세요." |
| 키 없음 | `game/scripts/craft_words.gd:92` | "AI가 그림을 그렸어요! C를 눌러 확인해 주세요." |
| 키 없음 | `game/scripts/craft_words.gd:92` | "설계와 견적이 나왔어요! C를 눌러 확인해 주세요." |
| 키 없음 | `game/scripts/craft_words.gd:93` | "AI가 그림을 그렸어요! 마음에 드는지 확인해 주세요." |
| 키 없음 | `game/scripts/craft_words.gd:93` | "설계와 견적이 나왔어요! 확인하고 제작을 맡겨 주세요." |
| 키 없음 | `game/scripts/interaction_panel.gd:575` | "여러 부품으로 만든 물건만 밀 수 있어요." |
| 키 없음 | `game/scripts/interaction_panel.gd:694` | "바늘" |
| 키 없음 | `game/scripts/interaction_panel.gd:695` | "내 컴퓨터의 시각에 맞춰 움직여요." |
| 키 없음 | `game/scripts/interaction_panel.gd:741` | "앞으로 빼기" |
| 키 없음 | `game/scripts/interaction_panel.gd:741` | "옆으로 밀기" |
| 키 없음 | `game/scripts/interaction_panel.gd:741` | "위로 올리기" |
| 키 없음 | `game/scripts/interaction_panel.gd:742` | "거리" |
| 키 없음 | `game/scripts/interaction_panel.gd:744` | "옆에서 보기" |
| 키 없음 | `game/scripts/interaction_panel.gd:744` | "정면에서 보기" |
| 키 없음 | `game/scripts/interaction_panel.gd:744` | "제자리" |
| 키 없음 | `game/scripts/interaction_panel.gd:745` | "한 걸음" |
| 키 없음 | `game/scripts/interaction_panel.gd:747` | "비틀기" |
| 키 없음 | `game/scripts/interaction_panel.gd:747` | "앞뒤로" |
| 키 없음 | `game/scripts/interaction_panel.gd:747` | "좌우로" |
| 키 없음 | `game/scripts/main.gd:1275` | "소켓 보기 (ISS-1)" |
| 키 없음 | `game/scripts/settings_menu.gd:168` | "성능 표시" |
| 키 없음 | `game/scripts/settings_menu.gd:168` | "화면 구석에 프레임과 메모리 사용량을 보여 줘요. F2로도 켜고 꺼요." |
| 키 없음 | `game/scripts/social_hud.gd:451` | "보기" |
| 키 없음 | `game/scripts/social_hud.gd:451` | "친구 신청이 왔어요" |
| 키 없음 | `game/scripts/social_hud.gd:460` | "%s님이 마을로 초대했어요" |
| 키 없음 | `game/scripts/social_hud.gd:460` | "%s님이 파티에 초대했어요" |
| 키 없음 | `game/scripts/social_hud.gd:471` | "%s님이 마을 문을 두드려요" |
| 키 없음 | `game/scripts/social_hud.gd:472`<br>`game/scripts/social_window.gd:250` | "들이기" |
| 키 없음 | `game/scripts/social_hud.gd:495` | "귓속말은 /w 이름 내용" |
| 키 없음 | `game/scripts/social_hud.gd:500` | "답할 귓속말이 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:513` | "이 월드에서는 마을 대화만 할 수 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:552` | "조금 천천히 보내 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:553` | "같은 말을 연달아 보낼 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:554` | "전체 대화는 5초에 한 번 보낼 수 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:555` | "전체 대화가 붐벼요. 잠시 뒤에 보내 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:556` | "이 월드는 전체 대화가 꺼져 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:557` | "잠시 대화를 쉬어야 해요." |
| 키 없음 | `game/scripts/social_hud.gd:558` | "보낼 수 없는 말이 들어 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:559` | "파티에 들어가 있지 않아요." |
| 키 없음 | `game/scripts/social_hud.gd:560` | "귓속말을 받을 수 없는 상대예요. 접속 중인 친구에게만 보낼 수 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:563` | "지금은 보낼 수 없어요. 잠시 뒤에 다시 해 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:564` | "보낼 내용이 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:565` | "연결이 끊겨서 보내지 못했어요." |
| 키 없음 | `game/scripts/social_hud.gd:566` | "보내지 못했어요." |
| 키 없음 | `game/scripts/social_hud.gd:655` | "그런 이름의 모험가가 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:656` | "나 자신에게는 신청할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:657` | "차단한 사람이에요. 차단을 풀고 다시 해 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:658` | "오늘은 친구 신청을 더 보낼 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:659` | "답을 기다리는 신청이 너무 많아요." |
| 키 없음 | `game/scripts/social_hud.gd:660` | "친구가 가득 찼어요." |
| 키 없음 | `game/scripts/social_hud.gd:661` | "이미 처리된 신청이에요." |
| 키 없음 | `game/scripts/social_hud.gd:662` | "나 자신은 차단할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:663` | "차단 목록이 가득 찼어요." |
| 키 없음 | `game/scripts/social_hud.gd:664` | "나 자신은 신고할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:665` | "오늘은 신고를 더 할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:666` | "내 마을이에요." |
| 키 없음 | `game/scripts/social_hud.gd:667` | "지금 마을에 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:668` | "마을이 가득 찼어요." |
| 키 없음 | `game/scripts/social_hud.gd:669` | "잠시 뒤에 다시 두드려 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:670` | "탐험 중에는 할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:671` | "파티는 최대 3명이에요." |
| 키 없음 | `game/scripts/social_hud.gd:672` | "이미 파티에 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:673` | "파티장만 할 수 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:674` | "초대할 수 없는 상대예요. 이름을 확인해 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:675` | "만료되었거나 이미 처리된 초대예요." |
| 키 없음 | `game/scripts/social_hud.gd:676` | "내 마을로 돌아간 뒤 초대해 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:677` | "잠시 뒤에 다시 해 주세요." |
| 키 없음 | `game/scripts/social_hud.gd:678` | "연결이 끊겼어요." |
| 키 없음 | `game/scripts/social_hud.gd:681` | "지금은 할 수 없어요." |
| 키 없음 | `game/scripts/social_hud.gd:691`<br>`game/scripts/social_hud.gd:701` | "친구가 되었어요!" |
| 키 없음 | `game/scripts/social_hud.gd:694` | "친구 신청을 보냈어요" |
| 키 없음 | `game/scripts/social_hud.gd:710` | "%s님을 차단했어요" |
| 키 없음 | `game/scripts/social_hud.gd:722` | "%s님을 신고했어요. 운영자가 확인해요." |
| 키 없음 | `game/scripts/social_hud.gd:733` | "마을에서 놀러 갈 수 있어요." |
| 키 없음 | `game/scripts/social_hud.gd:739` | "%s님의 마을로 가요" |
| 키 없음 | `game/scripts/social_hud.gd:741` | "%s님의 마을 문을 두드렸어요" |
| 키 없음 | `game/scripts/social_hud.gd:742` | "%s님의 게임은 아직 방문을 받을 수 없어요. 초대를 부탁해 보세요." |
| 키 없음 | `game/scripts/social_hud.gd:747` | "마을 초대를 보냈어요" |
| 키 없음 | `game/scripts/social_hud.gd:747` | "파티 초대를 보냈어요" |
| 키 없음 | `game/scripts/social_window.gd:29` | "접속 중" |
| 키 없음 | `game/scripts/social_window.gd:30` | "우리 마을" |
| 키 없음 | `game/scripts/social_window.gd:67` | "이름으로 친구 신청" |
| 키 없음 | `game/scripts/social_window.gd:67`<br>`game/scripts/social_window.gd:221` | "친구 신청" |
| 키 없음 | `game/scripts/social_window.gd:68` | "마을 초대" |
| 키 없음 | `game/scripts/social_window.gd:68` | "마을로 초대할 이름" |
| 키 없음 | `game/scripts/social_window.gd:69` | "파티 초대" |
| 키 없음 | `game/scripts/social_window.gd:69` | "파티로 초대할 이름" |
| 키 없음 | `game/scripts/social_window.gd:146` | "집 %d층" |
| 키 없음 | `game/scripts/social_window.gd:152` | "방금" |
| 키 없음 | `game/scripts/social_window.gd:152` | "오늘" |
| 키 없음 | `game/scripts/social_window.gd:153` | "어제" |
| 키 없음 | `game/scripts/social_window.gd:154` | "%d일 전" |
| 키 없음 | `game/scripts/social_window.gd:181` | "받은 친구 신청" |
| 키 없음 | `game/scripts/social_window.gd:183` | "친구가 되고 싶어 해요" |
| 키 없음 | `game/scripts/social_window.gd:187` | "친구 %d명" |
| 키 없음 | `game/scripts/social_window.gd:188` | "아직 친구가 없어요. 위에서 이름으로 신청해 보세요." |
| 키 없음 | `game/scripts/social_window.gd:193`<br>`game/scripts/social_window.gd:225` | "놀러가기" |
| 키 없음 | `game/scripts/social_window.gd:193` | "놀러가기 (문 두드리기)" |
| 키 없음 | `game/scripts/social_window.gd:195`<br>`game/scripts/social_window.gd:222` | "귓속말" |
| 키 없음 | `game/scripts/social_window.gd:196`<br>`game/scripts/social_window.gd:223` | "더 보기" |
| 키 없음 | `game/scripts/social_window.gd:198` | "친구 끊기" |
| 키 없음 | `game/scripts/social_window.gd:199`<br>`game/scripts/social_window.gd:226` | "차단" |
| 키 없음 | `game/scripts/social_window.gd:200`<br>`game/scripts/social_window.gd:227` | "신고" |
| 키 없음 | `game/scripts/social_window.gd:202` | "보낸 신청" |
| 키 없음 | `game/scripts/social_window.gd:204` | "답을 기다려요" |
| 키 없음 | `game/scripts/social_window.gd:205` | "신청 취소" |
| 키 없음 | `game/scripts/social_window.gd:208` | "차단한 사람" |
| 키 없음 | `game/scripts/social_window.gd:211` | "차단 풀기" |
| 키 없음 | `game/scripts/social_window.gd:215` | "지금 %d명 접속 중" |
| 키 없음 | `game/scripts/social_window.gd:216` | "이 월드는 접속자 목록을 보여 주지 않아요." |
| 키 없음 | `game/scripts/social_window.gd:217` | "지금은 나 혼자예요." |
| 키 없음 | `game/scripts/social_window.gd:232` | "%s님의 마을에 놀러 와 있어요." |
| 키 없음 | `game/scripts/social_window.gd:239` | "받은 초대" |
| 키 없음 | `game/scripts/social_window.gd:242` | "마을로 초대했어요" |
| 키 없음 | `game/scripts/social_window.gd:242` | "파티로 초대했어요" |
| 키 없음 | `game/scripts/social_window.gd:247` | "문 두드리는 사람" |
| 키 없음 | `game/scripts/social_window.gd:249` | "놀러 오고 싶어 해요" |
| 키 없음 | `game/scripts/social_window.gd:252` | "마을에 있는 사람" |
| 키 없음 | `game/scripts/social_window.gd:267` | "방문 끝내기" |
| 키 없음 | `game/scripts/social_window.gd:269` | "마을 주인" |
| 키 없음 | `game/scripts/social_window.gd:276` | "아직 아무도 놀러 오지 않았어요. 위에서 이름으로 초대해 보세요." |
| 키 없음 | `game/scripts/social_window.gd:279` | "보낸 초대: %s" |
| 키 없음 | `game/scripts/social_window.gd:281` | "나의 공개 설정" |
| 키 없음 | `game/scripts/social_window.gd:283` | "접속 숨기기" |
| 키 없음 | `game/scripts/social_window.gd:284` | "친구는 문 두드리지 않고 들어오기" |
| 키 없음 | `game/scripts/social_window.gd:285` | "친구 신청 받기" |
| 키 없음 | `game/scripts/social_window.gd:300` | "파티를 만들면 함께 탐험을 떠날 수 있어요. 최대 3명." |
| 키 없음 | `game/scripts/social_window.gd:302` | "파티를 만들었어요" |
| 키 없음 | `game/scripts/social_window.gd:305` | "파티 %d/3명" |
| 키 없음 | `game/scripts/social_window.gd:308` | "파티장" |
| 키 없음 | `game/scripts/social_window.gd:318` | "마을에서 함께 출발할 수 있어요." |
| 키 없음 | `game/scripts/social_window.gd:320` | "파티에서 나왔어요" |
| 키 없음 | `game/scripts/social_window.gd:325` | "협동 탐험 보상을 받았어요" |
| 키 없음 | `game/scripts/social_window.gd:326` | "협동 탐험 보상 받기" |
| 키 없음 | `game/scripts/studio.gd:1649` | "보관함으로 옮겼어요." |
| 키 없음 | `game/tests/craft_one_check.gd:130` | "이 그림으로 만들기" |
| 키 없음 | `game/tests/craft_panel_check.gd:159` | "오래" |
| 키 없음 | `game/tests/hud_click_tour.gd:64` | "가구를 놓았어요" |
| 키 없음 | `game/tests/quest_check.gd:152`<br>`game/tests/quest_check.gd:155` | "별지기" |
| 키 없음 | `game/tests/quest_check.gd:152`<br>`game/tests/quest_check.gd:155` | "하늘" |
| 키 없음 | `game/tests/quest_check.gd:153` | "밤 산책자" |
| 키 없음 | `game/tests/quest_e2e.gd:146`<br>`game/tests/quest_e2e.gd:262` | "마을 주민들이 부탁을 기다리고 있어요" |
| 키 없음 | `game/tests/story_chapter.gd:203` | "카페" |
