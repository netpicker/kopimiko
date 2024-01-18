from functools import partial
from typing import cast
from unittest.mock import patch

import pytest

from kopimiko.comm import TransferCommand
from kopimiko.platforms import (
    PlatformHandler, TransferMethod, TransferMethods,
    get_platform_handler_class
)

from kopimiko.file_transfer import (
    FileTransferError, FileTransferInfo,
    ProtoTransferParam, SimpleTransferSpec
)


scp_chat = {"copy flash:/config scp://localhost:/config.cfg": 'content'}


@pytest.fixture
def sts():
    ptp = ProtoTransferParam(dst_ip='localhost')
    sts = SimpleTransferSpec({'scp': ptp})
    return sts


class MockFti(FileTransferInfo):
    def prepare_destination(self, netmiko_kw=None):
        self.src_file = 'config'
        self.src_volume = 'flash:'
        self.dst_file = 'config.cfg'
        self.dst_ip = 'localhost'

    def check_destination(self):
        return self.dst_file


class MockHandler(PlatformHandler):
    proto_copy_templates = {'scp': 'scp this to that'}

    cmd = TransferCommand(command='transfer', proto='scp', prompts={})

    def transfer_methods(self, fti: FileTransferInfo) -> TransferMethods:
        return cast(TransferMethod, partial(self.command_transfer, cmd=self.cmd)),


def test_send_command(platform_handler):
    ph = PlatformHandler()
    with platform_handler({'query': 'reply'}):
        assert ph.send_command('query') == 'reply'


def test_transfer_none(caplog):
    fti = FileTransferInfo()
    PlatformHandler().file_transfer(None, fti)
    assert caplog.records[-1].levelname == 'WARNING'


def test_transfer_scp(platform_handler, sts):
    ph = MockHandler(proto_transfer_spec=sts, fti_class=MockFti)
    config = 'config.cfg'
    fti = MockFti(
        src_file='config', src_volume='flash:',
        dst_file='config', dst_ip='localhost')
    with platform_handler(scp_chat):
        with patch.object(fti, 'check_destination', return_value=config):
            ch = ph.get_ssh_handler()
            saved = ph.file_transfer(ch, fti)
            assert saved == config

            with ph.get_configuration() as dest:
                assert dest == config


def test_get_config_two_methods(platform_handler, sts):
    cmd = TransferCommand(command='transfer', proto='scp', prompts={})

    def failing_method(ch, fti):
        fti.fail()

    def double_methods(self, fti):
        method = partial(self.command_transfer, cmd=cmd)
        return failing_method, method

    ph = MockHandler(proto_transfer_spec=sts, fti_class=MockFti)
    fti = MockFti()
    fti.prepare_destination()
    config = 'config.cfg'
    with platform_handler(scp_chat):
        with (
            patch.object(fti, 'check_destination', return_value=config),
            patch(f"{__name__}.MockHandler.transfer_methods", double_methods),
            patch('kopimiko.platforms.reset_channel') as chr
        ):
            ch = ph.get_ssh_handler()
            assert ph.file_transfer(ch, fti) is not None
            chr.assert_called()


def test_proto_transfer(platform_handler, sts, fti):
    fti.prepare_destination({})
    cmd = TransferCommand(command='transfer', proto='scp', prompts={})
    with platform_handler({}):
        with (
            patch.object(MockHandler, 'setup_proto_transfer', return_value=0),
            patch.object(MockHandler, 'persist_configuration') as persister,
        ):
            ph = MockHandler()
            ch = ph.get_ssh_handler()
            assert ph.command_transfer(ch, fti, cmd) is None
            persister.assert_not_called()

        ph = MockHandler(proto_transfer_spec=sts)
        with patch('kopimiko.comm.PromptCommand.validate_response',
                   return_value=None):
            with pytest.raises(FileTransferError):
                ph.command_transfer(ch, fti, cmd)


def test_command_transfer_no_proto_specs(platform_handler, fti):
    with platform_handler({}):
        ph = MockHandler()
        tc = TransferCommand(command='', proto='proto')
        with patch.object(tc, 'exec_prompt_command') as epc:
            ph.command_transfer(None, fti, tc)
        epc.assert_not_called()


@pytest.mark.parametrize('was_persisted', [False, True])
def test_command_transfer_calls_persist_config(platform_handler, fti, sts, was_persisted):
    fti.prepare_destination({})
    fti.persisted = was_persisted
    with platform_handler({}):
        ph = MockHandler(proto_transfer_spec=sts)
        tc = TransferCommand(command='copy {src_file} to...', proto='scp')
        with (
            patch.object(ph, 'persist_configuration') as persister,
            patch.object(tc, 'exec_prompt_command'),
            patch.object(fti, 'check_destination', return_value=True)
        ):
            ph.command_transfer(None, fti, tc)
        if was_persisted:
            persister.assert_not_called()
        else:
            persister.assert_called()


def test_get_platform_handler_class():
    cisco_ios = get_platform_handler_class('cisco_ios')
    assert issubclass(cisco_ios, PlatformHandler)

    assert get_platform_handler_class('no no') is PlatformHandler
