"""School chat word filter (server/chat.py): masks listed Korean and English words with *, and
phone numbers and links, in the original text. Lists: server/data/chat_words.txt (syntax in its
header) plus an optional operator file (VILLAGEN_CHAT_FILTER_EXTRA). Loaded once per process.

Matching runs on normalised copies of the line, never on what is shown:
- Hangul: NFKC per character (compatibility jamo become conjoining jamo, for terms too), every
  non-Hangul character dropped, so "시 1 발" and "ㅅ.ㅂ" read "시발" and "ㅅㅂ". A match split by a
  plain space counts only when its first letter starts a word ("다시 발견" is not "시발").
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
    return ''.join(ch for c in term for ch in normal(c) if is_hangul(ch))


def latin_key(term):
    return ''.join(ch for c in term for ch in normal(c) if 'a' <= ch <= 'z')


@dataclass
class Checked:
    text: str
    masked: int = 0       # listed words masked (these count towards the automatic mute)
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
    def __init__(self, extra=None):
        self.rules = Rules()
        for path in (DEFAULT_LIST, extra):
            if path:
                for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
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
        """(letters, original index, starts its space-separated word, a space since the previous letter)"""
        letters, origin, word_start, spaced = [], [], [], []
        new_word, gap = True, False
        for i, c in enumerate(text):
            if c.isspace():
                new_word = gap = True
                continue
            for ch in normal(c):
                if is_hangul(ch):
                    letters.append(ch)
                    origin.append(i)
                    word_start.append(new_word)
                    spaced.append(gap)
                    new_word = gap = False
            # A digit or letter before the first Hangul one ("1등") means the word started earlier;
            # a dot or a dash ("ㅡ시 발") does not.
            if c.isalnum():
                new_word = False
        return ''.join(letters), origin, word_start, spaced

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
        spans = {'mask': [], 'block': []}
        letters, origin, word_start, spaced = self.hangul_view(text)
        allowed = [m.span() for m in self.ko['allow'].finditer(letters)] if self.ko['allow'] and letters else []
        for kind in ('mask', 'block'):
            if not self.ko[kind] or not letters:
                continue
            for m in self.ko[kind].finditer(letters):
                s, e = m.span()
                if any(a <= s and e <= b for a, b in allowed):
                    continue
                if any(spaced[k] for k in range(s + 1, e)) and not word_start[s]:
                    continue
                spans[kind].append((origin[s], origin[e - 1]))
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
                        spans[kind].append((places[0], places[-1]))
            for kind in ('mask', 'block'):
                if self.sub[kind]:
                    for m in self.sub[kind].finditer(word):
                        s, e = m.span()
                        if not any(a <= position + s and position + e <= b for a, b in latin_allowed):
                            spans[kind].append((places[s], places[e - 1]))
            position += len(word)
        for kind in ('mask', 'block'):
            if self.phrase[kind] and stream:
                for m in self.phrase[kind].finditer(stream):
                    s, e = m.span()
                    spans[kind].append((stream_places[s], stream_places[e - 1]))
        if spans['block']:
            result.blocked = True
            return result
        for first, last in spans['mask']:
            for k in range(first, last + 1):
                if not out[k].isspace():
                    out[k] = '*'
        result.masked = len(spans['mask'])
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
