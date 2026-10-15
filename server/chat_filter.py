"""School chat word filter (server/chat.py): masks listed Korean and English words with *, and
phone numbers and links, in the original text. Lists: server/data/chat_words.txt (syntax in its
header) plus an optional operator file (VILLAGEN_CHAT_FILTER_EXTRA). Loaded once per process.

Matching runs on normalised copies of the line, never on what is shown:
- Hangul: NFKC per character (compatibility jamo become conjoining jamo, for terms too), every
  non-Hangul character dropped, so "시 1 발" and "ㅅ.ㅂ" read "시발" and "ㅅㅂ". A second reading
  composes jamo typed one by one into syllables ("ㅆㅣㅂㅏㄹ", "시바ㄹ" read "씨발", "시발"). A
  match split by a plain space counts only when every part is a whole word: its first letter
  starts a word and its last letter ends one ("다시 발견", "몇 시 발표야" are not "시발"). Such a
  split match is masked but does not count towards the automatic mute (Checked.split).
- Latin: NFKC, lower case, the usual digit and symbol stand-ins (f4ck, $hit) read as letters,
  three or more single letters in a row joined ("f u c k"). Whole words by default.
"""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIST = Path(__file__).resolve().parent / 'data' / 'chat_words.txt'
LEET = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's', '!': 'i'}
PHONE = re.compile(r'(?<!\d)0\d{1,2}[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)')
LINK = re.compile(r'(?i)(?:https?://|www\.)\S+|\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|kr|io|gg|me|co|xyz|tv|ly|app|site|link)\b(?:/\S*)?')
MAX_TERMS = 5000


def is_hangul(c):
    o = ord(c)
    return 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F or 0xA960 <= o <= 0xA97F or 0xD7B0 <= o <= 0xD7FF


def normal(c):
    return unicodedata.normalize('NFKC', c).lower()


def hangul_key(term):
    return ''.join(item[0] for item in compose([(ch, 0, 0, False, False) for c in term for ch in normal(c) if is_hangul(ch)]))


# Conjoining jamo: leading consonants (choseong) U+1100..U+1112, vowels (jungseong) U+1161..U+1175,
# trailing consonants (jongseong) U+11A8..U+11C2. A consonant typed alone is a choseong after NFKC;
# after a vowel and before no vowel it is that syllable's final ("시바ㄹ" = 시발).
L_BASE, V_BASE, T_BASE, S_BASE = 0x1100, 0x1161, 0x11A7, 0xAC00
TRAILING = dict(zip('\u1100\u1101\u1102\u1103\u1105\u1106\u1107\u1109\u110a\u110b\u110c\u110e\u110f\u1110\u1111\u1112',
                    '\u11a8\u11a9\u11ab\u11ae\u11af\u11b7\u11b8\u11ba\u11bb\u11bc\u11bd\u11be\u11bf\u11c0\u11c1\u11c2'))


def _lead(ch):
    return L_BASE <= ord(ch) <= 0x1112


def _vowel(ch):
    return V_BASE <= ord(ch) <= 0x1175


def _trail(ch):
    return 0x11A8 <= ord(ch) <= 0x11C2


def compose(items):
    """Letters as (letter, first index, last index, starts a word, a space before it), with jamo
    typed one by one composed into syllables (never across a space). Precomposed text comes back
    unchanged."""
    jamo = []
    for letter, first, last, start, gap in items:
        parts = unicodedata.normalize('NFD', letter) if S_BASE <= ord(letter) <= 0xD7A3 else letter
        for k, ch in enumerate(parts):
            jamo.append([ch, first, last, start and k == 0, gap and k == 0])
    for k, item in enumerate(jamo):
        if (item[0] in TRAILING and k and _vowel(jamo[k-1][0]) and not item[4]
                and not (k+1 < len(jamo) and _vowel(jamo[k+1][0]) and not jamo[k+1][4])):
            item[0] = TRAILING[item[0]]
    out, k = [], 0
    while k < len(jamo):
        ch, first, last, start, gap = jamo[k]
        if _lead(ch) and k+1 < len(jamo) and _vowel(jamo[k+1][0]) and not jamo[k+1][4]:
            code = (ord(ch)-L_BASE)*588 + (ord(jamo[k+1][0])-V_BASE)*28
            last, k = jamo[k+1][2], k+2
            if k < len(jamo) and _trail(jamo[k][0]) and not jamo[k][4]:
                code += ord(jamo[k][0])-T_BASE
                last, k = jamo[k][2], k+1
            out.append((chr(S_BASE+code), first, last, start, gap))
            continue
        out.append((ch, first, last, start, gap))
        k += 1
    return out


