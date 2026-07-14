from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import EmailQueue

def send_smart_email(subject: str, body: str, to: str, html: str = "") -> None:
    """Send email. In OFFLINE_MODE, emails go to files (filebased backend).
    We still try send_mail; backend will handle writing to disk."""
    try:
        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(subject, body, settings.EMAIL_HOST_USER, [to])
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        EmailQueue.objects.create(to=to, subject=subject, body=body, html=html, last_error=str(e))

def retry_email_queue(max_attempts: int = 5) -> int:
    sent = 0
    for item in EmailQueue.objects.filter(sent_at__isnull=True, attempts__lt=max_attempts)[:50]:
        try:
            send_mail(item.subject, item.body, settings.EMAIL_HOST_USER, [item.to], html_message=item.html, fail_silently=False)
            item.sent_at = timezone.now()
            item.last_error = ""
            item.attempts += 1
            item.save(update_fields=['sent_at','last_error','attempts'])
            sent += 1
        except Exception as e:
            item.attempts += 1
            item.last_error = str(e)
            item.save(update_fields=['attempts','last_error'])
    return sent

