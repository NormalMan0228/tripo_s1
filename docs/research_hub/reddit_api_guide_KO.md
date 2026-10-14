# Reddit 공식 API 사용 안내 (2026-10-14)

Reddit은 Claude의 브라우저·웹 도구에서 막혀 있다. 미러·프록시·캐시·우회 프런트엔드는 쓰지 않는다. 공식 API 키가 생겼을 때만 읽기 전용으로 수집한다.

## 1. 바뀐 점: 셀프 발급 종료, 승인제

- 2025년 11월부터 Reddit은 공개 데이터 API의 셀프 발급을 닫았다. 새 앱을 만들려면 먼저 승인을 받아야 한다. [블로그·제3자 문서] https://docs.n8n.io/integrations/builtin/credentials/reddit.md
- 승인 기준은 Responsible Builder Policy다. [공식, 원문은 도구로 열리지 않음] https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy
- 개발자는 먼저 Devvit(Reddit 안에서 도는 앱)을 쓰라고 안내하고, Devvit으로 안 되는 경우에 신청서를 내라고 한다. 우리 용도(외부에서 읽어 와 요약)는 Devvit에 맞지 않는다. [블로그, Reddit 공지 2차 인용] https://data365.co/blog/how-to-get-reddit-api-key
- 심사는 사람이 하고 2~4주 걸린다는 글이 있다. [블로그] https://www.keyapi.ai/blog/reddit-data-api-overhaul-major-changes-and-migration-guide/
- 개인 스크립트는 예외를 받기 어렵다는 보고가 있다(유명 봇 개발자 발언 인용, 1개 블로그). [블로그] https://medium.com/@alex_79882/reddits-api-is-officially-dead-in-2026-here-s-what-i-use-instead-f88ee5b809c8
- 2025년 11월 전에 이미 만든 앱은 정책 안에서 계속 쓸 수 있다. [블로그, 공지 인용] 위 n8n·keyapi 글

## 2. 사용자가 할 일 (단계별)

계정 만들기, 로그인, 비밀번호 입력, 신청서 제출은 모두 사용자가 직접 한다.

1. **기존 앱 확인:** 로그인한 상태에서 https://www.reddit.com/prefs/apps 를 연다. 예전에 만든 "script" 앱이 있으면 바로 6단계로 간다.
2. **정책 읽기:** Responsible Builder Policy(위 링크)를 훑어본다. 특히 AI 학습 금지, 데이터 보관·삭제 규칙.
3. **신청서 열기:** Reddit Developer Support 신청서 https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164 (링크 출처: n8n 공식 문서)
4. **신청 내용 예시 (영어로 써도 됨):**
   - 목적: 개인 인디 게임 개발. AI 영상·3D 애니메이션 도구에 대한 공개 의견을 주 1회 읽고 요약.
   - 비상업, 읽기 전용. 글쓰기·투표·메시지 없음.
   - 대상: r/aivideo, r/KlingAI_Videos, r/StableDiffusion, r/blender, r/gamedev, r/godot, r/animation 정도의 공개 글 검색.
   - 양: 주 1회, 수백 건 이하, 분당 요청 한도 준수.
   - 보관: 원문은 저장하지 않거나 30일 안에 삭제, 요약과 링크만 남김. AI 모델 학습에 쓰지 않음.
5. **답장 기다리기:** 승인 메일이 오면 다음 단계. 거절되면 Reddit은 계속 제외하고 다른 커뮤니티로 대신한다.
6. **앱 만들기 (승인 후):** https://www.reddit.com/prefs/apps → "create another app" → 종류 **script** → redirect uri는 `http://localhost:8080` → 만들기.
7. **키 저장:** 앱 이름 아래 짧은 문자열(client_id)과 secret을 `Desktop\reddit_key.txt`에 저장한다. 형식:
   ```
   client_id=...
   client_secret=...
   user_agent=windows:tripothon-research:0.1 (by /u/사용자이름)
   ```
   비밀번호는 넣지 않는다(읽기 전용 앱 전용 토큰 방식으로 쓴다).
8. 저장했다고 알려 주면, 정보 수집 세션이 art-venv 파이썬으로 읽기 전용 수집 스크립트를 만든다. 키 파일은 저장소에 올리지 않는다.
