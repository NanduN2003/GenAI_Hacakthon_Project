"""Intent handler for flight booking related post-processing.

This module exposes a `process` function that the orchestrator calls after
the LLM has produced a structured `TravelRequest`. The function enriches the
LLM output with CRM-derived notes and returns a simple serializable dict
ready for SSE streaming to the client.
"""
from typing import Dict, Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


def process(response, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a flight booking TravelRequest and enrich with CRM hints.

    Args:
        response: A Pydantic `TravelRequest` instance produced by the LLM.
        customer_data: CRM record for the requested company (may be empty).

    Returns:
        A plain dict containing the final result to be sent to the client.
    """
    # Converting the Pydantic model to a  dict so it can be serialized for streaming event(SSE).
    result: Dict[str, Any] = response.dict()

    # flight_etails with agency notes derived from CRM 
    flight_details = result.get("flight_details")
    if flight_details:
        agency_notes = []
        if customer_data.get("VIP"):
            agency_notes.append("VIP client — prioritize upgrades and preferred handling.")
        prefs = customer_data.get("Preferences") or {}
        # if availableMerge some common preference  
        preferred_airlines = prefs.get("airlines_opted") if isinstance(prefs, dict) else None
        if preferred_airlines:
            agency_notes.append(f"Preferred airlines: {', '.join(preferred_airlines)}")

        if agency_notes:
            # Append to existing agency_notes if present
            existing = flight_details.get("agency_notes")
            flight_details["agency_notes"] = (existing + " ") + " ".join(agency_notes) if existing else " ".join(agency_notes)
            result["flight_details"] = flight_details

    # Summary from CRM travel history if present
    history = customer_data.get("TravelHistory")
    if history:
        # Keep the insights_from_history field if already populated by the LLM,
        # otherwise add a brief summary.
        insights = result.get("insights_from_history") or {}
        if not insights:
            insights = {"general_notes": f"Found {len(history)} past trips in CRM."}
        else:
            # Ensure a general_notes key exists
            insights.setdefault("general_notes", f"Found {len(history)} past trips in CRM.")
        result["insights_from_history"] = insights

    logger.info("Processed flight booking result with CRM enrichment.")
    return result
