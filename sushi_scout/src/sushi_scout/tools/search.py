"""Restaurant search tools using Google Places API.

Supports two auth modes for Google Places API calls:

1. API Key mode (default): Uses GOOGLE_PLACES_API_KEY via Arcade's
   requires_secrets pattern. Simple to set up - just add the key to .env.

2. OAuth mode: Uses a custom Arcade OAuth2 provider with Google's
   cloud-platform scope. No API key needed - users authenticate via
   browser. Requires registering a custom OAuth2 provider in Arcade.
   Set SUSHI_SCOUT_AUTH_MODE=oauth to enable.

See README.md "Auth Setup" section for detailed instructions on both modes.

Arcade Google OAuth is also demonstrated via get_user_profile, which uses
the supported userinfo.email scope from Arcade's built-in Google provider.
"""

import os
from typing import Annotated, Any

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Google, OAuth2

PLACES_BASE_URL = "https://places.googleapis.com/v1/places"

# ---------------------------------------------------------------------------
# Auth configuration
# ---------------------------------------------------------------------------
# Set SUSHI_SCOUT_AUTH_MODE=oauth to switch from API key to OAuth mode.
# OAuth mode requires a custom Arcade OAuth2 provider - see README.md.
AUTH_MODE = os.environ.get("SUSHI_SCOUT_AUTH_MODE", "api_key")

# Custom OAuth2 provider settings (only used when AUTH_MODE="oauth")
# These must match the provider registered in Arcade's dashboard or engine.yaml.
OAUTH_PROVIDER_ID = "google-places"
OAUTH_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Google Cloud project ID for billing when using OAuth mode.
# Required because OAuth replaces the API key, so Google needs to know
# which project to bill for Places API usage.
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")


def _places_auth_kwargs() -> dict:
    """Build the auth kwargs for the @tool decorator based on AUTH_MODE.

    Returns either requires_secrets (API key) or requires_auth (OAuth)
    config, which gets unpacked into the @tool() decorator.
    """
    if AUTH_MODE == "oauth":
        return {"requires_auth": OAuth2(id=OAUTH_PROVIDER_ID, scopes=OAUTH_SCOPES)}
    return {"requires_secrets": ["GOOGLE_PLACES_API_KEY"]}


def _build_places_headers(context: Context, field_mask: list[str]) -> dict[str, str]:
    """Build Google Places API request headers for the active auth mode.

    In API key mode: uses X-Goog-Api-Key header.
    In OAuth mode: uses Authorization: Bearer header + X-Goog-User-Project.
    """
    if AUTH_MODE == "oauth":
        token = context.get_auth_token_or_empty()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-FieldMask": ",".join(field_mask),
        }
        if GCP_PROJECT_ID:
            headers["X-Goog-User-Project"] = GCP_PROJECT_ID
        return headers
    else:
        api_key = context.get_secret("GOOGLE_PLACES_API_KEY")
        return {
            "X-Goog-Api-Key": api_key,
            "Content-Type": "application/json",
            "X-Goog-FieldMask": ",".join(field_mask),
        }

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


@tool(**_places_auth_kwargs())
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
    headers = _build_places_headers(context, SEARCH_FIELDS)

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


@tool(**_places_auth_kwargs())
async def get_restaurant_details(
    context: Context,
    place_id: Annotated[str, "Google Places ID of the restaurant"],
) -> Annotated[dict, "Detailed restaurant information including hours and reviews"]:
    """Get detailed information about a specific restaurant.

    Returns delivery availability, hours, reviews, and more.
    Use this after search_nearby_restaurants to get details for a specific place.
    """
    headers = _build_places_headers(context, DETAIL_FIELDS)

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
