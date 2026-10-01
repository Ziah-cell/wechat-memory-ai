"""Allowlisted metadata logging; no body, identity or arbitrary exception fields."""
from datetime import datetime, timezone
from logging import Formatter, LogRecord
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json
import re


class Audit:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(directory / 'audit.log', maxBytes=1_000_000,
                                          backupCount=3, encoding='utf-8')
        self.handler.setFormatter(Formatter('%(message)s'))

    def write(self, status, event_key='', code=''):
        # Callers cannot attach text, URLs, names, or exception objects.
        allowed = {'rejected','duplicate','dry_run','simulated','model_failed','budget_blocked',
                   'identity_blocked','unknown','review_required','paused','stopped','interrupted'}
        safe_codes = {'timeout','auth','quota','network','server','format','empty','network_disabled',
                      'model_failure','invalid_event','history','not_allowed','target_changed',
                      'send_failure','cost_limit','call_limit',''}
        item = {'time': datetime.now(timezone.utc).isoformat(),
                'status': status if status in allowed else 'rejected',
                'event': event_key if re.fullmatch('[a-f0-9]{64}', event_key) else '',
                'code': code if code in safe_codes else 'model_failure'}
        self.handler.handle(LogRecord('audit', 20, '', 0, json.dumps(item), (), None))

    def close(self):
        self.handler.close()
