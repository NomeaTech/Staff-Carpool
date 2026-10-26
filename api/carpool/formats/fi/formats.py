# Finnish date and time formats (see carpool/formats/__init__.py), in the
# Django date format syntax: https://docs.djangoproject.com/en/stable/ref/templates/builtins/#date
# E is the month's name as it follows a day: "lokakuuta".

# Standard formats
TIME_FORMAT = "G.i"                                     # 12.30, 7.05
DATE_FORMAT = "j. E Y"                                  # 25. lokakuuta 2026
DATETIME_FORMAT = r"j. E Y \k\l\o G.i"                  # 25. lokakuuta 2026 klo 12.30
MONTH_DAY_FORMAT = "j. E"                               # 25. lokakuuta

# The app's own formats
WEEKDAY_DATE_FORMAT = "l j. E Y"                        # lauantai 25. lokakuuta 2026
WEEKDAY_MONTH_DAY_FORMAT = "l j. E"                     # lauantai 25. lokakuuta
SHORT_WEEKDAY_MONTH_DAY_FORMAT = "D j. E"               # la 25. lokakuuta
SHORT_WEEKDAY_DATE_FORMAT = "D j.n."                    # la 25.10.
SHORT_WEEKDAY_DATETIME_FORMAT = r"D j.n. \k\l\o G.i"    # la 25.10. klo 12.30
NUMERIC_MONTH_DAY_FORMAT = "j.n."                       # 25.10.
NUMERIC_MONTH_DAY_TIME_FORMAT = "j.n. G.i"              # 25.10. 12.30
