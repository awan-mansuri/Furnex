from django.conf import settings

def send_sms(to_number: str, message: str) -> bool:
    """Send SMS using Twilio if configured. Returns True if attempted.
    Falls back silently if Twilio settings are missing.
    """
    try:
        if not all([
            getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
            getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
            getattr(settings, 'TWILIO_FROM_NUMBER', ''),
        ]):
            return False
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to_number
        )
        return True
    except Exception:
        return False


