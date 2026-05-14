"""
Cryptography utilities.

Handles SSH Key generation using the cryptographic library.
Provides pure-python key generation to avoid external dependencies on OpenSSL.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class KeyGenerator:
    """
    Generates and Manages cryptographic SSH keys.

    Uses the cryptography library to generate RSA key pairs for SSH authentication.
    This is pure-python and does not require external dependencies like OpenSSL, making it portable and easy to use in various environments.
    """

    @staticmethod
    def generate_ssh_key_pair(key_size: int = 2048) -> Tuple[str, str]:
        """
        Generates an RSA SSH key pair.

        Args:
            key_size (int): The size of the RSA key in bits. Default is 2048.

        Returns:
            Tuple[str, str]: A tuple containing the private key and public key as strings.
        """
        # Generate the private key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)

        # Serialize the private key to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        # Serialize the public key to OpenSSH format
        public_key = private_key.public_key()
        public_ssh = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')

        return private_pem, public_ssh
    
    @staticmethod
    def save_keys_to_files(private_key: str, public_key: str, droplet_name: str, directory: Optional[Path] = None, droplet_id: Optional[int] = None) -> Tuple[Path, Path]:
        """
        Saves the private and public keys to files with the droplet name in the filename.

        Args:
            private_key (str): The private key as a string.
            public_key (str): The public key as a string.
            droplet_name (str): The name of the droplet to incorporate into the filenames.
            directory (Optional[Path]): The directory to save the keys. If None, saves to ./SSH_Keys/.
            droplet_id (Optional[int]): The droplet ID to organize keys in a nested directory.
        
        Returns:
            Tuple[Path, Path]: A tuple containing the paths to the private and public key files

        Example:
            private_key, public_key = KeyGenerator.generate_ssh_key_pair()
            private_path, public_path = KeyGenerator.save_keys_to_files(private_key, public_key, droplet_name="my_droplet", droplet_id=12345)
            print(f"Private key saved to: {private_path}")
        """
        if directory is None:
            directory = Path("./SSH_Keys")
        
        # If droplet_id is provided, create nested directory: SSH_Keys/droplet_name/droplet_id/
        if droplet_id:
            directory = directory / droplet_name / str(droplet_id)
        else:
            directory = directory / droplet_name
        
        # Create directory if it doesn't exist
        directory.mkdir(parents=True, exist_ok=True)
        
        # Create file paths
        private_key_path = directory / "id_rsa"
        public_key_path = directory / "id_rsa.pub"
        
        # Write keys to files
        private_key_path.write_text(private_key)
        private_key_path.chmod(0o600)  # SSH requires restrictive permissions on private key
        
        public_key_path.write_text(public_key)
        public_key_path.chmod(0o644)
        
        return private_key_path, public_key_path