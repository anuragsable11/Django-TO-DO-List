"""Use each visitor's own time zone, so "today" and "overdue" match their calendar, not the server's UTC.

app.js stores the browser's zone (e.g. "Asia/Kolkata") in a `tz` cookie. Signed-in users also get it
saved on their profile, which the morning email needs since it is sent without a browser around.
"""
import zoneinfo

from django.utils import timezone

from .models import Profile

COOKIE = 'tz'


def valid_zone(name):
    if not name or len(name) > 64:
        return None
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return None


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = request.COOKIES.get(COOKIE, '')
        zone = valid_zone(name)
        user = getattr(request, 'user', None)
        signed_in = user is not None and user.is_authenticated
        if zone:
            timezone.activate(zone)
            # one write per session (or zone change), not one per request
            if signed_in and request.session.get('tz_saved') != name:
                Profile.objects.update_or_create(user=user, defaults={'timezone': name})
                request.session['tz_saved'] = name
        elif signed_in and valid_zone(request.session.get('tz_saved', '')):
            # no cookie yet on this browser: use the zone this session already saw
            timezone.activate(valid_zone(request.session['tz_saved']))
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
