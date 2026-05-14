"""
Data Models

Droplet and related data structures for deployment tracking.
"""

from datetime import datetime
from typing import Optional, Dict


class Droplet:
    """
    Represents a single DigitalOcean droplet with all its metadata.
    
    This is a data class that encapsulates droplet information for easy
    manipulation and serialization. It's separate from the API operations,
    making it testable and reusable across different contexts.
    
    Properties tracked:
    - Identity: id, name
    - Location: region, status
    - Network: public_ip, networks
    - Provisioning: ssh_key_id, role, profile
    - Storage: private_key_path
    - Lifecycle: created_at
    
    Example:
        >>> droplet = Droplet(
        ...     id=570650646,
        ...     name="sliver-test",
        ...     ip="170.64.206.109",
        ...     region="syd1",
        ...     role="sliver"
        ... )
        >>> print(f"SSH: ssh -i {droplet.private_key_path} root@{droplet.ip}")
    """

    def __init__(
        self,
        id: int,
        name: str,
        ip: str,
        region: str = "syd1",
        role: str = "sliver",
        profile: str = "sydney-small",
        ssh_key_id: Optional[int] = None,
        private_key_path: Optional[str] = None,
        status: str = "new",
        created_at: Optional[str] = None
    ):
        """
        Initialize a Droplet instance.
        
        Args:
            id (int): Droplet ID from DigitalOcean
            name (str): Droplet display name
            ip (str): Public IPv4 address
            region (str): DigitalOcean region (e.g., "syd1")
            role (str): Provisioning role (e.g., "sliver", "redirector")
            profile (str): Deployment profile used (e.g., "sydney-small")
            ssh_key_id (int, optional): SSH key ID in DigitalOcean
            private_key_path (str, optional): Local path to private SSH key
            status (str): Current droplet status (e.g., "active", "new", "destroyed")
            created_at (str, optional): ISO timestamp of creation
        """
        self.id = id
        self.name = name
        self.ip = ip
        self.region = region
        self.role = role
        self.profile = profile
        self.ssh_key_id = ssh_key_id
        self.private_key_path = private_key_path
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert droplet to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "ip": self.ip,
            "region": self.region,
            "role": self.role,
            "profile": self.profile,
            "ssh_key_id": self.ssh_key_id,
            "private_key_path": self.private_key_path,
            "status": self.status,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data: Dict) -> "Droplet":
        """
        Create a Droplet instance from a dictionary.
        
        Auto-detects SSH private key path if not provided or doesn't exist.
        Searches in multiple common locations (by name, by ID, or combinations):
        1. Nested by ID: SSH_Keys/{droplet_name}/{droplet_id}/id_rsa
        2. Flat by name: SSH_Keys/{droplet_name}_id_rsa
        3. Simple nested by name: SSH_Keys/{droplet_name}/id_rsa
        4. Flat by ID: SSH_Keys/{droplet_id}_id_rsa
        5. Nested by ID: SSH_Keys/{droplet_id}/id_rsa
        """
        from pathlib import Path
        
        droplet_name = data["name"]
        droplet_id = data["id"]
        private_key_path = data.get("private_key_path")
        
        # If private_key_path is not set or file doesn't exist, try to auto-detect it
        if not private_key_path or not Path(private_key_path).exists():
            patterns = []
            
            # Try patterns using droplet name and ID
            if droplet_name and droplet_id:
                patterns.extend([
                    Path(f"SSH_Keys/{droplet_name}/{droplet_id}/id_rsa"),
                    Path(f"SSH_Keys/{droplet_name}_id_rsa"),
                    Path(f"SSH_Keys/{droplet_name}/id_rsa"),
                ])
            
            # Try patterns using just droplet ID
            if droplet_id:
                patterns.extend([
                    Path(f"SSH_Keys/{droplet_id}_id_rsa"),
                    Path(f"SSH_Keys/{droplet_id}/id_rsa"),
                ])
            
            # Try patterns using just droplet name
            if droplet_name:
                patterns.extend([
                    Path(f"SSH_Keys/{droplet_name}_id_rsa"),
                    Path(f"SSH_Keys/{droplet_name}/id_rsa"),
                ])
            
            private_key_path = None
            for pattern_path in patterns:
                if pattern_path.exists():
                    private_key_path = str(pattern_path)
                    break
        
        return Droplet(
            id=droplet_id,
            name=droplet_name,
            ip=data["ip"],
            region=data.get("region", "syd1"),
            role=data.get("role", "sliver"),
            profile=data.get("profile", "sydney-small"),
            ssh_key_id=data.get("ssh_key_id"),
            private_key_path=private_key_path,
            status=data.get("status", "new"),
            created_at=data.get("created_at")
        )

    def ssh_command(self) -> str:
        """
        Generate SSH command for connecting to this droplet.
        
        Returns:
            str: SSH command ready to paste into terminal
        
        Example:
            >>> cmd = droplet.ssh_command()
            >>> print(cmd)
            ssh -i ./SSH_keys/sliver-test/sliver-test_ssh_key root@170.64.206.109
        """
        if self.private_key_path:
            return f"ssh -i {self.private_key_path} root@{self.ip}"
        return f"ssh root@{self.ip}"