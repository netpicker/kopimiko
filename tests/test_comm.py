from io import StringIO
import re
from unittest.mock import patch

import pytest

from kopimiko import FileTransferError, FileTransferInfo
from kopimiko.comm import PromptCommand, ScrapeCommand, TransferCommand


def test_mock_connection(connection):
    with connection({'query': 'reply'}) as ch:
        assert ch.send_command('query') == 'reply'
        assert ch.send_command('queery') == 'ERROR'


def test_prompt_command_with_error(connection, fti):
    pc = PromptCommand(command='foo', prompts={'ERROR': FileTransferError})
    with connection({'cmd': 'data'}) as ch:
        with pytest.raises(FileTransferError):
            pc.exec_prompt_command(ch, fti)


def test_prompt_command_with_invalid(connection, fti):
    pc = PromptCommand(command='foo', validator=lambda fti, data: False)
    with connection({'foo': 'bar'}) as ch:
        assert pc.exec_prompt_command(ch, fti) is None


@pytest.mark.parametrize('prompts', [
    {('Q', re.compile('^really')): '{username}'},
    {'[Y/N]': 'Y'},
    {('si', 'no'): 'no', ('Y/N',): 'Y'},
    {re.compile(r'sure \['): 'Y'},
    {('Q', re.compile('^really')): 'Y'},
])
def test_prompt_command_dialogue(connection, prompts):
    pc = PromptCommand(
        command='copy',
        prompts=prompts,
    )
    prompt = 'really sure [Y/N]'
    fti = FileTransferInfo(username='Y')
    with connection({'copy': prompt, 'Y': 'DATA'}) as ch:
        assert pc.exec_prompt_command(ch, fti) == f"{prompt}DATA"


class Unclosable(StringIO):
    def close(self):
        ...


class MockFTI(FileTransferInfo):
    def check_destination(self):
        return True


def test_scrape_command(connection):
    sc = ScrapeCommand('cmd', ['bar', re.compile('ignore')])
    response = 'ignored\nfoo\nbar\n'
    with connection({'cmd': response}) as ch:
        dest = Unclosable()
        with patch('builtins.open', return_value=dest):
            sc.transfer(ch, MockFTI(dst_file='/tmp/x'))
        assert dest.getvalue() == 'foo\n'


def test_transfer_command_set_indirect_source():
    assert TransferCommand(command='save some_file').indirect_source is False
    assert TransferCommand(command='save {src_file}').indirect_source is True
