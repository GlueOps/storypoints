import os
import json
import time
import datetime
import traceback
from typing import List, Dict, Any, Optional

import requests

import glueops.setup_logging
from utils.github import auth

# Initialize Logger
logger = glueops.setup_logging.configure(level=os.environ.get('LOG_LEVEL', 'INFO'))

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_DELIVERIES_URL = "https://api.github.com/app/hook/deliveries"


def get_list_of_all_failed_delivery_ids(deliveries: List[Dict[str, Any]]) -> List[str]:
    """
    Extracts unique failed delivery IDs from a list of webhook deliveries.

    Args:
        deliveries (List[Dict[str, Any]]): A list of webhook delivery dictionaries.

    Returns:
        List[str]: A list of unique failed delivery IDs.
    """
    failed_delivery_ids = []
    guids = []
    for delivery in deliveries:
        status_code = delivery.get("status_code")
        guid = delivery.get("guid")
        delivery_id = delivery.get("id")
        redelivery = delivery.get("redelivery", False)

        if status_code != 200 and guid not in guids and delivery_id:
            failed_delivery_ids.append(delivery_id)
            guids.append(guid)
            if redelivery:
                logger.error(f"A redelivery has failed. Will try again: {delivery}")

    logger.debug(f"Failed delivery IDs extracted: {failed_delivery_ids}")
    return failed_delivery_ids


def get_webhook_deliveries(auth_headers: Dict[str, str], days_to_reprocess: int) -> List[Dict[str, Any]]:
    """
    Fetches all webhook deliveries from the last specified number of days.

    Args:
        auth_headers (Dict[str, str]): Authentication headers containing the GitHub token.
        days_to_reprocess (int): Number of days to look back for failed deliveries.

    Returns:
        List[Dict[str, Any]]: A list of webhook delivery dictionaries.
    """
    deliveries = []
    url = f"{GITHUB_DELIVERIES_URL}?per_page=100"
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(days=days_to_reprocess)

    while url:
        try:
            logger.debug(f"Fetching webhook deliveries from URL: {url}")
            response = requests.get(url, headers=auth_headers, allow_redirects=True)
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.debug("No more deliveries found.")
                break

            for delivery in data:
                delivered_at_str = delivery.get('delivered_at')
                if not delivered_at_str:
                    logger.warning(f"Delivery missing 'delivered_at' timestamp: {delivery}")
                    continue  # Skip if no timestamp is available

                try:
                    delivered_at = datetime.datetime.strptime(delivered_at_str, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError as ve:
                    logger.error(f"Invalid date format for delivery: {delivered_at_str} - {ve}")
                    continue  # Skip invalid date formats

                if delivered_at >= cutoff_time:
                    logger.debug(f"Valid delivery within cutoff: {delivery}")
                    deliveries.append(delivery)
                else:
                    logger.debug("Reached deliveries older than the cutoff. Stopping fetch.")
                    return deliveries

            # Handle pagination using 'Link' headers
            link_header = response.headers.get('Link', '')
            next_url = None

            if 'rel="next"' in link_header:
                parts = link_header.split(',')
                for part in parts:
                    if 'rel="next"' in part:
                        next_url = part[part.find('<') + 1:part.find('>')]
                        break

            url = next_url  # Set the URL for the next iteration
            logger.debug(f"Next URL for pagination: {url}")

            if not next_url:
                logger.debug("No next page found. Completed fetching all deliveries.")
                break

            # Respect GitHub API rate limits
            time.sleep(1)  # Sleep for 1 second between requests

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching deliveries: {http_err} - Status Code: {response.status_code}")
            logger.debug(f"Response Content: {response.text}")
            break  # Exit loop on HTTP errors
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception occurred while fetching deliveries: {req_err}")
            logger.debug(traceback.format_exc())
            break  # Exit loop on other request exceptions
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching deliveries: {e}")
            logger.debug(traceback.format_exc())
            break  # Exit loop on any other exceptions

    logger.info(f"Total deliveries fetched: {len(deliveries)}")
    return deliveries


def retry_webhook_delivery(delivery_id: str, auth_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Retries a failed webhook delivery attempt on GitHub.

    Args:
        delivery_id (str): The unique identifier for the webhook delivery.
        auth_headers (Dict[str, str]): Authentication headers containing the GitHub token.

    Returns:
        Optional[Dict[str, Any]]: JSON response from the GitHub API if successful, else None.
    """
    url = f'https://api.github.com/app/hook/deliveries/{delivery_id}/attempts'

    try:
        logger.info(f"Retrying webhook delivery for DELIVERY_ID: {delivery_id}")
        response = requests.post(url, headers=auth_headers, allow_redirects=True, timeout=30)
        if response.status_code == 202:
            logger.info(f"Successfully resent webhook delivery for DELIVERY_ID: {delivery_id}")
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while retrying delivery {delivery_id}: {http_err} - Status Code: {response.status_code}")
        logger.debug(f"Response Content: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred while retrying delivery {delivery_id}: {conn_err}")
        logger.debug(traceback.format_exc())
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred while retrying delivery {delivery_id}: {timeout_err}")
        logger.debug(traceback.format_exc())
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request exception occurred while retrying delivery {delivery_id}: {req_err}")
        logger.debug(traceback.format_exc())
    except Exception as e:
        logger.error(f"An unexpected error occurred while retrying delivery {delivery_id}: {e}")
        logger.debug(traceback.format_exc())

    return None


def retry_failed_deliveries(github_app_id: str, github_app_private_key: str, number_of_days_to_reprocess: int) -> None:
    """
    Retries all failed webhook deliveries within the specified number of days.

    Args:
        github_app_id (str): GitHub App ID.
        github_app_private_key (str): GitHub App private key.
        number_of_days_to_reprocess (int): Number of days to look back for failed deliveries.

    Returns:
        None
    """
    try:
        logger.debug("Generating GitHub authentication headers.")
        auth_headers = auth.github_auth_jwt(github_app_id, github_app_private_key)
        logger.debug("GitHub authentication headers generated successfully.")

        logger.debug(f"Fetching webhook deliveries from the last {number_of_days_to_reprocess} days.")
        deliveries = get_webhook_deliveries(auth_headers, number_of_days_to_reprocess)
        logger.info(f"Total webhook deliveries fetched: {len(deliveries)}")

        failed_delivery_ids = get_list_of_all_failed_delivery_ids(deliveries)
        logger.info(f"Total failed deliveries to retry: {len(failed_delivery_ids)}")

        for delivery_id in failed_delivery_ids:
            retry_webhook_delivery(delivery_id, auth_headers)
            
        logger.info(f"Total failed deliveries that were retried: {len(failed_delivery_ids)}")
        

    except Exception as e:
        logger.error(f"An unexpected error occurred in retry_failed_deliveries: {e}")
        logger.debug(traceback.format_exc())