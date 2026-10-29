import asyncio
import json
import logging
import urllib.request

UA = "ledwall/0.1 (home LED display)"


class Poller:
    """Base for data sources: refresh() in a thread every `interval` s; set_interval() applies live."""
    name = "source"

    def __init__(self, interval: float):
        self.interval = interval
        self._wake = asyncio.Event()

    def set_interval(self, seconds: float):
        if seconds != self.interval:
            self.interval = seconds
            self._wake.set()  # re-fetch now and continue on the new schedule

    def refresh(self):
        raise NotImplementedError

    async def run(self):
        log = logging.getLogger(type(self).__module__)
        while True:
            self._wake.clear()
            try:
                await asyncio.to_thread(self.refresh)
                delay = self.interval
            except Exception as e:
                log.warning("%s fetch failed: %s", self.name, e)
                delay = min(60, self.interval)
            try:
                await asyncio.wait_for(self._wake.wait(), delay)
            except asyncio.TimeoutError:
                pass


def fetch_json(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
