#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import requests
import yaml

# --- Configuration ---
CIRCLECI_API_BASE_URL = "https://circleci.com/api/v2"
CIRCLECI_CONFIG_PATH = Path.home() / ".circleci" / "cli.yml"
TOKEN_ENV_VAR = "CI_TOKEN"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- Helper Functions ---

def get_api_token() -> Optional[str]:
    """
    Retrieves the CircleCI API token.
    Tries to read from ~/.circleci/cli.yml first, then falls back
    to the CI_TOKEN environment variable.

    Returns:
        The API token string or None if not found.
    """
    token = None
    # Try reading from cli.yml
    try:
        if CIRCLECI_CONFIG_PATH.is_file():
            logging.info(f"Attempting to read token from {CIRCLECI_CONFIG_PATH}")
            with open(CIRCLECI_CONFIG_PATH, 'r') as f:
                config_data = yaml.safe_load(f)
                # Handle potential variations in YAML structure (e.g., older cli versions)
                if isinstance(config_data, dict):
                    token = config_data.get('token')
                if token:
                     logging.info(f"Successfully read token from {CIRCLECI_CONFIG_PATH}")
                else:
                    logging.warning(f"Token key not found or empty in {CIRCLECI_CONFIG_PATH}")

    except yaml.YAMLError as e:
        logging.warning(f"Error parsing YAML file {CIRCLECI_CONFIG_PATH}: {e}")
    except IOError as e:
        logging.warning(f"Could not read file {CIRCLECI_CONFIG_PATH}: {e}")
    except Exception as e:
        logging.warning(f"An unexpected error occurred reading {CIRCLECI_CONFIG_PATH}: {e}")


    # Fallback to environment variable if token not found in file
    if not token:
        logging.info(f"Attempting to read token from environment variable {TOKEN_ENV_VAR}")
        token = os.environ.get(TOKEN_ENV_VAR)
        if token:
            logging.info(f"Successfully read token from environment variable {TOKEN_ENV_VAR}")

    if not token:
        logging.error("CircleCI API token not found.")
        logging.error(f"Please ensure it's set in {CIRCLECI_CONFIG_PATH} (under 'token:')")
        logging.error(f"or as the environment variable {TOKEN_ENV_VAR}.")
        return None

    return token


