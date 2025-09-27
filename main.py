"""main.py
Travel Assistant API (FastAPI)

What this file does (core responsibilities):
 1. Serve the lightweight frontend (GET /) + static assets.
 2. Accept image uploads (POST /uploadfile/) and assign a file_id.
 3. Stream structured travel intent extraction over Server‑Sent Events (GET /stream/{file_id}).
 4. Provide a combined flight (+ optional hotel) search endpoint (POST /find_flights/).

Execution flow for intent extraction:
    upload image -> get file_id -> open /stream with company_name -> orchestrator runs
    vision -> CRM lookup -> LLM intent + enrichment -> final structured TravelRequest.

Relies on:
    - Orchestrator graph (see core_logic/orchestrator + dependencies.build_graph)
    - Amadeus helper functions for flight + hotel logic
    - Environment variables (UPDATES DIR, AMADEUS creds, GOOGLE_API_KEY)

Key response formats:
    - Streaming: SSE lines "data: {json}\n\n" with status or final result
    - Flight search: plain JSON { offers: [...], hotel_recommendations: [...] }

Files are stored temporarily under UPLOADS_DIR (default 'uploads'). Orchestrator cleans them after streaming.
Keep comments lean; this header is your quick mental model.
"""

import os
import uuid
import uvicorn
import json
from typing import Dict, Any, AsyncGenerator, Union

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file as early as possible
load_dotenv()

from core_logic.orchestrator import TravelOrchestrator
from core_logic.dependencies import get_orchestrator
from core_logic.utils.logger import get_logger
from core_logic.models import FlightDetails, TravelRequest, SearchPayload
from core_logic.utils.amadeus_api import find_flight_offers, get_itinerary_price_metrics, analyze_deal_from_metrics, search_hotels_for_destination
import asyncio

logger = get_logger(__name__)

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(title="Travel Intent Extraction API",
              description="Extract travel intent from email/image + search flights/hotels")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

file_registry: Dict[str, str] = {}  # file_id -> absolute path

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def read_root() -> FileResponse:
    """Serve landing page (simple demo UI)."""
    return FileResponse('static/index.html')


@app.post("/uploadfile/", tags=["Image Analysis"])
async def create_upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """Save uploaded image and return a file_id used for streaming."""
    try:
        file_extension = os.path.splitext(file.filename or "")[1] or ".png"
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOADS_DIR, f"{file_id}{file_extension}")

        # Read file contents from the UploadFile (awaitable) and write using a regular file context manager.
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        file_registry[file_id] = file_path
        logger.info("File uploaded: id=%s, path=%s", file_id, file_path)

        return {"file_id": file_id}
    except Exception as e:
        logger.error("File upload failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="File upload failed")


@app.get("/stream/{file_id}", tags=["Image Analysis"])
async def stream_analysis(
    file_id: str,
    company_name: str = Query(..., description="Company name for CRM lookup"),
    orchestrator: TravelOrchestrator = Depends(get_orchestrator)
) -> StreamingResponse:
    """SSE stream of step updates + final structured result."""
    file_path = file_registry.get(file_id)

    async def error_stream(error_message: str, error_type: str) -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'error': error_message, 'error_type': error_type})}\n\n"

    if not file_path or not os.path.exists(file_path):
        logger.warning("File not found for id: %s", file_id)
        return StreamingResponse(
            error_stream("File not found or session expired.", "file_not_found"),
            media_type="text/event-stream"
        )

    logger.info("Starting analysis for file_id: %s, company: %s", file_id, company_name)
    stream_generator = orchestrator.run_streaming(image_path=file_path, company_name=company_name)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(stream_generator, media_type="text/event-stream", headers=headers)


@app.post("/find_flights/", tags=["Flight Booking"])
async def search_for_flights(payload: Union[SearchPayload, FlightDetails]) -> Dict[str, Any]:
    """Flight (and optional hotel) search via Amadeus."""
    # Accept both new SearchPayload and legacy FlightDetails-only body
    if hasattr(payload, "flight_details"):
        flight_details = payload.flight_details
        hotel_preferences = getattr(payload, "hotel_preferences", None)
    else:
        # Legacy: client posted just FlightDetails
        flight_details = payload  # type: ignore[assignment]
        hotel_preferences = None
    logger.info("Received request to find flights with details: %s", flight_details.dict())
    
    if not flight_details.origin_iata or not flight_details.destination_iata:
        logger.error("Missing IATA codes for flight search.")
        raise HTTPException(status_code=400, detail="Origin and destination IATA codes are required for flight search.")

    # Parallel execution (flights + optional hotels)
    tasks = []
    
    # Task 1: Flight Search
    async def flight_task():
        offers = find_flight_offers(flight_details)
        if not offers:
            return []
        
        price_metrics = get_itinerary_price_metrics(
            origin_iata=flight_details.origin_iata,
            destination_iata=flight_details.destination_iata,
            departure_date=flight_details.departure_date
        )
        if price_metrics:
            for offer in offers:
                offer_price = float(offer.get("price", {}).get("total", 0))
                deal_analysis = analyze_deal_from_metrics(offer_price, price_metrics)
                offer["deal"] = deal_analysis
        return offers

    tasks.append(flight_task())

    # Optional hotel search
    hotel_offers = []
    if hotel_preferences and hotel_preferences.preferred_chains:
        logger.info("Hotel preferences found, searching for hotels.")
        async def hotel_task():
            return search_hotels_for_destination(
                destination_iata=flight_details.destination_iata,
                check_in_date=flight_details.departure_date,
                adults=flight_details.number_of_passengers or 1,
                preferred_chains=hotel_preferences.preferred_chains
            )
        tasks.append(hotel_task())

    # Wait for async tasks
    results = await asyncio.gather(*tasks)
    
    flight_offers = results[0]
    if len(results) > 1:
        hotel_offers = results[1]

    return {"offers": flight_offers, "hotel_recommendations": hotel_offers}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
