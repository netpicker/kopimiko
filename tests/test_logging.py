import logging
import pytest
from loguru import logger

from kopimiko.utils.logs import (
    InterceptHandler, logfuscator, obfuscate, secret_keeper
)


@pytest.fixture
def loguscate():
    secret_keeper.add_secret('secret')
    with logfuscator():
        yield


@pytest.mark.parametrize('given, expected', [
    (None, None),
    ('', ''),
    ('a', '*'),
    ('aaa', '***'),
    ('aaaaaaa', '*******'),
    ('aaaaaaaa', 'aa****aa'),
    ('xxxxxxxxxx', 'xx******xx'),
    ('the_very_long_secret', 'th****************et')
])
def test_obfuscate(given, expected):
    assert obfuscate(given) == expected


def test_clear_test(caplog):
    logger.info('you can seen the secret')
    assert len(caplog.messages) == 1
    assert 'secret' in caplog.messages[0]


def test_obscate_guru(loguscate, caplog):
    logger.info('can you seen the secret now?')
    assert 'secret' not in caplog.messages[0]


def test_obfuscate_long_secret(loguscate, caplog):
    secret_keeper.add_secret('the_very_long_secret')
    logger.info('Xthe_very_long_secretX')
    assert caplog.messages[0] == 'Xth****************etX'


def test_obfuscate_catcher(loguscate, caplog):
    @logger.catch(reraise=True)
    def throw(msg):
        if msg:
            raise Exception(msg)

    with pytest.raises(Exception):
        msg = 'you should keep secrets all the time'
        throw(msg)
    assert 'secret' not in caplog.messages[0]


def test_classic_logging(loguscate, caplog):
    root_logger = logging.getLogger("")
    root_logger.handlers = [InterceptHandler()]
    root_logger.error('is this secret or what')
    assert 'secret' not in caplog.messages[0]
