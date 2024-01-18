import logging
from collections import OrderedDict
from contextlib import contextmanager
from typing import Mapping, Optional, Union

from loguru import logger, _logger
from loguru._better_exceptions import ExceptionFormatter


SHORT_PWD_LEN = 8
INDICATOR_LEN = 2


def obfuscate(s: str) -> str:
    if s is not None:
        length = len(s)
        if length < SHORT_PWD_LEN:
            s = '*' * length
        else:
            pre = s[:INDICATOR_LEN]
            mid = '*' * (length - 2*INDICATOR_LEN)
            post = s[-INDICATOR_LEN:]
            s = ''.join((pre, mid, post))
    return s


class SecretsFilter(logging.Filter):
    def __init__(
            self,
            name=None,
            secrets: Union[set[str], dict[str, str], None] = None
    ) -> None:
        super().__init__(name=name or 'secret_obfuscator')
        if isinstance(secrets, Mapping):
            self._secrets = secrets
        elif isinstance(secrets, set):
            self._secrets = {secret: obfuscate(secret) for secret in secrets}
        else:
            self._secrets = dict()
        self.order()

    def order(self):
        keys = sorted(self._secrets, key=lambda s: -len(s))
        self._secrets = OrderedDict((k, self._secrets[k]) for k in keys)

    def add_secret(self, secret: str, public: Optional[str] = None):
        if secret:
            public = public or obfuscate(secret)
            self._secrets[secret] = public
            self.order()

    def filter_string(self, s: str) -> str:
        for secret, public in self._secrets.items():
            s = s.replace(secret, public)
        return s

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.filter_string(record.msg)
        return True

    def loguru_filter(self, record: dict) -> bool:
        record['message'] = self.filter_string(record['message'])
        return True


secret_keeper = SecretsFilter()


class SecretExceptionFormatter(ExceptionFormatter):
    @classmethod
    def from_exception_formatter(cls, formatter: ExceptionFormatter):
        result = cls()
        result.__dict__.update(formatter.__dict__)
        result.original_formatter = formatter
        return result

    def format_exception(self, *args, **kwargs):
        for line in super().format_exception(*args, **kwargs):
            yield secret_keeper.filter_string(line)


class InterceptHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        opter = logger.opt(depth=depth, exception=record.exc_info)
        opter.log(level, record.getMessage())


@contextmanager
def logfuscator():
    core = logger._core
    old_exfmt, _logger.ExceptionFormatter = (
        _logger.ExceptionFormatter, SecretExceptionFormatter)
    old_patcher, core.patcher = core.patcher, secret_keeper.loguru_filter
    patcher = SecretExceptionFormatter.from_exception_formatter
    with core.lock:
        for h in core.handlers.copy().values():
            h._exception_formatter = patcher(h._exception_formatter)
    try:
        yield
    finally:
        core.patcher = old_patcher
        _logger.ExceptionFormatter = old_exfmt
        with core.lock:
            for h in core.handlers.copy().values():
                original = getattr(h, 'original_formatter', None)
                if original:
                    h._exception_formatter = original


def logfuscated(func):
    def inner(*args, **kwargs):
        with logfuscator():
            return func(*args, **kwargs)
    return inner
