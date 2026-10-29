import json
import urllib.request

UA = "ledwall/0.1 (home LED display)"


def fetch_json(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
