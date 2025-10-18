"""Module import for listings.views"""

from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (
    PropertyViewSet,
    BookingViewSet,
    UserViewSet,
    ReviewViewSet,
    InitiatePaymentView,
    VerifyPaymentView,
    chapa_callback,
    chapa_payment_status,
    PaymentDetailView,
    UserPaymentsListView,
    UserBookingsWithPaymentView,
    PaymentSummaryView,
    RetryPaymentView,
    CancelPaymentView,
)

router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"users", UserViewSet, basename="user")

APP_NAME = "listings"

urlpatterns = [
    path("", include(router.urls)),
    # JWT Authentication endpoints
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Payment endpoints
    path(
        "payments/initiate/", InitiatePaymentView.as_view(), name="initiate-payment"
    ),
    path("payments/verify/", VerifyPaymentView.as_view(), name="verify-payment"),
    path("payments/callback/", chapa_callback, name="payment-callback"),
    path("payments/summary/", PaymentSummaryView.as_view(), name="payment-summary"),
    path(
        "payments/<str:transaction_id>/",
        PaymentDetailView.as_view(),
        name="payment-detail",
    ),
    path(
        "payments/<str:transaction_id>/retry/",
        RetryPaymentView.as_view(),
        name="retry-payment",
    ),
    path(
        "payments/<str:transaction_id>/cancel/",
        CancelPaymentView.as_view(),
        name="cancel-payment",
    ),
    path("payments/", UserPaymentsListView.as_view(), name="user-payments"),
    path("bookings/<uuid:booking_id>/payment-status/", chapa_payment_status, name="payment-status"),
    # Booking with payment info
    path(
        "bookings/with-payments/",
        UserBookingsWithPaymentView.as_view(),
        name="bookings-with-payments",
    ),
]
