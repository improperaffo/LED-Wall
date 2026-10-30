"""Swiss coordinates: WGS84 -> LV95 (swisstopo approximate formulas, ~1 m accuracy)."""


def lv95(lon: float, lat: float) -> tuple[float, float]:
    p = (lat * 3600 - 169028.66) / 10000
    l = (lon * 3600 - 26782.5) / 10000  # noqa: E741
    e = 2600072.37 + 211455.93 * l - 10938.51 * l * p - 0.36 * l * p ** 2 - 44.54 * l ** 3
    n = (1200147.07 + 308807.95 * p + 3745.25 * l ** 2 + 76.63 * p ** 2
         - 194.56 * l ** 2 * p + 119.79 * p ** 3)
    return e, n
