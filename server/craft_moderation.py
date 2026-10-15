"""Inappropriate craft requests are refused with a reason, never quietly softened into something else.

Three gates, each ending the craft as refused_<category> (sexual, violence, hate, drugs, person,
words, other) with the starseeds kept or refunded:
1. The description, before anything is charged: server/data/craft_words.txt per category, plus the
   chat swear list (server/chat_filter.py) as `words`.
2. The LLM designer, in the same call that designs the object (no extra cost): the contract
   (server/asset_contract.py SAFETY) makes it answer {"refused": category} for the description or
   the reference photo; a provider's own safety block counts as `other`.
3. Tripo: a request rejected for its content policy (code 2008) or a task it bans.

failure_reason() groups every studio error code into the few reasons the craft window words.
"""
import re
from functools import lru_cache
from pathlib import Path
from .chat_filter import ChatFilter
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
def _filters():
    sections, current = {}, None
    for line in WORDS.read_text(encoding='utf-8-sig').splitlines():
        head = re.fullmatch(r'\s*\[([a-z]+)\]\s*', line)
        if head:
            current = sections.setdefault(head.group(1), [])
        elif current is not None:
            current.append(line)
    filters = [(name, ChatFilter(lines=lines)) for name, lines in sections.items()]
    return filters + [('words', ChatFilter())]


def check_text(text):
    """The category the description is refused for, or '' when it may be crafted."""
    for name, words in _filters():
        found = words.check(text)
        # Chat masks phone numbers and links too; only listed words refuse a craft.
        if found.blocked or found.masked:
            return name
    return ''


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
    'credit': ('insufficient_provider_credit', 'tripo_budget_exhausted'),
    'limit': ('craft_over_trial_limit', 'user_total_generation_limit'),
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