def latin_key(term):
    return ''.join(ch for c in term for ch in normal(c) if 'a' <= ch <= 'z')


@dataclass
class Checked:
    text: str
    masked: int = 0       # listed words masked
    split: int = 0        # of those, matches split by a space (masked, not counted towards the mute)
    info_masked: int = 0  # phone numbers and links masked (personal-information safety only)
    blocked: bool = False


class Rules:
    def __init__(self):
        self.ko_mask, self.ko_block, self.ko_allow = set(), set(), set()
        self.word_mask, self.word_block = set(), set()
        self.sub_mask, self.sub_block = set(), set()
        self.phrase_mask, self.phrase_block, self.latin_allow = set(), set(), set()

    def add(self, line):
        line = line.strip()
        if not line or line.startswith('#'):
            return
        block = allow = False
        if line[0] in '!+':
            block, allow, line = line[0] == '!', line[0] == '+', line[1:].strip()
        sub = line.endswith('*')
        line = line.rstrip('*').strip()
        ko, en = hangul_key(line), latin_key(line)
        if ko and not en:
            (self.ko_allow if allow else self.ko_block if block else self.ko_mask).add(ko)
        elif en and not ko:
            if allow:
                self.latin_allow.add(en)
            elif ' ' in line:
                (self.phrase_block if block else self.phrase_mask).add(en)
            elif sub:
                (self.sub_block if block else self.sub_mask).add(en)
            else:
                (self.word_block if block else self.word_mask).add(en)

    def count(self):
        return sum(len(s) for s in vars(self).values())


def pattern(terms):
    # Longest first, so "개새끼야" is one match, not "개새끼" plus a stray letter.
    return re.compile('|'.join(re.escape(t) for t in sorted(terms, key=len, reverse=True))) if terms else None


