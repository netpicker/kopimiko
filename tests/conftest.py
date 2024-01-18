from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from netmiko import BaseConnection, ConnectHandler

from kopimiko import FileTransferInfo
from kopimiko.platforms import CTRL_C


NBC = 'netmiko.base_connection.BaseConnection'


class MockChannel:
    def __init__(self, use_echo: bool, dialogue: dict[str, str]):
        self.use_echo = use_echo
        self.dialogue = dialogue
        self.response = ''
        self.prompt = '#'

    def read_channel(self):
        response, self.response = self.response, None
        result = f"{response}\n{self.prompt}" if response is not None else ''
        return result

    def write_channel(self, data: str):
        if data == '' or data == CTRL_C:
            self.response = ''
            return

        challenge = data.rstrip()
        response = self.dialogue.get(challenge, 'ERROR')
        if self.use_echo:
            response = f"{data}{response}"
        self.response = response


@pytest.fixture
def connection():
    @contextmanager
    def inner(responses: dict[str, str], ch: ConnectHandler = None):
        def open_channel(self):
            self.channel = MockChannel(self.global_cmd_verify, responses)

        with patch(f"{NBC}._open", open_channel):
            with patch('time.sleep', float):
                conn = ch or BaseConnection(host='localhost')
                conn.global_cmd_verify = False
                yield conn
    return inner


@dataclass
class CFTI(FileTransferInfo):
    def __post_init__(self):
        self.__dict__.update(dict(
            persisted=True,
            src_file='startup-conf',
            dst_file='/tmp/config-file',
            dst_ip='1.2.3.4',
            username='usr',
            password='Hera!D0.',
            src_volume='flash:',
        ))


@pytest.fixture
def fti():
    return CFTI()
