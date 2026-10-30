"""Airline / operator names and colours, aircraft type names and the aircraft groups.

AIRLINES: hand-picked display names and brand colours. Everything else comes from
data/airlines.csv, the VRS standing-data airline list (CC0, ~6000 airlines,
github.com/vradarserver/standing-data), shown in the default colour."""
import csv
from pathlib import Path
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
    "NJE": ("NetJets", (200, 200, 210)), "VJT": ("VistaJet", (230, 30, 40)),
}
DEFAULT_COLOR = (170, 170, 170)


def _load_vrs() -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "data" / "airlines.csv"
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return [r for r in csv.DictReader(f) if r.get("ICAO")]
    except OSError:
        return []


_VRS = _load_vrs()
VRS_AIRLINES = {r["ICAO"]: r["Name"] for r in _VRS if r.get("Name")}
VRS_IATA = {r["ICAO"]: r["IATA"] for r in _VRS if r.get("IATA")}


def short_callsign(callsign: str) -> str:
    """KLM591 -> KL591 (airline ICAO prefix replaced by its 2-character IATA code). For numeric
    callsigns this is usually the published flight number; alphanumeric ones (EWG3HP -> EW3HP)
    are just shorter. Anything else is returned unchanged."""
    iata = airline_iata(callsign)
    if iata and len(iata) == 2 and iata.isalnum():
        return iata + callsign[3:]
    return callsign


def airline_iata(callsign: str) -> str | None:
    """IATA code of the airline behind an airline-style callsign (for its logo)."""
    if len(callsign) > 3 and callsign[:3].isalpha() and callsign[3].isdigit():
        return VRS_IATA.get(callsign[:3])
    return None


# Common business, general-aviation and helicopter types (ICAO type designator -> name)
TYPES = {
    "EC35": "Airbus H135", "EC45": "Airbus H145", "BK17": "Airbus H145", "EC30": "Airbus H130",
    "AS50": "Ecureuil", "AS55": "Ecureuil 2", "AS65": "Dauphin", "EC55": "Airbus H155", "EC75": "Airbus H175",
    "A109": "AW109", "A119": "AW119", "A139": "AW139", "A169": "AW169", "B06": "Bell 206", "B407": "Bell 407",
    "B429": "Bell 429", "B505": "Bell 505", "AS32": "Super Puma", "AS3B": "Cougar", "EC25": "Airbus H225",
    "NH90": "NH90", "H160": "Airbus H160", "A149": "AW149", "A189": "AW189", "R22": "Robinson R22", "R44": "Robinson R44", "R66": "Robinson R66", "S76": "Sikorsky S-76",
    "PC12": "Pilatus PC-12", "PC24": "Pilatus PC-24", "PC6T": "Pilatus Porter", "PC21": "Pilatus PC-21",
    "PC7": "Pilatus PC-7", "TBM7": "TBM 700", "TBM8": "TBM 850", "TBM9": "TBM 900", "C208": "Cessna Caravan",
    "C172": "Cessna 172", "C182": "Cessna 182", "C510": "Citation Mustang", "C525": "CitationJet",
    "C25A": "Citation CJ2", "C25B": "Citation CJ3", "C25C": "Citation CJ4", "C56X": "Citation Excel",
    "C68A": "Citation Latitude", "C700": "Citation Longitude", "E50P": "Phenom 100", "E55P": "Phenom 300",
    "E545": "Praetor 500", "E550": "Praetor 600", "LJ45": "Learjet 45", "LJ75": "Learjet 75",
    "CL30": "Challenger 300", "CL35": "Challenger 350", "CL60": "Challenger 600", "GL5T": "Global 5000",
    "GLEX": "Global Express", "GL7T": "Global 7500", "G280": "Gulfstream G280", "GLF4": "Gulfstream IV",
    "GLF5": "Gulfstream V", "GLF6": "Gulfstream G650", "GA6C": "Gulfstream G600", "FA50": "Falcon 50",
    "FA7X": "Falcon 7X", "FA8X": "Falcon 8X", "F900": "Falcon 900", "F2TH": "Falcon 2000",
    "HDJT": "HondaJet", "SF50": "Cirrus Vision Jet", "SR22": "Cirrus SR22", "SR20": "Cirrus SR20",
    "DA40": "Diamond DA40", "DA42": "Diamond DA42", "DA62": "Diamond DA62", "P28A": "Piper Cherokee",
    "PA46": "Piper Malibu", "BE20": "King Air 200", "BE9L": "King Air 90", "B350": "King Air 350",
    "P180": "Piaggio Avanti", "DHC6": "Twin Otter",
}
# Airliner ICAO type designators -> the usual short names (for the type/registration line)
AIRLINER_TYPES = {
    "A19N": "A319neo", "A20N": "A320neo", "A21N": "A321neo", "A318": "A318", "A319": "A319",
    "A320": "A320", "A321": "A321", "A332": "A330-200", "A333": "A330-300", "A338": "A330-800",
    "A339": "A330-900", "A343": "A340-300", "A346": "A340-600", "A359": "A350-900", "A35K": "A350-1000",
    "A388": "A380", "BCS1": "A220-100", "BCS3": "A220-300", "B733": "737-300", "B734": "737-400",
    "B737": "737-700", "B738": "737-800", "B739": "737-900", "B37M": "737 MAX 7", "B38M": "737 MAX 8",
    "B39M": "737 MAX 9", "B3XM": "737 MAX 10", "B744": "747-400", "B748": "747-8", "B752": "757-200",
    "B763": "767-300", "B764": "767-400", "B772": "777-200", "B77L": "777-200LR", "B77W": "777-300ER",
    "B778": "777-8", "B779": "777-9", "B788": "787-8", "B789": "787-9", "B78X": "787-10",
    "E170": "E170", "E175": "E175", "E190": "E190", "E195": "E195", "E290": "E190-E2", "E295": "E195-E2",
    "CRJ7": "CRJ-700", "CRJ9": "CRJ-900", "CRJX": "CRJ-1000", "DH8D": "Dash 8-400", "AT45": "ATR 42-500",
    "AT46": "ATR 42-600", "AT75": "ATR 72-500", "AT76": "ATR 72-600", "SB20": "Saab 2000",
    "SU95": "Superjet 100", "C919": "C919",
}


