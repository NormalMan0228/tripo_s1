import pytest
from server.chat_filter import ChatFilter


@pytest.fixture(scope='module')
def words():
    return ChatFilter()


@pytest.mark.parametrize('line,shown', [
    ('시발', '**'),
    ('시 1 발 뭐야', '* * * 뭐야'),        # spaces and digits between the letters
    ('ㅅ.ㅂ 진짜', '*** 진짜'),            # dotted compatibility jamo
    ('ㅅㅂ', '**'),
    ('야 이 개새끼야', '야 이 ***야'),
    ('ㅈㄴ 웃겨', '** 웃겨'),
    ('씨　발', '*　*'),                     # an ideographic space
    ('ｆｕｃｋ', '****'),                   # full-width letters
    ('f u c k you', '* * * * you'),
    ('fucking hell', '****ing hell'),
    ('you ass!', 'you ***!'),
    ('sh1t', '****'),
    ('kill your self', '**** **** ****'),
])
def test_masks_listed_words_and_their_disguises(words, line, shown):
    checked = words.check(line)
    assert checked.text == shown and checked.masked >= 1 and not checked.blocked


@pytest.mark.parametrize('line', [
    '다시 발견했어', '시발점에서 출발', '생존 나무', '보존나무', '1등 신발', 'class assassin', 'hello!',
    '안녕하세요 반가워요', '그거 보지 마', '불이 꺼져', '새끼 고양이 귀여워', 'Scunthorpe', 'grape juice', '2024년 3월',
])
def test_leaves_ordinary_lines_alone(words, line):
    checked = words.check(line)
    assert checked.text == line and checked.masked == 0


def test_masks_phone_numbers_and_links_without_counting_them_as_swearing(words):
    checked = words.check('010-1234-5678 로 연락해 www.example.com 도 봐')
    assert checked.text == '***-****-**** 로 연락해 *************** 도 봐'
    assert checked.masked == 0 and checked.info_masked == 2
    assert words.check('https://bad.example/x?y').text == '*' * len('https://bad.example/x?y')


def test_operator_list_adds_masks_blocks_and_allowed_phrases(tmp_path):
    extra = tmp_path/'words.txt'
    extra.write_text('# school extras\n바보\n!금지어\n+바보상자\nnoob*\n', encoding='utf-8')
    words = ChatFilter(extra)
    assert words.check('이 바보야').text == '이 **야'
    assert words.check('바보상자 켜자').masked == 0
    assert words.check('금 지 어 하나').blocked
    assert words.check('noobs').text == '****s'
