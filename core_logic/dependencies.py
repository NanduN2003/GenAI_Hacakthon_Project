import json
import re
from functools import lru_cache
from typing import Dict, Any

from fastapi import Depends
from langchain_core.runnables import Runnable


import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core_logic.chains import get_llm_chain
from core_logic.utils.logger import get_logger
from core_logic.orchestrator import TravelOrchestrator

logger = get_logger(__name__)

CRM_DATA_PATH = "scripts/dummy_crm_data.json"


@lru_cache(maxsize=1)
def get_crm_data() -> Dict[str, Any]:
    """Loads and caches CRM data from a JSON file.

    The `@lru_cache` decorator ensures the file is read from disk only once.

    Returns:
        Dict[str, Any]: A dictionary containing the CRM data.

    Raises:
        FileNotFoundError: If the CRM data file is not found.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    logger.info("Loading CRM data from %s", CRM_DATA_PATH)
    try:
        with open(CRM_DATA_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # Convert list-based CRM export into a mapping keyed by a normalized company name
        def normalize_name(name: str) -> str:
            if not name:
                return ""
            s = name.lower().strip()
            # Removes common suffixes and punctuation
            s = re.sub(r"\b(inc|llc|ltd|corp|co|company)\b", "", s)
            s = re.sub(r"[^a-z0-9]+", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        crm_map: Dict[str, Any] = {}
        for entry in raw:
            data = entry.get("Data") if isinstance(entry, dict) else None
            if not data and isinstance(entry, dict):
                data = entry
            if not data:
                continue
            name = data.get("Name") or data.get("Company") or ""
            key = normalize_name(name)
            if key:
                norm: Dict[str, Any] = {}
                # Agency notes
                norm["AgencyNotes"] = data.get("AgencyNotes") or data.get("Notes") or ""


                #norm["Contacts"] = data.get("Contacts") or []

                # Travel history - if the export has a TravelHistory key, use it; otherwise empty
                norm["TravelHistory"] = data.get("TravelHistory") or data.get("PastTrips") or []

                # Conversion of TravelPreferences Array into a  Preferences dict
                raw_prefs = data.get("TravelPreferences") or data.get("Preferences") or []
                prefs: Dict[str, Any] = {
                    "airlines_opted": [],
                    "alliance": None,
                    "past_class_preference": None,
                    "preferred_chains": [],
                    "room_type": None,
                }
                discount_codes = []
                for p in raw_prefs:
                    if not isinstance(p, dict):
                        continue
                    svc = (p.get("ServiceType") or "").lower()
                    desc = p.get("Description") or p.get("DescriptionText") or ""
                    if svc == "airline":
                        if desc:
                            prefs["airlines_opted"].append(desc)
                        if p.get("Alliance") and not prefs.get("alliance"):
                            prefs["alliance"] = p.get("Alliance")
                        if p.get("ClassPreference") and not prefs.get("past_class_preference"):
                            prefs["past_class_preference"] = p.get("ClassPreference")
                    elif svc == "hotel":
                        if desc:
                            prefs["preferred_chains"].append(desc)
                        if p.get("Category") and not prefs.get("room_type"):
                            prefs["room_type"] = p.get("Category")
                    elif svc == "route":
                        # Storing route info in a dedicated field inside Preferences
                        prefs.setdefault("route_info", p.get("Description") or p.get("Policy"))
                    elif svc == "classpolicy":
                        prefs.setdefault("class_policy", p.get("Description") or p.get("Policy"))

                    # Collect discount codes if present
                    if p.get("DiscountCode"):
                        discount_codes.append(p.get("DiscountCode"))

                norm["Preferences"] = prefs
                norm["DiscountCodes"] = discount_codes

                crm_map[key] = norm

        logger.info("Loaded %d CRM records into lookup map", len(crm_map))
        return crm_map
    except FileNotFoundError:
        logger.error("CRM data file not found at %s. Aborting.", CRM_DATA_PATH)
        raise
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from %s. Aborting.", CRM_DATA_PATH)
        raise


def get_orchestrator(
    crm_data: Dict[str, Any] = Depends(get_crm_data),
    llm_chain: Runnable = Depends(get_llm_chain)
) -> TravelOrchestrator:
    """FastAPI dependency to get a `TravelOrchestrator` instance.

    Initializes the orchestrator with its required dependencies (CRM data and LLM chain),
    which are themselves resolved by FastAPI's dependency injection system.

    Args:
        crm_data: The CRM data, injected by `get_crm_data`.
        llm_chain: The LangChain runnable, injected by `get_llm_chain`.

    Returns:
        TravelOrchestrator: A fully configured instance.
    """
    return TravelOrchestrator(crm_data=crm_data, llm_chain=llm_chain)
