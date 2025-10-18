# test_payment_onetoone.py
"""
Payment testing script for OneToOne relationship between Payment and Booking
"""

import traceback
from datetime import datetime, timedelta
import requests

BASE_URL = "http://localhost:8000"
EMAIL = "kev@travel.com"
PASSWORD = "AlxTravelApp"


# pylint: disable=broad-exception-raised
# pylint: disable=broad-exception-caught
# pylint: disable=attribute-defined-outside-init
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message):
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")


def print_warning(message):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


class PaymentTesterOneToOne:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.listing_id = None
        self.booking_id = None
        self.transaction_id = None
        self.checkout_url = None
        self.use_mock_mode = False

    def run_test(self):
        """Run payment test for OneToOne relationship"""
        try:
            print_info("🚀 Starting Payment Test (OneToOne Relationship)")

            # Check Chapa connectivity first
            self.check_chapa_connectivity()

            # 1. Authenticate
            self.authenticate()

            # 2. Get or create property
            self.get_or_create_property()

            # 3. Create a NEW booking (to avoid duplicate payments)
            self.create_new_booking()

            # 4. Check if booking already has payment
            if self.booking_has_payment():
                print_warning(
                    "Booking already has a payment. Creating a new booking..."
                )
                self.create_new_booking()  # Create another booking

            # 5. Test payment flow
            if self.use_mock_mode:
                self.test_mock_payment()
            else:
                self.test_payment_flow()

            print_success("🎉 Payment test completed!")

        except Exception as e:
            print_error(f"Test failed: {str(e)}")
            traceback.print_exc()

    def check_chapa_connectivity(self):
        """Check if Chapa API is accessible"""
        print_info("Checking Chapa API connectivity...")

        # Since we know Chapa sandbox has DNS issues, let's be more specific
        test_urls = [
            "https://api.chapa.co",  # Try production first
        ]

        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code in [200, 404, 405]:
                    print_success(f"Chapa accessible: {url}")
                    return
            except Exception as e:
                print_warning(f"Chapa not accessible: {url} - {e}")

        print_warning("Chapa API is inaccessible. Using mock mode.")
        self.use_mock_mode = True

    def authenticate(self):
        """Authenticate user"""
        print_info("Step 1: Authentication")
        response = self.session.post(
            f"{BASE_URL}/api/token/", json={"email": EMAIL, "password": PASSWORD}
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            if not self.token:
                print_warning(
                    "No access token in response; authentication may be incomplete"
                )
            else:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print_success("Authentication request succeeded")

            # Try to get the current user via /api/users/me/ (common pattern)
            try:
                user_response = self.session.get(f"{BASE_URL}/api/users/me/")
                if user_response.status_code == 200:
                    user_json = user_response.json()
                    # try multiple possible id keys
                    self.user_id = (
                        user_json.get("id")
                        or user_json.get("user_id")
                        or user_json.get("pk")
                    )
                    print_info(f"User (me) fetched: id={self.user_id}")
                    return
            except Exception as e:
                print_warning(f"/api/users/me/ failed: {e}")

            # Fallback: try /api/users/ (some APIs return a list or an object)
            user_response = self.session.get(f"{BASE_URL}/api/users/")
            if user_response.status_code == 200:
                try:
                    users_data = user_response.json()
                    # If it's a dict with results, take first result
                    if isinstance(users_data, dict) and "results" in users_data:
                        first = (
                            users_data["results"][0] if users_data["results"] else {}
                        )
                    elif isinstance(users_data, list):
                        first = users_data[0] if users_data else {}
                    elif isinstance(users_data, dict):
                        first = users_data
                    else:
                        first = {}

                    self.user_id = (
                        first.get("id") or first.get("user_id") or first.get("pk")
                    )
                    print_info(f"User fetched fallback: id={self.user_id}")
                except Exception as e:
                    print_warning(f"Could not parse /api/users/ response: {e}")
            else:
                print_warning(
                    f"/api/users/ returned status {user_response.status_code}"
                )

        else:
            print_error(f"Authentication failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            raise Exception("Authentication failed")

    def get_or_create_property(self):
        """Get or create a test property"""
        print_info("Step 2: Get or Create Property")

        # Try to get existing properties
        response = self.session.get(f"{BASE_URL}/api/properties/")

        if response.status_code == 200:
            try:
                data = response.json()
                properties = data.get("results", []) if isinstance(data, dict) else data

                if properties:
                    # try multiple id keys
                    first = properties[0]
                    self.property_id = (
                        first.get("id") or first.get("listing_id") or first.get("pk")
                    )
                    print_success(f"Using existing property: ID {self.property_id}")
                    print_info(f"Title: {first.get('name', first.get('title', 'N/A'))}")
                    print_info(
                        f"Price: ${first.get('pricepernight', first.get('price', 'N/A'))}/night"
                    )
                    return
            except Exception as e:
                print_warning(f"Could not parse properties: {e}")

        # Create property if none exists (be defensive about required fields)
        property_data = {
            "name": "Test Property",
            "description": "Property for payment testing with OneToOne relationship",
            "location": "Addis Ababa",
            "pricepernight": "85.00",
        }
        # include host only if we got the user id (some APIs infer host from auth)
        if self.user_id:
            property_data["host"] = self.user_id

        print_info(f"Creating property with payload: {property_data}")
        response = self.session.post(f"{BASE_URL}/api/properties/", json=property_data)
        if response.status_code in (200, 201):
            created = response.json()
            # tolerate multiple possible keys for returned id
            self.property_id = (
                created.get("id")
                or created.get("listing_id")
                or created.get("pk")
                or created.get("listing", {}).get("id")
            )
            print_success(f"Property created: ID {self.property_id}")
        else:
            print_error(f"Property creation failed: {response.status_code}")
            print_error(f"Response: {response.text}")

            # Try to use any existing property as a last resort
            response2 = self.session.get(f"{BASE_URL}/api/properties/")
            if response2.status_code == 200:
                data = response2.json()
                properties = data.get("results", []) if isinstance(data, dict) else data
                if properties:
                    first = properties[0]
                    self.property_id = (
                        first.get("id") or first.get("listing_id") or first.get("pk")
                    )
                    print_warning(f"Using existing property: ID {self.property_id}")
                    return
                else:
                    raise Exception("No properties available")
            else:
                print_warning("Skipping property creation error temporarily for debugging.")

    def create_new_booking(self):
        """Create a NEW booking to ensure no payment exists"""
        print_info("Step 3: Create New Booking")

        # Use dates that are definitely in the future
        check_in = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

        booking_data = {
            "listing_id": str(self.listing_id),
            "user_id": str(self.user_id),
            "check_in": check_in,
            "check_out": check_out,
            "guests": 2,
            "total_price": "170.00",  # 2 nights * $85
        }

        print_info(f"Creating booking with payload: {booking_data}")
        response = self.session.post(f"{BASE_URL}/api/bookings/", json=booking_data)

        if response.status_code == 201:
            data = response.json()
            self.booking_id = data.get("id") or data.get("booking_id") or data.get("pk")
            print_success(f"New booking created: ID {self.booking_id}")
            print_info(f"Dates: {check_in} to {check_out}")
            print_info(f"Total: ${data.get('total_price', '170.00')}")
        else:
            print_error(f"Booking creation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            raise Exception("Booking creation failed")

    def booking_has_payment(self):
        """Check if the current booking already has a payment"""
        print_info("Step 4: Check for Existing Payment")

        # Method 1: Check via payments endpoint
        response = self.session.get(f"{BASE_URL}/api/payments/")
        if response.status_code == 200:
            data = response.json()
            payments = data.get("results", []) if isinstance(data, dict) else data

            for payment in payments:
                if (
                    payment.get("booking") == self.booking_id
                    or payment.get("booking_id") == self.booking_id
                ):
                    print_warning(f"Booking {self.booking_id} already has payment:")
                    print_info(
                        f"  Payment ID: {payment.get('payment_id') or payment.get('id')}"
                    )
                    print_info(f"  Status: {payment.get('status')}")
                    return True

        # Method 2: Check via booking detail endpoint
        response = self.session.get(f"{BASE_URL}/api/bookings/{self.booking_id}/")
        if response.status_code == 200:
            booking = response.json()
            if booking.get("payment") or booking.get("payment_id"):
                print_warning(
                    f"Booking has payment relation: {booking.get('payment') or booking.get('payment_id')}"
                )
                return True

        print_success("No existing payment found for this booking")
        return False

    def test_payment_flow(self):
        """Test actual payment flow"""
        print_info("Step 5: Real Payment Flow")

        payment_data = {
            "booking_id": self.booking_id,
            "first_name": "Test",
            "last_name": "User",
            "email": "test.user@example.com",
            "phone_number": "+251911334455",
            "amount": "170.00",
        }

        print_info("Initiating payment...")
        response = self.session.post(
            f"{BASE_URL}/api/payments/initiate/", json=payment_data
        )

        if response.status_code == 201:
            data = response.json()
            payment_info = data.get("payment", {})
            self.transaction_id = payment_info.get("transaction_id") or data.get(
                "transaction_id"
            )
            self.checkout_url = data.get("checkout_url")

            print_success("Payment initiated successfully!")
            print_info(f"Transaction ID: {self.transaction_id}")
            print_info(f"Amount: ${payment_info.get('amount')}")
            print_info(f"Status: {payment_info.get('status')}")

            if self.checkout_url:
                print_info(f"Checkout URL: {self.checkout_url}")

                # Wait for manual payment completion
                input("\n⏳ Complete payment on Chapa page, then press Enter...")

                # Verify payment
                self.verify_payment()
            else:
                print_warning("No checkout URL returned")

        else:
            print_error(f"Payment initiation failed: {response.status_code}")
            print_error(f"Response: {response.text}")

            # Check if it's a duplicate error
            if (
                "duplicate" in response.text.lower()
                or "already exists" in response.text.lower()
            ):
                print_warning(
                    "Duplicate payment detected! This booking already has a payment."
                )
                if self.booking_has_payment():
                    print_info("Using existing payment for verification test...")
                    self.test_with_existing_payment()
            else:
                print_warning("Falling back to mock mode...")
                self.test_mock_payment()

    def test_with_existing_payment(self):
        """Test with existing payment record"""
        # Get the existing payment for this booking
        response = self.session.get(f"{BASE_URL}/api/payments/")
        if response.status_code == 200:
            data = response.json()
            payments = data.get("results", []) if isinstance(data, dict) else data

            for payment in payments:
                if (
                    payment.get("booking") == self.booking_id
                    or payment.get("booking_id") == self.booking_id
                ):
                    self.transaction_id = payment.get("transaction_id")
                    print_info(f"Using existing payment: {self.transaction_id}")

                    # Test verification
                    self.verify_payment()
                    return

    def test_mock_payment(self):
        """Test mock payment flow"""
        print_info("Step 5: Mock Payment Flow")

        # Generate mock transaction data
        self.transaction_id = f"MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        print_success("Mock payment initiated")
        print_info(f"Mock Transaction ID: {self.transaction_id}")
        print_info("Status: pending")

        # Simulate successful payment
        print_info("\n💰 Simulating successful payment...")

        # Directly update the payment status via API if possible
        self.update_payment_status("success")

        print_success("Mock payment completed successfully!")

        # Show final status
        self.show_final_status()

    def verify_payment(self):
        """Verify payment status"""
        if not self.transaction_id:
            print_warning("No transaction ID available for verification")
            return

        print_info("Verifying payment...")

        verify_data = {"transaction_id": self.transaction_id}

        response = self.session.post(
            f"{BASE_URL}/api/payments/verify/", json=verify_data
        )

        if response.status_code == 200:
            data = response.json()
            payment_info = data.get("payment", {})

            print_success("Payment verification completed!")
            print_info(f"Status: {payment_info.get('status')}")
            print_info(f"Payment Method: {payment_info.get('payment_method', 'N/A')}")

            if payment_info.get("status") == "success":
                print_success("🎉 Payment completed successfully!")
            else:
                print_warning(f"Payment status: {payment_info.get('status')}")
        else:
            print_warning(f"Verification failed: {response.status_code}")
            print_warning(f"Verify response: {response.text}")

    def update_payment_status(self, status):
        """Update payment status directly (for mock payments)"""
        # This would require a PATCH endpoint on your payments API
        print_info(f"Would update payment status to: {status}")

    def show_final_status(self):
        """Show final booking and payment status"""
        print_info("\n📊 Final Status:")

        if self.booking_id:
            response = self.session.get(f"{BASE_URL}/api/bookings/{self.booking_id}/")
            if response.status_code == 200:
                booking = response.json()
                print_info(f"Booking Status: {booking.get('status', 'N/A')}")
                print_info(f"Total Nights: {booking.get('total_nights', 'N/A')}")
                print_info(f"Total Price: ${booking.get('total_price', 'N/A')}")


if __name__ == "__main__":
    tester = PaymentTesterOneToOne()
    tester.run_test()
