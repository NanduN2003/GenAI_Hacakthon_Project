"""LLM chain factory.
Provides get_llm_chain() returning a Runnable that maps structured inputs to a TravelRequest.
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from .models import TravelRequest
from .utils.text_processing import load_prompt_template
from .utils.logger import get_logger
import json
from datetime import datetime

logger = get_logger(__name__)

def get_llm_chain() -> Runnable:
    logger.info("Initializing Google Generative AI model chain (fallback chat-bison)")
    model = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)
    parser = JsonOutputParser(pydantic_object=TravelRequest)
    template = load_prompt_template("core_logic/prompt_template.txt")
    prompt = PromptTemplate(
        template=template,
        input_variables=["request_text", "current_date", "customer_preferences", "customer_history", "discount_codes"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | model | parser
    return chain
