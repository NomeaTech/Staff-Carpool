# English date and time formats (see carpool/formats/__init__.py), in the
# Django date format syntax: https://docs.djangoproject.com/en/stable/ref/templates/builtins/#date

# Standard formats
TIME_FORMAT = "H:i"                                     # 12:30
DATE_FORMAT = "j F Y"                                   # 25 October 2026
DATETIME_FORMAT = "j F Y, H:i"                          # 25 October 2026, 12:30
MONTH_DAY_FORMAT = "j F"                                # 25 October

# The app's own formats
WEEKDAY_DATE_FORMAT = "l, j F Y"                        # Saturday, 25 October 2026
WEEKDAY_MONTH_DAY_FORMAT = "l j F"                      # Saturday 25 October
SHORT_WEEKDAY_MONTH_DAY_FORMAT = "D j F"                # Sat 25 October
SHORT_WEEKDAY_DATE_FORMAT = "D j M"                     # Sat 25 Oct
SHORT_WEEKDAY_DATETIME_FORMAT = "D j M, H:i"            # Sat 25 Oct, 12:30
NUMERIC_MONTH_DAY_FORMAT = "j.n."                       # 25.10.
NUMERIC_MONTH_DAY_TIME_FORMAT = "j.n. H:i"              # 25.10. 12:30
