"""Inappropriate craft requests are refused with a reason, never quietly softened into something else.

Three gates, each ending the craft as refused_<category> (sexual, violence, hate, drugs, person,
words, other) with the starseeds kept or refunded:
1. The description, before anything is charged: server/data/craft_words.txt per category (Hangul
   at the start of a word, Latin whole words), plus the chat swear list's Korean words as `words`.
2. The LLM designer, in the same call that designs the object (no extra cost): the contract
   (server/asset_contract.py SAFETY) makes it answer {"refused": category} for the description or
   the reference photo; a provider's own safety block counts as `other`.
3. Tripo: a request rejected for its content policy (code 2008) or a task it bans.

failure_reason() groups every studio error code into the few reasons the craft window words.
"""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from .chat_filter import ChatFilter, hangul_key, latin_key, is_hangul
from .provider import ProviderError

CATEGORIES = ('sexual', 'violence', 'hate', 'drugs', 'person', 'words', 'other')
WORDS = Path(__file__).resolve().parent / 'data' / 'craft_words.txt'


class Refused(ProviderError):
    """A craft refused for its content. Never uncertain: nothing was made or will be."""
    def __init__(self, category='other'):
        self.category = category if category in CATEGORIES else 'other'
        super().__init__('refused_' + self.category)


def category_of(value):
    """The refusal category a designer answered (any case, a few synonyms), or '' for none."""
    if not isinstance(value, str):
        return ''
    word = value.strip().lower()
    if not word or word in ('none', 'no', 'false', 'ok'):
        return ''
    word = {'sex': 'sexual', 'nudity': 'sexual', 'gore': 'violence', 'self_harm': 'violence', 'extremism': 'hate',
            'drug': 'drugs', 'real_person': 'person', 'people': 'person', 'profanity': 'words'}.get(word, word)
    return word if word in CATEGORIES else 'other'


@lru_cache(maxsize=1)
def _lists():
    """{category: (terms, allowed)}: Hangul keys (hangul_key) or Latin entries, per craft_words.txt section."""
    sections, current = {}, None
    for line in WORDS.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        head = re.fullmatch(r'\[([a-z]+)\]', line)
        if head:
            current = sections.setdefault(head.group(1), ([], []))
        elif current is not None and line and not line.startswith('#'):
            allow = line.startswith('+')
            (current[1] if allow else current[0]).append(line.lstrip('+').strip())
    return sections


@lru_cache(maxsize=1)
def _swears():
    return ChatFilter()


def _korean_hit(words, term, allowed):
    """A listed Hangul term at the start of a word (it may run on over the next words)."""
    key = hangul_key(term)
    if not key:
        return False
    for i in range(len(words)):
        run = ''.join(words[i:i + 4])
        if run.startswith(key) and not any(run.startswith(hangul_key(a)) for a in allowed):
            return True
    return False


def _latin_hit(tokens, term):
    if term.endswith('*'):
        stem = term[:-1]
        return any(t.startswith(stem) for t in tokens)
    parts = term.split()
    if len(parts) > 1:
        return ' '.join(parts) in ' '.join(tokens)
    return any(t in (term, term + 's', term + 'es') for t in tokens)


def check_text(text):
    """The category the description is refused for, or '' when it may be crafted."""
    plain = unicodedata.normalize('NFKC', text).lower()
    words = [w for w in (hangul_key(w) for w in plain.split()) if w]
    tokens = re.findall(r'[a-z0-9]+', plain)
    for name, (terms, allowed) in _lists().items():
        for term in terms:
            if latin_key(term):
                if _latin_hit(tokens, term):
                    return name
            elif _korean_hit(words, term, allowed):
                return name
    # Korean swearing from the chat list (its English words name ordinary things too: cock, balls...).
    masked = _swears().check(text)
    if masked.blocked or any(a != b and is_hangul(a) for a, b in zip(text, masked.text)):
        return 'words'
    return ''


# What a released game (no code for refusals, <= 0.11.7) shows: it prints a reply that has a space as it is.
SENTENCES = {
    'sexual': '성적인 내용은 만들 수 없어요.',
    'violence': '잔인하거나 끔찍한 내용은 만들 수 없어요.',
    'hate': '혐오를 담은 상징은 만들 수 없어요.',
    'drugs': '마약과 관련된 물건은 만들 수 없어요.',
    'person': '실제 사람의 얼굴이나 모습은 만들 수 없어요.',
    'words': '욕설이 들어간 의뢰는 받을 수 없어요.',
    'other': '모두가 함께하는 마을에 어울리지 않아 만들 수 없어요.',
}
WORDED_FROM = '0.11.8'


def refusal_detail(category, client_version):
    """The refusal reply: the code for games that word it (WORDED_FROM and later), else the sentence."""
    from .client_policy import older
    category = category if category in CATEGORIES else 'other'
    return SENTENCES[category] if older(client_version or None, WORDED_FROM) else 'refused_' + category


# Studio error code -> the reason the craft window shows (game/scripts/craft_words.gd failure()).
REASONS = {
    'timeout': ('generation_timeout', 'concept_timeout', 'llm_timeout'),
    'design': ('llm_invalid_design', 'llm_incomplete', 'studio_validation_failed', 'design_too_large'),
    'busy': ('llm_busy', 'llm_rate_limited', 'llm_model_unavailable', 'llm_request_failed', 'codex_request_failed',
             'upstream_rate_limit', 'upstream_unavailable', 'upstream_unreachable', 'provider_busy'),
    'mesh': ('generation_failed', 'upstream_schema', 'upstream_rejected', 'upstream_non_json', 'upstream_invalid_json',
             'upstream_response_too_large', 'asset_download_failed', 'asset_integrity_failed', 'unsafe_asset_url',
             'unapproved_asset_host', 'invalid_model', 'stored_part_changed'),
    'heavy': ('assembly_render_budget_exceeded', 'assembly_too_large', 'asset_too_large', 'room_render_budget_exceeded'),
    'photo': ('image_refinement_failed', 'reference_upload_failed', 'invalid_reference_image', 'invalid_image'),
    'restart': ('planning_interrupted', 'worker_lease_expired', 'submission_interrupted'),
    'setup': ('llm_not_configured', 'provider_configuration_required', 'key_not_configured', 'codex_unavailable',
              'developer_provider_forbidden', 'live_generation_disabled', 'upstream_authentication'),
    'credit': ('insufficient_provider_credit', 'tripo_budget_exhausted', 'tester_credit_budget_exhausted'),
    'limit': ('craft_over_trial_limit', 'user_total_generation_limit', 'craft_star_limit_exceeded'),
}
_REASON_OF = {code: reason for reason, codes in REASONS.items() for code in codes}


def failure_reason(code):
    """('refused', category) for a refused craft, else (reason, '') — reason '' when there is no error."""
    code = str(code or '')
    if not code:
        return '', ''
    if code.startswith('refused_'):
        return 'refused', category_of(code[8:]) or 'other'
    return _REASON_OF.get(code, 'other'), ''
