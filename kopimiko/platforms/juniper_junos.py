from typing import cast

from kopimiko import FileTransferInfo
from kopimiko.comm import ScrapeCommand
from kopimiko.platforms import PlatformHandler, TransferMethods


scraper = ScrapeCommand(command='show configuration')


class CiscoPlatform(PlatformHandler):
    def transfer_methods(self, _: FileTransferInfo) -> TransferMethods:
        methods = [
            # TODO: *(partial(self.command_transfer, cmd=tc) for tc in transfer_cmd),
            scraper.transfer,
        ]
        return cast(TransferMethods, methods)
