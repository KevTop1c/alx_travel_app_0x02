import json
from django.contrib import admin
from django.utils.html import format_html

# from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils import timezone

from .services.chapa_service import ChapaPaymentService
from .models import Property, Booking, Payment, User


# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    model = User
    list_display = ("email", "username", "is_staff", "is_active", "role")
    list_filter = ("is_staff", "is_active")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                    "first_name",
                    "last_name",
                    "phone_number",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "role",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)

    # def user_link(self, obj):
    #     url = reverse("admin:listings_user_change", args=[obj.user.user_id])
    #     return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())

    # user_link.short_description = "Username"


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "host_link", "pricepernight", "created_at"]
    search_fields = ["name", "location", "description"]
    list_filter = ["location", "created_at"]
    ordering = ["-created_at"]
    readonly_fields = ["listing_id", "created_at", "updated_at"]

    def host_link(self, obj):
        url = reverse("admin:listings_user_change", args=[obj.host.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.host.get_full_name())

    host_link.short_description = "Host"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "booking_reference",
        "user_link",
        "property_link",
        "check_in",
        "check_out",
        "guests",
        "total_nights",
        "total_price_display",
        "status_badge",
        "payment_status_badge",
        "created_at",
    ]
    list_filter = ["status", "created_at", "check_in"]
    search_fields = [
        "booking_id",
        "user__email",
        "user__first_name",
        "user__last_name",
        "listing_id__name",
    ]
    readonly_fields = [
        "booking_id",
        "booking_reference",
        "total_nights",
        "total_price",
        "created_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Booking Information",
            {
                "fields": (
                    "booking_id",
                    "booking_reference",
                    "user",
                    "guests",
                    "listing_id",
                    "status",
                )
            },
        ),
        ("Dates", {"fields": ("check_in", "check_out", "total_nights")}),
        ("Pricing", {"fields": ("total_price",)}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def user_link(self, obj):
        url = reverse("admin:listings_user_change", args=[obj.user.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())

    user_link.short_description = "Guest"

    def property_link(self, obj):
        url = reverse(
            "admin:listings_property_change", args=[obj.listing_id.listing_id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.listing_id.name)

    property_link.short_description = "Property"

    def total_price_display(self, obj):
        return f"ETB {obj.total_price}"

    total_price_display.short_description = "Total Price"

    def status_badge(self, obj):
        colors = {
            "pending": "#FFA500",
            "confirmed": "#28A745",
            "canceled": "#DC3545",
        }
        color = colors.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    def payment_status_badge(self, obj):
        if hasattr(obj, "payment"):
            payment_status = obj.payment.status
            colors = {
                "pending": "#FFA500",
                "success": "#28A745",
                "failed": "#DC3545",
                "cancelled": "#6C757D",
            }
            color = colors.get(payment_status, "#6C757D")
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">{}</span>',
                color,
                payment_status.upper(),
            )
        return format_html('<span style="color: #6C757D;">No Payment</span>')

    payment_status_badge.short_description = "Payment Status"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "transaction_id",
        "booking_link",
        "customer_name",
        "amount_display",
        "status_badge",
        "payment_method",
        "created_at",
    ]
    list_filter = ["status", "currency", "created_at", "payment_method"]
    search_fields = [
        "transaction_id",
        "chapa_reference",
        "email",
        "first_name",
        "last_name",
        "booking__booking_reference",
    ]
    readonly_fields = [
        "transaction_id",
        "chapa_reference",
        "checkout_url_link",
        "chapa_response_display",
        "created_at",
        "updated_at",
        "completed_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Payment Information",
            {
                "fields": (
                    "transaction_id",
                    "chapa_reference",
                    "booking",
                    "status",
                    "payment_method",
                )
            },
        ),
        ("Amount Details", {"fields": ("amount", "currency")}),
        (
            "Customer Information",
            {"fields": ("first_name", "last_name", "email", "phone_number")},
        ),
        (
            "Chapa Integration",
            {
                "fields": ("checkout_url_link", "chapa_response_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["verify_payments", "mark_as_failed"]

    def booking_link(self, obj):
        url = reverse("admin:listings_booking_change", args=[obj.booking.id])
        return format_html('<a href="{}">{}</a>', url, obj.booking.booking_reference)

    booking_link.short_description = "Booking"

    def customer_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    customer_name.short_description = "Customer"

    def amount_display(self, obj):
        return f"{obj.currency} {obj.amount}"

    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {
            "pending": "#FFA500",
            "success": "#28A745",
            "failed": "#DC3545",
            "cancelled": "#6C757D",
        }
        color = colors.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    def checkout_url_link(self, obj):
        if obj.checkout_url:
            return format_html(
                '<a href="{}" target="_blank">Open Checkout Page</a>', obj.checkout_url
            )
        return "-"

    checkout_url_link.short_description = "Checkout URL"

    def chapa_response_display(self, obj):
        if obj.chapa_response:
            formatted_json = json.dumps(obj.chapa_response, indent=2)
            return format_html(
                '<pre style="background-color: #f5f5f5; padding: 10px; '
                'border-radius: 5px; overflow: auto; max-height: 400px;">{}</pre>',
                formatted_json,
            )
        return "-"

    chapa_response_display.short_description = "Chapa Response"

    def verify_payments(self, request, queryset):
        """Admin action to verify selected payments"""

        chapa_service = ChapaPaymentService()
        verified_count = 0

        for payment in queryset.filter(status="pending"):
            result = chapa_service.verify_payment(payment.transaction_id)

            if result["success"]:
                data = result["data"]
                payment_status = data.get("status", "").lower()

                payment.chapa_response = data
                payment.payment_method = data.get("payment_method", "")

                if payment_status == "success":
                    payment.status = "success"
                    payment.completed_at = timezone.now()
                    payment.booking.status = "confirmed"
                    payment.booking.save()
                    verified_count += 1
                elif payment_status == "failed":
                    payment.status = "failed"

                payment.save()

        self.message_user(
            request, f"{verified_count} payment(s) verified successfully."
        )

    verify_payments.short_description = "Verify selected payments with Chapa"

    def mark_as_failed(self, request, queryset):
        """Admin action to mark payments as failed"""
        updated = queryset.update(status="failed")
        self.message_user(request, f"{updated} payment(s) marked as failed.")

    mark_as_failed.short_description = "Mark selected payments as failed"


# Customize admin site header
admin.site.site_header = "Booking Management System"
admin.site.site_title = "Booking Admin"
admin.site.index_title = "Welcome to Booking Management"
