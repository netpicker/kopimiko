from functools import partial
from typing import cast

from loguru import logger
from netmiko import ConnectHandler

from . import (
    FileTransferInfo, PlatformHandler, PromptCommand,
    TransferCommand, TransferMethods,
)
from ._cisco_base import scraper

import re
dest_file = {re.compile(r'Destination file\s??name'): ''}

remote_addr = {'Address or name of remote host ': ''}
remote_ip = {'Host name or ip address': ''}
dest_user = {'Destination username ': ''}
overwrite = {'Do you want to over write': ''}
password = {'Password': '{password}'}
passcode = {'passcode': '{password}'}
overwrite_explicit = {'Overwrite {dest_file} on {dst_ip}': 'yes'}
remote_ip_explicit = {'Host name or ip address': '{dst_ip}'}
dest_user_explicit = {'Destination username': '{username}'}
dest_pass_explicit = {'Destination password': '{password}'}

secure_prompts = password | passcode | remote_addr | remote_ip | dest_file
remote_prompts = remote_addr | dest_file
ftp_explicit = remote_ip_explicit | dest_user_explicit | dest_pass_explicit


def validate_response(fti: FileTransferInfo, output: str):
    if 'bytes copied' in output:
        return True
    fti.fail('Transfer failed')


transfer_cmd = [
    TransferCommand(
        command='scp disk0:/{src_file} {username}@{dst_ip}:{dst_file}',
        prompts=secure_prompts | dest_user | overwrite,
        proto='scp'
    ),
    TransferCommand(
        command='sftp disk0:/{src_file} {username}@{dst_ip}:{dst_file}',
        prompts=secure_prompts | overwrite_explicit | overwrite,
        proto='sftp'
    ),
    TransferCommand(
        command='copy disk0:/{src_file} ftp://{username}@{dst_ip}:/{dst_file}',
        prompts=remote_prompts | ftp_explicit | overwrite | password,
        proto='ftp'
    ),
    TransferCommand(
        command='copy disk0:/{src_file} tftp://{dst_ip}:/{dst_file}',
        prompts=remote_prompts | remote_ip_explicit,
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
        fti.src_file = fti.dst_file
        command = 'copy running-config disk0:/{src_file}'
        PromptCommand.exec(ch, fti, command, dest_file)
        logger.info("Copied running-config to flash.")

    def remove_persisted_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        command = 'delete disk0:/{src_file}'
        PromptCommand.exec(ch, fti, command, {'confirm': ''})
        logger.info("Cleaned temp file from networkdevice storage.")
