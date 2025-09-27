import re
from typing import List
from .logger import get_logger

logger = get_logger(__name__)

# Regex patterns text cleaning
PATTERNS_TO_REMOVE: List[re.Pattern] = [
    re.compile(r'Best regards,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Thanks & Regards,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Sincerely,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Warmly,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Respectfully,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Thank you,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Yours faithfully,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Kind regards,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Best wishes,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'All the best,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'Cheers,.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\[cid:.*?\]', re.IGNORECASE | re.DOTALL),
    re.compile(r'Disclaimer:.*', re.IGNORECASE | re.DOTALL),
    re.compile(r'This email and any files transmitted with it are confidential.*', re.IGNORECASE | re.DOTALL),
]
# Regex to consolidate multiple newlines into a maximum of two
CLEANED_TEXT_PATTERN: re.Pattern = re.compile(r'\n\s*\n')

def clean_text(raw_text: str) -> str:
    """
    Cleans raw text extracted from an email image by removing common signatures,
    disclaimers, and excessive whitespace.

    This function iterates through a list of pre-compiled regular expressions
    to strip common email closing remarks and other non-essential text. It
    also normalizes newline characters to improve readability.

    Args:
        raw_text: The raw string extracted from OCR.

    Returns:
        A cleaned string, ready for LLM processing.
    """
    logger.info("Starting text cleaning process...")
    cleaned_text = raw_text
    
    # Remove common mail footers and signatures
    for pattern in PATTERNS_TO_REMOVE:
        # Split and take the first part to remove the signature and everything after it
        cleaned_text = pattern.split(cleaned_text, 1)[0].strip()
    
    # Clean-up for spacing and extra lines
    cleaned_text = CLEANED_TEXT_PATTERN.sub('\n\n', cleaned_text).strip()
    
    logger.info("Text cleaning complete.")
    return cleaned_text

def load_prompt_template(template_path: str) -> str:
    """
    Load a prompt template from a file path.
    
    Args:
        template_path: Path to the prompt template file
        
    Returns:
        The contents of the template file as a string
        
    Raises:
        FileNotFoundError: If the template file doesn't exist
        IOError: If there's an error reading the file
    """
    try:
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        logger.info(f"Successfully loaded prompt template from {template_path}")
        return template_content
    except FileNotFoundError:
        logger.error(f"Prompt template file not found: {template_path}")
        raise
    except IOError as e:
        logger.error(f"Error reading prompt template file {template_path}: {e}")
        raise
