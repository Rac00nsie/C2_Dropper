"""
Configuration Management Module

Centralized configuration for all deployments:
- Droplet profiles (region, size, image combinations)
- Cloud-init provisioning templates
- API constants and timeouts
- File paths
"""

from pathlib import Path
from typing import Optional, Dict, List


class Config:
    """
    Manages all configuration settings for droplet deployments.
    
    This class provides a single source of truth for:
    - Droplet profiles (region, size, image combinations)
    - Cloud-init provisioning templates for different roles
    - API constants and timeouts
    - File paths for SSH keys and registries
    
    Benefits:
    - Easy to modify defaults without touching other code
    - Simple to add new regions, sizes, or roles
    - Configuration can be loaded from environment or files in future
    """

    # ========================================
    # Regional Deployment Profiles
    # ========================================
    # Each profile specifies a combination of region, droplet size, and base image
    # This allows users to easily switch deployment targets
    DROPLET_PROFILES = {
        "sydney-small": {
            "region": "syd1",
            "size": "s-1vcpu-1gb",
            "image": "debian-13-x64",
            "description": "1 vCPU, 1GB RAM, 25GB SSD in Sydney"
        },
        "sydney-medium": {
            "region": "syd1",
            "size": "s-2vcpu-2gb",
            "image": "debian-13-x64",
            "description": "2 vCPU, 2GB RAM, 50GB SSD in Sydney"
        },
        "london": {
            "region": "lon1",
            "size": "s-1vcpu-1gb",
            "image": "debian-13-x64",
            "description": "1 vCPU, 1GB RAM, 25GB SSD in London"
        },
        "new-york": {
            "region": "nyc3",
            "size": "s-1vcpu-1gb",
            "image": "debian-13-x64",
            "description": "1 vCPU, 1GB RAM, 25GB SSD in New York"
        },
        "singapore": {
            "region": "sgp1",
            "size": "s-1vcpu-1gb",
            "image": "debian-13-x64",
            "description": "1 vCPU, 1GB RAM, 25GB SSD in Singapore"
        },
        "frankfurt": {
            "region": "fra1",
            "size": "s-1vcpu-1gb",
            "image": "debian-13-x64",
            "description": "1 vCPU, 1GB RAM, 25GB SSD in Frankfurt"
        }
    }

    # ========================================
    # Cloud-Init Provisioning Templates
    # ========================================
    # Cloud-init templates are now in separate modules for scalability
    # See provisioning/ directory for role-specific configurations
    
    # ========================================
    # API Configuration
    # ========================================
    DROPLET_WAIT_TIMEOUT = 300  # Maximum 5 minutes to wait for droplet activation
    POLL_INTERVAL = 5           # Check droplet status every 5 seconds
    FIREWALL_NAME_PREFIX = "management-whitelist"  # Prefix for unique firewall names
    
    # ========================================
    # File Paths
    # ========================================
    SSH_KEY_DIR = Path("SSH_Keys")           # Directory for storing SSH keys
    DEPLOYMENT_REGISTRY = "deployment_info.json"  # JSON file tracking all deployments

    @staticmethod
    def get_profile(profile_name: str) -> Optional[Dict]:
        """
        Retrieve a deployment profile by name.
        
        Args:
            profile_name (str): Name of the profile (e.g., "sydney-small")
        
        Returns:
            dict: Profile configuration or None if not found
        """
        return Config.DROPLET_PROFILES.get(profile_name)

    @staticmethod
    def list_profiles() -> List[str]:
        """Return list of all available profiles."""
        return list(Config.DROPLET_PROFILES.keys())