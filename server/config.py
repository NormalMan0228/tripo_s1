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
    user_daily_generation_limit: int = field(default_factory=lambda: int(os.getenv('TRIPO_USER_DAILY_REQUEST_LIMIT', '5')))
    # Crafts one account may ever start (0 = no lifetime limit; the daily limits still apply).
    user_total_generation_limit: int = field(default_factory=lambda: int(os.getenv('TRIPO_USER_TOTAL_REQUEST_LIMIT', '0')))
    # Stars a new live account starts with (judging servers let visitors craft right away).
    welcome_stars: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_WELCOME_STARS', '150')))
    max_stars_per_craft: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_MAX_STARS_PER_CRAFT', '200')))
    tester_welcome_stars: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_TESTER_WELCOME_STARS', '1500')))
    tester_credit_budget: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_TESTER_CREDIT_BUDGET', '10000')))

    def limits_for(self, user):
        """Only an operator-set database flag grants tester limits; names grant nothing."""
        tester = bool(user['is_tester']) if user is not None and 'is_tester' in user.keys() else False
        return AccountLimits(
            daily_generation_limit=0 if tester else self.daily_generation_limit,
            user_daily_generation_limit=0 if tester or self.mode != 'live' else self.user_daily_generation_limit,
            user_total_generation_limit=0 if tester or self.mode != 'live' else self.user_total_generation_limit,
            welcome_stars=self.tester_welcome_stars if tester else self.welcome_stars,
            max_stars_per_craft=self.max_stars_per_craft,
            max_credits_per_craft=self.max_credits_per_craft if self.mode == 'live' else 0,
            tripo_credit_budget=self.tripo_credit_budget,
            tester_credit_budget=self.tester_credit_budget if tester else 0,
            is_tester=tester)

    # Selling at the village shop also pays starseeds: one per this many leaf coins of sales, at
    # most sell_stars_daily a day (the player's day; 0 = selling pays leaf coins only).
    sell_stars_daily: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SELL_STARS_DAILY', '15')))
    sell_coins_per_star: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SELL_COINS_PER_STAR', '3')))
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
    # Resident moves are opt-in until the client/map integration is ready.
    resident_moves: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_RESIDENT_MOVES', 'off').lower() in ('on', '1', 'true'))
    resident_arrive_seconds: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_RESIDENT_ARRIVE_SECONDS', '90')))
    resident_leave_seconds: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_RESIDENT_LEAVE_SECONDS', '90')))
    # New accounts start the opening story chapter (server/story.py); off: they never see it.
    story_enabled: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_STORY', 'on').lower() not in ('off', '0', 'false'))
    # Residents' requests (server/quests.py): their starseed rewards (quests.STARS) times this;
    # 0 turns the rewards off (the requests still run and pay nothing).
    quest_stars_scale: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_QUEST_STARS_SCALE', '1.0')))
    # Treasure chests (server/treasure.py): their starseed rewards (treasure.STARS) times this;
    # 0 turns the rewards off (the chests still open and pay nothing).
    chest_stars_scale: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_CHEST_STARS_SCALE', '1.0')))
    # Friendship points for hearts 1..4 (each new heart brings a letter, the fourth a return gift).
    npc_levels: tuple = field(default_factory=lambda: tuple(int(v) for v in os.getenv('TRIPOTHON_NPC_LEVELS', '30,80,160,300').split(',')))
    session_seconds: int = 12 * 60 * 60
    # Seconds of an expedition's first stage (server/stages.py: then 120, 150, ... at 90). Demo/QA
    # servers may shorten it (TRIPOTHON_STAGE_SECONDS) for quick test runs; live servers keep 90.
    day_seconds: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_STAGE_SECONDS', '90')))
    studio_llm: str = field(default_factory=lambda: os.getenv('TRIPOTHON_STUDIO_LLM', 'fixture'))
    studio_design_format: str = field(default_factory=lambda: os.getenv('TRIPOTHON_DESIGN_FORMAT','classic'))
    studio_credit_rate: float = field(default_factory=lambda: float(os.getenv('TRIPOTHON_STARS_PER_CREDIT','1')))
    llm_key: str = field(default_factory=lambda: configured_secret('OPENAI_API_KEY'), repr=False)
    gemini_key: str = field(default_factory=lambda: configured_secret('GEMINI_API_KEY'), repr=False)
    # Shared UTC-day call budget for craft/interaction design, including failed calls,
    # repairs and model retries. Testers use the same caps; 0 disables LLM calls.
    llm_user_daily_call_limit: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_LLM_USER_DAILY_CALL_LIMIT', '20')))
    llm_server_daily_call_limit: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_LLM_SERVER_DAILY_CALL_LIMIT', '1000')))
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
    # Chat lines one address may send per minute (a school shares one address: 120 players chatting
    # every 20 s are 360 a minute, so keep it generous; each account has its own tighter limits).
    chat_ip_per_minute: int = field(default_factory=lambda: int(os.getenv('VILLAGEN_CHAT_IP_PER_MINUTE', '600')))
    # Hours a chat line is kept (history and reports read only this window).
    chat_retention_hours: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_CHAT_RETENTION_HOURS', '24')))
    # Polling advice the server gives clients in /health (seconds): presence with other players
    # around, presence alone, and the social window's roster refresh.
    presence_together_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PRESENCE_TOGETHER', '0.25')))
    presence_alone_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PRESENCE_ALONE', '1')))
    people_seconds: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PEOPLE_SECONDS', '5')))
    # Presence polls a second the server is meant to carry (all players together). Above it, the
    # advice in every chat2 reply (social.poll) slows the clients down smoothly, up to 4 times.
    # 60 keeps a t4g.small near its CPU baseline with a class of 60 (docs/design/SOCIAL_API.md, 9).
    presence_budget: float = field(default_factory=lambda: float(os.getenv('VILLAGEN_PRESENCE_BUDGET', '60')))

    def validate(self):
        from .campfire import configured_mode
        configured_mode()
        if self.mode not in ('demo', 'live'):
            raise ValueError('TRIPOTHON_MODE must be demo or live')
        if self.studio_llm not in ('fixture','codex','openai','gemini'):
            raise ValueError('Invalid studio LLM provider')
        if self.studio_design_format not in ('classic','structured'):
            raise ValueError('Invalid studio design format')
        if (type(self.llm_user_daily_call_limit) is not int or type(self.llm_server_daily_call_limit) is not int
                or not 0 <= self.llm_user_daily_call_limit <= 1000000
                or not 0 <= self.llm_server_daily_call_limit <= 1000000):
            raise ValueError('Invalid LLM daily call limits')
        if self.mode=='live' and self.studio_llm=='codex':
            raise ValueError('Codex subscription experiments are local development only')
        if self.mode == 'live' and self.day_seconds != 90:
            raise ValueError('TRIPOTHON_STAGE_SECONDS is for demo and QA servers only')
        if self.mode == 'live' and len(self.registration_code) < 24:
            raise ValueError('Live mode requires a registration invitation code of at least 24 characters')
        if not 1 <= self.max_stars_per_craft <= 10000:
            raise ValueError('Invalid craft star cap')
        if not 0 <= self.tester_welcome_stars <= 10000 or not 1 <= self.tester_credit_budget <= 10000000:
            raise ValueError('Invalid tester limits')
        if not 0 <= self.max_credits_per_craft <= 100000:
            raise ValueError('Invalid craft credit cap')
        if not 0 <= self.tripo_credit_budget <= 10000000:
            raise ValueError('Invalid Tripo credit budget')
        if not 1 <= self.signups_per_ip_day <= 1000 or not 1 <= self.signups_per_day <= 100000:
            raise ValueError('Invalid open sign-up limits')
        if not 0 <= self.user_total_generation_limit <= 1000 or not 0 <= self.welcome_stars <= 10000:
            raise ValueError('Invalid account craft limit or welcome stars')
        if not 0 <= self.sell_stars_daily <= 1000 or not 1 <= self.sell_coins_per_star <= 1000:
            raise ValueError('TRIPOTHON_SELL_STARS_DAILY must be 0-1000 and TRIPOTHON_SELL_COINS_PER_STAR 1-1000')
        # TRIPO_DAILY_REQUEST_LIMIT=0: no server-wide daily count (the main server, 2026-10-16: the
        # Tripo credit budget is the limit); each account keeps its own daily limit.
        if self.credit_reserve <= 0 or self.daily_generation_limit < 0 or self.user_daily_generation_limit < 1:
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
        for delay in (self.resident_arrive_seconds, self.resident_leave_seconds):
            if not math.isfinite(delay) or not 0 <= delay <= 30 * 86400:
                raise ValueError('Invalid resident move timing')
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
        if not (math.isfinite(self.presence_budget) and 5 <= self.presence_budget <= 5000):
            raise ValueError('Invalid presence budget')
        if not (math.isfinite(self.quest_stars_scale) and 0 <= self.quest_stars_scale <= 5):
            raise ValueError('TRIPOTHON_QUEST_STARS_SCALE must be between 0 (off) and 5')
        if not (math.isfinite(self.chest_stars_scale) and 0 <= self.chest_stars_scale <= 5):
            raise ValueError('TRIPOTHON_CHEST_STARS_SCALE must be between 0 (off) and 5')
        if self.usage_key and len(self.usage_key) < 32:
            raise ValueError('The usage key must be at least 32 characters (ops/usage_key.sh makes one)')
        self.data_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AccountLimits:
    daily_generation_limit: int
    user_daily_generation_limit: int
    user_total_generation_limit: int
    welcome_stars: int
    max_stars_per_craft: int
    max_credits_per_craft: int
    tripo_credit_budget: int
    tester_credit_budget: int
    is_tester: bool
