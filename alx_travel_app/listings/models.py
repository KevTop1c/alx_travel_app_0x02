"""Module imports for model creation"""

import uuid
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator


# pylint: disable=no-member
# pylint: disable=missing-function-docstring
class UserManager(BaseUserManager):
    """Manager for custom User model using email instead of username"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model matching the SQL schema"""

    ROLE_CHOICES = [
        ("guest", "Guest"),
        ("host", "Host"),
        ("admin", "Admin"),
    ]

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="guest")
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    # Override username field since we're using email
    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        """User table definition"""

        db_table = "user"
        indexes = [
            models.Index(fields=["email"], name="idx_user_email"),
        ]

    @property
    def id(self):
        return self.user_id

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Return the user's first name."""
        return self.first_name


class Property(models.Model):
    """Property model matching the SQL schema"""

    listing_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    host = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="properties",
        db_column="host_id",
    )
    name = models.CharField(max_length=150)
    description = models.TextField()
    location = models.CharField(max_length=255)
    pricepernight = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Property table definition"""

        db_table = "property"
        indexes = [
            models.Index(fields=["host"], name="idx_property_host"),
            models.Index(fields=["listing_id"], name="idx_property_id"),
            models.Index(fields=["location"], name="idx_property_location"),
        ]

    def __str__(self):
        return f"{self.name} - {self.location}"


def generate_booking_reference():
    """Custom booking reference"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"BOOKING-{date_str}-{random_part}"


class Booking(models.Model):
    """Booking model matching the SQL schema"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("canceled", "Canceled"),
    ]

    booking_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    booking_reference = models.CharField(
        max_length=100,
        unique=True,
        default=generate_booking_reference,
    )
    listing_id = models.ForeignKey(
        "Property",
        on_delete=models.CASCADE,
        related_name="bookings",
        db_column="property_id",
    )
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="bookings",
        db_column="user_id",
    )
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Booking table definition"""

        db_table = "booking"
        indexes = [
            models.Index(fields=["listing_id"], name="idx_booking_property"),
            models.Index(fields=["user"], name="idx_booking_user"),
        ]

    def clean(self):

        if self.check_in and self.check_out and self.check_in >= self.check_out:
            raise ValidationError("End date must be after start date.")

    @property
    def total_nights(self):
        """Calculating number of nights"""
        if self.check_in and self.check_out:
            return (self.check_out - self.check_in).days
        return 0

    @property
    def total_price(self):
        """Calculating total price"""
        # pylint: disable=no-member
        return self.total_nights * self.listing_id.pricepernight

    def __str__(self):
        return f"#{self.booking_id} - {self.listing_id.name} ({self.check_in} to {self.check_out})"


class Review(models.Model):
    """Review model matching the SQL schema"""

    review_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing_id = models.ForeignKey(
        "Property",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="property_id",
    )
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="user_id",
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Review table definition"""

        db_table = "review"
        indexes = [
            models.Index(fields=["listing_id"], name="idx_review_property"),
            models.Index(fields=["user"], name="idx_review_user"),
        ]
        # Ensure one review per user per property
        unique_together = ["listing_id", "user"]

    def __str__(self):
        # pylint: disable=no-member
        return f"Review by {self.user.first_name} for {self.listing_id.name} - {self.rating} stars"


class Payment(models.Model):
    """Payment model for Chapa integration"""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    CURRENCY_CHOICES = [
        ("ETB", "Ethiopian Birr"),
        ("USD", "US Dollar"),
    ]

    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        "Booking",
        on_delete=models.CASCADE,
        related_name="payment",
        db_column="booking_id",
    )
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="Unique transaction reference for this payment",
    )
    chapa_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Reference returned by Chapa API",
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default="ETB")
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Payment method used (e.g., Mobile Money, Card)",
    )

    # Customer information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Chapa integration fields
    checkout_url = models.URLField(
        blank=True,
        null=True,
        help_text="Chapa checkout page URL",
    )
    chapa_response = models.JSONField(
        blank=True,
        null=True,
        help_text="Full response from Chapa API",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        blank=True, null=True, help_text="Timestamp when payment was completed"
    )

    class Meta:
        """Payment table definition"""

        db_table = "payment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["transaction_id"], name="idx_payment_txn"),
            models.Index(fields=["status"], name="idx_payment_status"),
            models.Index(fields=["chapa_reference"], name="idx_payment_chapa_ref"),
            models.Index(fields=["booking"], name="idx_payment_booking"),
            models.Index(fields=["email"], name="idx_payment_email"),
        ]

        # ✅ Added database-level constraint for safety
        constraints = [
            models.UniqueConstraint(
                fields=["booking"], name="unique_payment_per_booking"
            )
        ]

    def save(self, *args, **kwargs):
        """Generate transaction ID on creation"""
        if not self.transaction_id:
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)

    # ✅ Improved validation with decimal tolerance
    def clean(self):
        if self.booking.booking_id and abs(
            self.amount - Decimal(self.booking.total_price)
        ) > Decimal("0.01"):
            raise ValidationError(
                f"Payment amount ({self.amount}) must approximately match booking total ({self.booking.total_price})"
            )

    @property
    def customer_name(self):
        """Get full customer name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_completed(self):
        """Check if payment is completed"""
        return self.status == "success"

    @property
    def is_pending(self):
        """Check if payment is pending"""
        return self.status == "pending"

    @property
    def can_retry(self):
        """Check if payment can be retried"""
        return self.status in ["failed", "cancelled"]

    @property
    def status_label(self):
        """Return human-readable status"""
        return self.get_status_display()

    def mark_as_success(self):
        """Mark payment and booking as successful"""
        now = timezone.now()
        self.status = "success"
        self.completed_at = now
        self.save(update_fields=["status", "completed_at", "updated_at"])

        # Confirm booking
        self.booking.status = "confirmed"
        self.booking.save(update_fields=["status"])

    # ✅ Enhanced failure and cancel handlers
    def mark_as_failed(self, reason=None):
        """Mark payment as failed"""
        self.status = "failed"
        self.save(update_fields=["status", "updated_at"])
        if reason:
            self.chapa_response = {"failure_reason": reason}
            self.save(update_fields=["chapa_response"])

    def mark_as_cancelled(self):
        """Mark payment as cancelled"""
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status} ({self.amount} {self.currency})"
