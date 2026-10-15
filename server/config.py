from dataclasses import dataclass, field
from pathlib import Path
import os
import math
import re

ROOT = Path(__file__).resolve().parents[1]

def _tripo_key_line(value):
    value = value.strip()
    if value.startswith('TRIPO_API_KEY='):
        value = value.split('=', 1)[1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    if not value or len(value) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError
    return value

def read_tripo_keys(path):
    """All keys of a server-local key file: one per line, blank lines and # comments
    ignored, first line first. Errors never include file contents."""
    try:
        with Path(path).open('rb') as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise ValueError
        keys = []
        for line in raw.decode('utf-8-sig').splitlines():
            if line.strip() and not line.strip().startswith('#'):
                key = _tripo_key_line(line)
                if key not in keys: keys.append(key)
        if not keys or len(keys) > 32:
            raise ValueError
        return tuple(keys)
    except (OSError, UnicodeError, ValueError):
        raise ValueError('invalid_tripo_key_file') from None

def read_tripo_key(path):
    """The first key of a key file (tools that need only one)."""
    return read_tripo_keys(path)[0]

def configured_tripo_keys():
    direct = os.getenv('TRIPO_API_KEY', '')
    path = os.getenv('TRIPO_API_KEY_FILE', '')
    if direct and path:
        raise ValueError('configure_only_one_tripo_key_source')
    if path:
        return read_tripo_keys(path)
    return (direct,) if direct else ()

def configured_tripo_key():
    keys = configured_tripo_keys()
    return keys[0] if keys else ''

def server_version():
    """The release this server runs: config/version of game/project.godot, the number every
    release bumps (the client built from the same commit shows it too; the image copies the
    file). The update script adds the git commit (VILLAGEN_SERVER_COMMIT) for builds between
    releases."""
    try:
        text = (ROOT / 'game' / 'project.godot').read_text(encoding='utf-8')
        found = re.search(r'^config/version="([0-9A-Za-z.+-]{1,40})"', text, re.M)
        version = found.group(1) if found else 'unknown'
    except OSError:
        version = 'unknown'
    commit = os.getenv('VILLAGEN_SERVER_COMMIT', '').strip()
    return version, commit if re.fullmatch(r'[0-9a-f]{7,40}', commit) else ''

def configured_secret(name):
    direct = os.getenv(name, '')
    path = os.getenv(name + '_FILE', '')
    if direct and path:
        raise ValueError('configure_only_one_' + name.lower() + '_source')
    if not path:
        return direct
    try:
        with Path(path).open('rb') as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError
        value = raw.decode('utf-8-sig').strip()
        if not value or len(value) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError
        return value
    except (OSError, UnicodeError, ValueError):
        raise ValueError('invalid_' + name.lower() + '_file') from None

@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('TRIPOTHON_DATA_DIR', str(ROOT / 'server-data'))))
    mode: str = field(default_factory=lambda: os.getenv('TRIPOTHON_MODE', 'demo'))
    tripo_key: str = field(default_factory=configured_tripo_key, repr=False)
    # Several Tripo accounts: new crafts use the first key with enough credit; each task
    # keeps the key it was created with. Empty means just tripo_key.
    tripo_keys: tuple = field(default_factory=configured_tripo_keys, repr=False)
    tripo_model: str = field(default_factory=lambda: os.getenv('TRIPO_MODEL', 'P2-20260801'))
    paid_enabled: bool = field(default_factory=lambda: os.getenv('TRIPO_ENABLE_PAID', 'false').lower() == 'true')
    registration_code: str = field(default_factory=lambda: configured_secret('TRIPOTHON_REGISTRATION_CODE'), repr=False)
    daily_generation_limit: int = field(default_factory=lambda: int(os.getenv('TRIPO_DAILY_REQUEST_LIMIT', '5')))
    user_daily_generation_limit: int = field(default_factory=lambda: int(os.getenv('TRIPO_USER_DAILY_REQUEST_LIMIT', '2')))
    # Crafts one account may ever start (0 = no lifetime limit; the daily limits still apply).
    user_total_generation_limit: int = field(default_factory=lambda: int(os.getenv('TRIPO_USER_TOTAL_REQUEST_LIMIT', '0')))
    # Stars a new live account starts with (judging servers let visitors craft right away).
    welcome_stars: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_WELCOME_STARS', '0')))
    # Trial servers: most Tripo credits one craft may spend (0 = no cap). 10 allows the
    # cheapest craft only (one untextured H3 mesh from text).
    max_credits_per_craft: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_MAX_CREDITS_PER_CRAFT', '0')))
    # Tripo credits this server may spend in total (spent plus confirmed builds); 0 = no budget.
    tripo_credit_budget: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_TRIPO_CREDIT_BUDGET', '0')))
    # Open sign-up: live accounts without the invitation code, within these limits.
    open_registration: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_OPEN_REGISTRATION', 'false').lower() == 'true')
    signups_per_ip_day: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SIGNUPS_PER_IP_DAY', '3')))
    signups_per_day: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SIGNUPS_PER_DAY', '200')))
    legacy_generation_enabled: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_ENABLE_LEGACY_GENERATION', 'false').lower() == 'true')
    credit_reserve: int = field(default_factory=lambda: int(os.getenv('TRIPO_RESERVE_PER_JOB', '200')))
    # Seconds one submitted Tripo part may take (queued, running or unreachable) before the craft
    # fails and its starseeds come back; the task is never submitted again.
    studio_part_deadline: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_STUDIO_PART_DEADLINE', '1200')))
    # Village residents decorate their homes with gifts (server/npc_homes.py). Seconds from a gift
    # until the resident puts it up (random in this range), and between later rearrangements.
    # Tests and QA shorten them; NPC_SEED fixes every home's dice (0 = a fresh seed per home).
    npc_place_min: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_NPC_PLACE_MIN', '300')))
    npc_place_max: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_NPC_PLACE_MAX', '10800')))
    npc_shuffle_min: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_NPC_SHUFFLE_MIN', '14400')))
    npc_shuffle_max: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_NPC_SHUFFLE_MAX', '86400')))
    npc_seed: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_NPC_SEED', '0')))
    # New accounts start the opening story chapter (server/story.py); off: they never see it.
    story_enabled: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_STORY', 'on').lower() not in ('off', '0', 'false'))
    # Friendship points for hearts 1..4 (each new heart brings a letter, the fourth a return gift).
    npc_levels: tuple = field(default_factory=lambda: tuple(int(v) for v in os.getenv('TRIPOTHON_NPC_LEVELS', '30,80,160,300').split(',')))
    session_seconds: int = 12 * 60 * 60
    day_seconds: float = 60.0
    studio_llm: str = field(default_factory=lambda: os.getenv('TRIPOTHON_STUDIO_LLM', 'fixture'))
    studio_design_format: str = field(default_factory=lambda: os.getenv('TRIPOTHON_DESIGN_FORMAT','classic'))
    studio_credit_rate: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_STARS_PER_CREDIT','1')))
    llm_key: str = field(default_factory=lambda: configured_secret('OPENAI_API_KEY'), repr=False)
    gemini_key: str = field(default_factory=lambda: configured_secret('GEMINI_API_KEY'), repr=False)
    # Tried in order; a model the key cannot use (404) falls through to the next.
    gemini_models: tuple = field(default_factory=lambda: tuple(m.strip() for m in os.getenv(
        'TRIPOTHON_GEMINI_MODELS', 'gemini-3.5-flash,gemini-3.8-flash,gemini-3.1-flash-lite').split(',') if m.strip()))
    # Read-only usage totals for the PC cost monitor (server/usage_report.py, ops/usage_key.sh).
    # Not a login; empty turns the route off.
    usage_key: str = field(default_factory=lambda: configured_secret('TRIPOTHON_USAGE_KEY'), repr=False)
    # Development servers (ops/staging.sh fake): crafting talks to the built-in stand-in for Tripo
    # (server/fake_tripo.py) instead of the network; no key, no credits. Optional seconds per fake task.
    fake_tripo: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_FAKE_TRIPO', 'false').lower() == 'true')
    fake_tripo_seconds: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_FAKE_TRIPO_SECONDS', '0')))
    # /health shows it when set (the development server says "staging"); empty on production.
    environment: str = field(default_factory=lambda: os.getenv('TRIPOTHON_ENVIRONMENT', '').strip())
    # Social layer (server/chat.py, server/friends.py, docs/design/SOCIAL_API.md).
    # The server-wide "everyone" chat channel (rate limited, filtered); off: only village, party, whispers.
    global_chat: bool = field(default_factory=lambda: os.getenv('VILLAGEN_GLOBAL_CHAT', 'on').lower() not in ('off', '0', 'false'))
    # Who appears in the online roster (/v1/social/people): all players, friends only, or nobody.
    social_roster: str = field(default_factory=lambda: os.getenv('VILLAGEN_SOCIAL_ROSTER', 'all').strip().lower())
    # An operator's extra word list (same syntax as server/data/chat_words.txt); relative to data_dir.
    chat_filter_extra: str = field(default_factory=lambda: os.getenv('VILLAGEN_CHAT_FILTER_EXTRA', '').strip())
    # Chat lines one address may send per minute (a school shares one address: keep it generous).
    chat_ip_per_minute: int = field(default_factory=lambda: int(os.getenv('VILLAGEN_CHAT_IP_PER_MINUTE', '240')))
    # Hours a chat line is kept (history and reports read only this window).
    chat_retention_hours: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_CHAT_RETENTION_HOURS', '24')))
    # Polling advice the server gives clients in /health (seconds): presence with other players
    # around, presence alone, and the social window's roster refresh.
    presence_together_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PRESENCE_TOGETHER', '0.25')))
    presence_alone_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PRESENCE_ALONE', '1')))
    people_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PEOPLE_SECONDS', '5')))

    def validate(self):
        if self.mode not in ('demo', 'live'):
            raise ValueError('TRIPOTHON_MODE must be demo or live')
        if self.studio_llm not in ('fixture','codex','openai','gemini'):
            raise ValueError('Invalid studio LLM provider')
        if self.studio_design_format not in ('classic','structured'):
            raise ValueError('Invalid studio design format')
        if self.mode=='live' and self.studio_llm=='codex':
            raise ValueError('Codex subscription experiments are local development only')
        if self.mode == 'live' and len(self.registration_code) < 24:
            raise ValueError('Live mode requires a registration invitation code of at least 24 characters')
        if not 0 <= self.max_credits_per_craft <= 100000:
            raise ValueError('Invalid craft credit cap')
        if not 0 <= self.tripo_credit_budget <= 10000000:
            raise ValueError('Invalid Tripo credit budget')
        if not 1 <= self.signups_per_ip_day <= 1000 or not 1 <= self.signups_per_day <= 100000:
            raise ValueError('Invalid open sign-up limits')
        if not 0 <= self.user_total_generation_limit <= 1000 or not 0 <= self.welcome_stars <= 10000:
            raise ValueError('Invalid account craft limit or welcome stars')
        if self.credit_reserve <= 0 or self.daily_generation_limit < 1 or self.user_daily_generation_limit < 1:
            raise ValueError('Generation budget must be positive')
        if not 60 <= self.studio_part_deadline <= 86400:
            raise ValueError('Invalid studio part deadline')
        if self.fake_tripo:
            from .fake_tripo import FAKE_KEY
            if any(key and key != FAKE_KEY for key in (self.tripo_key, *self.tripo_keys)):
                raise ValueError('The fake Tripo (TRIPOTHON_FAKE_TRIPO) runs without real Tripo keys')
            self.tripo_key, self.tripo_keys = FAKE_KEY, (FAKE_KEY,)
        if not (math.isfinite(self.fake_tripo_seconds) and 0 <= self.fake_tripo_seconds <= 600):
            raise ValueError('Invalid fake Tripo task time')
        if self.environment and not re.fullmatch(r'[a-z0-9-]{1,20}', self.environment):
            raise ValueError('TRIPOTHON_ENVIRONMENT must be a short lowercase name')
        if self.mode == 'live' and self.paid_enabled and not self.tripo_key:
            raise ValueError('Paid live mode requires a Tripo server secret')
        # Without an OpenAI design provider, live crafting offers only the simple
        # one-mesh designer (the player's prompt goes straight to Tripo).
        if self.mode == 'live' and self.paid_enabled and self.studio_llm == 'openai' and not self.llm_key:
            raise ValueError('Paid live mode with OpenAI design requires an OpenAI server secret')
        if self.mode == 'live' and self.paid_enabled and self.studio_llm == 'gemini' and not self.gemini_key:
            raise ValueError('Paid live mode with Gemini design requires a Gemini server secret')
        if self.studio_llm == 'gemini' and not self.gemini_models:
            raise ValueError('Gemini design needs at least one model name')
        for low, high in ((self.npc_place_min, self.npc_place_max), (self.npc_shuffle_min, self.npc_shuffle_max)):
            if not (math.isfinite(low) and math.isfinite(high) and 0.5 <= low <= high <= 30 * 86400):
                raise ValueError('Invalid resident home timing')
        if len(self.npc_levels) != 4 or any(not 0 <= a < b for a, b in zip((0,) + tuple(self.npc_levels), self.npc_levels)):
            raise ValueError('Friendship hearts need four rising point thresholds')
        if not 0 <= self.npc_seed < 2**31:
            raise ValueError('Invalid resident home seed')
        if not math.isfinite(self.studio_credit_rate) or not .1<=self.studio_credit_rate<=100:
            raise ValueError('Invalid reward currency conversion')
        if self.social_roster not in ('all', 'friends', 'off'):
            raise ValueError('VILLAGEN_SOCIAL_ROSTER must be all, friends or off')
        if not 10 <= self.chat_ip_per_minute <= 100000:
            raise ValueError('Invalid chat lines per address')
        if not (math.isfinite(self.chat_retention_hours) and 1 <= self.chat_retention_hours <= 24 * 30):
            raise ValueError('Invalid chat retention')
        if not (math.isfinite(self.presence_together_seconds) and math.isfinite(self.presence_alone_seconds) and math.isfinite(self.people_seconds)
                and .1 <= self.presence_together_seconds <= self.presence_alone_seconds <= 10 and 2 <= self.people_seconds <= 120):
            raise ValueError('Invalid social polling advice')
        if self.usage_key and len(self.usage_key) < 32:
            raise ValueError('The usage key must be at least 32 characters (ops/usage_key.sh makes one)')
        self.data_dir.mkdir(parents=True, exist_ok=True)
