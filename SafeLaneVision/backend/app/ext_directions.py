from .http import client, get_with_retry
from .config import MAPBOX_TOKEN
def cycle_route(lat1,lon1,lat2,lon2):
    if not MAPBOX_TOKEN: return {"error":"MAPBOX_TOKEN missing"}
    url=(f"https://api.mapbox.com/directions/v5/mapbox/cycling/"
         f"{lon1},{lat1};{lon2},{lat2}?alternatives=true&geometries=geojson&overview=full&access_token={MAPBOX_TOKEN}")
    with client() as c:
        r = get_with_retry(c, "GET", url)
        return r.json()