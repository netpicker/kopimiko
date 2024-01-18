from functools import partial
from typing import cast

from loguru import logger
from netmiko import ConnectHandler

from . import (
    FileTransferInfo, PlatformHandler, TransferCommand,
    FileTransferError, TransferMethods, ScrapeCommand,
)

scraper = ScrapeCommand(command='configuration show')

errors_replies = dict.fromkeys({
    'ERROR:.*',
}, FileTransferError)


transfer_prompts = {'password:': '{password}', 'yes/no': 'yes'}

# tftp syntax does not look like it makes sense but is really that way
# file tput <host> <remote-file> <local-file>
transfer_cmd = [
    TransferCommand(
        command='file scp config/startup-config {username}@{dst_ip}:/{dst_file}',
        prompts=transfer_prompts,
        proto='scp'
    ),
    TransferCommand(
        command='file tput {dst_ip} {dst_file} config/startup-config',
        proto='tftp'
    ),
]


class CienaSAOSPlatform(PlatformHandler):
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
        ch.send_command_timing('configuration save')
        logger.info("Saved configuration")
