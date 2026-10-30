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
    "NJE": ("NetJets", (200, 200, 210)), "VJT": ("VistaJet", (230, 30, 40)),
}
DEFAULT_COLOR = (170, 170, 170)


# Common business, general-aviation and helicopter types (ICAO type designator -> name)
TYPES = {
    "EC35": "Airbus H135", "EC45": "Airbus H145", "BK17": "Airbus H145", "EC30": "Airbus H130",
    "AS50": "Ecureuil", "AS55": "Ecureuil 2", "AS65": "Dauphin", "EC55": "Airbus H155", "EC75": "Airbus H175",
    "A109": "AW109", "A119": "AW119", "A139": "AW139", "A169": "AW169", "B06": "Bell 206", "B407": "Bell 407",
    "B429": "Bell 429", "R22": "Robinson R22", "R44": "Robinson R44", "R66": "Robinson R66", "S76": "Sikorsky S-76",
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
# ADS-B emitter category -> label, for aircraft we know nothing else about
CATEGORIES = {"A1": "Light aircraft", "A2": "Small aircraft", "A7": "Helicopter", "B1": "Glider",
              "B2": "Balloon", "B4": "Ultralight", "B6": "Drone"}
OPERATORS = {  # callsign prefix -> (name, colour), for non-airline operators
    "RGA": ("Rega", (230, 0, 20)), "SAZ": ("Rega", (230, 0, 20)),
    "CEF": ("Czech Air Force", (120, 160, 90)), "SUI": ("Swiss Air Force", (230, 0, 20)),
}
HELI_COLOR, GA_COLOR = (255, 120, 80), (120, 200, 255)


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
    prefix = callsign[:3]
    if prefix in AIRLINES and len(callsign) > 3 and callsign[3].isdigit():
        return AIRLINES[prefix]
    return None, DEFAULT_COLOR
