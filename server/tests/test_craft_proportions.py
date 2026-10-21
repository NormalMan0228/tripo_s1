import pytest
from server.craft_moderation import check_text


@pytest.mark.parametrize('text', ['3등신의 치비 로봇', '8등신 캐릭터', '2.5등신으로 만들어줘',
                                  '３등신 인형', '12등신인 로봇', '3등신. 빨간 목도리'])
def test_numeric_character_proportions_are_not_profanity(text):
    assert check_text(text) == ''


@pytest.mark.parametrize('text', ['등신 캐릭터', '너 등신', '3등신 캐릭터 씨발', '3등신새끼',
                                  '3등신의 로봇 fuck', '8등신 로봇 등신'])
def test_proportions_do_not_disable_other_profanity(text):
    assert check_text(text) == 'words'
