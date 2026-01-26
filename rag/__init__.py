# Main package initialization
import os
import logging
import vertexai
from .config import PROJECT_ID, LOCATION
import google.auth
logger = logging.getLogger(__name__)

creds = google.auth.default()


try:
    if PROJECT_ID and LOCATION:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Initialized Vertex AI with project {PROJECT_ID}, location={LOCATION}, with user as : {creds.service_account_email if hasattr(creds, 'service_account_email') else 'USER'}")
    else:
        logger.warning("PROJECT_ID or LOCATION not set. Vertex AI initialization skipped.")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")

# Temporarily commenting out agent import to allow isolated tool testing
from .agent import root_agent
