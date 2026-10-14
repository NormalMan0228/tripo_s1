CC5 Headshot 실행 안내 (character1 얼굴)

[A] 직접 Headshot 화면에서 하기
 1. CC5 > Headshot(메쉬 모드) > hd/export/character1_head_headshot.fbx 불러오기
 2. 정렬 포인트는 직접 찍기(카툰 비율). hd/cc5/headshot_point_guide.jpg 의 23개 위치 참고
 3. Refine Mesh 서브디비전 Level 2 → 생성
 4. 결과를 FBX로 내보내 hd/cc5/ 에 저장해 주세요 (검수는 scripts/qa_headshot_result.py)

[B] 스크립트로 한 번에 (1회 실행, 상시 브리지 아님)
 CC5 > Script > Load Python > C:\lsm26\triphthonS1\tools\cc5_bridge\run_headshot_mesh_once.py
 - Headshot API 목록 기록 → OBJ(hd/export/character1_head_headshot.obj)를 Headshot 메쉬 모드로 가져오기(자동 정렬, Level 2)
 - 프로젝트 저장, 미리보기 렌더, FBX 내보내기 시도 (체험판은 내보내기가 제한될 수 있음)
 - 결과/로그: hd/cc5/run_headshot_mesh_log.txt

[C] 상시 브리지(tools/cc5_bridge/bridge.py)
 Claude 자동 권한 검사가 막고 있음. 쓰려면 Claude Code 권한 설정에 허용 규칙을 추가해야 함.
