import os
import json
import requests
import traceback
from typing import Optional

import glueops.setup_logging

logger = glueops.setup_logging.configure(level=os.environ.get('LOG_LEVEL', 'WARNING'))

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def get_project_node_id(project_id: str, org_name: str, headers: dict) -> Optional[str]:
    """
    Retrieve the GitHub Project V2 node ID using the provided project number and organization name.

    Args:
        project_id (int): The GitHub Project V2 number.
        org_name (str): The GitHub organization name.
        headers (dict): Authentication headers containing the GitHub token.

    Returns:
        Optional[str]: The node ID of the GitHub Project V2 if successful, otherwise None.
    """
    query = """
    query($org: String!, $projNum: Int!) {
      organization(login: $org) {
        projectV2(number: $projNum) {
          id
        }
      }
    }
    """

    variables = {
        "org": org_name,
        "projNum": int(project_id)
    }

    payload = {
        "query": query,
        "variables": variables
    }

    try:
        logger.debug(f"Sending GraphQL request to retrieve project node ID for project_num: {project_id}, org: {org_name}")
        response = requests.post(GITHUB_GRAPHQL_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        logger.debug(f"GraphQL response data: {data}")

        if "errors" in data:
            logger.error(f"GraphQL errors encountered: {data['errors']}")
            return None

        node_id = data['data']['organization']['projectV2']['id']
        logger.info(f"Successfully retrieved project node ID: {node_id} for project_num: {project_id}")
        return node_id

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed while retrieving project node ID: {e}")
        logger.debug(traceback.format_exc())
    except KeyError as e:
        logger.error(f"Unexpected response structure when retrieving project node ID: Missing key {e}")
        logger.debug(traceback.format_exc())
    except Exception as e:
        logger.error(f"An unexpected error occurred while retrieving project node ID: {e}")
        logger.debug(traceback.format_exc())

    return None


def add_to_project(project_node_id: str, item_node_id: str, auth_headers: dict) -> bool:
    """
    Add an item (e.g., an issue) to a GitHub Project V2.

    Args:
        project_node_id (str): The node ID of the GitHub Project V2.
        item_node_id (str): The node ID of the item to add (e.g., an issue).
        auth_headers (dict): Authentication headers containing the GitHub token.

    Returns:
        bool: True if the item was added successfully, False otherwise.
    """
    mutation = f'''
    mutation {{
        addProjectV2ItemById(input: {{projectId: "{project_node_id}", contentId: "{item_node_id}"}}) {{
            item {{
                id
            }}
        }}
    }}
    '''

    payload = {
        "query": mutation
    }

    try:
        logger.debug(f"Sending GraphQL mutation to add item '{item_node_id}' to project '{project_node_id}'")
        response = requests.post(GITHUB_GRAPHQL_URL, headers=auth_headers, json=payload)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"GraphQL mutation response data: {data}")

        if "errors" in data:
            logger.error(f"GraphQL errors encountered while adding item: {data['errors']}")
            return False

        item_id = data['data']['addProjectV2ItemById']['item']['id']
        logger.info(f"Successfully added item '{item_id}' to project '{project_node_id}'")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed while adding item to project: {e}")
        logger.debug(traceback.format_exc())
    except KeyError as e:
        logger.error(f"Unexpected response structure when adding item to project: Missing key {e}")
        logger.debug(traceback.format_exc())
    except Exception as e:
        logger.error(f"An unexpected error occurred while adding item to project: {e}")
        logger.debug(traceback.format_exc())

    return False