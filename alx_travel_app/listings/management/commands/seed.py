"""Modules for seed data"""

import random
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from listings.models import User, Property, Booking, Review


class Command(BaseCommand):
    """Custom Django management command executed via `manage.py`."""

    help = "Seed the database with sample data for listing app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=20,
            help="Number of users to create (default: 20)",
        )
        parser.add_argument(
            "--properties",
            type=int,
            default=15,
            help="Number of users to create (default: 15)",
        )
        parser.add_argument(
            "--bookings",
            type=int,
            default=30,
            help="Number of users to create (default: 30)",
        )
        parser.add_argument(
            "--reviews",
            type=int,
            default=25,
            help="Number of users to create (default: 25)",
        )
        parser.add_argument(
            "--clear",
            type=int,
            default=30,
            help="Clear existing data before seeding",
        )

    # pylint: disable=no-member
    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            with transaction.atomic():
                Review.objects.all().delete()
                Booking.objects.all().delete()
                Property.objects.all().delete()
                User.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("✓ Existing data cleared"))

        try:
            with transaction.atomic():
                # Create users
                self.stdout.write("Creating users...")
                users = self.create_user(options["users"])
                self.stdout.write(self.style.SUCCESS(f"✓ Created {len(users)} users"))

                # Create properties
                self.stdout.write("Creating properties...")
                properties = self.create_properties(users, options["properties"])
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created {len(properties)} properties")
                )

                # Create bookings
                self.stdout.write("Creating bookings...")
                bookings = self.create_bookings(users, properties, options["bookings"])
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created {len(bookings)} bookings")
                )

                # Create reviews
                self.stdout.write("Creating reviews...")
                reviews = self.create_reviews(
                    users, properties, bookings, options["reviews"]
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created {len(reviews)} reviews")
                )

                self.stdout.write(
                    self.style.SUCCESS("\n**Database seeding completed successfully!**")
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error during seeding: {str(e)}"))
            raise

        self.stdout.write(
            self.style.SUCCESS("\n🎉 Database seeding completed successfully!")
        )

    def create_user(self, count):
        """Create sample users with different roles"""

        first_names = [
            "John",
            "Jane",
            "Mike",
            "Sarah",
            "David",
            "Lisa",
            "Chris",
            "Emma",
            "Alex",
            "Maria",
            "James",
            "Anna",
            "Robert",
            "Laura",
            "Kevin",
            "Sophie",
            "Daniel",
            "Rachel",
            "Mark",
            "Jennifer",
            "Paul",
            "Amy",
            "Steven",
            "Nicole",
        ]

        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
            "Hernandez",
            "Lopez",
            "Gonzalez",
            "Wilson",
            "Anderson",
            "Thomas",
            "Taylor",
            "Moore",
            "Jackson",
            "Martin",
        ]

        users = []

        # Create admin user
        admin_user = User.objects.create(
            first_name="Admin",
            last_name="User",
            email="admin@example.com",
            password=make_password("admin123"),
            phone_number="+1234567890",
            role="admin",
        )
        users.append(admin_user)

        # Create regular users
        for i in range(count - 1):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            role = random.choices(["guest", "host"], weights=[70, 30])[
                0
            ]  # 70% guests 30% hosts

            user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=f"{first_name.lower()}.{last_name.lower()}{i}@example.com",
                password=make_password("password123"),
                phone_number=f"+123456{random.randint(1000, 9999)}",
                role=role,
            )
            users.append(user)

        return users

    def create_properties(self, users, count):
        """Create sample data for properties"""

        hosts = [user for user in users if user.role in ["host", "admin"]]

        property_data = [
            {
                "name": "Cozy Downtown Apartment",
                "description": "Beautiful 2-bedroom apartment in the heart of the city with modern amenities and great views.",
                "location": "New York, NY",
                "price": Decimal("125.00"),
            },
            {
                "name": "Beachfront Villa",
                "description": "Stunning oceanfront villa with private beach access, perfect for a relaxing getaway.",
                "location": "Miami, FL",
                "price": Decimal("350.00"),
            },
            {
                "name": "Mountain Cabin Retreat",
                "description": "Rustic cabin nestled in the mountains, ideal for nature lovers and outdoor enthusiasts.",
                "location": "Denver, CO",
                "price": Decimal("180.00"),
            },
            {
                "name": "Historic Brownstone",
                "description": "Charming historic brownstone in a quiet neighborhood with vintage charm and modern updates.",
                "location": "Boston, MA",
                "price": Decimal("200.00"),
            },
            {
                "name": "Modern Loft",
                "description": "Sleek and stylish loft in the arts district with exposed brick and industrial design.",
                "location": "Chicago, IL",
                "price": Decimal("165.00"),
            },
            {
                "name": "Suburban Family Home",
                "description": "Spacious family home with large backyard, perfect for families with children.",
                "location": "Austin, TX",
                "price": Decimal("140.00"),
            },
            {
                "name": "Luxury Penthouse",
                "description": "Premium penthouse suite with panoramic city views and top-tier amenities.",
                "location": "San Francisco, CA",
                "price": Decimal("500.00"),
            },
            {
                "name": "Cozy Studio",
                "description": "Compact but comfortable studio apartment, perfect for solo travelers or couples.",
                "location": "Seattle, WA",
                "price": Decimal("85.00"),
            },
            {
                "name": "Lakeside Cottage",
                "description": "Peaceful cottage by the lake with kayak access and beautiful sunset views.",
                "location": "Lake Tahoe, CA",
                "price": Decimal("220.00"),
            },
            {
                "name": "Urban Townhouse",
                "description": "Modern townhouse in trendy neighborhood with easy access to restaurants and shopping.",
                "location": "Portland, OR",
                "price": Decimal("175.00"),
            },
        ]

        properties = []

        for i in range(count):
            property_info = property_data[i % len(property_data)]
            host = random.choice(hosts)

            # Add some variatioin to repeated properties
            variation = i // len(property_data)
            name = property_info["name"]
            if variation > 0:
                name += f" #{variation + 1}"

            property_obj = Property.objects.create(
                host=host,
                name=name,
                description=property_info["description"],
                location=property_info["location"],
                pricepernight=property_info["price"]
                + Decimal(random.randint(-50, 100)),
            )
            properties.append(property_obj)

        return properties

    def create_bookings(self, users, properties, count):
        """Create sample data for booking"""

        guests = [user for user in users if user.role in ["guest", "admin"]]
        statuses = ["pending", "confirmed", "canceled"]
        status_weights = [20, 70, 10]  # 70% confirmed, 20% pending, 10% canceled

        bookings = []

        for _ in range(count):
            guest = random.choice(guests)
            property_obj = random.choice(properties)

            # Generate random dates (some in past, some in future)
            days_offset = random.randint(-180, 180)  # 6 months before, 6 months after
            start_date = date.today() + timedelta(days=days_offset)
            end_date = start_date + timedelta(
                days=random.randint(1, 14)
            )  # 1 to 14 night stays

            status = random.choices(statuses, weights=status_weights)[0]

            # Check for overlapping bookings to avoid conflicts
            overlapping = Booking.objects.filter(
                property_obj=property_obj,
                status__in=["pending", "confirmed"],
                start_date__lt=end_date,
                end_date__gt=start_date,
            ).exists()

            if not overlapping:
                booking = Booking.objects.create(
                    property_obj=property_obj,
                    user=guest,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                )
                bookings.append(booking)

        return bookings

    def create_reviews(self, users, properties, bookings, count):
        """Create sample reviews"""
        # Only create reviews for past confirmed bookings
        past_confirmed_bookings = [
            b for b in bookings if b.status == "confirmed" and b.end_date < date.today()
        ]

        if not past_confirmed_bookings:
            return []

        review_comments = [
            "Amazing property! Clean, comfortable, and exactly as described. Highly recommend!",
            "Great location and wonderful host. Would definitely stay here again.",
            "Beautiful place with fantastic amenities. Perfect for our weekend getaway.",
            "The property exceeded our expectations. Everything was perfect!",
            "Good value for money. The location was convenient and the space was clean.",
            "Lovely property in a quiet neighborhood. Very peaceful and relaxing.",
            "Host was very responsive and helpful. The property was well-maintained.",
            "Perfect for our family vacation. Kids loved the space and amenities.",
            "Decent place but could use some updates. Overall a pleasant stay.",
            "Outstanding property! Will definitely book again in the future.",
            "Clean and comfortable. Great communication from the host throughout.",
            "The property was good but not exceptional. Average experience overall.",
            "Fantastic location! Walking distance to everything we wanted to see.",
            "Beautiful property with stunning views. Highly recommended!",
            "Good property but a bit pricey for what you get. Still enjoyable though.",
        ]

        reviews = []
        created_reviews = set()  # Track (property, user) pairs to avoid duplicates

        for _ in range(min(count, len(past_confirmed_bookings))):
            booking = random.choice(past_confirmed_bookings)

            # Pick explicitly from provided users and properties
            user = booking.user if booking.user in users else random.choice(users)
            prop = (
                booking.property_obj
                if booking.property_obj in properties
                else random.choice(properties)
            )

            review_key = (prop.property_obj_id, user.user_id)
            if review_key in created_reviews:
                continue

            rating = random.choices([1, 2, 3, 4, 5], weights=[5, 5, 15, 35, 40])[0]

            review = Review.objects.create(
                property_obj=prop,
                user=user,
                rating=rating,
                comment=random.choice(review_comments),
            )
            reviews.append(review)
            created_reviews.add(review_key)

        return reviews
