"""Saved appearances of the 8 characters (m1..m4, f1..f4), old saves read safely, and the avatar8
migration (old character ids mapped, originals kept in profile_avatar8_backup, selection reopened)."""
import contextvars
import json

from pydantic import ValidationError

from .models import Avatar, AvatarPatch, CHARACTERS, SELECT_FROM

# The x-villagen-version of the request being answered (app.py ClientVersion sets it).
CLIENT_VERSION = contextvars.ContextVar('client_version', default=None)


def legacy_client():
    """A game older than the character select (0.11.8 and before, or no version header)."""
    from .client_policy import older
    version = CLIENT_VERSION.get()
    return bool(version) and older(version, SELECT_FROM)


def legacy_look(value):
    """What a 0.11.8 game can draw: its player.gd builds the wardrobe model only for explorer_b and
    otherwise loads assets/<id>.glb (none ship for m1..f4: a primitive placeholder), so it gets the
    released ids. accent is dropped by its normalize(); straw shows as its round hat."""
    return dict(value, character='explorer' if value['character'].startswith('m') else 'explorer_b')


def legacy_echo(patch, saved):
    """A 0.11.8 wardrobe re-sending the released id it was served (a colour-only save): the saved
    m1..f4 character stays."""
    return (legacy_client() and 'character' in patch.model_fields_set and patch.character not in CHARACTERS
            and legacy_look(saved)['character'] == patch.character)


EDIT_LIMIT = 10
EDIT_WINDOW_SECONDS = 60


def legacy_request_json(body):
    """Rebuild the old validated request for a retry accepted before the upgrade.

    The old request cache hashed the complete model (including defaults), in this
    field order. New partial edits need an omission-aware fingerprint instead.
    """
    defaults = dict(character='explorer_b',hair='#30595b',coat='#dba448',pants='#526552',
                    boots='#765744',skin='#e4b587',headwear='none',backpack=True)
    if not body.avatar.model_fields_set <= defaults.keys():
        return None
    defaults.update(body.avatar.model_dump(include=body.avatar.model_fields_set))
    return json.dumps(dict(request_id=str(body.request_id),version=body.version,avatar=defaults),
                      separators=(',',':'))


def saved_avatar(raw=None):
    """Read old or new saves; a damaged field must not prevent the account signing in.

    Request validation stays strict. Only stored data takes this recovery path; the
    migration keeps its exact original bytes in profile_avatar8_backup.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if not isinstance(raw, dict):
        return Avatar().model_dump()
    try:
        return AvatarPatch.model_validate(raw).resolve()
    except ValidationError:
        valid = {}
        for key, item in raw.items():
            if key not in AvatarPatch.model_fields:
                continue
            try:
                AvatarPatch.model_validate({key:item})
            except ValidationError:
                continue
            valid[key] = item
        return AvatarPatch.model_validate(valid).resolve()


def public_avatar(raw=None):
    """The avatar every reply carries (profile, presence, visits, friends): the saved look, with the
    released character ids for games older than 0.11.9 (legacy_look)."""
    value = saved_avatar(raw)
    return legacy_look(value) if legacy_client() else value


def migrate(db):
    """Upgrade once, atomically. No profile/version is invented for an unsaved look."""
    db.execute('BEGIN IMMEDIATE')
    try:
        if 'needs_character_select' not in [r[1] for r in db.execute('PRAGMA table_info(profiles)')]:
            db.execute('ALTER TABLE profiles ADD COLUMN needs_character_select INTEGER NOT NULL DEFAULT 1 '
                       'CHECK(needs_character_select IN (0,1))')
        if not db.execute("SELECT 1 FROM metadata WHERE key='avatar8_schema'").fetchone():
            for row in db.execute('SELECT user_id,avatar,version FROM profiles').fetchall():
                db.execute('INSERT OR IGNORE INTO profile_avatar8_backup(user_id,avatar,version) VALUES (?,?,?)',
                           (row['user_id'],row['avatar'],row['version']))
                db.execute('UPDATE profiles SET avatar=?,needs_character_select=1 WHERE user_id=?',
                           (json.dumps(saved_avatar(row['avatar'])),row['user_id']))
            db.execute("INSERT INTO metadata(key,value) VALUES ('avatar8_schema','1')")
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


# Starting looks per character (the game knows them too; servers can retune them without an update).
DEFAULT_LOOKS = {
    'm1': {'hair':'#2b2320','skin':'#e4b587','coat':'#3f6fa8','pants':'#3b4250','boots':'#5a4030','accent':'#c9a24a'},
    'm2': {'hair':'#5a3a22','skin':'#f0cdb1','coat':'#6a8f4e','pants':'#4a4436','boots':'#6b4a33','accent':'#d77a3d'},
    'm3': {'hair':'#151515','skin':'#bc865c','coat':'#b4553d','pants':'#2f3540','boots':'#3d2c22','accent':'#e0c06a'},
    'm4': {'hair':'#8a6b4a','skin':'#895b43','coat':'#5c4c86','pants':'#38384a','boots':'#4b3627','accent':'#9bc0d8'},
    'f1': {'hair':'#30595b','skin':'#e4b587','coat':'#dba448','pants':'#526552','boots':'#765744','accent':'#765744'},
    'f2': {'hair':'#7a3b2a','skin':'#f0cdb1','coat':'#c76d8a','pants':'#4b4a5e','boots':'#5d4636','accent':'#f2d27a'},
    'f3': {'hair':'#1c1a1a','skin':'#bc865c','coat':'#3d8a7d','pants':'#3a3f3a','boots':'#4a3528','accent':'#e6a25a'},
    'f4': {'hair':'#c9a46e','skin':'#604431','coat':'#8a5bb0','pants':'#3e3550','boots':'#3f2f25','accent':'#7ec7c0'},
}


def catalog():
    from .catalog import CHARACTERS as CARDS
    cards = {card['id']: card for card in CARDS}
    return {'characters': [{'id': key, 'name': cards.get(key, {}).get('name', key),
                            'description': cards.get(key, {}).get('description', ''),
                            'defaults': dict(Avatar(character=key).model_dump(), **DEFAULT_LOOKS[key])} for key in CHARACTERS],
            'headwear': ['none', 'cap', 'beret', 'straw'],
            'parts': ['hair', 'skin', 'coat', 'pants', 'boots', 'accent']}
