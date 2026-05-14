"""
Deployment Registry

Persistent storage of deployment records.
"""

import json
import os
from typing import Optional, List, Dict

from c2_dropper.config import Config
from c2_dropper.models.droplet import Droplet


class DeploymentRegistry:
    """
    Manages persistent storage of deployment information.
    
    The registry is a JSON file that tracks:
    - All deployed droplets (ID, IP, SSH key, etc.)
    - Deployment timestamps
    - Configuration used (role, profile, region)
    
    This enables:
    - Easy listing of all active deployments
    - Graceful cleanup when destroying droplets
    - Auditing and tracking of infrastructure changes
    - Recovery of deployment details for future operations
    
    Format:
        [
            {
                "id": 570650646,
                "name": "sliver-test",
                "ip": "170.64.206.109",
                ...
            },
            ...
        ]
    
    Example:
        >>> registry = DeploymentRegistry()
        >>> registry.save(droplet)
        >>> all_droplets = registry.load_all()
        >>> print(f"Deployed: {len(all_droplets)} droplets")
    """

    def __init__(self, filepath: str = None):
        """
        Initialize the deployment registry.
        
        Args:
            filepath (str, optional): Path to JSON registry file
        """
        self.filepath = filepath or Config.DEPLOYMENT_REGISTRY

    def save(self, droplet: Droplet) -> bool:
        """
        Add a droplet record to the registry.
        
        Args:
            droplet (Droplet): The droplet to save
        
        Returns:
            bool: True if successful
        
        Example:
            >>> registry.save(droplet)
            [+] Registered droplet: sliver-test
        """
        try:
            # Load existing deployments
            deployments = self.load_all()
            
            # Check if this droplet is already registered (update instead of duplicate)
            for i, dep in enumerate(deployments):
                if dep["id"] == droplet.id:
                    deployments[i] = droplet.to_dict()
                    print(f"[*] Updated registration for: {droplet.name}")
                    self._write(deployments)
                    return True

            # Add new deployment
            deployments.append(droplet.to_dict())
            self._write(deployments)
            print(f"[+] Registered droplet: {droplet.name}")
            return True

        except Exception as e:
            print(f"[-] Error saving deployment: {e}")
            return False

    def load_all(self) -> List[Dict]:
        """
        Load all deployments from the registry.
        
        Returns:
            list: List of droplet dictionaries
        
        Example:
            >>> deployments = registry.load_all()
            >>> for dep in deployments:
            ...     print(f"{dep['name']}: {dep['ip']}")
        """
        if not os.path.exists(self.filepath):
            return []

        try:
            with open(self.filepath, "r") as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[-] Registry file corrupted (JSON error at line {e.lineno}): {e.msg}")
            print(f"[*] Attempting to recover...")
            # Try to fix common issues like trailing commas
            try:
                with open(self.filepath, "r") as f:
                    content = f.read()
                    # Remove trailing commas before closing brackets
                    import re
                    content = re.sub(r',(\s*[}\]])', r'\1', content)
                    fixed = json.loads(content)
                    print(f"[+] Registry recovered: {len(fixed)} entries")
                    return fixed
            except:
                print(f"[-] Could not recover registry file. Starting fresh.")
                return []
        except Exception as e:
            print(f"[-] Error loading deployments: {e}")
            return []

    def get_by_id(self, droplet_id: int) -> Optional[Dict]:
        """Get a specific droplet by ID."""
        for dep in self.load_all():
            if dep["id"] == droplet_id:
                return dep
        return None

    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get a specific droplet by name."""
        for dep in self.load_all():
            if dep["name"] == name:
                return dep
        return None

    def remove(self, droplet_id: int) -> bool:
        """
        Remove a droplet from the registry.
        
        Args:
            droplet_id (int): The droplet ID to remove
        
        Returns:
            bool: True if successful
        """
        try:
            deployments = self.load_all()
            original_count = len(deployments)
            deployments = [d for d in deployments if d["id"] != droplet_id]
            
            if len(deployments) < original_count:
                self._write(deployments)
                print(f"[+] Removed droplet {droplet_id} from registry")
                return True
            
            return False

        except Exception as e:
            print(f"[-] Error removing deployment: {e}")
            return False

    def _write(self, deployments: List[Dict]) -> None:
        """Write deployments to registry file."""
        with open(self.filepath, "w") as f:
            json.dump(deployments, f, indent=2)