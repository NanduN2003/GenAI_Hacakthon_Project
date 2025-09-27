import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import Dict, Any, AsyncGenerator

from langchain_core.runnables import Runnable
from langchain_core.exceptions import OutputParserException

from core_logic.utils.vision import get_text_from_image
from core_logic.utils.text_processing import clean_text
from core_logic.models import Intent, TravelRequest
from core_logic.intents import flight_booking
from core_logic.utils.logger import get_logger

logger = get_logger(__name__)


class TravelOrchestrator:
    """
    Orchestrates the entire travel intent extraction process.
    
    This class coordinates the steps from OCR text extraction, text cleaning,
    and enrichment with CRM data to invoking the LLM and streaming the
    results back to the client.
    """

    def __init__(self, crm_data: Dict[str, Any], llm_chain: Runnable):
        """Initializes the orchestrator with its dependencies.

        Args:
            crm_data: A dictionary containing the pre-loaded CRM data.
            llm_chain: A pre-configured LangChain runnable (chain).
        """
        self.crm_data = crm_data
        self.chain = llm_chain
        logger.info("TravelOrchestrator initialized successfully.")

    def _get_customer_data(self, company_name: str) -> Dict[str, Any]:
        """Fetches customer data from the loaded CRM data.

        Args:
            company_name: The name of the company to look up.

        Returns:
            A dictionary containing the customer's data or an empty dict if not found.
        """
        if not company_name:
            logger.warning("Empty company name provided for CRM lookup.")
            return {}

        # Normalize the incoming company name using same rules as the CRM loader
        def normalize_name(name: str) -> str:
            s = name.lower().strip()
            s = s.replace('.', ' ')
            s = s.replace(',', ' ')
            for token in [' inc', ' llc', ' ltd', ' corp', ' co', ' company']:
                s = s.replace(token, '')
            s = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in s)
            s = ' '.join(s.split())
            return s

        key = normalize_name(company_name)
        if key in self.crm_data:
            logger.info("Found CRM data for company: %s (normalized: %s)", company_name, key)
            return self.crm_data[key]

        # Try substring matching if the above step fails finiding CRM keys
        for crm_key, record in self.crm_data.items():
            if key in crm_key or crm_key in key:
                logger.info("Found CRM data by substring match: %s -> %s", company_name, crm_key)
                return record

        logger.warning("No CRM data found for company: %s (normalized: %s)", company_name, key)
        return {}

    async def run_streaming(self, image_path: str, company_name: str) -> AsyncGenerator[str, None]:
        """
        Asynchronously runs the analysis pipeline and streams updates via SSE.

        This generator function yields Server-Sent Events (SSE) formatted strings
        to provide real-time feedback to the client.

        Args:
            image_path: The local file path to the uploaded image.
            company_name: The name of the company for CRM lookup.

        Yields:
            A string formatted as a Server-Sent Event.
        """
        try:
            # 1. Extract text from image
            yield f"data: {json.dumps({'status': 'Extracting text from image...'})}\n\n"
            await asyncio.sleep(0.5)  # Simulate work for better UX
            raw_text = get_text_from_image(image_path)
            if not raw_text:
                logger.warning("OCR returned no text for image: %s", image_path)
                yield f"data: {json.dumps({'error': 'No text could be extracted from the image.', 'error_type': 'ocr_error'})}\n\n"
                return

            # 2. Clean the extracted text
            yield f"data: {json.dumps({'status': 'Cleaning extracted text...'})}\n\n"
            await asyncio.sleep(0.5)
            cleaned_text = clean_text(raw_text)
            logger.info("Cleaned text: %s", cleaned_text)

            # 3. Get CRM data
            yield f"data: {json.dumps({'status': 'Fetching customer details...'})}\n\n"
            await asyncio.sleep(0.5)
            customer_data = self._get_customer_data(company_name)
            customer_preferences = customer_data.get("Preferences", {})
            customer_history = customer_data.get("TravelHistory", [])
            discount_codes = customer_data.get("DiscountCodes", [])

            # 4. Invoke the LLM chain
            yield f"data: {json.dumps({'status': 'Analyzing travel intent with AI...'})}\n\n"
            
            try:
                response: TravelRequest = await self.chain.ainvoke({
                    "request_text": cleaned_text,
                    "current_date": datetime.now().strftime("%Y-%m-%d"),
                    "customer_preferences": json.dumps(customer_preferences, indent=2),
                    "customer_history": json.dumps(customer_history, indent=2),
                    "discount_codes": ", ".join(discount_codes)
                })
                logger.info("LLM invocation successful.")
            except OutputParserException as e:
                logger.error("LLM output parsing failed: %s", e, exc_info=True)
                yield f"data: {json.dumps({'error': 'The AI failed to structure the response. The request may be ambiguous.', 'error_type': 'parsing_error', 'details': str(e)})}\n\n"
                return
            except Exception as e:
                logger.error("LLM invocation failed: %s", e, exc_info=True)
                yield f"data: {json.dumps({'error': 'An unexpected error occurred during AI analysis.', 'error_type': 'invocation_error', 'details': str(e)})}\n\n"
                return

            # 5. Process the result based on intent
            yield f"data: {json.dumps({'status': 'Finalizing results...'})}\n\n"
            final_result = response

            if response.get("intent") == Intent.FLIGHT_BOOKING:
                logger.info("Intent is FLIGHT_BOOKING. Processing...")
                # We need to convert the dict back to a TravelRequest model for processing
                try:
                    travel_request_model = TravelRequest(**response)
                    final_result = flight_booking.process(travel_request_model, customer_data)
                except Exception as e:
                    logger.error(f"Failed to process flight booking intent: {e}")
                    final_result['additional_info'] = "Error processing flight booking."
            else:
                logger.warning("Unhandled intent: %s", response.get("intent"))
                # Add basic info for unhandled intents
                final_result['additional_info'] = "This intent is recognized but not yet fully supported."

            # 6. Stream the final result
            yield f"data: {json.dumps(final_result)}\n\n"
            logger.info("Successfully streamed final result to client.")

        except Exception as e:
            logger.error("An error occurred in the main orchestration pipeline: %s\n%s", e, traceback.format_exc())
            error_payload = {
                "error": "A critical error occurred in the backend.",
                "error_type": "pipeline_failure",
                "details": str(e)
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            # Cleans up the uploaded file
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    logger.info("Cleaned up uploaded file: %s", image_path)
                except OSError as e:
                    logger.error("Error removing file %s: %s", image_path, e)