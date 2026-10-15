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
    ('ㅆㅣㅂㅏㄹ', '*****'),                # compatibility jamo typed one by one
    ('시발 뭐야', '***** 뭐야'),  # conjoining jamo (renders 시발)
    ('시바ㄹ', '***'),                      # a final typed apart
    ('쒸발', '**'),
    ('ㅆ.ㅣ.ㅂ.ㅏ.ㄹ', '*********'),
    ('씨 발!', '* *!'),                     # every part a whole word
    ('개 새끼야', '개 ***'),                # a refused split match lets a later one start inside it
])
def test_masks_listed_words_and_their_disguises(words, line, shown):
    checked = words.check(line)
    assert checked.text == shown and checked.masked >= 1 and not checked.blocked


@pytest.mark.parametrize('line', [
    '다시 발견했어', '시발점에서 출발', '생존 나무', '보존나무', '1등 신발', 'class assassin', 'hello!',
    '안녕하세요 반가워요', '그거 보지 마', '불이 꺼져', '새끼 고양이 귀여워', 'Scunthorpe', 'grape juice', '2024년 3월',
    # School phrases a split match used to catch (시/씨 alone always starts a word).
    '몇 시 발표야?', '국어 시 발표 언제야', '그 시 발음 어려워', '이 시 발표해', '지금 몇 시 발견했어', '씨 발라',
    '우리 개 새끼 낳았어', '몇시발표야', 'ㅋㅋㅋ ㅠㅠ', 'ㅇㅇ 알겠어', '가ㅋㅋ',
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


def test_a_match_split_by_a_space_is_masked_but_not_counted_towards_the_mute(words):
    split = words.check('아 시 발 진짜')
    assert split.text == '아 * * 진짜' and split.masked == 1 and split.split == 1
    whole = words.check('시발 진짜')
    assert whole.masked == 1 and whole.split == 0
