"""Module imports for serializers"""

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
# from django.contrib.auth import get_user_model
from .models import Property, Booking, Review, Payment, User
# from .tokens import CustomAccessToken

# User = get_user_model()


# pylint: disable=no-member
class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        """User serializer definition"""

        model = User
        fields = [
            "user_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone_number",
            "role",
            "created_at",
        ]
        read_only_fields = ["user_id", "created_at"]

    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}"

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class PropertyListSerializer(serializers.ModelSerializer):
    """Serializer for Property list view (minimal data)"""

    host_name = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        """Property List serializer definition"""

        model = Property
        fields = [
            "listing_id",
            "name",
            "location",
            "pricepernight",
            "host_name",
            "average_rating",
            "review_count",
            "created_at",
        ]

    def get_host_name(self, obj):
        """Get host's name"""
        return obj.host.get_full_name()

    def get_average_rating(self, obj):
        """Calculate the average rating for a property"""
        reviews = obj.reviews.all()
        if reviews:
            return round(sum(r.rating for r in reviews) / len(reviews), 1)
        return None

    def get_review_count(self, obj):
        """Count total reviews"""
        return obj.reviews.count()


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Serializer for Property detail view (complete data)"""

    host = UserSerializer(read_only=True)
    host_id = serializers.UUIDField(write_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    total_nights_booked = serializers.SerializerMethodField()

    class Meta:
        """Property Detail serializer definition"""

        model = Property
        fields = [
            "listing_id",
            "name",
            "description",
            "location",
            "pricepernight",
            "host",
            "host_id",
            "average_rating",
            "review_count",
            "total_nights_booked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["listing_id", "created_at", "updated_at"]

    def get_average_rating(self, obj):
        """Calculate the average rating for a property"""
        reviews = obj.reviews.all()
        if reviews:
            return round(sum(r.rating for r in reviews) / len(reviews), 1)
        return None

    def get_review_count(self, obj):
        """Count total reviews"""
        return obj.reviews.count()

    def get_total_nights_booked(self, obj):
        """Calculate total nights booked"""
        confirmed_bookings = obj.bookings.filter(status="confirmed")
        return sum(booking.total_nights for booking in confirmed_bookings)

    def validate_host_id(self, value):
        """Validate host's id"""
        try:
            host = User.objects.get(user_id=value)
            if host.role not in ["host", "admin"]:
                raise serializers.ValidationError(
                    "User must be a host or admin to create properties."
                )
        except User.DoesNotExist as exc:  # pylint: disable=no-member
            raise serializers.ValidationError("Host not found.") from exc
        return value


class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for Booking list view"""

    property_name = serializers.CharField(source="property.name", read_only=True)
    property_location = serializers.CharField(
        source="property.location", read_only=True
    )
    guest_name = serializers.CharField(source="user.get_full_name", read_only=True)
    total_nights = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()

    class Meta:
        """Booking List serialier definition"""

        model = Booking
        fields = [
            "booking_id",
            "property_name",
            "property_location",
            "guest_name",
            "guests",
            "check_in",
            "check_out",
            "total_nights",
            "total_price",
            "status",
            "created_at",
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for Booking detail view and creation"""

    property = PropertyListSerializer(read_only=True)
    listing_id = serializers.UUIDField(write_only=True)
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    total_nights = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()

    class Meta:
        """Booking Detail serializer definition"""

        model = Booking
        fields = [
            "booking_id",
            "property",
            "listing_id",
            "user",
            "user_id",
            "check_in",
            "check_out",
            "total_nights",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = ["booking_id", "created_at"]

    def validate(self, attrs):
        check_in = attrs.get("check_in")
        check_out = attrs.get("check_out")
        listing_id = attrs.get("listing_id")

        if check_in and check_out:
            if check_in >= check_out:
                raise serializers.ValidationError("End date must be after start date.")

            # Check for overlapping bookings if property is provided
            if listing_id:
                # pylint: disable=no-member
                overlapping_bookings = Booking.objects.filter(
                    listing_id=listing_id,
                    status__in=["pending", "confirmed"],
                    check_in__lt=check_in,
                    check_out__gt=check_out,
                )

                # Exclude current booking if updating
                if self.instance:
                    overlapping_bookings = overlapping_bookings.exclude(
                        booking_id=self.instance.booking_id
                    )

                if overlapping_bookings.exists():
                    raise serializers.ValidationError(
                        "Property is not available for the selected dates."
                    )

        return attrs

    def validate_user_id(self, value):
        """Validate user's id"""
        try:
            user = User.objects.get(user_id=value)
            if user.role not in ["guest", "admin"]:
                raise serializers.ValidationError("Only guests can make bookings.")
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Guest not found.") from exc
        return value

    def validate_listing_id(self, value):
        """Validate property's id"""
        try:
            Property.objects.get(listing_id=value)
        except Property.DoesNotExist as exc:
            raise serializers.ValidationError("Property not found.") from exc
        return value


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model"""

    property_name = serializers.CharField(source="property.name", read_only=True)
    reviewer_name = serializers.CharField(source="user.get_full_name", read_only=True)
    listing_id = serializers.UUIDField(write_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        """Review model serializer definition"""

        model = Review
        fields = [
            "review_id",
            "property_name",
            "reviewer_name",
            "listing_id",
            "user_id",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["review_id", "created_at"]

    def validate(self, attrs):
        listing_id = attrs.get("listing_id")
        user_id = attrs.get("user_id")

        # Check if user has a confirmed booking for this property
        if listing_id and user_id:
            has_booking = Booking.objects.filter(  # pylint: disable=no-member
                listing_id=listing_id,
                user_id=user_id,
                status="confirmed",
                end_date__lt=timezone.now().date(),  # Booking must be completed
            ).exists()

            if not has_booking:
                raise serializers.ValidationError(
                    "You can only review properties you have stayed at."
                )

        return attrs

    def validate_listing_id(self, value):
        """Validate property's id"""
        try:
            Property.objects.get(listing_id=value)  # pylint: disable=no-member
        except Property.DoesNotExist as exc:  # pylint: disable=no-member
            raise serializers.ValidationError("Property not found.") from exc
        return value

    def validate_user_id(self, value):
        """Validate user's id"""
        try:
            User.objects.get(user_id=value)
        except User.DoesNotExist as exc:  # pylint: disable=no-member
            raise serializers.ValidationError("User not found.") from exc
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""

    booking_reference = serializers.CharField(
        source="booking.booking_reference", read_only=True
    )
    property_name = serializers.CharField(
        source="booking.listing_id.name", read_only=True
    )
    customer_name = serializers.CharField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    can_retry = serializers.BooleanField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "payment_id",
            "booking",
            "booking_reference",
            "property_name",
            "transaction_id",
            "chapa_reference",
            "amount",
            "currency",
            "status",
            "payment_method",
            "first_name",
            "last_name",
            "customer_name",
            "email",
            "phone_number",
            "checkout_url",
            "is_completed",
            "is_pending",
            "can_retry",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "payment_id",
            "transaction_id",
            "chapa_reference",
            "status",
            "payment_method",
            "checkout_url",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    """Serializer for initiating payment"""

    booking_id = serializers.UUIDField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )

    def validate_booking_id(self, value):
        """Validate that booking exists and is valid for payment"""
        try:
            booking = Booking.objects.get(booking_id=value)

            # Check if booking already has a payment
            if hasattr(booking, "payment"):
                if booking.payment.status in ["pending", "success"]:
                    raise serializers.ValidationError(
                        "This booking already has a payment. "
                        f"Payment status: {booking.payment.status}"
                    )

            # Check if booking is pending
            if booking.status != "pending":
                raise serializers.ValidationError(
                    f"Payment can only be initiated for pending bookings. "
                    f"Current status: {booking.status}"
                )

            # Verify request user owns the booking
            request = self.context.get("request")
            if request and booking.user != request.user:
                raise serializers.ValidationError(
                    "You can only pay for your own bookings."
                )

        except Booking.DoesNotExist as exc:
            raise serializers.ValidationError("Booking not found.") from exc

        return value

    def create(self, validated_data):
        raise NotImplementedError("This serializer is read-only")

    def update(self, instance, validated_data):
        raise NotImplementedError("This serializer is read-only")


