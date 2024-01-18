import re

from functools import partial
from typing import cast

from netmiko import ConnectHandler

from . import (
    FileTransferInfo, PlatformHandler, PromptCommand, TransferMethods
)
from .. import FileTransferError
from ..comm import ScrapeCommand, TransferCommand

saved = r"\sNext\smain\sstartup\ssaved-configuration\sfile:\s(?P<filename>.+)$"
re_saved = re.compile(saved, re.MULTILINE)

scraper = ScrapeCommand(command='display current-configuration')

transfer_cmd = [
    TransferCommand(
        command='scp {dst_ip} put {src_file} {dst_file}',
        proto='scp',
        prompts={
            'Username:': '{username}',
            'The server is not authenticated': 'y',
            'Do you want to save the server public key': 'n',
            'password:': '{password}',
        }
    ),
    TransferCommand(
        command='ftp {dst_ip}',
        proto='ftp',
        prompts={
            'User': '{username}',
            'Password': '{password}',
            'mode to transfer files': 'put {src_file} {dst_file}',
            'ftp>': 'quit',
        }
    ),
    TransferCommand(
        command='tftp {dst_ip} put {src_file} {dst_file}',
        proto='tftp',
        prompts={
            'Address or name of remote host ': '',
            'Destination ': '',
        }
    ),
]


class HpComWarePlatform(PlatformHandler):
    def persist_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        # the destination file name has to be extracted implicitly
        prompts = {'[Y/N]': 'Y', 'unchanged': ''}
        PromptCommand.exec(ch, fti, 'save main', prompts=prompts)

        output = ch.send_command_timing('display startup')
        match = re.search(re_saved, output)
        if match is None:
            raise FileTransferError('cannot determine src_file')
        fti.src_file = match.groupdict()['filename']

    def transfer_methods(self, _: FileTransferInfo) -> TransferMethods:
        methods = [
            *(partial(self.command_transfer, cmd=tc) for tc in transfer_cmd),
            scraper.transfer,
        ]
        return cast(TransferMethods, methods)
