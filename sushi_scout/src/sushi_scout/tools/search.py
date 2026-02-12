"""Restaurant search tools using Google Places API.

Uses GOOGLE_PLACES_API_KEY (via requires_secrets) for Places API calls.
Google Maps APIs authenticate with API keys, not OAuth tokens, and the
cloud-platform scope isn't in Arcade's default Google provider anyway.

Arcade Google OAuth is demonstrated separately via get_user_profile,
which uses the supported userinfo.email scope.
"""

from typing import Annotated, Any

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Google

PLACES_BASE_URL = "https://places.googleapis.com/v1/places"

# Fields to request from Google Places API
SEARCH_FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.priceRange",
    "places.types",
]

DETAIL_FIELDS = [
    "displayName",
    "formattedAddress",
    "location",
    "rating",
    "userRatingCount",
    "priceLevel",
    "priceRange",
    "websiteUri",
    "googleMapsUri",
    "currentOpeningHours",
    "delivery",
    "dineIn",
    "takeout",
    "primaryType",
    "editorialSummary",
    "reviews",
]


def _miles_to_meters(miles: float) -> int:
    """Convert miles to meters, clamped to Google's max radius of 50000m."""
    return min(int(miles * 1609.34), 50000)


def _format_restaurant(place: dict[str, Any], index: int) -> dict[str, Any]:
    """Format a Places API result into a clean restaurant dict."""
    price_range = place.get("priceRange", {})
    start = price_range.get("startPrice", {})
    end = price_range.get("endPrice", {})

    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", "Unknown"),
        "address": place.get("formattedAddress", ""),
        "latitude": place.get("location", {}).get("latitude"),
        "longitude": place.get("location", {}).get("longitude"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount", 0),
        "price_level": place.get("priceLevel"),
        "price_range_low": int(start.get("units", 0)) if start else None,
        "price_range_high": int(end.get("units", 0)) if end else None,
        "types": place.get("types", []),
    }


def _format_restaurant_details(place: dict[str, Any]) -> dict[str, Any]:
    """Format detailed place data into a clean restaurant dict."""
    price_range = place.get("priceRange", {})
    start = price_range.get("startPrice", {})
    end = price_range.get("endPrice", {})

    hours = place.get("currentOpeningHours", {})
    weekday_descriptions = hours.get("weekdayDescriptions", [])

    reviews_raw = place.get("reviews", [])
    reviews = [
        {
            "rating": r.get("rating"),
            "text": r.get("text", {}).get("text", ""),
            "time": r.get("relativePublishTimeDescription", ""),
        }
        for r in reviews_raw[:3]
    ]

    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", "Unknown"),
        "address": place.get("formattedAddress", ""),
        "latitude": place.get("location", {}).get("latitude"),
        "longitude": place.get("location", {}).get("longitude"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount", 0),
        "price_level": place.get("priceLevel"),
        "price_range_low": int(start.get("units", 0)) if start else None,
        "price_range_high": int(end.get("units", 0)) if end else None,
        "delivery": place.get("delivery"),
        "takeout": place.get("takeout"),
        "dine_in": place.get("dineIn"),
        "website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "hours": weekday_descriptions,
        "summary": place.get("editorialSummary", {}).get("text"),
        "primary_type": place.get("primaryType"),
        "reviews": reviews,
    }


@tool(requires_secrets=["GOOGLE_PLACES_API_KEY"])
async def search_nearby_restaurants(
    context: Context,
    latitude: Annotated[float, "Latitude of the search center"],
    longitude: Annotated[float, "Longitude of the search center"],
    radius_miles: Annotated[float, "Search radius in miles (max ~31)"] = 2.0,
) -> Annotated[dict, "List of nearby sushi/Japanese restaurants with metadata"]:
    """Search for sushi and Japanese restaurants near a location.

    Returns restaurants with ratings, price ranges, and location data.
    Use this as the first step to find cheap tuna rolls nearby.
    """
    api_key = context.get_secret("GOOGLE_PLACES_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(SEARCH_FIELDS),
    }

    payload = {
        "includedTypes": ["japanese_restaurant", "sushi_restaurant"],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": _miles_to_meters(radius_miles),
            }
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PLACES_BASE_URL}:searchNearby",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    places = data.get("places", [])
    restaurants = [_format_restaurant(p, i) for i, p in enumerate(places)]

    return {
        "count": len(restaurants),
        "radius_miles": radius_miles,
        "center": {"latitude": latitude, "longitude": longitude},
        "restaurants": restaurants,
    }


@tool(requires_secrets=["GOOGLE_PLACES_API_KEY"])
async def get_restaurant_details(
    context: Context,
    place_id: Annotated[str, "Google Places ID of the restaurant"],
) -> Annotated[dict, "Detailed restaurant information including hours and reviews"]:
    """Get detailed information about a specific restaurant.

    Returns delivery availability, hours, reviews, and more.
    Use this after search_nearby_restaurants to get details for a specific place.
    """
    api_key = context.get_secret("GOOGLE_PLACES_API_KEY")
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(DETAIL_FIELDS),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PLACES_BASE_URL}/{place_id}",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return _format_restaurant_details(data)


@tool(
    requires_auth=Google(
        scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"]
    )
)
async def get_user_profile(
    context: Context,
) -> Annotated[dict, "Authenticated user's Google profile information"]:
    """Get the authenticated user's Google profile.

    Demonstrates Arcade's Google OAuth flow with supported scopes.
    Returns the user's email and basic profile info after they
    complete the OAuth authorization in their browser.
    """
    token = context.get_auth_token_or_empty()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return {
        "email": data.get("email"),
        "name": data.get("name"),
        "picture": data.get("picture"),
        "verified": data.get("verified_email"),
    }
