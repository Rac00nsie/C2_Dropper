"""
Droplet Management Module for C2 Dropper

High-Level droplet operations via the DigitalOcean API.
"""

import time
from typing import Optional

from ..config import Config
from ..api.digitalocean import DigitalOceanAPI

class DropletManager:
    """
    High-Level droplet operations using the DigitalOcean API.

    This class orchestrates droplet lifecycle management, including:
    - Creation with cloud-init privisioning
    - Status monitoring until active
    - IP address retrieval for post-deployment access
    - Graceful destruction of droplets when no longer needed

    Benefits:
    - Encapsulates all droplet-related logic in one place
    - Provides a clean interface for the main application to interact with droplets
    - Handles common edge cases like API errors and timeouts
    - easy to extend with additional features like tagging, backups, or snapshots in the future

    example usage:
        manager = DropletManager(api)
        droplet = manager.create_droplet(profile="sydney-small", ssh_key_id=123456, user_data="#cloud-config...")
        print(f"Droplet created with ID: {droplet['id']}")
        print(droplet.ip)
    """

    def __init__(self, api: DigitalOceanAPI):
        """
        Initializes the DropletManager with a DigitalOceanAPI instance.

        Args:
            api (DigitalOceanAPI): An instance of the DigitalOceanAPI class for interacting with the API.
        """
        self.api = api

    def create_droplet(self, name: str, region: str, size: str, profile: str, ssh_key_id: int, user_data: Optional[str] = None) -> Optional[int]:
        """
        create a new droplet via the DigitalOcean API

        Args:
            name (str): The name of the droplet to create.
            region (str): The region to create the droplet in (e.g., "syd1").
            size (str): The size of the droplet (e.g., "s-1vcpu-1gb").
            profile (str): The droplet profile to use for the base image (e.g., "debian-13-x64").
            ssh_key_id (int): The ID of the SSH key to associate with the droplet for authentication.
            user_data (Optional[str]): Optional cloud-init user data to provision the droplet on creation.

        Returns:
            Optional[int]: The ID of the created droplet, or None if creation failed.

        Note:
            - The droplet creation is asynchronous. This returns immediately after receiving the API response. Use the wait_for_activition method to wait until the droplet is active and retrieve its IP address.
    
        """
        droplet_config = {
            "name": name,
            "region": region,
            "size": size,
            "image": profile,
            "ssh_keys": [ssh_key_id],
            "tags": ["c2-dropper"]
        }

        if user_data:
            droplet_config["user_data"] = user_data
        
        droplet_id = self.api.create_droplet(droplet_config)
        
        if not droplet_id:
            print("[-] Failed to create droplet.")
        return droplet_id

    def create(
        self,
        name: str,
        region: str,
        size: str,
        image: str,
        ssh_key_id: int,
        user_data: Optional[str] = None,
    ) -> Optional[int]:
        """Backward-compatible alias for create_droplet."""
        return self.create_droplet(
            name=name,
            region=region,
            size=size,
            profile=image,
            ssh_key_id=ssh_key_id,
            user_data=user_data,
        )
        
    def get_status(self, droplet_id: int):
        """
        Retrieve current droplet status and details

        Args:
            droplet_id (int): The ID of the droplet to check.

        return
            Dict: A dictionary containing the droplet details, or None if not found or an error occurred.
        """
        return self.api.get_droplet(droplet_id)
    
    def get_ip(self, droplet_id: int) -> Optional[str]:
        """
        Retrieve the public IP address of the droplet.

        Args:
            droplet_id (int): The ID of the droplet to check.

        Returns:
            Optional[str]: The public IP address of the droplet, or None if not found or an error occurred.
        """
        droplet = self.get_status(droplet_id)
        if droplet and "networks" in droplet:
            for network in droplet["networks"]["v4"]:
                if network["type"] == "public":
                    return network["ip_address"]
        return None
    
    def wait_for_activition(self, droplet_id: int, timeout: int = None, poll_interval: int = None) -> Optional[str]:
        """
        Wait for the droplet to become active and retrieve its public IP address.

        Args:
            droplet_id (int): The ID of the droplet to monitor.
            timeout (int): Maximum time in seconds to wait for activation (default: Config.DROPLET_WAIT_TIMEOUT).
            poll_interval (int): Time in seconds between status checks. Default is Config.POLL_INTERVAL.
        
        Returns:
            Optional[str]: The public IP address of the droplet, or None if not found or an error occurred.

        Example usage:
            ip = manager.wait_for_activition(droplet_id=123456)
            if ip:
                print(f"Droplet is active with IP: {ip}")
            else:
                print("Droplet did not become active within the timeout period.")

        """
        timeout = timeout or Config.DROPLET_WAIT_TIMEOUT
        poll_interval = poll_interval or Config.POLL_INTERVAL
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                droplet = self.api.get_droplet(droplet_id)
                if not droplet:
                    print(f"[-] Droplet with ID {droplet_id} not found.")
                    return None
                if droplet["status"] == "active":
                    ip = self.get_ip(droplet_id)
                    if ip:
                        print(f"[+] Droplet {droplet_id} is active with IP: {ip}")
                        return ip
                    print(f"[*] Droplet status: {droplet['status']}. Waiting {poll_interval} seconds before checking again...")
    
            except Exception as e:
                print(f"Error while checking droplet status: {e}")
            
            time.sleep(poll_interval)
        print(f"[-] Timeout reached while waiting for droplet {droplet_id} to become active.")
        return None

    def wait_for_activation(self, droplet_id: int, timeout: int = None, poll_interval: int = None) -> Optional[str]:
        """Backward-compatible alias for wait_for_activition."""
        return self.wait_for_activition(droplet_id, timeout=timeout, poll_interval=poll_interval)
    
    def destroy_droplet(self, droplet_id: int) -> bool:
        """
        Permanently delete a droplet by ID.

        Args:
            droplet_id (int): The ID of the droplet to delete.

        Returns:
            bool: True if deletion was successful, False otherwise.

        Example usage:
            success = manager.destroy_droplet(droplet_id=123456)
            if success:
                print("Droplet successfully deleted.")
            else:
                print("Failed to delete droplet.")
        """
        if self.api.delete_droplet(droplet_id):
            print(f"[+] Droplet {droplet_id} deletion initiated.")
            return True
        return False

    def destroy(self, droplet_id: int) -> bool:
        """Backward-compatible alias for destroy_droplet."""
        return self.destroy_droplet(droplet_id)