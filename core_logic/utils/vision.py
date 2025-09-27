import os
import json
import base64
import mimetypes
from typing import Optional
from pathlib import Path

from google.cloud import vision
from google.oauth2 import service_account
import google.generativeai as genai

from .logger import get_logger

logger = get_logger(__name__)


def _build_vision_client() -> vision.ImageAnnotatorClient:
    """
    Builds a Vision API client using service account credentials.

    This function securely initializes the client by checking for credentials
    in environment variables, which is a best practice for production.

    Returns:
        An initialized `vision.ImageAnnotatorClient` instance.
    """
    creds_b64 = os.getenv("GOOGLE_CLOUD_CREDENTIALS_B64")
    if not creds_b64:
        logger.warning("GOOGLE_CLOUD_CREDENTIALS_B64 not found. Using Application Default Credentials.")
        return vision.ImageAnnotatorClient()

    try:
        decoded_creds = base64.b64decode(creds_b64).decode("utf-8")
        creds_info = json.loads(decoded_creds)
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        logger.info("Successfully built Vision API client from base64 credentials.")
        return vision.ImageAnnotatorClient(credentials=credentials)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error("Failed to parse credentials from GOOGLE_CLOUD_CREDENTIALS_B64: %s", e, exc_info=True)
        raise ValueError("Invalid service account credentials provided.") from e


def _get_text_with_vision_api(image_path: str) -> Optional[str]:
    """
    Extracts text from an image using the Google Cloud Vision API.

    Args:
        image_path: The path to the local image file.

    Returns:
        The extracted text as a string, or None if extraction fails.
    """
    logger.info("Attempting OCR with Google Cloud Vision API for: %s", image_path)
    try:
        client = _build_vision_client()
        with open(image_path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.text_detection(image=image)

        if response.error.message:
            logger.error("Vision API error: %s", response.error.message)
            return None

        return response.full_text_annotation.text
    except Exception as e:
        logger.error("An unexpected error occurred with Vision API: %s", e, exc_info=True)
        return None


def _get_text_with_gemini(image_path: str) -> Optional[str]:
    """
    Extracts text from an image using the Gemini Pro Vision model.

    Args:
        image_path: The path to the local image file.

    Returns:
        The extracted text as a string, or None if extraction fails.
    """
    logger.info("Attempting OCR with Gemini Pro Vision for: %s", image_path)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set. Cannot use Gemini for OCR.")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro-vision')

    try:
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image"):
            logger.error("Invalid image MIME type for: %s", image_path)
            return None

        image_parts = [{"mime_type": mime_type, "data": Path(image_path).read_bytes()}]
        prompt_parts = [
            "Extract all text from this image, preserving the original layout as much as possible.\n",
            image_parts[0],
        ]
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        logger.error("An unexpected error occurred with Gemini OCR: %s", e, exc_info=True)
        return None


def get_text_from_image(image_path: str) -> str:
    """
    Performs OCR on an image, trying the Vision API first and falling back to Gemini.

    Args:
        image_path: The path to the local image file.

    Returns:
        The extracted text, or an empty string if both methods fail.
    """
    text = _get_text_with_vision_api(image_path)
    if text:
        logger.info("Successfully extracted text with Vision API.")
        return text

    logger.warning("Vision API failed. Falling back to Gemini Pro Vision.")
    text = _get_text_with_gemini(image_path)
    if text:
        logger.info("Successfully extracted text with Gemini Pro Vision.")
        return text

    logger.error("Both Vision API and Gemini Pro Vision failed.")
    return ""