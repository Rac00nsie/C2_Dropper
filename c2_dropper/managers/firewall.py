"""
Firewall Manager

Network security firewall rules and management.
"""

from typing import Optional, Dict

from c2_dropper.api.digitalocean import DigitalOceanAPI
from c2_dropper.config import Config


class Firewall:
    """
    Manages network security firewall rules for droplets.
    
    Firewall philosophy:
    - WHITELIST approach: Explicitly allow only necessary traffic
    - INBOUND: Restrict SSH and C2 access to your IP only
    - OUTBOUND: Allow all (needed for updates, C2 callbacks, etc.)
    
    Ports configured:
    - 22: SSH (remote administration)
    - 8888: Sliver C2 (default C2 communication port)
    
    Example:
        >>> firewall = Firewall(api)
        >>> firewall.apply_whitelist_rules(570650646, "203.0.113.42")
    """

    def __init__(self, api: DigitalOceanAPI):
        """
        Initialize firewall manager.
        
        Args:
            api (DigitalOceanAPI): The API client
        """
        self.api = api

    def apply_whitelist_rules(self, droplet_id: int, whitelist_ip: str, inbound_ports: Dict[str, str] = None) -> Optional[str]:
        """
        Apply firewall rules that whitelist only a specific IP address.
        
        This creates a firewall that:
        - Allows specified ports only from your IP
        - Allows all outbound traffic (for updates, callbacks)
        - Blocks all other inbound traffic
        
        Args:
            droplet_id (int): The droplet to protect
            whitelist_ip (str): Your public IP address to whitelist (e.g., "203.0.113.42")
            inbound_ports (dict): Dictionary of {port: protocol} (e.g., {"22": "tcp", "8888": "tcp"})
                                 If None, defaults to SSH (port 22) only
        
        Returns:
            str: Firewall ID if successful, None otherwise
        
        Security Implications:
        - The /32 suffix denotes a single IP address (not a subnet)
        - If your IP changes, you'll be locked out - update firewall manually
        - All unspecified inbound ports are implicitly denied
        
        Example:
            >>> firewall_id = firewall.apply_whitelist_rules(570650646, "203.0.113.42", {"22": "tcp", "8888": "tcp"})
        """
        if inbound_ports is None:
            inbound_ports = {"22": "tcp"}  # Default: SSH only
        
        # Unique firewall name: {prefix}-{droplet_id}
        firewall_name = f"{Config.FIREWALL_NAME_PREFIX}-{droplet_id}"

        # Build inbound rules from the provided ports, all restricted to operator IP
        inbound_rules = []
        for port, protocol in inbound_ports.items():
            inbound_rules.append({
                "protocol": protocol,
                "ports": str(port),
                "sources": {"addresses": [f"{whitelist_ip}/32"]}
            })

        firewall_config = {
            "name": firewall_name,
            
            # ============================================
            # INBOUND RULES: Restrict incoming traffic
            # ============================================
            # These rules whitelist only specific ports from operator IP
            "inbound_rules": inbound_rules,
            
            # ============================================
            # OUTBOUND RULES: Allow outgoing traffic
            # ============================================
            # Outbound is fully open so the droplet can reach:
            # - Package repositories (apt, pip)
            # - C2 callbacks
            # - External services
            "outbound_rules": [
                {
                    "protocol": "tcp",
                    "ports": "all",
                    "destinations": {"addresses": ["0.0.0.0/0", "::/6"]}
                },
                {
                    "protocol": "udp",
                    "ports": "all",
                    "destinations": {"addresses": ["0.0.0.0/0", "::/6"]}
                }
            ],
            
            "droplet_ids": [droplet_id]
        }

        firewall_id = self.api.create_firewall(firewall_config)
        
        if firewall_id:
            print(f"[+] Applied firewall rules to {droplet_id} for IP: {whitelist_ip}")
            print(f"[+] Opened ports: {', '.join([f'{port}/{protocol}' for port, protocol in inbound_ports.items()])}")
        else:
            print(f"[-] Failed to apply firewall rules")

        return firewall_id

    def add_inbound_port(self, firewall_id: str, port: int, protocol: str = "tcp", source_ip: str = "0.0.0.0/0") -> bool:
        """
        Add an inbound rule to an existing firewall to open a port.
        
        Args:
            firewall_id (str): The ID of the firewall to update
            port (int): The port number to open
            protocol (str): The protocol (tcp or udp), default is tcp
            source_ip (str): The source IP/CIDR to allow, default allows all (0.0.0.0/0)
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> firewall.add_inbound_port("abc123", 443, "tcp", "203.0.113.42/32")
        """
        try:
            firewall = self.api.get_firewall(firewall_id)
            if not firewall:
                print(f"[-] Firewall {firewall_id} not found")
                return False
            
            inbound_rules = firewall.get("inbound_rules", [])
            
            # Check if rule already exists
            for rule in inbound_rules:
                if rule.get("ports") == str(port) and rule.get("protocol") == protocol:
                    print(f"[*] Port {port}/{protocol} already open in firewall")
                    return True
            
            # Add new rule
            new_rule = {
                "protocol": protocol,
                "ports": str(port),
                "sources": {"addresses": [source_ip]}
            }
            inbound_rules.append(new_rule)
            
            update_config = {
                "inbound_rules": inbound_rules,
                "outbound_rules": firewall.get("outbound_rules", []),
                "name": firewall.get("name")
            }
            
            if self.api.update_firewall(firewall_id, update_config):
                print(f"[+] Opened port {port}/{protocol} on firewall {firewall_id} for {source_ip}")
                return True
            else:
                print(f"[-] Failed to update firewall rules")
                return False
        except Exception as e:
            print(f"[-] Error adding port: {e}")
            return False

    def get_firewall_id_for_droplet(self, droplet_id: int) -> Optional[str]:
        """
        Get the firewall ID associated with a droplet.
        
        Args:
            droplet_id (int): The droplet ID
        
        Returns:
            Optional[str]: The firewall ID if found, None otherwise
        """
        try:
            firewalls = self.api.list_firewall_rules(droplet_id)
            if firewalls and len(firewalls) > 0:
                firewall = firewalls[0]
                firewall_id = firewall.get("id")
                return firewall_id
            else:
                return None
        except Exception as e:
            print(f"[!] Error getting firewall for droplet: {e}")
            return None
