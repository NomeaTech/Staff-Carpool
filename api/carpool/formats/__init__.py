"""
How dates and times are shown in each language (FORMAT_MODULE_PATH): in
English "Sat 25 Oct, 12:30", in Finnish "la 25.10. klo 12.30". Anything not
set here comes from Django's own formats for the language.

Templates show them in the user's language:
- the standard formats with Django's filters: {{ value|time }} (TIME_FORMAT),
  {{ value|date:"MONTH_DAY_FORMAT" }}, {{ value|date }} (DATE_FORMAT) ...
- the app's own formats (the ones with a weekday, or a numeric day and
  month) with the localized filter: {% load dates %}{{ value|localized:"SHORT_WEEKDAY_DATE_FORMAT" }}
  (home/templatetags/dates.py)

So never write a format such as "H:i" in a template: a Finnish user would
see 12:30 instead of 12.30. Add a format here, in each language, instead.
"""
