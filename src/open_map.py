import webbrowser

import pyproj


def open_map(center_xy: tuple[float, float], proj: str) -> None:
    coordinate_transformer = pyproj.Transformer.from_crs(proj, 'EPSG:4326', always_xy=True)
    lon, lat = coordinate_transformer.transform(*center_xy)

    url = f'https://www.google.com/maps/search/?api=1&query={lat:.7f}%2C{lon:.7f}'
    webbrowser.open(url, new=0, autoraise=True)
