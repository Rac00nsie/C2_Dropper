"""
DigitalOcean API client.

Lowlevel API interaction with error handling and type hints.
Wraps the pydo.client with a simplified interface

"""

import os
from typing import Optional, Dict
from pydo import Client
from pydo.exceptions import HttpResponseError

class DigitalOceanAPI:
    """
    Wraps the pydo.Client with a simplified interface for common operations.

    This will handle:
    - Client initialization with API token, either from environment variable or passed directly.
    - Common error handling and retry logic for API calls.
    - Request/Response logging
    - Type hints for better IDEA support and code clarity.

    Benefits of this wrapper:
    - Decouples the application from pydo.Client implementation details
    - Allows for easy testing via dependency injection
    - Provides a consistent error handling pattern
    - Makes it simple to add rate limiting or retries in the future if needed

    Example usage:
        api = DigitalOceanAPI()
        droplet = api.get_droplet(droplet_id=123456)
        print(droplet["name"])
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initializes the DigitalOcean API client.

        Args:
            api_token (Optional[str]): The API token to use for authentication. If not provided, it will be read from the DIGITALOCEAN_API_TOKEN environment variable.

        Raises:
            ValueError: If no API token is provided and the environment variable is not set.
        """
        if api_token is None:
            api_token = os.getenv("DIGITALOCEAN_API_TOKEN")
            if api_token is None:
                raise ValueError("API token must be provided either as an argument or via the DIGITALOCEAN_API_TOKEN environment variable.")
        self.client = Client(token=api_token)

    def create_droplet(self, droplet_config: Dict) -> Optional[int]:
        """
        Create a new droplet with the given configuration.

        Args:
            droplet_config (Dict): A dictionary containing the droplet configuration.

        Returns:
            Optional[int]: The ID of the created droplet, or None if creation failed.
        """
        try:
            response = self.client.droplets.create(body=droplet_config)
            droplet_id = response.get("droplet", {}).get("id")
            if droplet_id:
                print(f"[+] Droplet {droplet_id} creation initiated")
            return droplet_id
        except HttpResponseError as e:
            print(f"API Error while creating droplet: {e}")
            return None

    def get_droplet(self, droplet_id: int) -> Optional[Dict]:
        """
        Retrieve droplet details by ID.

        Args:
            droplet_id (int): The ID of the droplet to retrieve.

        Returns:
            Optional[Dict]: A dictionary containing the droplet details, or None if not found or an error occurred.
        """
        try:
            response = self.client.droplets.get(droplet_id)
            return response.get("droplet")
        except HttpResponseError as e:
            print(f"API Error while retrieving droplet {droplet_id}: {e}")
            return None

    def delete_droplet(self, droplet_id: int) -> bool:
        """
        Permanently delete a droplet by ID.

        Args:
            droplet_id (int): The ID of the droplet to delete.

        Returns:
            bool: True if the droplet was successfully deleted, False otherwise.
        """
        try:
            # pydo uses destroy() method for droplets
            self.client.droplets.destroy(droplet_id)
            return True
        except AttributeError:
            # Fallback: try the delete method if destroy doesn't exist
            try:
                self.client.droplets.delete(droplet_id)
                return True
            except Exception as e:
                print(f"API Error while deleting droplet {droplet_id}: {e}")
                return False
        except HttpResponseError as e:
            print(f"API Error while deleting droplet {droplet_id}: {e}")
            return False

    def list_droplets(self) -> Optional[list]:
        """
        List all droplets in the account.

        Returns:
            Optional[list]: A list of dictionaries containing the droplet details, or None if an error occurred.
        """
        try:
            response = self.client.droplets.list()
            return response.get("droplets", [])
        except HttpResponseError as e:
            print(f"API Error while listing droplets: {e}")
            return None

    def list_firewall_rules(self, droplet_id: int) -> Optional[list]:
        """
        List all firewall rules associated with a specific droplet.

        Args:
            droplet_id (int): The ID of the droplet for which to list firewall rules.

        Returns:
            Optional[list]: A list of dictionaries containing the firewall rule details, or None if an error occurred.
        """
        try:
            # Get all firewalls
            response = self.client.firewalls.list()
            all_firewalls = response.get("firewalls", [])
            
            # Filter to find firewalls associated with this droplet
            # First try: match by droplet_ids (if properly set)
            associated_firewalls = [
                fw for fw in all_firewalls 
                if droplet_id in fw.get("droplet_ids", [])
            ]
            
            # If no match by droplet_ids, try matching by firewall name pattern
            # Firewalls are typically named like "management-whitelist-570863894" or "fw-sliver-test-570858392"
            if not associated_firewalls:
                associated_firewalls = [
                    fw for fw in all_firewalls 
                    if str(droplet_id) in fw.get("name", "")
                ]
            
            return associated_firewalls
        except Exception as e:
            print(f"API Error while listing firewalls for droplet {droplet_id}: {e}")
            return None

    def create_firewall(self, firewall_config: Dict) -> Optional[str]:
        """
        Create a new firewall with the given configuration.

        Args:
            firewall_config (Dict): A dictionary containing the firewall configuration.

        Returns:
            Optional[str]: The ID of the created firewall, or None if creation failed.
        """
        try:
            response = self.client.firewalls.create(body=firewall_config)
            firewall_id = response.get("firewall", {}).get("id")
            if firewall_id:
                print(f"[+] Firewall {firewall_id} created")
            return firewall_id
        except HttpResponseError as e:
            print(f"API Error while creating firewall: {e}")
            return None

    def get_firewall(self, firewall_id: str) -> Optional[Dict]:
        """
        Retrieve firewall details by ID.

        Args:
            firewall_id (str): The ID of the firewall to retrieve.

        Returns:
            Optional[Dict]: A dictionary containing the firewall details, or None if not found or an error occurred.
        """
        try:
            response = self.client.firewalls.get(firewall_id)
            return response.get("firewall")
        except HttpResponseError as e:
            print(f"API Error while retrieving firewall {firewall_id}: {e}")
            return None

    def update_firewall(self, firewall_id: str, firewall_config: Dict) -> bool:
        """
        Update an existing firewall.

        Args:
            firewall_id (str): The ID of the firewall to update.
            firewall_config (Dict): A dictionary containing the updated firewall configuration.

        Returns:
            bool: True if the firewall was updated successfully, False otherwise.
        """
        try:
            self.client.firewalls.update(firewall_id, body=firewall_config)
            return True
        except HttpResponseError as e:
            print(f"API Error while updating firewall {firewall_id}: {e}")
            return None

    def delete_firewall(self, firewall_id: str) -> bool:
        """
        Delete a firewall by ID.

        Args:
            firewall_id (str): The ID of the firewall to delete.

        Returns:
            bool: True if the firewall was deleted successfully, False otherwise.
        """
        try:
            self.client.firewalls.delete(firewall_id)
            return True
        except HttpResponseError as e:
            print(f"API Error while deleting firewall {firewall_id}: {e}")
            return False