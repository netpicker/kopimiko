from functools import partial
from typing import cast

from loguru import logger
from netmiko import ConnectHandler

from . import FileTransferInfo, PlatformHandler, TransferMethods
from ._cisco_base import scraper
from .. import FileTransferError
from ..comm import TransferCommand

errors_replies = dict.fromkeys({
    '%Error.*',
    'Invalid input detected',
    'No such file or directory',
    'Error opening',
    'Transfer failed',
    'Permission denied'
}, FileTransferError)


def validate_response(fti: FileTransferInfo, output: str):
    if 'bytes copied' in output:
        return True
    fti.fail('Transfer failed')


transfer_prompts = errors_replies | {
    'Address or name of remote host ': '',
    'Destination username ': '',
    'Destination ': '',
}

transfer_cmd = [
    TransferCommand(
        command='copy flash:/{src_file} '
                'scp://{username}:{password}@{dst_ip}:/{dst_file}',
        prompts=transfer_prompts,
        proto='scp'
    ),
    TransferCommand(
        command='copy flash:/{src_file} '
                'ftp://{username}:{password}@{dst_ip}:/{dst_file}',
        prompts=transfer_prompts,
        proto='ftp'
    ),
    TransferCommand(
        command='copy flash:/{src_file} '
                'tftp://{dst_ip}/{dst_file}',
        prompts=transfer_prompts,
        proto='tftp'
    ),
]


class CiscoPlatform(PlatformHandler):
    def transfer_methods(self, _: FileTransferInfo) -> TransferMethods:
        methods = [
            *(partial(self.command_transfer, cmd=tc) for tc in transfer_cmd),
            scraper.transfer,
        ]
        return cast(TransferMethods, methods)

    def persist_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        fti.src_volume = 'flash:'
        fti.src_file = 'startup-config'
        ch.send_command_timing('write memory')
        logger.info("Saved running-config to startup-config.")
