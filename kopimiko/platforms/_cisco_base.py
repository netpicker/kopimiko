import re

from kopimiko.comm import ScrapeCommand


scraper = ScrapeCommand(
    command='show running-config',
    ignore_patterns=[re.compile(r'Building\sconfiguration')]
)
