from django.conf import settings


def offline_mode(request):
    """Expose OFFLINE_MODE to all templates."""
    context = {
        'OFFLINE_MODE': getattr(settings, 'OFFLINE_MODE', False)
    }
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        unread_qs = user.notifications.filter(is_read=False).order_by('-created_at')
        context.update({
            'header_unread_notifications': unread_qs[:5],
            'header_unread_count': unread_qs.count(),
        })
    else:
        context.update({
            'header_unread_notifications': [],
            'header_unread_count': 0,
        })
    return context
