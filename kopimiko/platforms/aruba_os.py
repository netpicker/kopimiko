from functools import partial
from typing import cast

from loguru import logger
from netmiko import ConnectHandler

from . import FileTransferInfo, PlatformHandler, TransferMethods
from ..comm import ScrapeCommand, TransferCommand

scraper = ScrapeCommand(command='show config')


def validate_response(fti: FileTransferInfo, output: str):
    # TODO in both cases you do not get any response,
    # need to test on file existence / content instead
    if 'bytes copied' in output:
        return True
    fti.fail('Transfer failed')


# its first dst_file, then dst_path (if applicable) with ftp

transfer_prompts = {'Password': '{password}'}
transfer_cmd = [
    TransferCommand(
        command='copy flash: {dst_file} scp: {dst_ip} {username} {dst_file}',
        prompts=transfer_prompts,
        proto='scp'
    ),
    TransferCommand(
        command='copy running-config ftp: {dst_ip} {username} {dst_file}',
        prompts=transfer_prompts,
        proto='ftp'
    ),
    TransferCommand(
        command='copy running-config tftp: {dst_ip} {dst_file}',
        prompts=transfer_prompts,
        proto='tftp'
    ),
]


class ArubaOSPlatform(PlatformHandler):
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
        ch.send_command_timing("write memory")
        logger.info("Saved running-config to startup-config.")
        fti.src_file = fti.dst_file
        command = f"copy running-config flash: {fti.src_file}"
        ch.send_command_timing(command)
        logger.info(f"Copied running-config to flash:/{fti.src_file}")

    def remove_persisted_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        ch.send_command_timing(f"delete filename {fti.src_file}")
        logger.info("Cleaned temp file from networkdevice storage.")
