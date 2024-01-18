import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Callable, Collection, Optional, Sequence, TextIO, Union

from loguru import logger
from netmiko import ConnectHandler

from .file_transfer import FileTransferInfo


Prompt = Callable[[str], str] | Exception | type[Exception]
Prompts = dict[str | Collection[str], str | Prompt]
MatchedValue = str | Exception | type[Exception]


class PromptMatcher:
    def __init__(self, fti: FileTransferInfo, prompts: Prompts):
        self.fti = fti
        self.prompts = prompts

    @staticmethod
    def _get_value(prompt: str, v: Prompt) -> MatchedValue:
        if isinstance(v, Exception):
            raise v
        if isinstance(v, type) and issubclass(v, Exception):
            raise v(prompt)
        return v()

    def _find(self, prompt, k, v):
        match = False
        if isinstance(k, re.Pattern):
            match = k.search(prompt)
        elif isinstance(k, str):
            match = k in prompt
        if match:
            logger.info(f"== `{k}` found in `{repr(prompt)}`")
            answer = self._get_value(prompt, v) if callable(v) else v
            if self.fti:
                answer = self.fti.format(answer)
            return answer

    def get_answer(self, prompt: str) -> str | None:
        for keys, v in self.prompts.items():
            if isinstance(keys, (str, re.Pattern)):
                if (answer := self._find(prompt, keys, v)) is not None:
                    return answer
            else:
                for k in keys:
                    if (answer := self._find(prompt, k, v)) is not None:
                        return answer
        return None


@dataclass
class PromptCommand:
    command: str
    proto: str = ''
    prompts: Prompts | None = None
    validator: Callable[[FileTransferInfo, str], str] = None

    def validate_response(self, fti: FileTransferInfo, response):
        valid = not callable(self.validator) or self.validator(fti, response)
        return valid

    def exec_prompt_command(
            self,
            connection: ConnectHandler,
            fti: FileTransferInfo
    ) -> Optional[str]:
        command = fti.format(self.command)
        logger.info(f">> {command}")
        reply = connection.send_command_timing(command)
        logger.info(f"<< {repr(reply)}")
        output = reply
        matcher = PromptMatcher(fti, self.prompts or {})
        while reply:
            answer, reply = matcher.get_answer(reply), None
            if answer is not None:
                logger.info(f">> {repr(answer)}")
                reply = connection.send_command_timing(answer)
                logger.info(f"<< {reply}")
                output += reply
        logger.info(f'output from `{self.command}`: {repr(output)}')
        valid = self.validate_response(fti, output)
        return output if valid else None

    @classmethod
    def exec(
            cls,
            ch: ConnectHandler,
            fti: FileTransferInfo,
            command: str,
            prompts: Prompts | None,
            **kwargs
    ):
        cmd = cls(command=command, prompts=prompts, **kwargs)
        return cmd.exec_prompt_command(ch, fti)


@dataclass
class TransferCommand(PromptCommand):
    indirect_source: bool = False

    def __post_init__(self):
        if '{src_file}' in self.command or '{src_volume}' in self.command:
            self.indirect_source = True


@dataclass
class ScrapeCommand:
    command: str
    ignore_patterns: Optional[Sequence[Union[str, re.Pattern]]] = None

    def is_ignored_line(self, line):
        for ignore in self.ignore_patterns:
            if isinstance(ignore, str):
                if ignore in line:
                    return True
            else:
                return re.search(ignore, line)

    def save_filtered_config(
            self,
            file: Union[str, Path, int, TextIO],
            content: str,
    ):
        counter = 0
        with StringIO(content) as source:
            with open(file, 'w') as dest:
                for source_line in source:
                    line = source_line.strip()
                    if self.ignore_patterns and self.is_ignored_line(line):
                        counter += 1
                    else:
                        dest.write(source_line)
        logger.info(f"{counter} matching lines have been deleted.")

    def transfer(
        self,
        ch: ConnectHandler,
        fti: FileTransferInfo,
    ):
        local_file = fti.destination_filename
        Path(local_file).unlink(missing_ok=True)
        response = ch.send_command(self.command)
        self.save_filtered_config(local_file, response)
        result = fti.check_destination()
        logger.info("File transferred using scraping")
        return result