class VerifyPaymentSerializer(serializers.Serializer):
    """Serializer for verifying payment"""

    transaction_id = serializers.CharField(max_length=100)

    def validate_transaction_id(self, value):
        """Validate that payment exists"""
        try:
            payment = Payment.objects.get(transaction_id=value)

            # Verify request user owns the payment's booking
            request = self.context.get("request")
            if request and payment.booking.user != request.user:
                raise serializers.ValidationError(
                    "You can only verify your own payments."
                )

        except Payment.DoesNotExist as exc:
            raise serializers.ValidationError("Payment not found.") from exc

        return value

    def create(self, validated_data):
        raise NotImplementedError("This serializer is read-only")

    def update(self, instance, validated_data):
        raise NotImplementedError("This serializer is read-only")


class BookingWithPaymentSerializer(serializers.ModelSerializer):
    """Extended booking serializer with payment details"""

    property_name = serializers.CharField(source="listing_id.name", read_only=True)
    property_location = serializers.CharField(
        source="listing_id.location", read_only=True
    )
    guest_name = serializers.CharField(source="user.get_full_name", read_only=True)
    guest_email = serializers.EmailField(source="user.email", read_only=True)
    total_nights = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    booking_reference = serializers.CharField(read_only=True)
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "booking_id",
            "booking_reference",
            "user",
            "guest_name",
            "guest_email",
            "listing_id",
            "property_name",
            "property_location",
            "check_in",
            "check_out",
            "total_nights",
            "total_price",
            "status",
            "payment",
            "created_at",
        ]
        read_only_fields = ["booking_id", "booking_reference", "status", "created_at"]


class PaymentSummarySerializer(serializers.Serializer):
    """Serializer for payment summary statistics"""

    total_payments = serializers.IntegerField()
    successful_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()

    def create(self, validated_data):
        raise NotImplementedError("This serializer is read-only")

    def update(self, instance, validated_data):
        raise NotImplementedError("This serializer is read-only")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Simple token serializer that handles email login and adds user data to response
    """

    def validate(self, attrs):
        username = attrs.get("username")

        # Allow login with email instead of username
        if "@" in username:
            try:
                user = User.objects.get(email=username)
                attrs["username"] = user.username
            except User.DoesNotExist:
                # Let the parent class handle the error
                pass

        # Get the standard token response
        data = super().validate(attrs)

        # Get the user object and add custom data to response
        user = User.objects.get(username=attrs["username"])
        data.update(
            {
                "user_id": user.user_id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            }
        )

        return data

    def create(self, validated_data):
        raise NotImplementedError("This serializer is read-only")

    def update(self, instance, validated_data):
        raise NotImplementedError("This serializer is read-only")
