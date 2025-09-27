# Mainly, Important/critical for sticking the LLM output content to be in the required format according to the Intents
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class Intent(str, Enum):
    """Enumeration of possible user intents related to flights."""
    FLIGHT_BOOKING = "flight_booking"
    ADDITIONAL_BAGGAGE = "additional_baggage"
    CHANGE_ITINERARY = "change_itinerary"
    CANCELLATION = "cancellation"
    OTHERS = "other"

class AirlinePreferences(BaseModel):
    """Detailed airline travel preferences based on history."""
    airlines_opted: Optional[List[str]] = Field(None, description="List of previously opted airlines, like 'Lufthansa', 'British Airways'.")
    alliance: Optional[str] = Field(None, description="Preferred airline alliance, like 'Star Alliance', 'Oneworld'.")
    past_class_preference: Optional[str] = Field(None, description="Previously preferred class of service, like 'Business', 'Economy'.")

class HotelPreferences(BaseModel):
    """Detailed hotel stay preferences based on history."""
    preferred_chains: Optional[List[str]] = Field(None, description="List of preferred hotel chains, like 'Marriott', 'Hilton'.")
    room_type: Optional[str] = Field(None, description="Preferred room type, like 'King Size Bed', 'Sea View'.")

class ServiceInfo(BaseModel):
    """Additional structured information related to travel policies and options."""
    route_info: Optional[str] = Field(None, description="Information or notes about the travel route (e.g., 'Direct flights preferred', 'Avoids layovers in specific countries').")
    class_policy: Optional[str] = Field(None, description="Company or traveler policy on class of service (e.g., 'Business class for flights over 6 hours').")
    ground_transport_info: Optional[str] = Field(None, description="Information regarding ground transportation (e.g., 'Rental car needed', 'Arrange airport transfer').")

class Insights(BaseModel):
    """A structured representation of insights derived from the user's travel history."""
    airline_preferences: Optional[AirlinePreferences] = Field(None, description="Insights based on airline travel history.")
    hotel_preferences: Optional[HotelPreferences] = Field(None, description="Insights based on hotel stay history.")
    general_notes: Optional[str] = Field(None, description="A brief, general note on how CRM data influenced the result if not covered by other fields.")

class FlightDetails(BaseModel):
    """
    Schema for extracting flight search details.
    Each field is described to guide the LLM on what to extract.
    """
    # Make origin/destination optional to avoid validation failures when only IATA codes are provided
    origin: Optional[str] = Field(None, description="The departure location for the flight.")
    origin_iata: Optional[str] = Field(None, description="The 3-letter IATA code for the origin airport.")
    destination: Optional[str] = Field(None, description="The arrival location for the flight.")
    destination_iata: Optional[str] = Field(None, description="The 3-letter IATA code for the destination airport.")
    departure_date: str = Field(..., description="The desired departure date in YYYY-MM-DD format.")
    return_date: Optional[str] = Field(None, description="The desired return date in YYYY-MM-DD format, if specified. Otherwise, null.")
    number_of_passengers: Optional[int] = Field(None, description="The number of passengers traveling.")
    class_of_service: Optional[str] = Field("N/A", description="Explicit class preference from the user's request. Set to 'any' if mentioned. Defaults to 'N/A' if not specified.")
    notes: Optional[str] = Field(None, description="Assumptions or ambiguity notices (e.g., 'Year for departure date was assumed to be 2025.').")
    agency_notes: Optional[str] = Field(None, description="Internal notes for the travel agency based on CRM data (e.g., 'High-value client', 'Check for loyalty program upgrades').")

class TravelRequest(BaseModel):
    """
    A model to represent a travel-related request. It captures the user's intent
    and the specific details associated with that intent.
    """
    intent: Intent = Field(..., description="The user's primary intent.")
    flight_details: Optional[FlightDetails] = Field(None, description="Populated if the intent is 'flight_booking'.")
    insights_from_history: Optional[Insights] = Field(None, description="Structured insights derived from CRM data.")
    additional_service_info: Optional[ServiceInfo] = Field(None, description="Additional structured info for route, class, and ground transport.")

class SearchPayload(BaseModel):
    """
    Defines the payload for the combined flight and hotel search endpoint.
    """
    flight_details: FlightDetails
    hotel_preferences: Optional[HotelPreferences] = None

