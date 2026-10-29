"""ICAO airline prefix -> (display name, brand-ish colour). Unknown prefixes fall back to grey."""
AIRLINES = {
    "EZS": ("easyJet CH", (255, 110, 0)),
    "EZY": ("easyJet", (255, 110, 0)),
    "EJU": ("easyJet EU", (255, 110, 0)),
    "SWR": ("SWISS", (230, 0, 20)),
    "EDW": ("Edelweiss", (255, 255, 255)),
    "HLO": ("Helvetic", (200, 30, 60)),
    "AFR": ("Air France", (60, 90, 255)),
    "DLH": ("Lufthansa", (255, 190, 0)),
    "BAW": ("British Airways", (60, 90, 220)),
    "KLM": ("KLM", (0, 160, 230)),
    "AUA": ("Austrian", (230, 20, 30)),
    "BEL": ("Brussels", (220, 30, 60)),
    "IBE": ("Iberia", (230, 30, 30)),
    "VLG": ("Vueling", (255, 210, 0)),
    "RYR": ("Ryanair", (40, 80, 200)),
    "WZZ": ("Wizz Air", (200, 0, 120)),
    "TAP": ("TAP", (0, 180, 80)),
    "ITY": ("ITA Airways", (40, 90, 220)),
    "SAS": ("SAS", (40, 60, 160)),
    "FIN": ("Finnair", (80, 120, 255)),
    "LOT": ("LOT", (40, 80, 200)),
    "THY": ("Turkish", (230, 20, 30)),
    "PGT": ("Pegasus", (255, 200, 0)),
    "UAE": ("Emirates", (230, 20, 30)),
    "QTR": ("Qatar", (140, 30, 80)),
    "ETD": ("Etihad", (200, 160, 90)),
    "ELY": ("El Al", (40, 80, 200)),
    "AEE": ("Aegean", (40, 90, 200)),
    "TRA": ("Transavia", (0, 200, 120)),
    "TVF": ("Transavia FR", (0, 200, 120)),
    "EWG": ("Eurowings", (160, 0, 120)),
    "CFG": ("Condor", (255, 200, 0)),
    "UAL": ("United", (40, 80, 200)),
    "DAL": ("Delta", (200, 30, 50)),
    "AAL": ("American", (160, 160, 180)),
    "ACA": ("Air Canada", (230, 20, 30)),
    "CTN": ("Croatia", (40, 80, 200)),
    "ASL": ("Air Serbia", (40, 80, 200)),
    "RAM": ("Royal Air Maroc", (200, 30, 40)),
    "TUN": ("Tunisair", (230, 20, 30)),
    "DAH": ("Air Algerie", (220, 30, 40)),
    "MSR": ("EgyptAir", (40, 80, 200)),
    "SVA": ("Saudia", (0, 150, 90)),
    "CCA": ("Air China", (230, 20, 30)),
    "SIA": ("Singapore", (255, 180, 0)),
    "FDX": ("FedEx", (130, 40, 200)),
    "UPS": ("UPS", (160, 110, 40)),
    "DHK": ("DHL", (255, 200, 0)),
    "BCS": ("DHL", (255, 200, 0)),
    "SUI": ("Swiss Air Force", (230, 0, 20)),
    "REGA": ("Rega", (230, 0, 20)),
}
DEFAULT_COLOR = (170, 170, 170)


def airline(callsign: str) -> tuple[str | None, tuple[int, int, int]]:
    if callsign.startswith("HBZ") or callsign.startswith("SAREGA"):
        return AIRLINES["REGA"]
    prefix = callsign[:3]
    if prefix in AIRLINES and len(callsign) > 3 and callsign[3].isdigit():
        return AIRLINES[prefix]
    return None, DEFAULT_COLOR
