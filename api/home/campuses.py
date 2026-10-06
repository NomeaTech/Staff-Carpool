from django.utils.translation import gettext_lazy as _

# The LUT campuses offered as destinations on the search and add ride pages.
#
# "place" is stored as the ride's destination_json, in the same format the
# Google Places autocomplete produces (place.toJSON()), so selecting a campus
# needs no Google API query. The id, address and location were fetched from
# the Places API (place details, English). The displayName is our own, as
# Google's names for the campuses are inconsistent.
CAMPUSES = [
    {
        "label": _("Lappeenranta campus"),
        "place": {
            "id": "ChIJmZVaQ_SUkEYRzaXC3OMePhM",
            "resourceName": "places/ChIJmZVaQ_SUkEYRzaXC3OMePhM",
            "displayName": "Lappeenranta campus",
            "formattedAddress": "Yliopistonkatu 34, 53850 Lappeenranta, Finland",
            "location": {"lat": 61.06499650000001, "lng": 28.094338699999998},
        },
    },
    {
        "label": _("Lahti Mukkula campus"),
        "place": {
            "id": "ChIJoWJMZU0ojkYRP7JlaZwlqz0",
            "resourceName": "places/ChIJoWJMZU0ojkYRP7JlaZwlqz0",
            "displayName": "Lahti Mukkula campus",
            "formattedAddress": "Mukkulankatu 19, 15210 Lahti, Finland",
            "location": {"lat": 61.00579469999999, "lng": 25.6643549},
        },
    },
    {
        "label": _("Lahti Niemi campus"),
        "place": {
            "id": "ChIJWVy17NwpjkYRhcV8Ogq8E04",
            "resourceName": "places/ChIJWVy17NwpjkYRhcV8Ogq8E04",
            "displayName": "Lahti Niemi campus",
            "formattedAddress": "Niemenkatu 73, 15140 Lahti, Finland",
            "location": {"lat": 61.006307299999996, "lng": 25.655549500000003},
        },
    },
    {
        "label": _("Kouvola campus"),
        "place": {
            "id": "ChIJIX5tasWzkUYRi8_7Vv-24Ko",
            "resourceName": "places/ChIJIX5tasWzkUYRi8_7Vv-24Ko",
            "displayName": "Kouvola campus",
            "formattedAddress": "Kauppalankatu 13, 45100 Kouvola, Finland",
            "location": {"lat": 60.869944999999994, "lng": 26.704601399999998},
        },
    },
    {
        "label": _("Mikkeli campus"),
        "place": {
            "id": "ChIJW_4ScwuhmkYR50aBXKdGUCo",
            "resourceName": "places/ChIJW_4ScwuhmkYR50aBXKdGUCo",
            "displayName": "Mikkeli campus",
            "formattedAddress": "Sammonkatu 12, 50130 Mikkeli, Finland",
            "location": {"lat": 61.681957499999996, "lng": 27.2545705},
        },
    },
]
