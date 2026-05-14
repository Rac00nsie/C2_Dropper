"""SSH Manager for generation, uploads, and cleanup of SSH keys on DigitalOcean droplets."""

from pathlib import Path
from typing import Optional, Tuple

from ..utils.crypto import KeyGenerator
from ..config import Config
from ..api.digitalocean import DigitalOceanAPI

class SSHKeyManager:
    """
    Manage SSH key lifecycle: local generation and DigitalOcean account Management.

    This class handles:
    - Generating SSH key pairs using the KeyGenerator utility
    - Securely saving keys to disk with droplet-specific filenames
    - Uploading public keys to the DigitalOcean account for use in droplet provisioning
    - Tracking uploaded keys for cleanup after droplet deletion
    - Deleting SSH keys from both local storage and the DigitalOcean account when no longer needed

    Example usage:
        manager = SSHKeyManager(API_TOKEN)
        private_key, public_key = manager.generate_local_keys(droplet_name="sliver-droplet")
        key_id = manager.upload_public_key(public_key, key_name="sliver-droplet-key")
        # Use the key_id when creating droplets
    """

    def __init__(self, api: DigitalOceanAPI):
        """
        Initializes the SSHKeyManager with a DigitalOceanAPI instance.

        Args:
            api (DigitalOceanAPI): An instance of the DigitalOceanAPI class for interacting with the API.
        """
        self.api = api
        Config.SSH_KEY_DIR.mkdir(exist_ok=True)  # Ensure the SSH key directory exists

    def generate_local_keys(self, droplet_name: str) -> Tuple[Path, Path]:
        """
        Generate an RSA SSH key pair and save them to local files with droplet-specific names.

        Key storage is organized as follows:
        SSH_keys/
            {droplet_name}_id_rsa (private key) (Private, 0600 permissions)
            {droplet_name}_id_rsa.pub (public key) (Public, 0644 permissions)

        Args:
            droplet_name (str): The name of the droplet to incorporate into the key filenames.

        Returns:
            Tuple: (private_key_path, public_key_path) - Paths to the saved private and public key files. or (None, None) if generation failed.

        Example usage:
            private_key_path, public_key_path = manager.generate_local_keys(droplet_name="sliver-droplet")
            print(f"Private key saved to: {private_key_path}")
            print(f"Public key saved to: {public_key_path}")
        """
        try:
            private_key, public_key = KeyGenerator.generate_ssh_key_pair()
            private_path, public_path = KeyGenerator.save_keys_to_files(
                private_key,
                public_key,
                droplet_name,
                directory=Config.SSH_KEY_DIR,
            )
            return private_path, public_path
        except Exception as e:
            print(f"Error generating SSH keys for {droplet_name}: {e}")
            return None, None

    def generate_local_keypair(self, droplet_name: str) -> Tuple[Path, Path]:
        """Backward-compatible alias for generate_local_keys."""
        return self.generate_local_keys(droplet_name)
        
    def upload_public_key(self, public_key: str, key_name: str) -> Optional[int]:
        """
        Upload the public SSH key to the DigitalOcean account.

        Args:
            public_key (str): The public key string to upload.
            key_name (str): A unique name for the SSH key in the DigitalOcean account.

        Returns:
            Optional[int]: The ID of the uploaded SSH key in DigitalOcean, or None if upload failed.

        Example usage:
            key_id = manager.upload_public_key(public_key, key_name="sliver-droplet-key")
            print(f"Uploaded SSH key with ID: {key_id}")
        """
        try:
            response = self.api.client.ssh_keys.create(body={"name": key_name, "public_key": public_key})
            return response.get("ssh_key", {}).get("id")
        except Exception as e:
            print(f"Error uploading SSH key '{key_name}': {e}")
            return None
        
    def cleanup_keys(self, key_id: int, private_key_path: Path, public_key_path: Path) -> bool:
        """
        Delete the SSH key from the DigitalOcean account and remove local key files.

        Args:
            key_id (int): The ID of the SSH key in DigitalOcean to delete.
            private_key_path (Path): The file path to the private key to delete.
            public_key_path (Path): The file path to the public key to delete.
        Returns:
            bool: True if cleanup was successful, False otherwise.
        """
        success = True
        # Delete from DigitalOcean
        try:
            self.api.client.ssh_keys.delete(key_id)
        except Exception as e:
            print(f"Error deleting SSH key with ID {key_id} from DigitalOcean: {e}")
            success = False
        
        # Delete local files
        for path in [private_key_path, public_key_path]:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                print(f"Error deleting local SSH key file {path}: {e}")
                success = False
        
        return success

    def cleanup_key(
        self,
        key_id: int,
        private_key_path: Optional[Path] = None,
        public_key_path: Optional[Path] = None,
    ) -> bool:
        """Backward-compatible cleanup helper used by the orchestrator."""
        if private_key_path is None or public_key_path is None:
            try:
                self.api.client.ssh_keys.delete(key_id)
                return True
            except Exception as e:
                print(f"Error deleting SSH key with ID {key_id} from DigitalOcean: {e}")
                return False

        return self.cleanup_keys(key_id, private_key_path, public_key_path)
    
    def list_uploaded_keys(self) -> Optional[list]:
        """
        List all SSH keys currently uploaded to the DigitalOcean account.

        Returns:
            Optional[list]: A list of dictionaries containing the SSH key details, or None if an error occurred.

        Example usage:
            keys = manager.list_uploaded_keys()
            for key in keys:
                print(f"Key ID: {key['id']}, Name: {key['name']}")
        """
        try:
            response = self.api.client.ssh_keys.list()
            return response.get("ssh_keys", [])
        except Exception as e:
            print(f"Error listing uploaded SSH keys: {e}")
            return None
        