def load_config_yaml(file_path: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    Loads the context configuration from a YAML file.

    Args:
        file_path: Path to the YAML configuration file.

    Returns:
        A dictionary representing the parsed YAML, or None on error.
        Expected format:
        {
            "context-name-1": [{"VAR1": "value1"}, {"VAR2": "value2"}],
            "context-name-2": [{"VAR_A": "valueA"}]
        }
    """
    try:
        path = Path(file_path)
        if not path.is_file():
             logging.error(f"Configuration file not found: {file_path}")
             return None
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        # Basic validation
        if not isinstance(config, dict):
            logging.error(f"Invalid YAML format in {file_path}. Root should be a dictionary (mapping).")
            return None
        for ctx_name, var_list in config.items():
            if not isinstance(var_list, list):
                 logging.error(f"Invalid format for context '{ctx_name}' in {file_path}. Value should be a list.")
                 return None
            for item in var_list:
                if not isinstance(item, dict) or len(item) != 1:
                    logging.error(f"Invalid variable format under context '{ctx_name}' in {file_path}. Each list item should be a single key-value pair dictionary.")
                    return None
        logging.info(f"Successfully loaded configuration from {file_path}")
        return config
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {file_path}: {e}")
        return None
    except IOError as e:
        logging.error(f"Could not read file {file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred loading {file_path}: {e}")
        return None


# --- CircleCI API Client Class ---

class CircleCIClient:
    """A basic client for interacting with the CircleCI v2 API."""

    def __init__(self, api_token: str, org_id: str, base_url: str = CIRCLECI_API_BASE_URL):
        if not api_token:
            raise ValueError("API token cannot be empty.")
        if not org_id:
             raise ValueError("Organization ID cannot be empty.")

        self.base_url = base_url
        self.org_id = org_id
        self._headers = {
            "Circle-Token": api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Makes an HTTP request to the CircleCI API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"API Request failed: {method} {url}")
            if e.response is not None:
                logging.error(f"Status Code: {e.response.status_code}")
                try:
                     # Try to get more specific error message from CircleCI response
                     error_data = e.response.json()
                     logging.error(f"Error details: {error_data.get('message', e.response.text)}")
                except ValueError: # If response isn't JSON
                     logging.error(f"Error details: {e.response.text}")
            else:
                logging.error(f"Error: {e}")
            return None

    def list_contexts(self) -> Dict[str, str]:
        """
        Lists all contexts for the configured organization.

        Returns:
            A dictionary mapping context names to context IDs.
            Returns an empty dictionary on error or if no contexts exist.
        """
        contexts = {}
        next_page_token = None
        endpoint = f"context?owner-id={self.org_id}" # Use Org ID

        while True:
            current_endpoint = endpoint
            if next_page_token:
                current_endpoint += f"&page-token={next_page_token}"

            logging.debug(f"Listing contexts: GET {current_endpoint}")
            response = self._request("GET", current_endpoint)

            if response:
                try:
                    data = response.json()
                    for item in data.get("items", []):
                        contexts[item["name"]] = item["id"]
                    next_page_token = data.get("next_page_token")
                    if not next_page_token:
                        break # Exit loop if no more pages
                except (ValueError, KeyError) as e:
                     logging.error(f"Failed to parse list contexts response: {e}")
                     return {} # Return empty on parsing error
            else:
                logging.error("Failed to retrieve contexts from API.")
                return {} # Return empty on API request error

        logging.info(f"Found {len(contexts)} existing contexts for org ID {self.org_id}")
        return contexts

    def create_context(self, context_name: str) -> Optional[str]:
        """
        Creates a new context in the configured organization.

        Args:
            context_name: The name for the new context.

        Returns:
            The ID of the newly created context, or None on failure.
        """
        endpoint = "context"
        payload = {
            "name": context_name,
            "owner": {
                "id": self.org_id,
                "type": "organization" # API requires specifying type
            }
        }
        logging.info(f"Attempting to create context '{context_name}'...")
        response = self._request("POST", endpoint, json=payload)

        if response:
            try:
                data = response.json()
                context_id = data.get("id")
                if context_id:
                    logging.info(f"Successfully created context '{context_name}' with ID: {context_id}")
                    return context_id
                else:
                    logging.error(f"Context creation response did not contain an ID. Response: {data}")
                    return None
            except ValueError:
                 logging.error("Failed to parse create context response.")
                 return None
        else:
            # Error logged in _request
            return None

    def list_environment_variables(self, context_id: str) -> Set[str]:
        """
        Lists environment variable names for a given context ID.

        Args:
            context_id: The ID of the context.

        Returns:
            A set containing the names of existing environment variables.
            Returns an empty set on error.
        """
        variables = set()
        next_page_token = None
        endpoint = f"context/{context_id}/environment-variable"

        while True:
            current_endpoint = endpoint
            if next_page_token:
                current_endpoint += f"?page-token={next_page_token}"

            logging.debug(f"Listing env vars for context {context_id}: GET {current_endpoint}")
            response = self._request("GET", current_endpoint)

            if response:
                try:
                    data = response.json()
                    for item in data.get("items", []):
                        variables.add(item["variable"]) # Add the variable name to the set
                    next_page_token = data.get("next_page_token")
                    if not next_page_token:
                        break # Exit loop if no more pages
                except (ValueError, KeyError) as e:
                     logging.error(f"Failed to parse list env vars response for context {context_id}: {e}")
                     return set() # Return empty on parsing error
            else:
                 logging.error(f"Failed to retrieve env vars for context {context_id} from API.")
                 return set() # Return empty on API request error

        logging.debug(f"Found {len(variables)} existing variables in context {context_id}")
        return variables


    def create_or_update_environment_variable(
        self, context_id: str, var_name: str, var_value: str
    ) -> bool:
        """
        Creates or updates an environment variable within a context.
        Uses the PUT endpoint as specified in the OpenAPI spec.

        Args:
            context_id: The ID of the context.
            var_name: The name of the environment variable.
            var_value: The value of the environment variable.

        Returns:
            True if the operation was successful, False otherwise.
        """
        # Value must be a string according to API specs observed in practice
        if not isinstance(var_value, str):
             var_value = str(var_value)

        endpoint = f"context/{context_id}/environment-variable/{var_name}"
        payload = {"value": var_value}

        logging.debug(f"Attempting to create/update env var '{var_name}' in context {context_id}...")
        response = self._request("PUT", endpoint, json=payload)

        if response:
            # PUT returns the updated/created variable object on success (status 200)
            logging.debug(f"Successfully created/updated variable '{var_name}' in context {context_id}.")
            return True
        else:
            # Error logged in _request
            logging.error(f"Failed to create/update variable '{var_name}' in context {context_id}.")
            return False


# --- Main Execution Logic ---

def main():
    parser = argparse.ArgumentParser(
        description="Manage CircleCI Contexts and Environment Variables based on a YAML config file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--org-id",
        required=True,
        help="Your CircleCI Organization ID. Found in Organization Settings in the CircleCI UI."
             " Required to identify which organization owns the contexts."
    )
    # Potential future addition: --org-slug argument as an alternative to org-id
    # parser.add_argument(
    #     "--org-slug",
    #     help="Your CircleCI Organization Slug (e.g., 'gh/my-org'). Alternative to --org-id."
    # )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the actions without making any changes in CircleCI."
    )

    args = parser.parse_args()

    # --- Initialization ---
    api_token = get_api_token()
    if not api_token:
        sys.exit(1) # Error logged in get_api_token

    config_data = load_config_yaml(args.config)
    if not config_data:
        sys.exit(1) # Error logged in load_config_yaml

    if args.dry_run:
        logging.warning("--- DRY RUN MODE ENABLED: No changes will be made to CircleCI. ---")

    # --- API Client Setup ---
    try:
         client = CircleCIClient(api_token=api_token, org_id=args.org_id)
    except ValueError as e:
         logging.error(f"Failed to initialize CircleCI client: {e}")
         sys.exit(1)

    # --- Get Existing Contexts ---
    logging.info("Fetching existing contexts from CircleCI...")
    if args.dry_run:
        existing_contexts = {name: f"dry-run-id-{name}" for name in config_data.keys()} # Simulate existing
        logging.info("[Dry Run] Simulated fetching contexts.")
    else:
        existing_contexts = client.list_contexts()
        if existing_contexts is None: # Check if API call failed critically
             logging.error("Could not retrieve existing contexts. Aborting.")
             sys.exit(1)


    # --- Process Contexts from Config ---
    for context_name, variables_list in config_data.items():
        logging.info(f"Processing Context: '{context_name}'")
        context_id = existing_contexts.get(context_name)

        # 1. Ensure Context Exists
        if context_id:
            logging.info(f"Context '{context_name}' already exists with ID: {context_id}")
        else:
            logging.info(f"Context '{context_name}' not found.")
            if args.dry_run:
                logging.info(f"[Dry Run] Would create context '{context_name}'.")
                context_id = f"dry-run-new-id-{context_name}" # Simulate ID for dry run
            else:
                context_id = client.create_context(context_name)
                if not context_id:
                    logging.warning(f"Skipping context '{context_name}' due to creation failure.")
                    continue # Skip to the next context if creation failed
                existing_contexts[context_name] = context_id # Add newly created context to our map


        # 2. Process Environment Variables for this Context
        logging.info(f"Processing environment variables for context '{context_name}' (ID: {context_id})...")

        # Get existing variable names for comparison
        existing_var_names: Set[str] = set()
        if not args.dry_run:
            existing_var_names = client.list_environment_variables(context_id)
            # list_environment_variables returns empty set on error, logs the error.
            # We can proceed, but updates might fail if the list is incomplete due to error.


        # Iterate through variables defined in the YAML config
        # Remember the format is: [{"VAR1": "value1"}, {"VAR2": "value2"}]
        for var_dict in variables_list:
             if not isinstance(var_dict, dict) or len(var_dict) != 1:
                 logging.warning(f"Skipping invalid variable entry in context '{context_name}': {var_dict}")
                 continue

             var_name = list(var_dict.keys())[0]
             var_value = var_dict[var_name]

             action = "Updated" if var_name in existing_var_names else "Created"

             if args.dry_run:
                  logging.info(f"[Dry Run] Would ensure variable '{var_name}' is set in context '{context_name}'. Action: {action}.")
             else:
                  success = client.create_or_update_environment_variable(
                       context_id, var_name, var_value
                  )
                  if success:
                       logging.info(f"-> {action} variable '{var_name}' in context '{context_name}'.")
                  else:
                       # Error logged by client method
                       logging.warning(f"-> Failed to process variable '{var_name}' in context '{context_name}'.")


    logging.info("Script finished.")


if __name__ == "__main__":
    main()