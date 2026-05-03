# ============================================================
#  auth.py — OAuth token lifecycle: fetch, cache, refresh
# ============================================================

import os
import pickle
import logging
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from config import SCOPES, TOKEN_FILE, CLIENT_SECRET_FILE

logger = logging.getLogger(__name__)


def get_credentials():
    """
    Returns valid Google OAuth credentials.
    - First run  : opens browser for user login → saves token.pickle
    - Later runs : loads from token.pickle, auto-refreshes if expired
    """
    creds = _load_token()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("Token expired — refreshing silently...")
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}. Re-authenticating...")

    creds = _run_oauth_flow()
    _save_token(creds)
    return creds


def _load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"Could not load token file: {e}")
        return None


def _save_token(creds):
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)
    logger.info(f"Token saved to {TOKEN_FILE}")


def _run_oauth_flow():
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(
            f"'{CLIENT_SECRET_FILE}' not found.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials"
        )
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    logger.info("OAuth flow completed successfully.")
    return creds
