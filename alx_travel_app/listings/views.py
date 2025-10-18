"""Module imports for viewsets"""

import logging
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework_simplejwt.views import TokenObtainPairView

from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from .models import Property, Booking, Review, User, Payment
from .serializers import (
    PropertyListSerializer,
    PropertyDetailSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    ReviewSerializer,
    UserSerializer,
    PaymentSerializer,
    InitiatePaymentSerializer,
    VerifyPaymentSerializer,
    BookingWithPaymentSerializer,
    PaymentSummarySerializer,
    CustomTokenObtainPairSerializer,
)
from .services.chapa_service import ChapaPaymentService
from .tasks import send_payment_confirmation_email, send_payment_failed_email

logger = logging.getLogger(__name__)


# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=broad-exception-caught
class PropertyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Property model providing CRUD operations.

    list:
    Return a list of all properties with basic information.

    retrieve:
    Return detailed information about a specific property.

    create:
    Create a new property.

    update:
    Update an existing property.

    partial_update:
    Partially update an existing property.

    destroy:
    Delete a property.
    """

    queryset = Property.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["host", "location"]
    search_fields = ["name", "description", "location"]
    ordering_fields = ["pricepernight", "created_at", "name"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == "list":
            return PropertyListSerializer
        return PropertyDetailSerializer

    @action(detail=True, methods=["get"])
    def bookings(self, request, pk=None):
        """Get all bookings for a specific property"""
        property_obj = self.get_object()
        bookings = property_obj.bookings.all()
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        """Get all reviews for a specific property"""
        property_obj = self.get_object()
        reviews = property_obj.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Booking model providing CRUD operations.

    list:
    Return a list of all bookings.

    retrieve:
    Return detailed information about a specific booking.

    create:
    Create a new booking.

    update:
    Update an existing booking.

    partial_update:
    Partially update an existing booking.

    destroy:
    Delete a booking.
    """

    queryset = Booking.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["listing_id", "user", "status"]
    ordering_fields = ["start_date", "end_date", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == "list":
            return BookingListSerializer
        return BookingDetailSerializer

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm a pending booking"""
        booking = self.get_object()
        if booking.status != "pending":
            return Response(
                {"error": "Only pending bookings can be confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = "confirmed"
        booking.save()
        serializer = BookingDetailSerializer(booking)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        if booking.status == "canceled":
            return Response(
                {"error": "Booking is already canceled."},
                status=status.HTTP_404_BAD_REQUEST,
            )

        booking.status = "canceled"
        booking.save()
        serializer = BookingDetailSerializer(booking)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Review model providing CRUD operations.
    """

    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["listing_id", "user", "rating"]
    ordering_fields = ["rating", "created_at"]
    ordering = ["-created_at"]


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User model providing CRUD operations.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["role"]
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["first_name", "last_name", "created_at"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["get"])
    def properties(self, request, pk=None):
        """Get all properties for a specific host"""
        user = self.get_object()
        if user.role not in ["host", "admin"]:
            return Response(
                {"error": "User is not a host or admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        properties = user.properties.all()
        serializer = PropertyListSerializer(properties, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def bookings(self, request, pk=None):
        """Get all bookings for a specific user"""
        user = self.get_object()
        bookings = user.bookings.all()
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)


class InitiatePaymentView(generics.CreateAPIView):
    """
    API endpoint to initiate payment for a booking

    POST /api/payments/initiate/
    """

    serializer_class = InitiatePaymentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        booking_id = serializer.validated_data["booking_id"]
        booking = get_object_or_404(Booking, booking_id=booking_id)

        # Verify the booking belongs to the authenticated user
        if booking.user.user_id != request.user.user_id:
            return Response(
                {"error": "You do not have permission to pay for this booking."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data["last_name"],
            email=serializer.validated_data["email"],
            phone_number=serializer.validated_data.get("phone_number", ""),
            status="pending",
        )

        # Initialize payment with Chapa
        chapa_service = ChapaPaymentService()

        # Build URLs
        callback_url = request.build_absolute_uri("/api/payments/callback/")
        return_url = request.build_absolute_uri(
            f"/api/bookings/{booking.booking_id}/payment-status/"
        )

        # Customize payment page
        customization = {
            "title": f"Payment for Booking {booking.booking_reference}",
            "description": f"Payment for {booking.listing_id.name} - {booking.listing_id.location}",
            "logo": "",  # Add your logo URL here if available
        }

        result = chapa_service.initialize_payment(
            amount=float(payment.amount),
            email=payment.email,
            first_name=payment.first_name,
            last_name=payment.last_name,
            tx_ref=payment.transaction_id,
            callback_url=callback_url,
            return_url=return_url,
            phone_number=payment.phone_number if payment.phone_number else None,
            customization=customization,
        )

        if result["success"]:
            # Update payment with Chapa response
            payment.checkout_url = result["data"].get("checkout_url")
            payment.chapa_reference = result["data"].get("tx_ref")
            payment.chapa_response = result["data"]
            payment.save()

            logger.info(
                "Payment initiated for booking %s by user %s",
                booking.booking_reference,
                request.user.email,
            )

            return Response(
                {
                    "message": "Payment initiated successfully",
                    "payment": PaymentSerializer(payment).data,
                    "checkout_url": payment.checkout_url,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            payment.status = "failed"
            payment.save()

            logger.error(
                "Failed to initiate payment for booking %s: %s",
                booking.booking_reference,
                result.get("error"),
            )

            return Response(
                {"error": result.get("message"), "details": result.get("error")},
                status=status.HTTP_400_BAD_REQUEST,
            )


class VerifyPaymentView(generics.GenericAPIView):
    """
    API endpoint to verify payment status

    POST /api/payments/verify/
    """

    serializer_class = VerifyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        transaction_id = serializer.validated_data["transaction_id"]
        payment = get_object_or_404(Payment, transaction_id=transaction_id)

        # Verify the payment belongs to the authenticated user's booking
        if payment.booking.user.user_id != request.user.user_id:
            return Response(
                {"error": "You do not have permission to verify this payment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verify payment with Chapa
        chapa_service = ChapaPaymentService()
        result = chapa_service.verify_payment(payment.transaction_id)

        if result["success"]:
            data = result["data"]
            payment_status = data.get("status", "").lower()

            # Update payment record
            payment.chapa_response = data
            payment.payment_method = data.get("payment_method", "")

            if payment_status == "success":
                payment.mark_as_success()

                # Send confirmation email asynchronously
                send_payment_confirmation_email.delay(str(payment.payment_id))

                logger.info(
                    "Payment verified successfully: %s for user %s",
                    transaction_id,
                    request.user.email,
                )

            elif payment_status == "failed":
                payment.mark_as_failed()

                # Send failure notification
                send_payment_failed_email.delay(str(payment.payment_id))

                logger.warning("Payment failed: %s", transaction_id)
            else:
                payment.save()

            return Response(
                {
                    "message": "Payment verified successfully",
                    "payment": PaymentSerializer(payment).data,
                    "status": payment.status,
                },
                status=status.HTTP_200_OK,
            )
        else:
            logger.error(
                "Failed to verify payment %s: %s",
                transaction_id,
                result.get("error"),
            )

            return Response(
                {"error": result.get("message"), "details": result.get("error")},
                status=status.HTTP_400_BAD_REQUEST,
            )


@api_view(["POST"])
@permission_classes([AllowAny])  # since Chapa calls this without a token
def chapa_callback(request):
    """
    Webhook endpoint for Chapa to send payment status updates.
    POST /api/payments/callback/

    This endpoint verifies the transaction and updates the local Payment record.
    """
    try:
        data = request.data
        tx_ref = data.get("tx_ref") or data.get("trx_ref")

        if not tx_ref:
            logger.error("Callback received without transaction reference")
            return Response(
                {"error": "Missing transaction reference"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = get_object_or_404(Payment, transaction_id=tx_ref)

        # ✅ Verify payment authenticity from Chapa
        chapa_service = ChapaPaymentService()
        result = chapa_service.verify_payment(tx_ref)

        if not result["success"]:
            logger.error("Failed to verify payment in callback: %s", tx_ref)
            return Response(
                {"error": "Failed to verify payment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified_data = result.get("data", {})
        payment_status = verified_data.get("status", "").lower()

        # ✅ Save Chapa’s latest response for traceability
        payment.chapa_response = verified_data
        payment.payment_method = verified_data.get("payment_method", "")
        payment.chapa_reference = verified_data.get("reference", "")
        payment.save(
            update_fields=[
                "chapa_response",
                "payment_method",
                "chapa_reference",
                "updated_at",
            ]
        )

        # ✅ Handle different payment statuses
        if payment_status == "success":
            payment.mark_as_success()
            send_payment_confirmation_email.delay(str(payment.payment_id))
            logger.info("✅ Payment marked as SUCCESS via callback: %s", tx_ref)

        elif payment_status in ["failed", "cancelled"]:
            payment.mark_as_failed(reason=f"Chapa returned {payment_status}")
            send_payment_failed_email.delay(str(payment.payment_id))
            logger.warning("❌ Payment marked as FAILED via callback: %s", tx_ref)

        elif payment_status == "pending":
            # 👇 Optional: keep record updated but don’t mark success yet
            payment.is_pending = True
            payment.save(update_fields=["is_pending", "updated_at"])
            logger.info("⏳ Payment still PENDING via callback: %s", tx_ref)

        else:
            logger.warning(
                "⚠️ Unhandled payment status '%s' for tx_ref=%s", payment_status, tx_ref
            )

        return Response(
            {
                "message": f"Callback processed for payment ({payment_status})",
                "status": payment_status,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception("Error processing callback: %s", e)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])  # or IsAuthenticated if you want to restrict
def chapa_payment_status(request, booking_id):
    """
    Retrieve payment status for a booking.
    GET /bookings/<booking_id>/payment-status/
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)
    payment = Payment.objects.filter(booking=booking).order_by("-created_at").first()

    if not payment:
        return Response(
            {"message": "No payment found for this booking"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "booking_reference": booking.booking_reference,
            "property_name": getattr(booking.listing_id, "name", ""),
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "is_completed": payment.is_completed,
            "is_pending": payment.is_pending,
            "checkout_url": payment.checkout_url,
            "transaction_id": payment.transaction_id,
            "chapa_reference": payment.chapa_reference,
            "completed_at": payment.completed_at,
        },
        status=status.HTTP_200_OK,
    )


class PaymentDetailView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve payment details

    GET /api/payments/<transaction_id>/
    """

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "transaction_id"

    def get_queryset(self):
        return Payment.objects.filter(
            booking__user__user_id=self.request.user.user_id
        ).select_related("booking", "booking__listing_id", "booking__user")


class UserPaymentsListView(generics.ListAPIView):
    """
    API endpoint to list all payments for authenticated user

    GET /api/payments/
    """

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Payment.objects.filter(booking__user__user_id=self.request.user.user_id)
            .select_related("booking", "booking__listing_id", "booking__user")
            .order_by("-created_at")
        )


class UserBookingsWithPaymentView(generics.ListAPIView):
    """
    API endpoint to list all bookings with payment info for authenticated user

    GET /api/bookings/with-payments/
    """

    serializer_class = BookingWithPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects.filter(user__user_id=self.request.user.user_id)
            .select_related("listing_id", "listing_id__host", "user")
            .prefetch_related("payment")
            .order_by("-created_at")
        )


class PaymentSummaryView(generics.GenericAPIView):
    """
    API endpoint to get payment summary statistics

    GET /api/payments/summary/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSummarySerializer

    def get(self, request, *args, **kwargs):
        user_payments = Payment.objects.filter(
            booking__user__user_id=request.user.user_id
        )

        summary = {
            "total_payments": user_payments.count(),
            "successful_payments": user_payments.filter(status="success").count(),
            "pending_payments": user_payments.filter(status="pending").count(),
            "failed_payments": user_payments.filter(status="failed").count(),
            "total_revenue": user_payments.filter(status="success").aggregate(
                total=Sum("amount")
            )["total"]
            or 0,
            "currency": "ETB",
        }

        serializer = self.get_serializer(data=summary)
        serializer.is_valid()

        return Response(serializer.data, status=status.HTTP_200_OK)


class RetryPaymentView(generics.GenericAPIView):
    """
    API endpoint to retry a failed payment

    POST /api/payments/<transaction_id>/retry/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        payment = get_object_or_404(Payment, transaction_id=transaction_id)

        # Verify ownership
        if payment.booking.user.user_id != request.user.user_id:
            return Response(
                {"error": "You do not have permission to retry this payment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if payment can be retried
        if not payment.can_retry:
            return Response(
                {
                    "error": "This payment cannot be retried.",
                    "current_status": payment.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark old payment as cancelled
        payment.status = "cancelled"
        payment.save()

        # Create new payment
        new_payment = Payment.objects.create(
            booking=payment.booking,
            amount=payment.amount,
            currency=payment.currency,
            first_name=payment.first_name,
            last_name=payment.last_name,
            email=payment.email,
            phone_number=payment.phone_number,
            status="pending",
        )

        # Initialize payment with Chapa
        chapa_service = ChapaPaymentService()

        callback_url = request.build_absolute_uri("/api/payments/callback/")
        return_url = request.build_absolute_uri(
            f"/bookings/{payment.booking.booking_id}/payment-status/"
        )

        customization = {
            "title": f"Retry Payment - {payment.booking.booking_reference}",
            "description": f"Payment for {payment.booking.listing_id.name}",
        }

        result = chapa_service.initialize_payment(
            amount=float(new_payment.amount),
            email=new_payment.email,
            first_name=new_payment.first_name,
            last_name=new_payment.last_name,
            tx_ref=new_payment.transaction_id,
            callback_url=callback_url,
            return_url=return_url,
            phone_number=new_payment.phone_number if new_payment.phone_number else None,
            customization=customization,
        )

        if result["success"]:
            new_payment.checkout_url = result["data"].get("checkout_url")
            new_payment.chapa_reference = result["data"].get("tx_ref")
            new_payment.chapa_response = result["data"]
            new_payment.save()

            logger.info("Payment retry initiated: %s", new_payment.transaction_id)

            return Response(
                {
                    "message": "Payment retry initiated successfully",
                    "payment": PaymentSerializer(new_payment).data,
                    "checkout_url": new_payment.checkout_url,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            new_payment.status = "failed"
            new_payment.save()

            return Response(
                {"error": result.get("message"), "details": result.get("error")},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CancelPaymentView(generics.GenericAPIView):
    """
    API endpoint to cancel a pending payment

    POST /api/payments/<transaction_id>/cancel/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        payment = get_object_or_404(Payment, transaction_id=transaction_id)

        # Verify ownership
        if payment.booking.user.user_id != request.user.user_id:
            return Response(
                {"error": "You do not have permission to cancel this payment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if payment is pending
        if payment.status != "pending":
            return Response(
                {
                    "error": "Only pending payments can be cancelled.",
                    "current_status": payment.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = "cancelled"
        payment.save()

        logger.info("Payment cancelled by user: %s", transaction_id)

        return Response(
            {
                "message": "Payment cancelled successfully",
                "payment": PaymentSerializer(payment).data,
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
