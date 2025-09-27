"""
Utility for interacting with the Amadeus Self-Service API.

This module provides a function to search for flight offers based on
the details extracted from the user's request. It handles the
authentication and API call logic.
"""
import os
from typing import Dict, Any, List
from dotenv import load_dotenv

from amadeus import Client, ResponseError

from core_logic.models import FlightDetails
from core_logic.utils.logger import get_logger

logger = get_logger(__name__)

# Ensure environment variables are loaded even if this module is imported early
load_dotenv()

# --- Amadeus Client Initialization ---

try:
    amadeus_client = Client(
        client_id=os.getenv("AMADEUS_CLIENT_ID"),
        client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
        logger=logger,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
    logger.info("Amadeus client initialized successfully.")
except Exception as e:
    logger.error("Failed to initialize Amadeus client: %s", e, exc_info=True)
    amadeus_client = None


def find_flight_offers(flight_details: FlightDetails) -> List[Dict[str, Any]]:
    """
    Searches for flight offers using the Amadeus API.

    Args:
        flight_details: A Pydantic model containing the flight search parameters.

    Returns:
        A list of flight offers, or an empty list if an error occurs or no flights are found.
    """
    if not amadeus_client:
        logger.error("Amadeus client is not available. Cannot search for flights.")
        return []

    try:
        # --- Parameter Mapping ---
        search_params = {
            "originLocationCode": flight_details.origin_iata,
            "destinationLocationCode": flight_details.destination_iata,
            "departureDate": flight_details.departure_date,
            "adults": flight_details.number_of_passengers or 1,
            "max": 5  # Limit the number of results for this demo
        }
        if flight_details.return_date:
            search_params["returnDate"] = flight_details.return_date
        
        if flight_details.class_of_service and flight_details.class_of_service.upper() in ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]:
            search_params["travelClass"] = flight_details.class_of_service.upper()

        logger.info("Searching Amadeus for flights with params: %s", search_params)

        # --- API Call ---
        response = amadeus_client.shopping.flight_offers_search.get(**search_params)
        
        logger.debug("Amadeus API raw response: %s", response.data)
        return response.data

    except ResponseError as error:
        logger.error("Amadeus API error: %s", error.description, exc_info=True)
        # You could optionally parse error.description for more specific error handling
        return []
    except Exception as e:
        logger.error("An unexpected error occurred while searching for flights: %s", e, exc_info=True)
        return []

def get_itinerary_price_metrics(origin_iata: str, destination_iata: str, departure_date: str) -> List[Dict[str, Any]]:
    """
    Retrieves itinerary price metrics from the Amadeus API.

    Args:
        origin_iata: The IATA code for the origin airport.
        destination_iata: The IATA code for the destination airport.
        departure_date: The departure date in YYYY-MM-DD format.

    Returns:
        A list of price metrics, or an empty list if an error occurs.
    """
    if not amadeus_client:
        logger.error("Amadeus client is not available. Cannot get price metrics.")
        return []

    try:
        search_params = {
            "originIataCode": origin_iata,
            "destinationIataCode": destination_iata,
            "departureDate": departure_date,
        }
        logger.info("Fetching itinerary price metrics with params: %s", search_params)
        response = amadeus_client.analytics.itinerary_price_metrics.get(**search_params)
        logger.debug("Amadeus itinerary price metrics raw response: %s", response.data)
        return response.data
    except ResponseError as error:
        logger.error("Error fetching itinerary price metrics: %s", error.description, exc_info=True)
        return []

