
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Payment

logger = logging.getLogger(__name__)


# pylint: disable=no-member
@shared_task(bind=True, max_retries=3)
def send_payment_confirmation_email(self, payment_id):
    """
    Send payment confirmation email to user

    Args:
        payment_id: ID of the payment record
    """
    try:
        payment = Payment.objects.select_related(
            "booking", "booking__listing_id", "booking__user"
        ).get(payment_id=payment_id)

        # Prepare email context
        context = {
            "user_name": f"{payment.first_name} {payment.last_name}",
            "booking_reference": payment.booking.booking_reference,
            "listing_title": payment.booking.listing_id.name,
            "check_in": payment.booking.check_in,
            "check_out": payment.booking.check_out,
            "amount": payment.amount,
            "currency": payment.currency,
            "transaction_id": payment.transaction_id,
            "payment_method": payment.payment_method,
        }

        # Render email template
        html_message = render_to_string("emails/payment_confirmation.html", context)
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject=f"Payment Confirmation - Booking {payment.booking.booking_reference}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Payment confirmation email sent for payment %s", payment.transaction_id
        )

    except Payment.DoesNotExist:
        logger.error("Payment with id %s not found", payment_id)

    except Exception as e:
        logger.error("Error sending payment confirmation email: %s", e)
        # Retry the task
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_payment_failed_email(self, payment_id):
    """
    Send payment failure notification email

    Args:
        payment_id: ID of the payment record
    """
    try:
        payment = Payment.objects.select_related(
            "booking", "booking__listing_id", "booking__user"
        ).get(payment_id=payment_id)

        context = {
            "user_name": f"{payment.first_name} {payment.last_name}",
            "booking_reference": payment.booking.booking_reference,
            "listing_title": payment.booking.listing_id.name,
            "amount": payment.amount,
            "currency": payment.currency,
            "transaction_id": payment.transaction_id,
        }

        html_message = render_to_string("emails/payment_failed.html", context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=f"Payment Failed - Booking {payment.booking.booking_reference}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info("Payment failed email sent for payment %s", payment.transaction_id)

    except Payment.DoesNotExist:
        logger.error("Payment with id %s not found", payment_id)

    except Exception as e:
        logger.error("Error sending payment failed email: %s", e)
        raise self.retry(exc=e, countdown=60)
