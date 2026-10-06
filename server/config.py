from dataclasses import dataclass, field
from pathlib import Path
import os
import math

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
    # Open sign-up: live accounts without the invitation code, within these limits.
    open_registration: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_OPEN_REGISTRATION', 'false').lower() == 'true')
    signups_per_ip_day: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SIGNUPS_PER_IP_DAY', '3')))
    signups_per_day: int = field(default_factory=lambda: int(os.getenv('TRIPOTHON_SIGNUPS_PER_DAY', '200')))
    legacy_generation_enabled: bool = field(default_factory=lambda: os.getenv('TRIPOTHON_ENABLE_LEGACY_GENERATION', 'false').lower() == 'true')
    credit_reserve: int = field(default_factory=lambda: int(os.getenv('TRIPO_RESERVE_PER_JOB', '200')))
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
        if not 1 <= self.signups_per_ip_day <= 1000 or not 1 <= self.signups_per_day <= 100000:
            raise ValueError('Invalid open sign-up limits')
        if not 0 <= self.user_total_generation_limit <= 1000 or not 0 <= self.welcome_stars <= 10000:
            raise ValueError('Invalid account craft limit or welcome stars')
        if self.credit_reserve <= 0 or self.daily_generation_limit < 1 or self.user_daily_generation_limit < 1:
            raise ValueError('Generation budget must be positive')
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
        if not math.isfinite(self.studio_credit_rate) or not .1<=self.studio_credit_rate<=100:
            raise ValueError('Invalid reward currency conversion')
        self.data_dir.mkdir(parents=True, exist_ok=True)
