import logging
from typing import Dict, Optional
import requests
from django.conf import settings
from django.utils import timezone
from listings.models import Payment

logger = logging.getLogger(__name__)

# pylint: disable=no-member
class ChapaPaymentService:
    """Service class for handling Chapa API interactions"""

    BASE_URL = "https://api.chapa.co/v1"
    # SANDBOX_URL = "https://api.sandbox.chapa.co/v1"

    def __init__(self):
        self.secret_key = settings.CHAPA_SECRET_KEY
        self.base_url = self.BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize_payment(
        self,
        amount: float,
        email: str,
        first_name: str,
        last_name: str,
        tx_ref: str,
        callback_url: str,
        return_url: str,
        currency: str = "ETB",
        phone_number: Optional[str] = None,
        customization: Optional[Dict] = None,
    ) -> Dict:
        """
        Initialize a payment with Chapa

        Args:
            amount: Payment amount
            email: Customer email
            first_name: Customer first name
            last_name: Customer last name
            tx_ref: Unique transaction reference
            callback_url: URL for Chapa to send payment status
            return_url: URL to redirect user after payment
            currency: Payment currency (default: ETB)
            phone_number: Customer phone number (optional)
            customization: Customization options (optional)

        Returns:
            Dictionary containing payment initialization response
        """
        url = f"{self.base_url}/transaction/initialize"

        payload = {
            "amount": str(amount),
            "currency": currency,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
        }

        if phone_number:
            payload["phone_number"] = phone_number

        if customization:
            # Ensure title length compliance
            if "title" in customization and len(customization["title"]) > 16:
                customization["title"] = customization["title"][:16]
            payload["customization"] = customization

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            logger.info("Payment initialized successfully: %s", tx_ref)
            return {
                "success": True,
                "data": data.get("data", {}),
                "message": data.get("message", "Payment initialized successfully"),
            }

        except requests.exceptions.RequestException as e:
            logger.error("Error initializing payment: %s", e)
            if hasattr(e, "response") and e.response is not None:
                logger.error("Chapa error body: %s", e.response.text)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to initialize payment",
            }

    def verify_payment(self, tx_ref: str) -> Dict:
        """
        Verify a payment transaction with Chapa and update the local Payment record.
        """
        url = f"{self.BASE_URL}/transaction/verify/{tx_ref}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            logger.info("Payment verified successfully: %s", tx_ref)

            chapa_data = data.get("data", {})

            # ✅ 1. Find the corresponding Payment record
            payment = Payment.objects.filter(transaction_id=tx_ref).first()

            if not payment:
                logger.warning("No payment record found for tx_ref: %s", tx_ref)
                return {
                    "success": False,
                    "message": "No matching payment record found",
                    "data": chapa_data,
                }

            # ✅ 2. Check if Chapa says payment was successful
            status = chapa_data.get("status", "").lower()
            if status == "success":
                payment.chapa_reference = chapa_data.get("reference")
                payment.status = "success"
                payment.completed_at = timezone.now()
                payment.save()

                # Optionally, mark booking as confirmed
                if hasattr(payment, "mark_as_success"):
                    payment.mark_as_success()

                logger.info("Payment %s marked as success.", tx_ref)

            else:
                payment.status = "failed"
                payment.save()
                logger.warning("Payment %s verification failed: %s", tx_ref, status)

            return {
                "success": True,
                "data": chapa_data,
                "message": f"Payment verification result: {status}",
            }

        except requests.exceptions.RequestException as e:
            logger.error("Error verifying payment: %s", e)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to verify payment",
            }

    def get_banks(self) -> Dict:
        """
        Get list of available banks for bank transfers

        Returns:
            Dictionary containing list of banks
        """
        url = f"{self.base_url}/banks"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "data": data.get("data", []),
                "message": "Banks retrieved successfully",
            }

        except requests.exceptions.RequestException as e:
            logger.error("Error fetching banks: %s", e)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch banks",
            }
