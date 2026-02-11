"""Shared test fixtures for sushi_scout tests."""

import pytest


# Sample Google Places API response (based on real SF test data)
SAMPLE_PLACES_RESPONSE = {
    "places": [
        {
            "id": "ChIJ86TLv5GAhYARdhd8cNsVbe8",
            "displayName": {"text": "Mensho Tokyo SF"},
            "formattedAddress": "672 Geary St, San Francisco, CA 94102, USA",
            "location": {"latitude": 37.7864, "longitude": -122.4134},
            "rating": 4.5,
            "userRatingCount": 3158,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "priceRange": {
                "startPrice": {"currencyCode": "USD", "units": "20"},
                "endPrice": {"currencyCode": "USD", "units": "30"},
            },
            "types": ["japanese_restaurant", "ramen_restaurant"],
        },
        {
            "id": "ChIJsYdOvCx-j4ARJItjWBikyOk",
            "displayName": {"text": "Marufuku Ramen"},
            "formattedAddress": "1581 Webster St #235, San Francisco, CA 94115, USA",
            "location": {"latitude": 37.7853, "longitude": -122.4316},
            "rating": 4.5,
            "userRatingCount": 2923,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "priceRange": {
                "startPrice": {"currencyCode": "USD", "units": "20"},
                "endPrice": {"currencyCode": "USD", "units": "30"},
            },
            "types": ["japanese_restaurant", "ramen_restaurant"],
        },
        {
            "id": "ChIJRintaro_fake_id",
            "displayName": {"text": "Rintaro"},
            "formattedAddress": "82 14th St, San Francisco, CA 94103, USA",
            "location": {"latitude": 37.7685, "longitude": -122.4155},
            "rating": 4.6,
            "userRatingCount": 1500,
            "priceLevel": "PRICE_LEVEL_EXPENSIVE",
            "priceRange": {
                "startPrice": {"currencyCode": "USD", "units": "100"},
            },
            "types": ["japanese_restaurant"],
        },
    ]
}

# Sample place detail response
SAMPLE_PLACE_DETAIL = {
    "id": "ChIJ86TLv5GAhYARdhd8cNsVbe8",
    "displayName": {"text": "Mensho Tokyo SF"},
    "formattedAddress": "672 Geary St, San Francisco, CA 94102, USA",
    "location": {"latitude": 37.7864, "longitude": -122.4134},
    "rating": 4.5,
    "userRatingCount": 3158,
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "priceRange": {
        "startPrice": {"currencyCode": "USD", "units": "20"},
        "endPrice": {"currencyCode": "USD", "units": "30"},
    },
    "delivery": True,
    "takeout": True,
    "dineIn": True,
    "websiteUri": "https://mensho.com/",
    "googleMapsUri": "https://maps.google.com/?cid=12345",
    "primaryType": "ramen_restaurant",
    "editorialSummary": {
        "text": "American spin-off of Tokyo's standout ramen brand.",
    },
    "currentOpeningHours": {
        "weekdayDescriptions": [
            "Monday: 11:30 AM - 9:00 PM",
            "Tuesday: 11:30 AM - 9:00 PM",
        ],
    },
    "reviews": [
        {
            "rating": 5,
            "text": {"text": "Amazing ramen with tuna appetizers!"},
            "relativePublishTimeDescription": "a week ago",
        },
        {
            "rating": 4,
            "text": {"text": "Great service, a bit pricey though."},
            "relativePublishTimeDescription": "2 weeks ago",
        },
    ],
}


@pytest.fixture
def sample_places_response():
    """Return a sample Google Places API nearby search response."""
    return SAMPLE_PLACES_RESPONSE


@pytest.fixture
def sample_place_detail():
    """Return a sample Google Places API place detail response."""
    return SAMPLE_PLACE_DETAIL


@pytest.fixture
def sample_restaurants():
    """Return a list of formatted restaurant dicts (as returned by search tool)."""
    return [
        {
            "id": "ChIJ86TLv5GAhYARdhd8cNsVbe8",
            "name": "Mensho Tokyo SF",
            "address": "672 Geary St, San Francisco, CA 94102, USA",
            "latitude": 37.7864,
            "longitude": -122.4134,
            "rating": 4.5,
            "review_count": 3158,
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "price_range_high": 30,
            "delivery": True,
            "types": ["japanese_restaurant"],
        },
        {
            "id": "ChIJsYdOvCx-j4ARJItjWBikyOk",
            "name": "Marufuku Ramen",
            "address": "1581 Webster St, San Francisco, CA 94115, USA",
            "latitude": 37.7853,
            "longitude": -122.4316,
            "rating": 4.5,
            "review_count": 2923,
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "price_range_high": 30,
            "delivery": True,
            "types": ["japanese_restaurant"],
        },
        {
            "id": "ChIJRintaro_fake_id",
            "name": "Rintaro",
            "address": "82 14th St, San Francisco, CA 94103, USA",
            "latitude": 37.7685,
            "longitude": -122.4155,
            "rating": 4.6,
            "review_count": 1500,
            "price_level": "PRICE_LEVEL_EXPENSIVE",
            "price_range_low": 100,
            "price_range_high": None,
            "delivery": False,
            "types": ["japanese_restaurant"],
        },
    ]
