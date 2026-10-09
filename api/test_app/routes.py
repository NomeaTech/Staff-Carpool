"""
Driving routes of rides, used to find rides that pass by a searcher's start
or destination on the way (see search_rides in home/views.py).

The route is fetched once, when a ride is created, from the Google Routes API
and stored as a line in Ride.route. Searching never calls the API.
"""
import logging
import os

import requests
from django.contrib.gis.geos import LineString, Point

logger = logging.getLogger(__name__)

# Finland's national coordinate system (ETRS-TM35FIN), measured in metres
ROUTE_SRID = 3067

ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def decode_polyline(encoded):
    """Decode a Google encoded polyline into a list of (lat, lng) pairs."""
    coordinates = []
    index = lat = lng = 0
    while index < len(encoded):
        for is_lng in (False, True):
            result = shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        coordinates.append((lat / 1e5, lng / 1e5))
    return coordinates


def _lat_lng(point):
    return {"location": {"latLng": {"latitude": point.y, "longitude": point.x}}}


def fetch_driving_route(points):
    """
    The driving route through the given points (WGS84 Points, in order), as a
    list of (lat, lng) pairs, or None if the Routes API request fails.
    """
    # A key restricted to websites (HTTP referrers) only works from browsers,
    # so server requests need their own key, restricted to the server's IP.
    key = os.getenv("GOOGLE_MAPS_SERVER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        return None
    body = {
        "origin": _lat_lng(points[0]),
        "destination": _lat_lng(points[-1]),
        "intermediates": [_lat_lng(p) for p in points[1:-1]],
        "travelMode": "DRIVE",
    }
    try:
        response = requests.post(
            ROUTES_API_URL,
            json=body,
            headers={
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "routes.polyline.encodedPolyline",
            },
            timeout=10,
        )
    except requests.RequestException:
        logger.exception("Could not reach the Routes API")
        return None
    if not response.ok:
        # Google explains the problem in the body, e.g. a key restriction
        logger.error("The Routes API refused the request (%s): %s", response.status_code, response.text[:500])
        return None
    try:
        return decode_polyline(response.json()["routes"][0]["polyline"]["encodedPolyline"])
    except (KeyError, IndexError, ValueError):
        logger.exception("Unexpected response from the Routes API")
        return None


def build_route(ride):
    """
    The ride's route from its start through its vias to its destination, in
    ROUTE_SRID. Falls back to straight lines between the points if the driving
    route cannot be fetched. None if the ride has no start or destination.
    """
    if not ride.start_location or not ride.destination_location:
        return None
    points = [ride.start_location]
    points += [via.location for via in ride.via_points.all()]
    points.append(ride.destination_location)

    coordinates = fetch_driving_route(points)
    if coordinates and len(coordinates) >= 2:
        line = LineString([(lng, lat) for lat, lng in coordinates], srid=4326)
    else:
        line = LineString([(p.x, p.y) for p in points], srid=4326)
    return line.transform(ROUTE_SRID, clone=True)


def as_route_point(point):
    """A WGS84 Point in the route's coordinate system, for comparing with Ride.route."""
    return Point(point.x, point.y, srid=4326).transform(ROUTE_SRID, clone=True)
