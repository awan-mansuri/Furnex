from importlib import import_module
import datetime

from django.conf import settings
from django.utils import timezone
from django.utils.http import http_date
from django.utils.cache import patch_vary_headers


class PathBasedSessionMiddleware:
	"""
	Use a separate session cookie for admin URLs to isolate admin auth
	from the public site session.
	"""

	def __init__(self, get_response):
		self.get_response = get_response
		engine = import_module(settings.SESSION_ENGINE)
		self.SessionStore = engine.SessionStore

	def _cookie_name_for_request(self, request):
		if request.path.startswith('/admin'):
			return 'admin_sessionid'
		return settings.SESSION_COOKIE_NAME

	def __call__(self, request):
		cookie_name = self._cookie_name_for_request(request)
		session_key = request.COOKIES.get(cookie_name)
		request.session = self.SessionStore(session_key)

		response = self.get_response(request)
		# Ensure caches vary on Cookie like Django's SessionMiddleware
		patch_vary_headers(response, ('Cookie',))

		try:
			accessed = request.session.accessed
			modified = request.session.modified
			empty = request.session.is_empty()
		except AttributeError:
			return response

		if (cookie_name in request.COOKIES) and (not accessed) and (not modified):
			return response

		if request.session.get_expire_at_browser_close():
			max_age = None
			expires = None
		else:
			max_age = settings.SESSION_COOKIE_AGE
			expires_time = timezone.now() + datetime.timedelta(seconds=max_age)
			expires = http_date(int(expires_time.timestamp()))

		if empty:
			if cookie_name in request.COOKIES:
				response.delete_cookie(
					cookie_name,
					path=settings.SESSION_COOKIE_PATH,
					domain=settings.SESSION_COOKIE_DOMAIN,
					samesite=settings.SESSION_COOKIE_SAMESITE,
				)
			return response

		# Only persist the session/cookie if needed
		if accessed and (modified or getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', False)):
			request.session.save()

		if not request.session.session_key:
			return response

		response.set_cookie(
			cookie_name,
			request.session.session_key,
			max_age=max_age,
			expires=expires,
			domain=settings.SESSION_COOKIE_DOMAIN,
			path=settings.SESSION_COOKIE_PATH,
			secure=settings.SESSION_COOKIE_SECURE,
			httponly=settings.SESSION_COOKIE_HTTPONLY,
			samesite=settings.SESSION_COOKIE_SAMESITE,
		)
		return response



class SimpleSessionCookieMiddleware:
    """
    Map a dedicated admin cookie 'admin_sessionid' to Django's 'sessionid' for
    admin requests on the way in, and rename it back on the way out. This keeps
    admin and site sessions completely isolated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Determine if this is an admin request
        admin_paths = (
            request.path.startswith('/admin') or
            request.path.startswith('/admin-dashboard-data/') or
            request.path.startswith('/admin-model-counts/') or
            request.path.startswith('/retry-email-queue/') or
            request.path.startswith('/order-invoice/')
        )
        
        # Work on a copy of cookies to avoid mutation issues
        request.COOKIES = request.COOKIES.copy()
        
        if admin_paths:
            # For admin paths: use only admin_sessionid, ignore user sessionid
            if 'admin_sessionid' in request.COOKIES:
                # Map admin session to Django's expected cookie name
                request.COOKIES['sessionid'] = request.COOKIES['admin_sessionid']
            else:
                # No admin session: ensure sessionid is removed so no user session leaks
                if 'sessionid' in request.COOKIES:
                    del request.COOKIES['sessionid']
        else:
            # For non-admin paths: use only sessionid, ignore admin_sessionid
            if 'admin_sessionid' in request.COOKIES:
                del request.COOKIES['admin_sessionid']

        response = self.get_response(request)

        # Handle response cookies
        try:
            if admin_paths:
                # Admin path: convert sessionid to admin_sessionid
                if 'sessionid' in response.cookies:
                    session_cookie = response.cookies['sessionid']
                    # Set admin_sessionid cookie with same properties
                    response.set_cookie(
                        'admin_sessionid',
                        session_cookie.value,
                        max_age=session_cookie.get('max-age'),
                        expires=session_cookie.get('expires'),
                        path='/',
                        domain=session_cookie.get('domain'),
                        secure=session_cookie.get('secure', False),
                        httponly=session_cookie.get('httponly', True),
                        samesite=session_cookie.get('samesite', 'Lax'),
                    )
                    # Remove the sessionid cookie from response only
                    del response.cookies['sessionid']
        except Exception:
            pass

        return response