def search_transfer_offers(transfer_details: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Searches for transfer offers (e.g., private car, shuttle) using the Amadeus API.

    Args:
        transfer_details: A dictionary containing the search parameters for transfers.
                          Example: {
                              "start_latitude": 40.7128,
                              "start_longitude": -74.0060,
                              "end_latitude": 40.7769,
                              "end_longitude": -73.969,
                              "transfer_type": "PRIVATE"
                          }

    Returns:
        A list of transfer offers, or an empty list if an error occurs.
    """
    if not amadeus_client:
        logger.error("Amadeus client is not available. Cannot search for transfers.")
        return []

    try:
        # The Amadeus API expects a specific JSON body for POST requests.
        # We construct it from the provided details.
        request_body = {
            "startAddress": {
                "latitude": transfer_details["start_latitude"],
                "longitude": transfer_details["start_longitude"]
            },
            "endAddress": {
                "latitude": transfer_details["end_latitude"],
                "longitude": transfer_details["end_longitude"]
            },
            "transferType": transfer_details.get("transfer_type", "PRIVATE") # Default to PRIVATE
        }

        logger.info("Searching for transfer offers with body: %s", request_body)
        
        # The SDK uses a post method and expects the body as the first argument.
        response = amadeus_client.shopping.transfer_offers.post(request_body)
        
        logger.debug("Amadeus transfer offers raw response: %s", response.data)
        return response.data
    except ResponseError as error:
        logger.error("Error searching for transfer offers: %s", error.description, exc_info=True)
        return []
    except KeyError as e:
        logger.error("Missing required key in transfer_details: %s", e, exc_info=True)
        return []

def analyze_deal_from_metrics(offer_price: float, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes a flight offer price against Amadeus price metrics.

    Args:
        offer_price: The price of the flight offer.
        metrics: The price metrics data from Amadeus for the given route.

    Returns:
        A dictionary containing the deal analysis (e.g., score, text).
    """
    if not metrics:
        return {"text": "N/A", "score": "neutral"}

    try:
        # Metrics are per quartile: 25%, 50% (median), 75%
        quartile_25 = float(metrics[0].get("price", {}).get("amount", float('inf')))
        quartile_50 = float(metrics[1].get("price", {}).get("amount", float('inf')))
        
        if offer_price <= quartile_25:
            return {"text": "Great Deal", "score": "good"}
        elif offer_price <= quartile_50:
            return {"text": "Good Deal", "score": "good"}
        else:
            return {"text": "Standard Price", "score": "neutral"}

    except (IndexError, KeyError, TypeError) as e:
        logger.warning("Could not parse price metrics for deal analysis: %s", e)
        return {"text": "N/A", "score": "neutral"}


def search_hotels_for_destination(destination_iata: str,
                                  check_in_date: str = None,
                                  adults: int = 1,
                                  preferred_chains: List[str] | None = None,
                                  max_results: int = 6) -> List[Dict[str, Any]]:
    """
    Searches for hotels for a given destination (city IATA code) and returns
    a prioritized list of hotel entries. If `preferred_chains` is provided,
    results that match those chains (by substring match) are ranked first.

    Args:
        destination_iata: City IATA code (e.g. 'SIN').
        check_in_date: Optional check-in date (not required for by_city lookups).
        adults: Number of adults (used if later switching to offers endpoint).
        preferred_chains: Optional list of preferred hotel chains to prioritize.
        max_results: Max number of results to return.

    Returns:
        A list of hotel dicts (as returned by Amadeus) or an empty list on error.
    """
    if not amadeus_client:
        logger.error("Amadeus client is not available. Cannot search for hotels.")
        return []

    try:
        logger.info("Searching hotels for city: %s (adults=%s) -- preferred_chains=%s",
                    destination_iata, adults, preferred_chains)

        # Use the reference data endpoint to list hotels in a city. This is fast and
        # doesn't require constructing a full availability search. For production
        # you may want to call shopping.hotel_offers or hotel_availability endpoints.
        response = amadeus_client.reference_data.locations.hotels.by_city.get(cityCode=destination_iata)
        hotels = response.data or []

        # Simple prioritization: if preferred_chains provided, move matches to top
        if preferred_chains and isinstance(preferred_chains, list) and hotels:
            lowered_pref = [p.lower() for p in preferred_chains if p]
            preferred = []
            others = []
            for h in hotels:
                name = (h.get('name') or '') + ' ' + (h.get('address', {}).get('lines', [''])[0] or '')
                name_lower = name.lower()
                matched = False
                for p in lowered_pref:
                    if p in name_lower:
                        preferred.append(h)
                        matched = True
                        break
                if not matched:
                    others.append(h)
            hotels = preferred + others

        # Return only up to max_results
        return hotels[:max_results]

    except ResponseError as error:
        logger.error("Error searching hotels: %s", error.description, exc_info=True)
        return []
    except Exception as e:
        logger.error("Unexpected error while searching hotels: %s", e, exc_info=True)
        return []
