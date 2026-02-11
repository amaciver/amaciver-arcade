"""Tests for the restaurant search tools (pure formatting functions, no API calls)."""

from sushi_scout.tools.search import (
    _format_restaurant,
    _format_restaurant_details,
    _miles_to_meters,
)


class TestMilesToMeters:
    """Test distance conversion utility."""

    def test_one_mile(self):
        assert _miles_to_meters(1.0) == 1609

    def test_two_miles(self):
        assert _miles_to_meters(2.0) == 3218

    def test_zero_miles(self):
        assert _miles_to_meters(0.0) == 0

    def test_clamped_to_max(self):
        """Should not exceed Google's 50000m limit."""
        assert _miles_to_meters(100.0) == 50000

    def test_fractional_miles(self):
        assert _miles_to_meters(0.5) == 804


class TestFormatRestaurant:
    """Test formatting Google Places API results into clean dicts."""

    def test_formats_complete_place(self, sample_places_response):
        """Should extract all fields from a complete Places API result."""
        place = sample_places_response["places"][0]
        result = _format_restaurant(place, 0)

        assert result["id"] == "ChIJ86TLv5GAhYARdhd8cNsVbe8"
        assert result["name"] == "Mensho Tokyo SF"
        assert result["address"] == "672 Geary St, San Francisco, CA 94102, USA"
        assert result["latitude"] == 37.7864
        assert result["longitude"] == -122.4134
        assert result["rating"] == 4.5
        assert result["review_count"] == 3158
        assert result["price_level"] == "PRICE_LEVEL_MODERATE"
        assert result["price_range_low"] == 20
        assert result["price_range_high"] == 30

    def test_handles_missing_price_range(self):
        """Should handle places without price data."""
        place = {
            "id": "test_id",
            "displayName": {"text": "No Price Restaurant"},
            "formattedAddress": "123 Main St",
            "location": {"latitude": 37.0, "longitude": -122.0},
        }
        result = _format_restaurant(place, 0)

        assert result["name"] == "No Price Restaurant"
        assert result["price_level"] is None
        assert result["price_range_low"] is None
        assert result["price_range_high"] is None

    def test_handles_empty_place(self):
        """Should handle completely empty place data gracefully."""
        result = _format_restaurant({}, 0)

        assert result["id"] == ""
        assert result["name"] == "Unknown"
        assert result["rating"] is None
        assert result["price_range_low"] is None

    def test_formats_all_places_in_response(self, sample_places_response):
        """Should correctly format all places from a search response."""
        places = sample_places_response["places"]
        results = [_format_restaurant(p, i) for i, p in enumerate(places)]

        assert len(results) == 3
        assert results[0]["name"] == "Mensho Tokyo SF"
        assert results[1]["name"] == "Marufuku Ramen"
        assert results[2]["name"] == "Rintaro"


class TestFormatRestaurantDetails:
    """Test formatting detailed place data."""

    def test_formats_complete_details(self, sample_place_detail):
        """Should extract all detail fields."""
        result = _format_restaurant_details(sample_place_detail)

        assert result["name"] == "Mensho Tokyo SF"
        assert result["delivery"] is True
        assert result["takeout"] is True
        assert result["dine_in"] is True
        assert result["website"] == "https://mensho.com/"
        assert result["primary_type"] == "ramen_restaurant"
        assert "spin-off" in result["summary"]

    def test_formats_reviews(self, sample_place_detail):
        """Should extract and format reviews."""
        result = _format_restaurant_details(sample_place_detail)

        assert len(result["reviews"]) == 2
        assert result["reviews"][0]["rating"] == 5
        assert "tuna" in result["reviews"][0]["text"].lower()
        assert result["reviews"][0]["time"] == "a week ago"

    def test_formats_hours(self, sample_place_detail):
        """Should extract opening hours."""
        result = _format_restaurant_details(sample_place_detail)

        assert len(result["hours"]) == 2
        assert "Monday" in result["hours"][0]

    def test_handles_missing_details(self):
        """Should handle place data with minimal fields."""
        place = {
            "displayName": {"text": "Bare Minimum"},
            "formattedAddress": "456 Oak Ave",
        }
        result = _format_restaurant_details(place)

        assert result["name"] == "Bare Minimum"
        assert result["delivery"] is None
        assert result["website"] is None
        assert result["reviews"] == []
        assert result["hours"] == []
        assert result["summary"] is None

    def test_reviews_capped_at_three(self):
        """Should return at most 3 reviews even if more are available."""
        place = {
            "displayName": {"text": "Popular Place"},
            "reviews": [
                {"rating": 5, "text": {"text": f"Review {i}"}}
                for i in range(10)
            ],
        }
        result = _format_restaurant_details(place)
        assert len(result["reviews"]) == 3