def short_type(t: str | None) -> str:
    return AIRLINER_TYPES.get(t or "", t or "")


# ADS-B emitter category -> label, for aircraft we know nothing else about
CATEGORIES = {"A1": "Light aircraft", "A2": "Small aircraft", "A7": "Helicopter", "B1": "Glider",
              "B2": "Balloon", "B4": "Ultralight", "B6": "Drone"}
OPERATORS = {  # callsign prefix -> (name, colour), for non-airline operators
    "RGA": ("Rega", (230, 0, 20)), "SAZ": ("Rega", (230, 0, 20)),
    "CEF": ("Czech Air Force", (120, 160, 90)), "SUI": ("Swiss Air Force", (230, 0, 20)),
}
HELI_COLOR, GA_COLOR = (255, 120, 80), (120, 200, 255)

HELI_TYPES = {"EC35", "EC45", "BK17", "EC30", "AS50", "AS55", "AS65", "EC55", "EC75", "A109", "A119", "A139",
              "A169", "B06", "B407", "B429", "R22", "R44", "R66", "S76", "AS32", "AS3B", "EC25", "NH90",
              "B505", "H160", "EC20", "AS35", "MI8", "H64", "UH1", "A149", "A189"}
LIGHT_TYPES = {"C172", "C182", "SR20", "SR22", "DA40", "DA42", "DA62", "P28A", "PA46", "PC6T", "PC7", "PC21"}
BUSINESS_TYPES = {"PC12", "PC24", "TBM7", "TBM8", "TBM9", "C208", "C510", "C525", "C25A", "C25B", "C25C",
                  "C56X", "C68A", "C700", "E50P", "E55P", "E545", "E550", "LJ45", "LJ75", "CL30", "CL35",
                  "CL60", "GL5T", "GLEX", "GL7T", "G280", "GLF4", "GLF5", "GLF6", "GA6C", "FA50", "FA7X",
                  "FA8X", "F900", "F2TH", "HDJT", "SF50", "BE20", "BE9L", "B350", "P180", "DHC6"}
BUSINESS_OPERATORS = {"NJE", "VJT"}


def aircraft_group(a: dict) -> str:
    """'heli', 'light', 'business' (business jets, private flights) or 'airliners'.
    Category first (what the transponder says), then the type, then the callsign: airline-style
    callsigns (3 letters + digit) are airliners unless the operator or type is a business one;
    registration-style callsigns (HBZZX, N81YY) are private."""
    cat, t, cs = a.get("category", ""), a.get("t", ""), a.get("callsign", "")
    if cat == "A7" or t in HELI_TYPES:
        return "heli"
    if cat in ("A1", "B1", "B2", "B4", "B6") or t in LIGHT_TYPES:
        return "light"
    if cs[:3] in BUSINESS_OPERATORS or t in BUSINESS_TYPES:
        return "business"
    if len(cs) > 3 and cs[:3].isalpha() and cs[3].isdigit():
        return "airliners"
    return "business"


def describe(a: dict) -> tuple[str, tuple[int, int, int]]:
    """Top-line name for an aircraft: airline, else known operator, else type in words, else
    the broadcast category, else the registration."""
    cs = a.get("callsign", "")
    name, color = airline(cs)
    if name:
        return name, color
    for prefix, op in OPERATORS.items():
        if cs.startswith(prefix):
            return op
    cat = a.get("category", "")
    color = HELI_COLOR if cat == "A7" else GA_COLOR if cat in ("A1", "A2", "B1", "B4") else DEFAULT_COLOR
    if a.get("t") in TYPES:
        return TYPES[a["t"]], color
    if cat in CATEGORIES:
        return CATEGORIES[cat], color
    return a.get("t") or a.get("r") or "", DEFAULT_COLOR


def airline(callsign: str) -> tuple[str | None, tuple[int, int, int]]:
    """Airline for an airline-style callsign (3 letters + digit): our styled entry, else the
    VRS airline list in the default colour."""
    prefix = callsign[:3]
    if len(callsign) > 3 and prefix.isalpha() and callsign[3].isdigit():
        if prefix in AIRLINES:
            return AIRLINES[prefix]
        if prefix in VRS_AIRLINES:
            return VRS_AIRLINES[prefix], DEFAULT_COLOR
    return None, DEFAULT_COLOR