class ChatFilter:
    def __init__(self, extra=None, lines=None):
        """`lines` (same syntax as the list files) replaces both files: the craft request filter
        (server/craft_moderation.py) builds one filter per refusal category this way."""
        self.rules = Rules()
        for path in (() if lines is not None else (DEFAULT_LIST, extra)):
            if path:
                for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
                    self.rules.add(line)
        for line in lines or ():
            self.rules.add(line)
        if self.rules.count() > MAX_TERMS:
            raise ValueError('chat word list too long')
        r = self.rules
        self.ko = {'mask': pattern(r.ko_mask), 'block': pattern(r.ko_block), 'allow': pattern(r.ko_allow)}
        self.sub = {'mask': pattern(r.sub_mask), 'block': pattern(r.sub_block)}
        self.phrase = {'mask': pattern(r.phrase_mask), 'block': pattern(r.phrase_block), 'allow': pattern(r.latin_allow)}

    # --- normalised views of one line -------------------------------------------------------
    @staticmethod
    def hangul_view(text):
        """Letters as (letter, original index, original index, starts its space-separated word,
        a space since the previous letter)."""
        items = []
        new_word, gap = True, False
        for i, c in enumerate(text):
            if c.isspace():
                new_word = gap = True
                continue
            for ch in normal(c):
                if is_hangul(ch):
                    items.append((ch, i, i, new_word, gap))
                    new_word = gap = False
            # A digit or letter before the first Hangul one ("1등") means the word started earlier;
            # a dot or a dash ("ㅡ시 발") does not.
            if c.isalnum():
                new_word = False
        return items

    @staticmethod
    def word_ends(text):
        """ends[i]: no letter or digit follows text[i] before the next space ("발!" ends, "발표" not)."""
        ends, clean = [False]*len(text), True
        for i in range(len(text)-1, -1, -1):
            ends[i] = clean
            if text[i].isspace():
                clean = True
            elif text[i].isalnum():
                clean = False
        return ends

    def korean_spans(self, items, ends, spans):
        letters = ''.join(item[0] for item in items)
        if not letters:
            return
        allowed = [m.span() for m in self.ko['allow'].finditer(letters)] if self.ko['allow'] else []
        for kind in ('mask', 'block'):
            if not self.ko[kind]:
                continue
            position = 0
            while True:
                m = self.ko[kind].search(letters, position)
                if not m:
                    break
                s, e = m.span()
                # A refused match lets a later one start inside it ("개 새끼야": 새끼야).
                position = s + 1
                if any(a <= s and e <= b for a, b in allowed):
                    continue
                split = any(items[k][4] for k in range(s + 1, e))
                if split:
                    # Every part a whole word: "시 발", "ㅅ ㅂ", "씨 발!", not "몇 시 발표야".
                    last = items[e-1][2]
                    whole_end = ends[last] and (e == len(items) or items[e][1] > last)
                    if not items[s][3] or not whole_end:
                        continue
                key = (items[s][1], items[e-1][2])
                spans[kind][key] = spans[kind].get(key, True) and split
                position = e

    @staticmethod
    def latin_tokens(text):
        """Words of Latin letters (stand-ins read as letters) as (word, [original index per letter])."""
        tokens, word, places = [], [], []
        for i, c in enumerate(text):
            chars = [ch for ch in normal(c)]
            mapped = [LEET.get(ch, ch) for ch in chars]
            if mapped and all('a' <= ch <= 'z' for ch in mapped):
                for ch in mapped:
                    word.append(ch)
                    places.append(i)
                continue
            if word:
                tokens.append((word, places))
            word, places = [], []
        if word:
            tokens.append((word, places))
        # "!" ends a sentence far more often than it spells an i.
        trimmed = []
        for word, places in tokens:
            while word and text[places[0]] == '!':
                word, places = word[1:], places[1:]
            while word and text[places[-1]] == '!':
                word, places = word[:-1], places[:-1]
            if any(not text[i].isdigit() and text[i] not in LEET for i in places):
                trimmed.append((word, places))
        tokens = trimmed
        # Three or more single letters in a row ("f u c k", "f.u.c.k") are one word.
        joined, run = [], []
        for word, places in tokens:
            if len(word) == 1 and (not run or places[0] - run[-1][1][-1] <= 2):
                run.append((word, places))
                continue
            joined.extend(_flush(run))
            run = [(word, places)] if len(word) == 1 else []
            if len(word) > 1:
                joined.append((''.join(word), places))
        joined.extend(_flush(run))
        return joined

    # --- checking ---------------------------------------------------------------------------
    def check(self, text):
        out = list(text)
        result = Checked(text)
        # (first, last) original index -> the match was split by a space; one entry per place.
        spans = {'mask': {}, 'block': {}}
        items = self.hangul_view(text)
        if items:
            ends = self.word_ends(text)
            self.korean_spans(items, ends, spans)
            # Jamo typed one by one: the composed reading too (precomposed text adds nothing).
            if any(0x1100 <= ord(item[0]) <= 0x11FF for item in items):
                self.korean_spans(compose(items), ends, spans)
        tokens = self.latin_tokens(text)
        stream, stream_places = '', []
        for word, places in tokens:
            stream += word
            stream_places += places
        latin_allowed = [m.span() for m in self.phrase['allow'].finditer(stream)] if self.phrase['allow'] and stream else []
        position = 0
        for word, places in tokens:
            for kind, words in (('mask', self.rules.word_mask), ('block', self.rules.word_block)):
                if word in words or (word.endswith('s') and word[:-1] in words) or (word.endswith('es') and word[:-2] in words):
                    if not any(a <= position and position + len(word) <= b for a, b in latin_allowed):
                        spans[kind][(places[0], places[-1])] = False
            for kind in ('mask', 'block'):
                if self.sub[kind]:
                    for m in self.sub[kind].finditer(word):
                        s, e = m.span()
                        if not any(a <= position + s and position + e <= b for a, b in latin_allowed):
                            spans[kind][(places[s], places[e - 1])] = False
            position += len(word)
        for kind in ('mask', 'block'):
            if self.phrase[kind] and stream:
                for m in self.phrase[kind].finditer(stream):
                    s, e = m.span()
                    spans[kind][(stream_places[s], stream_places[e - 1])] = False
        if spans['block']:
            result.blocked = True
            return result
        for first, last in spans['mask']:
            for k in range(first, last + 1):
                if not out[k].isspace():
                    out[k] = '*'
        result.masked = len(spans['mask'])
        result.split = sum(1 for split in spans['mask'].values() if split)
        masked = ''.join(out)
        for rule in (PHONE, LINK):
            def hide(m):
                result.info_masked += 1
                return ''.join(c if c in '-. ' and rule is PHONE else '*' for c in m.group(0))
            masked = rule.sub(hide, masked)
        result.text = masked
        return result


def _flush(run):
    if len(run) >= 3:
        return [(''.join(w[0] for w, _ in run), [p[0] for _, p in run])]
    return [(''.join(w), p) for w, p in run]
