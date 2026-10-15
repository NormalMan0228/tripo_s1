"""Localized 0.11.9 copy for existing request conditions and letter hooks.

These catalogs describe content only. Quest IDs, conditions, rewards, event
delivery and gift grants remain owned by their existing gameplay modules.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path


DATA = Path(__file__).with_name('data')


def _load(filename, key):
    data = json.loads((DATA / filename).read_text(encoding='utf-8'))
    entries = tuple(data[key])
    if len({entry['id'] for entry in entries}) != len(entries):
        raise ValueError(f'duplicate_content_id: {filename}')
    return entries


QUEST_TEMPLATES = _load('quest_templates_0119.json', 'templates')
LETTER_TEMPLATES = _load('npc_letters_0119.json', 'letters')


def quest_template(quest_id, now):
    """Rotate copy on each appearance in the existing KST board schedule."""
    # Local imports keep this data module usable from the mailbox during startup.
    from . import quest_board, quests

    choices = [entry for entry in QUEST_TEMPLATES if entry['quest_id'] == quest_id]
    if not choices:
        return None
    catalog = tuple(quests.QUESTS)
    slots_before_today = int((now + 9 * 3600) // 86400) * quest_board.BOARD_SIZE
    appearance = (slots_before_today + len(catalog) - 1 - catalog.index(quest_id)) // len(catalog)
    content = deepcopy(choices[appearance % len(choices)])
    for translations in content['text'].values():
        for field, value in translations.items():
            translations[field] = value.format(count=quests.QUESTS[quest_id]['count'])
    return content


def letter_template(npc, occasion, key=''):
    """Return matching copy without creating mail or granting its optional gift."""
    choices = [entry for entry in LETTER_TEMPLATES
               if entry['npc'] == npc and entry['occasion'] == occasion]
    if not choices:
        return None
    index = int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:8], 'big') % len(choices)
    return deepcopy(choices[index])
