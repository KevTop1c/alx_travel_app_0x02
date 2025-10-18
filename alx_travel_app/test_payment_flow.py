# test_payment_flow.py
"""
Manual testing script for Chapa payment integration
Run this script to test the complete payment workflow
"""

import traceback
from datetime import datetime, timedelta
import requests

# Configuration
BASE_URL = "http://localhost:8000"
EMAIL = "kev@travel.com"
PASSWORD = "AlxTravelApp"


# pylint: disable=broad-exception-caught
# pylint: disable=broad-exception-raised
# Color codes for terminal output
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


def print_section(title):
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{title}")
    print(f"{'='*60}{Colors.END}\n")


class PaymentTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.listing_id = None
        self.booking_id = None
        self.payment_id = None
        self.transaction_id = None
        self.checkout_url = None

    def run_all_tests(self):
        """Run all test cases"""
        print_section("CHAPA PAYMENT INTEGRATION - TESTING SUITE")

        try:
            self.test_authentication()
            self.test_create_listing()
            self.test_create_booking()
            self.test_initiate_payment()
            self.test_get_payment_details()
            self.test_list_user_payments()

            print_info("\nWaiting for manual payment completion...")
            print_info("Please complete the payment on Chapa checkout page")
            print_info(f"Checkout URL: {self.checkout_url}")

            input("\nPress Enter after completing payment on Chapa...")

            self.test_verify_payment()
            self.test_final_status()

            print_section("TEST SUMMARY")
            print_success("All tests completed successfully!")
            print_info("Check your email for confirmation message")

        except Exception as e:
            print_error(f"Test failed: {str(e)}")

            traceback.print_exc()

    def test_authentication(self):
        """Test user authentication"""
        print_section("Test 1: Authentication")

        # Try to get or create user token
        response = self.session.post(
            f"{BASE_URL}/api/token/", json={"email": EMAIL, "password": PASSWORD}
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print_success("Authentication successful")
            print_info(f"Token: {self.token[:20]}...")
        else:
            print_error(f"Authentication failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            raise Exception("Authentication failed")

    def test_create_listing(self):
        """Create a test listing"""
        print_section("Test 2: Create Test Listing")

        listing_data = {
            "name": f"Test Property {datetime.now().strftime('%Y%m%d%H%M%S')}",
            "description": "A beautiful test property for payment integration",
            "pricepernight": "100.00",
        }

        response = self.session.post(f"{BASE_URL}/api/properties/", json=listing_data)

        if response.status_code == 201:
            data = response.json()
            self.listing_id = data.get("id")
            print_success(f"Listing created: ID {self.listing_id}")
            print_info(f"Title: {data.get('name')}")
            print_info(f"Price: ${data.get('pricepernight')}/night")
        else:
            print_warning("Could not create listing, trying to use existing listing...")
            # Try to get existing listing
            response = self.session.get(f"{BASE_URL}/api/properties/")
            if response.status_code == 200:
                listings = response.json().get("results", [])
                if listings:
                    self.listing_id = listings[0]["id"]
                    print_info(f"Using existing listing: ID {self.listing_id}")
                else:
                    raise Exception("No listings available")

    def test_create_booking(self):
        """Create a test booking"""
        print_section("Test 3: Create Test Booking")

        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=11)).strftime("%Y-%m-%d")

        booking_data = {
            "listing": self.listing_id,
            "check_in": check_in,
            "check_out": check_out,
            "total_price": "400.00",
        }

        response = self.session.post(f"{BASE_URL}/api/bookings/", json=booking_data)

        if response.status_code == 201:
            data = response.json()
            self.booking_id = data.get("id")
            print_success(f"Booking created: ID {self.booking_id}")
            print_info(f"Reference: {data.get('booking_reference')}")
            print_info(f"Check-in: {check_in}")
            print_info(f"Check-out: {check_out}")
            print_info(f"# of Nights: {data.get("total_nights")}")
            print_info(f"Total Price: ${data.get('total_price')}")
        else:
            print_error(f"Booking creation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            raise Exception("Booking creation failed")

    def test_initiate_payment(self):
        """Test payment initiation"""
        print_section("Test 4: Initiate Payment")

        payment_data = {
            "booking_id": self.booking_id,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone_number": "+251911234567",
        }

        response = self.session.post(
            f"{BASE_URL}/api/payments/initiate/", json=payment_data
        )

        if response.status_code == 201:
            data = response.json()
            payment_info = data.get("payment", {})
            self.transaction_id = payment_info.get("transaction_id")
            self.checkout_url = data.get("checkout_url")

            print_success("Payment initiated successfully")
            print_info(f"Transaction ID: {self.transaction_id}")
            print_info(f"Amount: ${payment_info.get('amount')}")
            print_info(f"Status: {payment_info.get('status')}")
            print_info(f"Checkout URL: {self.checkout_url}")
        else:
            print_error(f"Payment initiation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            raise Exception("Payment initiation failed")

    def test_get_payment_details(self):
        """Test getting payment details"""
        print_section("Test 5: Get Payment Details")

        response = self.session.get(f"{BASE_URL}/api/payments/{self.transaction_id}/")

        if response.status_code == 200:
            data = response.json()
            print_success("Payment details retrieved")
            print_info(f"Transaction ID: {data.get('transaction_id')}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Amount: {data.get('currency')} {data.get('amount')}")
            print_info(f"Customer: {data.get('first_name')} {data.get('last_name')}")
        else:
            print_error(f"Failed to get payment details: {response.status_code}")

    def test_list_user_payments(self):
        """Test listing all user payments"""
        print_section("Test 6: List User Payments")

        response = self.session.get(f"{BASE_URL}/api/payments/")

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print_success(f"Retrieved {len(results)} payment(s)")

            for idx, payment in enumerate(results, 1):
                print_info(f"\nPayment {idx}:")
                print(f"  Transaction ID: {payment.get('transaction_id')}")
                print(f"  Status: {payment.get('status')}")
                print(f"  Amount: {payment.get('currency')} {payment.get('amount')}")
        else:
            print_error(f"Failed to list payments: {response.status_code}")

    def test_verify_payment(self):
        """Test payment verification"""
        print_section("Test 7: Verify Payment")

        verify_data = {"transaction_id": self.transaction_id}

        response = self.session.post(
            f"{BASE_URL}/api/payments/verify/", json=verify_data
        )

        if response.status_code == 200:
            data = response.json()
            payment_info = data.get("payment", {})
            print_success("Payment verification successful")
            print_info(f"Status: {payment_info.get('status')}")
            print_info(f"Payment Method: {payment_info.get('payment_method')}")

            if payment_info.get("status") == "success":
                print_success("Payment completed successfully!")
            else:
                print_warning(f"Payment status: {payment_info.get('status')}")
        else:
            print_error(f"Payment verification failed: {response.status_code}")
            print_error(f"Response: {response.text}")

    def test_final_status(self):
        """Check final booking and payment status"""
        print_section("Test 8: Final Status Check")

        # Check payment
        payment_response = self.session.get(
            f"{BASE_URL}/api/payments/{self.transaction_id}/"
        )

        if payment_response.status_code == 200:
            payment = payment_response.json()
            print_info("Payment Status:")
            print(f"  Status: {payment.get('status')}")
            print(f"  Completed At: {payment.get('completed_at')}")

        # Check booking
        booking_response = self.session.get(
            f"{BASE_URL}/api/bookings/{self.booking_id}/"
        )

        if booking_response.status_code == 200:
            booking = booking_response.json()
            print_info("\nBooking Status:")
            print(f"  Status: {booking.get('status')}")
            print(f"  Payment Status: {booking.get('payment_status')}")


if __name__ == "__main__":
    tester = PaymentTester()
    tester.run_all_tests()
