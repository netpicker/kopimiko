import os
from dataclasses import asdict, dataclass
from typing import Callable, Optional
from uuid import uuid4

from netmiko import log as netmiko_log

from .utils.logs import secret_keeper


class FileTransferError(Exception):
    pass


netmiko_log.addFilter(secret_keeper)


@dataclass
class ProtoTransferParam:
    dst_ip: str = None
    dst_volume: str = None
    username: str = None
    password: str = None


ProtoTransferSpec = Callable[[str], Optional[ProtoTransferParam]]
ProtoTransferParams = dict[str, ProtoTransferParam]


class SimpleTransferSpec:
    def __init__(self, ptp: ProtoTransferParams):
        self.ptp = ptp

    def __call__(self, proto: str) -> Optional[ProtoTransferParam]:
        return self.ptp.get(proto)


@dataclass
class FileTransferInfo(ProtoTransferParam):
    persisted: bool = False
    src_file: str = None
    dst_file: str = None
    src_ip: str = None
    src_volume: str = None

    def __post_init__(self):
        secret_keeper.add_secret(self.password)

    dict = asdict

    def prepare_destination(self, netmiko_kw):
        base = netmiko_kw.get('host') or netmiko_kw.get('ip') or 'config'
        self.dst_file = f"{base}-{uuid4()}.cfg"

    @property
    def credentials(self):
        usr, pwd = self.username, self.password
        if not usr:
            return ''
        auth = ':'.join(filter(lambda n: n is not None, (usr, pwd)))
        return f"{auth}@"

    def destination(self, use_credentials: bool, host_sep: str = '') -> str:
        credentials = self.credentials if use_credentials else ''
        glue = {False: '/', True: ''}[self.dst_file.startswith('/')]
        dst = f"{credentials}{self.dst_ip}{host_sep}{glue}{self.dst_file}"
        return dst

    def format(self, fmt_str: str) -> str:
        return fmt_str.format(**asdict(self))

    @property
    def destination_filename(self):
        result = os.path.join(self.dst_volume or '', self.dst_file)
        return result

    def check_destination(self):
        target = self.destination_filename
        if os.path.isfile(target) is False:
            raise FileTransferError(f"{self.dst_file} not found")
        if os.path.getsize(target) == 0:
            raise FileTransferError(f"{self.dst_file} is empty")
        return target

    def fail(self, msg: str = None):
        msg = msg or 'File transfer failure'
        raise FileTransferError(f"{msg} for {self}")
