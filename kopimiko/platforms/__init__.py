import importlib
import inspect
import os
from contextlib import contextmanager, suppress
from dataclasses import asdict
import time
from typing import (
    Any, Callable, Iterator, Optional, Sequence, Tuple, Type, cast
)

from loguru import logger
from netmiko import ConnectHandler, NetmikoBaseException

from ..comm import PromptCommand, Prompts, ScrapeCommand, TransferCommand  # noqa
from ..file_transfer import (
    FileTransferError, FileTransferInfo, ProtoTransferSpec
)
from ..utils.logs import secret_keeper

CTRL_C = '\x03'

TransferMethod = Callable[[ConnectHandler, FileTransferInfo], Any]
TransferMethods = Sequence[TransferMethod]
TransferResult = dict[str, bool]
RemoteTransferParamSetter = Callable[[FileTransferInfo, str], None]


def reset_channel(ch):
    ch.write_channel(CTRL_C)
    time.sleep(0.25)


class PlatformHandler:
    proto_copy_templates = None

    def __init__(
            self,
            fti_class: Type[FileTransferInfo] = None,
            proto_transfer_spec: ProtoTransferSpec = None,
            **netmiko_connection_kwargs
    ):
        self.fti_class = fti_class or FileTransferInfo
        self.proto_transfer_spec = proto_transfer_spec
        self.netmiko_kw = netmiko_connection_kwargs
        secret_keeper.add_secret(netmiko_connection_kwargs.get('password'))

    def get_ssh_handler(self, enabled: bool = False, **kw) -> ConnectHandler:
        kwargs = self.netmiko_kw.copy()
        kwargs.update(kw)
        handler = ConnectHandler(**kwargs)
        if enabled and not handler.check_enable_mode():
            handler.enable()
        return handler

    def send_command(self, command: str) -> str:
        with self.get_ssh_handler() as ch:
            # TODO: investigate how to handle exceptions
            result = ch.send_command(command)
            logger.info(f'cmd {self} {command} -> {result}')
            return result

    def __str__(self):
        return f"{self.__class__.__name__} for {self.netmiko_kw}"

    def setup_proto_transfer(
            self,
            proto: str,
            fti: FileTransferInfo
    ) -> Optional[bool]:
        if callable(self.proto_transfer_spec):
            spec = self.proto_transfer_spec(proto)
            if spec:
                fti.__dict__.update(asdict(spec))
                return True
        return None

    def command_transfer(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo,
            cmd: TransferCommand
    ) -> Optional[str]:
        """
        Transfer file from the device via supported transfer protocols.

        It will first create a config copy by calling persist_configuration
        if it has not been created.

        :param ch: opened netmiko ConnectHandler
        :param fti: file transfer information
        :param cmd: command to execute to transfer the file
        :return: destination file when success, None otherwise
        """
        if not self.setup_proto_transfer(cmd.proto, fti):
            return None
        if not fti.persisted and cmd.indirect_source:
            self.persist_configuration(ch, fti)
            fti.persisted = True
        output = cmd.exec_prompt_command(ch, fti)
        if output is None:
            raise fti.fail()
        if output is not None:
            return fti.check_destination()
        return None

    def transfer_methods(self, fti: FileTransferInfo) -> TransferMethods:
        """
        Provide a list of callables which the device can be interrogated by
        :param fti: file transfer information
        :return: list of TransferMethod callables
        """
        return []

    def file_transfer(self, ch: ConnectHandler, fti: FileTransferInfo):
        for transfer in self.transfer_methods(fti):
            with suppress(FileTransferError, NetmikoBaseException):
                return transfer(ch, fti)
            reset_channel(ch)
        logger.warning('Could not obtain configuration')
        return None

    def persist_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        ...

    def remove_persisted_configuration(
            self,
            ch: ConnectHandler,
            fti: FileTransferInfo
    ) -> None:
        ...

    @contextmanager
    def get_configuration(self) -> Iterator[str]:
        fti = self.fti_class()
        fti.prepare_destination(self.netmiko_kw)
        with self.get_ssh_handler() as ch:
            config_file = self.file_transfer(ch, fti)
            try:
                yield config_file
            finally:
                if fti.persisted:
                    with suppress(Exception):
                        self.remove_persisted_configuration(ch, fti)
                if config_file is not None and os.path.exists(config_file):
                    with suppress(Exception):
                        os.unlink(config_file)


def is_platform_class(obj):
    return (
        inspect.isclass(obj)
        and issubclass(obj, PlatformHandler)
        and obj is not PlatformHandler
    )


PlatformClasses = list[Tuple[str, Type[PlatformHandler]]]


def get_platform_handler_class(platform: str) -> Type[PlatformHandler]:
    module_name = f"{__name__}.{platform}"
    try:
        mod = importlib.import_module(module_name)
    except ModuleNotFoundError:
        classes = None
    else:
        platform_classes = inspect.getmembers(mod, is_platform_class)
        classes = cast(PlatformClasses, platform_classes)
    if classes:
        return classes[-1][-1]
    logger.warning(f"platform `{platform}` not found, falling back to generic")
    return PlatformHandler
