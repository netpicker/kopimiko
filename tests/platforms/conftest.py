from contextlib import contextmanager
from unittest.mock import patch

import pytest


BPP = 'kopimiko.platforms.PlatformHandler'


@pytest.fixture
def platform_handler(connection):
    @contextmanager
    def inner(*args, **kwargs):
        with connection(*args, **kwargs) as conn:
            with patch(f"{BPP}.get_ssh_handler", return_value=conn):
                yield
    yield inner
