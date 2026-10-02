"""Strict local configuration; secrets never enter dataclass representations."""
from dataclasses import dataclass, field, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import re
import tomllib
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Persona:
    address: str = ''
    tone: str = '自然、尊重、中文交流，不确定时明确说明'
    reply_style: str = '尽量简短，不擅自设定恋爱关系'


@dataclass(frozen=True)
class ModelConfig:
    provider: str = 'fake'
    allow_network: bool = False
    endpoint: str = ''
    name: str = ''
    api_key_env: str = 'WECHAT_AI_API_KEY'
    timeout_seconds: float = 20.0
    context_chars: int = 6000
    history_messages: int = 12
    summary_chars: int = 700
    memory_chars: int = 1200
    max_reply_chars: int = 1500
    max_completion_tokens: int = 512
    api_key: str = field(default='', repr=False)


@dataclass(frozen=True)
class Limits:
    daily_calls: int = 50
    per_call_estimate: Decimal = Decimal('0.02')
    daily_estimate: Decimal = Decimal('2')
    currency: str = 'USD'
    timezone: str = 'Asia/Shanghai'


@dataclass(frozen=True)
class Config:
    peer_id: str
    data_dir: Path
    adapter: str = 'mock'
    dry_run: bool = True
    real_send: bool = False
    proactive: bool = False
    max_concurrency: int = 1
    max_input_chars: int = 1600
    persona: Persona = field(default_factory=Persona)
    model: ModelConfig = field(default_factory=ModelConfig)
    limits: Limits = field(default_factory=Limits)


def _section(data, name, cls, excluded=()):
    section = data.get(name, {})
    allowed = {f.name for f in fields(cls)} - set(excluded)
    if not isinstance(section, dict) or set(section) - allowed:
        raise ConfigError(f'{name}: invalid fields')
    return dict(section)


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ConfigError(f'{name}: out of range or invalid type')


def validate(c):
    if c.adapter != 'mock' or c.real_send is not False or c.proactive is not False:
        raise ConfigError('this build only supports mock, real_send=false, proactive=false')
    if type(c.dry_run) is not bool or c.max_concurrency != 1 or type(c.max_concurrency) is not int:
        raise ConfigError('invalid dry_run or max_concurrency')
    if not isinstance(c.peer_id, str) or not re.fullmatch(r'mock:[A-Za-z0-9_.-]{1,80}', c.peer_id):
        raise ConfigError('peer_id must be a stable mock identifier')
    _integer(c.max_input_chars, 'max_input_chars', 100, 10000)
    for value in (c.persona.address, c.persona.tone, c.persona.reply_style):
        if not isinstance(value, str) or len(value) > 200:
            raise ConfigError('persona values must be strings of at most 200 characters')
    m = c.model
    for name in ('endpoint', 'name', 'api_key_env'):
        if not isinstance(getattr(m, name), str):
            raise ConfigError('model string field invalid')
    if m.provider not in ('fake', 'chat_completions', 'deepseek') or type(m.allow_network) is not bool:
        raise ConfigError('model provider or allow_network invalid')
    if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', m.api_key_env):
        raise ConfigError('api_key_env invalid')
    try:
        timeout = Decimal(str(m.timeout_seconds))
    except InvalidOperation:
        raise ConfigError('timeout_seconds invalid') from None
    if not timeout.is_finite() or not 0.1 <= timeout <= 120:
        raise ConfigError('timeout_seconds invalid')
    for name, low, high in [('context_chars', 3000, 100000), ('history_messages', 2, 100),
                            ('summary_chars', 100, 5000), ('memory_chars', 100, 10000),
                            ('max_reply_chars', 100, 10000), ('max_completion_tokens', 16, 16000)]:
        _integer(getattr(m, name), name, low, high)
    if c.max_input_chars + m.memory_chars + m.summary_chars + 1000 > m.context_chars:
        raise ConfigError('context_chars too small for configured components')
    if m.provider in ('chat_completions', 'deepseek'):
        if not m.allow_network or not m.api_key.strip() or not m.name.strip():
            raise ConfigError('network model requires opt-in, model name and a local credential')
        if m.provider == 'deepseek' and m.endpoint not in (
                'https://api.deepseek.com/chat/completions',
                'https://api.deepseek.com/v1/chat/completions'):
            raise ConfigError('deepseek requires an official HTTPS chat endpoint')
        try:
            url = urlsplit(m.endpoint)
            valid = url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('127.0.0.1', '::1', 'localhost'))
            if not valid or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError
            if not url.path.endswith('/chat/completions') or url.port == 0:
                raise ValueError
        except ValueError:
            raise ConfigError('endpoint must be HTTPS (or loopback HTTP), without credentials or query') from None
    _integer(c.limits.daily_calls, 'daily_calls', 1, 100000)
    for amount in (c.limits.per_call_estimate, c.limits.daily_estimate):
        if not amount.is_finite() or amount <= 0:
            raise ConfigError('estimates must be positive finite numbers')
    if c.limits.timezone not in ('UTC', 'Asia/Shanghai'):
        raise ConfigError('timezone must be UTC or Asia/Shanghai')
    if not isinstance(c.limits.currency, str) or not re.fullmatch('[A-Z]{3}', c.limits.currency):
        raise ConfigError('currency must be a three-letter label')
    return c


def load_config(path, environ=None):
    path = Path(path).resolve()
    env = os.environ if environ is None else environ
    try:
        data = tomllib.loads(path.read_text('utf-8-sig'))
        if set(data) - {'app', 'persona', 'model', 'limits'}:
            raise ConfigError('unknown section')
        a = _section(data, 'app', Config, ('model', 'persona', 'limits'))
        if not isinstance(a.get('data_dir', 'data'), str):
            raise ConfigError('data_dir invalid')
        a['data_dir'] = (path.parent / a.get('data_dir', 'data')).resolve()
        p = _section(data, 'persona', Persona)
        m = _section(data, 'model', ModelConfig, ('api_key',))
        key_name = m.get('api_key_env', 'WECHAT_AI_API_KEY')
        credential = env.get(key_name, '') if isinstance(key_name, str) else ''
        # Parse only the one configured variable. Never execute .env as code.
        dotenv = path.parent / '.env'
        if not credential and dotenv.is_file():
            for line in dotenv.read_text('utf-8-sig').splitlines():
                key, sep, value = line.strip().partition('=')
                if sep and key.strip() == key_name:
                    credential = value.strip().strip('\"\'')
        m['api_key'] = credential
        lim = _section(data, 'limits', Limits)
        for key in ('per_call_estimate', 'daily_estimate'):
            if key in lim:
                lim[key] = Decimal(str(lim[key]))
        return validate(Config(**a, persona=Persona(**p), model=ModelConfig(**m), limits=Limits(**lim)))
    except ConfigError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError, InvalidOperation):
        # No TOML fragment, URL, key, or file content in errors.
        raise ConfigError('cannot load configuration; check schema and local file') from None
