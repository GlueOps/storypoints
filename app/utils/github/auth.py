import os
import datetime
import jwt
import time
import requests
import traceback
from threading import Lock
from typing import Dict, Optional, Any

import glueops.setup_logging

# Initialize Logger
logger = glueops.setup_logging.configure(level=os.environ.get('LOG_LEVEL', 'INFO'))

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_ACCESS_TOKENS_URL_TEMPLATE = "https://api.github.com/app/installations/{installation_id}/access_tokens"


def github_auth_jwt(github_app_id: str, github_app_private_key: str) -> Dict[str, str]:
    """
    Generate authentication headers using a JWT for GitHub App.

    Args:
        github_app_id (str): GitHub App ID.
        github_app_private_key (str): GitHub App private key.

    Returns:
        Dict[str, str]: Authentication headers.
    """
    now = int(datetime.datetime.utcnow().timestamp())
    payload = {
        "iat": now - 60,                 # Issued at time (60 seconds ago to account for clock skew)
        "exp": now + 60 * 8,              # Expiration time (8 minutes)
        "iss": github_app_id               # GitHub App ID
    }
    try:
        token = jwt.encode(payload=payload, key=github_app_private_key, algorithm="RS256")
        logger.debug("JWT token generated successfully.")
    except Exception as e:
        logger.error(f"Failed to encode JWT: {e}")
        logger.debug(traceback.format_exc())
        raise

    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }


class GitHubInstallationTokenManager:
    """
    Singleton class to manage GitHub Installation Access Tokens.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, installation_id: str, app_id: str, private_key: str):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GitHubInstallationTokenManager, cls).__new__(cls)
                cls._instance.github_app_installation_id = installation_id
                cls._instance.github_app_id = app_id
                cls._instance.github_app_private_key = private_key
                cls._instance._token: Optional[str] = None
                cls._instance._expires_at: float = 0  # Epoch time
                logger.debug("GitHubInstallationTokenManager instance created.")
            else:
                logger.debug("GitHubInstallationTokenManager instance reused.")
            return cls._instance

    def get_headers(self) -> Dict[str, str]:
        """
        Retrieve authentication headers, refreshing the token if necessary.

        Returns:
            Dict[str, str]: Authentication headers with the access token.
        """
        current_time = time.time()
        # Refresh the token if it's about to expire within the next hour (3600 seconds)
        if not self._token or (self._expires_at - current_time) < 3600:
            logger.info("Access token is missing or about to expire. Fetching a new token.")
            self._fetch_new_token()
        else:
            logger.debug("Using cached access token.")
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def _fetch_new_token(self) -> None:
        """
        Fetch a new GitHub Installation Access Token.

        Raises:
            Exception: If the token retrieval fails.
        """
        url = GITHUB_ACCESS_TOKENS_URL_TEMPLATE.format(installation_id=self.github_app_installation_id)
        headers = github_auth_jwt(self.github_app_id, self.github_app_private_key)
        try:
            logger.debug(f"Requesting new access token from URL: {url}")
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self._token = data.get("token")
            expires_at_str = data.get("expires_at")  # ISO 8601 format
            self._expires_at = self._parse_github_time(expires_at_str)
            logger.info("Successfully fetched a new installation access token.")
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed while fetching access token: {e}")
            logger.debug(traceback.format_exc())
            raise
        except KeyError as e:
            logger.error(f"Expected key {e} not found in the response.")
            logger.debug(traceback.format_exc())
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching access token: {e}")
            logger.debug(traceback.format_exc())
            raise

    @staticmethod
    def _parse_github_time(time_str: str) -> float:
        """
        Parses GitHub's ISO 8601 time string to epoch time.

        Args:
            time_str (str): ISO 8601 formatted time string.

        Returns:
            float: Epoch time.

        Raises:
            ValueError: If the time format is invalid.
        """
        try:
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
            epoch_time = dt.timestamp()
            logger.debug(f"Parsed GitHub time '{time_str}' to epoch: {epoch_time}")
            return epoch_time
        except ValueError as ve:
            logger.error(f"Invalid time format received from GitHub: {time_str} - {ve}")
            logger.debug(traceback.format_exc())
            raise