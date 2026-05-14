"""
Deployment Orchestrator

High-level deployment coordination and workflow management.
"""

import requests
from pathlib import Path
from typing import Optional, List, Dict

from ..api.digitalocean import DigitalOceanAPI
from ..config import Config
from ..managers.ssh import SSHKeyManager
from ..managers.droplet import DropletManager
from ..managers.firewall import Firewall
from ..managers.registry import DeploymentRegistry
from ..models.droplet import Droplet
from ..provisioning.templates import get_template, list_available_roles


class DeploymentOrchestrator:
    """
    High-level deployment coordination: pulls together all components.
    
    This class orchestrates the complete workflow:
    1. Detect your public IP (for firewall)
    2. Generate SSH key pair
    3. Upload SSH key to DigitalOcean
    4. Create droplet with cloud-init
    5. Wait for droplet to be active
    6. Apply firewall rules
    7. Register deployment in JSON
    8. Print summary
    
    Benefits:
    - Single entry point for deployments
    - All steps are logged and can be monitored
    - Easy to add new steps or modify workflow
    - Failures are gracefully handled with cleanup
    
    Example:
        >>> api = DigitalOceanAPI()
        >>> orchestrator = DeploymentOrchestrator(api)
        >>> droplet = orchestrator.deploy("sliver-test", "sliver", "sydney-small")
        >>> print(f"Deployed at: {droplet.ip}")
    """

    def __init__(self, api: DigitalOceanAPI):
        """
        Initialize the orchestrator with dependencies.
        
        Args:
            api (DigitalOceanAPI): The API client
        """
        self.api = api
        self.ssh_manager = SSHKeyManager(api)
        self.droplet_manager = DropletManager(api)
        self.firewall = Firewall(api)
        self.registry = DeploymentRegistry()
        
        # Firewall configuration (can be set via set_firewall_config)
        self.operator_ip = None
        self.inbound_ports = {"22": "tcp"}  # Default: SSH for operator only

    def deploy(
        self,
        droplet_name: str,
        role: str = "sliver",
        profile: str = "sydney-small"
    ) -> Optional[Droplet]:
        """
        Execute full deployment workflow.
        
        Args:
            droplet_name (str): Name for the droplet (e.g., "sliver-test")
            role (str): Provisioning role (e.g., "sliver", "redirector")
            profile (str): Deployment profile (e.g., "sydney-small")
        
        Returns:
            Droplet: Completed droplet object or None if deployment failed
        
        Example:
            >>> droplet = orchestrator.deploy("sliver-prod", "sliver", "sydney-medium")
            >>> print(f"ID: {droplet.id}, IP: {droplet.ip}")
        """
        print(f"\n{'='*70}")
        print(f"[*] Starting deployment of {droplet_name} ({role})")
        print(f"{'='*70}\n")

        # ====================================================================
        # STEP 1: Get user's public IP (required for firewall whitelist)
        # ====================================================================
        # Use pre-configured operator IP if set, otherwise detect it
        if self.operator_ip:
            my_ip = self.operator_ip
            print(f"[*] Using pre-configured operator IP: {my_ip}")
        else:
            my_ip = self._get_my_ip()
            if not my_ip:
                print("[!] Could not determine your IP. Aborting deployment.")
            return None
        print(f"[+] Your public IP: {my_ip}\n")

        # ====================================================================
        # STEP 2: Get deployment profile
        # ====================================================================
        profile_config = Config.get_profile(profile)
        if not profile_config:
            print(f"[-] Unknown profile: {profile}")
            print(f"[*] Available profiles: {', '.join(Config.list_profiles())}")
            return None

        region = profile_config["region"]
        size = profile_config["size"]
        image = profile_config["image"]
        print(f"[*] Using profile: {profile}")
        print(f"[*]   Region: {region}, Size: {size}, Image: {image}\n")

        # ====================================================================
        # STEP 3: Get cloud-init configuration
        # ====================================================================
        try:
            user_data = get_template(role)
        except ValueError as e:
            print(f"[-] {e}")
            print(f"[*] Available roles: {', '.join(list_available_roles())}")
            return None
        print(f"[*] Using role: {role}\n")

        # ====================================================================
        # STEP 4: Generate SSH key pair locally
        # ====================================================================
        print("[*] Generating SSH key pair...")
        priv_key, pub_key = self.ssh_manager.generate_local_keypair(droplet_name)
        if not priv_key:
            print("[!] Failed to generate SSH keys. Aborting.")
            return None
        print(f"[+] SSH keys generated\n")

        # ====================================================================
        # STEP 5: Upload public key to DigitalOcean
        # ====================================================================
        print("[*] Uploading SSH key to DigitalOcean...")
        key_name = f"{droplet_name}_key"
        # Read the public key file content for upload
        pub_key_content = pub_key.read_text()
        ssh_key_id = self.ssh_manager.upload_public_key(pub_key_content, key_name)
        if not ssh_key_id:
            print("[!] Failed to upload SSH key. Aborting.")
            return None
        print(f"[+] SSH key uploaded\n")

        # ====================================================================
        # STEP 6: Create droplet with cloud-init provisioning
        # ====================================================================
        print(f"[*] Creating droplet with {role} provisioning...")
        droplet_id = self.droplet_manager.create(
            name=droplet_name,
            region=region,
            size=size,
            image=image,
            ssh_key_id=ssh_key_id,
            user_data=user_data
        )

        if not droplet_id:
            print("[!] Failed to create droplet. Aborting.")
            # Cleanup SSH key if droplet creation failed
            self.ssh_manager.cleanup_key(ssh_key_id)
            return None
        print(f"[+] Droplet {droplet_id} creation request sent\n")

        # ====================================================================
        # STEP 6b: Reorganize SSH keys with droplet ID
        # ====================================================================
        try:
            old_dir = Path(f"./SSH_Keys/{droplet_name}")
            new_dir = Path(f"./SSH_Keys/{droplet_name}/{droplet_id}")
            if old_dir.exists() and old_dir != new_dir:
                # Create new directory and move files
                new_dir.mkdir(parents=True, exist_ok=True)
                for file in old_dir.glob("id_rsa*"):
                    file.rename(new_dir / file.name)
                # Remove old directory if empty
                try:
                    old_dir.rmdir()
                except:
                    pass
            priv_key = new_dir / "id_rsa"
            pub_key = new_dir / "id_rsa.pub"
        except Exception as e:
            print(f"[*] Note: Could not reorganize SSH keys: {e}")
            # Continue anyway - keys are still there, just not in ideal structure

        # ====================================================================
        # STEP 7: Wait for droplet to be active and get IP
        # ====================================================================
        print("[*] Waiting for droplet to become active...")
        droplet_ip = self.droplet_manager.wait_for_activation(droplet_id)
        if not droplet_ip:
            print("[!] Droplet activation timed out. Aborting.")
            # Cleanup: destroy droplet and SSH key
            self.droplet_manager.destroy(droplet_id)
            self.ssh_manager.cleanup_key(ssh_key_id)
            return None
        print(f"[+] Droplet is now active\n")

        # ====================================================================
        # STEP 8: Apply firewall rules (whitelist only your IP)
        # ====================================================================
        print("[*] Applying firewall rules...")
        self.firewall.apply_whitelist_rules(droplet_id, my_ip, self.inbound_ports)
        print(f"[+] Firewall configured\n")

        # ====================================================================
        # STEP 9: Create Droplet object and register in persistent storage
        # ====================================================================
        droplet = Droplet(
            id=droplet_id,
            name=droplet_name,
            ip=droplet_ip,
            region=region,
            role=role,
            profile=profile,
            ssh_key_id=ssh_key_id,
            private_key_path=priv_key,
            status="active"
        )

        self.registry.save(droplet)

        # ====================================================================
        # STEP 10: Print summary and return
        # ====================================================================
        self._print_deployment_summary(droplet)

        return droplet

    def destroy_by_id(self, droplet_id: int) -> bool:
        """
        Destroy a droplet and clean up all associated resources.
        
        Checks registry first, then falls back to API if not found.
        Prompts user for SSH key deletion.
        
        Args:
            droplet_id (int): The droplet ID to destroy
        
        Returns:
            bool: True if successful
        """
        # Try to retrieve droplet details from registry
        droplet_data = self.registry.get_by_id(droplet_id)
        
        droplet = None
        if droplet_data:
            try:
                droplet = Droplet.from_dict(droplet_data)
            except Exception as e:
                print(f"[!] Registry entry corrupted: {e}")
        
        # If not in registry or corrupted, try API
        if not droplet:
            api_droplet = self.api.get_droplet(droplet_id)
            if api_droplet:
                droplet = self._create_droplet_from_api(api_droplet)
        
        if not droplet:
            print(f"[-] Droplet {droplet_id} not found")
            return False

        print(f"\n[*] Destroying droplet: {droplet.name} (ID: {droplet.id})")

        # Destroy the droplet
        if not self.droplet_manager.destroy(droplet_id):
            print(f"[-] Failed to destroy droplet")
            return False

        # Delete associated firewall
        try:
            firewall_id = self.firewall.get_firewall_id_for_droplet(droplet_id)
            if firewall_id:
                if self.api.delete_firewall(firewall_id):
                    print(f"[+] Deleted associated firewall: {firewall_id}")
                else:
                    print(f"[!] Failed to delete firewall {firewall_id}")
        except Exception as e:
            print(f"[*] Note: Could not delete firewall: {e}")

        # Ask user about SSH key cleanup
        delete_keys = False
        if droplet.ssh_key_id or droplet.private_key_path:
            response = input("\n[?] Do you want to delete the SSH keys associated with this droplet? (yes/no): ").strip().lower()
            delete_keys = response == "yes"
        
        # Clean up SSH key if user confirmed
        if delete_keys and (droplet.ssh_key_id or droplet.private_key_path):
            try:
                if droplet.ssh_key_id:
                    self.ssh_manager.cleanup_key(droplet.ssh_key_id)
                if droplet.private_key_path:
                    # Delete the local SSH key file
                    key_path = Path(droplet.private_key_path)
                    if key_path.exists():
                        key_path.unlink()
                        print(f"[+] Deleted SSH private key: {droplet.private_key_path}")
                    # Try to delete public key if it exists
                    pub_key_path = Path(str(droplet.private_key_path).replace("id_rsa", "id_rsa.pub"))
                    if pub_key_path.exists():
                        pub_key_path.unlink()
                        print(f"[+] Deleted SSH public key: {pub_key_path}")
                    # Try to remove the directory if empty
                    try:
                        key_dir = key_path.parent
                        if key_dir.exists() and not any(key_dir.iterdir()):
                            key_dir.rmdir()
                            print(f"[+] Removed empty SSH key directory: {key_dir}")
                    except:
                        pass
            except Exception as e:
                print(f"[*] Note: Could not fully cleanup SSH keys: {e}")
        else:
            if droplet.private_key_path:
                print(f"[*] SSH keys retained at: {droplet.private_key_path}")

        # Remove from registry if present
        try:
            self.registry.remove(droplet_id)
        except:
            pass  # Not in registry, that's okay


        print(f"[+] Droplet destroyed successfully")
        return True

    def list_deployments(self) -> List[Droplet]:
        """
        List all deployed droplets.
        
        This fetches droplets from the DigitalOcean API and enriches them with
        local registry data (role, profile, SSH key paths) when available.
        
        Returns:
            list: List of Droplet objects from the API
        
        Behavior:
        - Droplets created through this tool will have full details from registry
        - Droplets created manually in DO will show with basic API info
        - All actual droplets in your account are displayed
        """
        droplets = []
        registry_data = {}
        
        # Try to load registry data, but handle gracefully if corrupted
        try:
            for dep in self.registry.load_all():
                registry_data[dep["id"]] = dep
        except Exception as e:
            print(f"[!] Warning: Could not load registry data ({e}), using API data only")
        
        # Fetch all droplets from DigitalOcean API
        api_droplets = self.api.list_droplets()
        if not api_droplets:
            print("[*] No droplets found in your DigitalOcean account")
            return droplets
        
        # Convert API droplets to Droplet objects, enriched with registry data if available
        for api_droplet in api_droplets:
            droplet_id = api_droplet.get("id")
            
            # Check if we have registry data for this droplet
            if droplet_id in registry_data:
                # Use registry data (complete information)
                try:
                    droplets.append(Droplet.from_dict(registry_data[droplet_id]))
                except KeyError as e:
                    print(f"[!] Warning: Registry entry for droplet {droplet_id} is incomplete ({e})")
                    # Fall back to API data
                    droplets.append(self._create_droplet_from_api(api_droplet))
            else:
                # Create Droplet from API data only (partial information)
                # This handles droplets created outside this tool
                droplets.append(self._create_droplet_from_api(api_droplet))
        
        return droplets

    def _create_droplet_from_api(self, api_droplet: Dict) -> Droplet:
        """
        Create a Droplet object from raw DigitalOcean API data.
        
        Attempts to find the private SSH key file using multiple search patterns:
        1. Nested by ID: SSH_Keys/{droplet_name}/{droplet_id}/id_rsa
        2. Flat by name: SSH_Keys/{droplet_name}_id_rsa
        3. Simple nested: SSH_Keys/{droplet_name}/id_rsa
        4. By droplet ID: SSH_Keys/{droplet_id}_id_rsa or SSH_Keys/{droplet_id}/id_rsa
        """
        try:
            ip = "N/A"
            if api_droplet.get("networks", {}).get("v4"):
                ip = api_droplet["networks"]["v4"][0].get("ip_address", "N/A")
            
            # Try to find SSH private key using multiple patterns
            droplet_name = api_droplet.get("name")
            droplet_id = api_droplet.get("id")
            private_key_path = None
            
            if droplet_name or droplet_id:
                # Build list of search patterns
                patterns = []
                
                if droplet_name and droplet_id:
                    patterns.extend([
                        Path(f"SSH_Keys/{droplet_name}/{droplet_id}/id_rsa"),
                        Path(f"SSH_Keys/{droplet_name}_id_rsa"),
                        Path(f"SSH_Keys/{droplet_name}/id_rsa"),
                    ])
                
                if droplet_id:
                    patterns.extend([
                        Path(f"SSH_Keys/{droplet_id}_id_rsa"),
                        Path(f"SSH_Keys/{droplet_id}/id_rsa"),
                    ])
                
                # Search for the key file
                for pattern_path in patterns:
                    if pattern_path.exists():
                        private_key_path = str(pattern_path)
                        break
            
            droplet = Droplet(
                id=droplet_id,
                name=droplet_name,
                ip=ip,
                region=api_droplet.get("region", {}).get("slug", "unknown"),
                status=api_droplet.get("status", "unknown"),
                role="unknown",  # Not in registry
                profile="unknown",  # Not in registry
                private_key_path=private_key_path  # Auto-detect if available
            )
            return droplet
        except Exception as e:
            print(f"[!] Error parsing droplet data: {e}")
            return None

    def monitor_droplet(self, droplet_id: int) -> bool:
        """
        Display current status of a specific droplet.
        
        First checks the local registry, then falls back to the DigitalOcean API.
        This allows monitoring of droplets created outside this tool.
        
        Args:
            droplet_id (int): The droplet ID to check
        
        Returns:
            bool: True if droplet found and displayed
        """
        # Try registry first
        droplet_data = self.registry.get_by_id(droplet_id)
        if droplet_data:
            try:
                droplet = Droplet.from_dict(droplet_data)
                self._print_droplet_info(droplet)
                return True
            except Exception as e:
                print(f"[!] Registry entry corrupted: {e}")
                print("[*] Attempting to fetch from DigitalOcean API...")
        
        # Fall back to API
        api_droplet = self.api.get_droplet(droplet_id)
        if api_droplet:
            droplet = self._create_droplet_from_api(api_droplet)
            if droplet:
                self._print_droplet_info(droplet)
                return True
        
        print(f"[-] Droplet {droplet_id} not found")
        return False

    @staticmethod
    def _get_my_ip() -> Optional[str]:
        """
        Retrieve your public IP address from ipify.org.
        
        Returns:
            str: Your public IP or None if detection fails
        """
        try:
            response = requests.get("https://api.ipify.org", timeout=5)
            ip = response.text.strip()
            return ip
        except Exception as e:
            print(f"[!] Error getting IP: {e}")
            return None

    def detect_operator_ip(self) -> Optional[str]:
        """
        Detect operator's public IP address.
        
        Returns:
            Optional[str]: The operator's public IP or None if detection fails
        """
        return self._get_my_ip()

    def set_firewall_config(self, operator_ip: str, inbound_ports: Dict[str, str]) -> None:
        """
        Set custom firewall configuration before deployment.
        
        Args:
            operator_ip (str): The operator's IP to whitelist
            inbound_ports (Dict[str, str]): Dictionary of {port: protocol} (e.g., {"22": "tcp", "8888": "tcp"})
        
        Example:
            >>> orch.set_firewall_config("203.0.113.42", {"22": "tcp", "8888": "tcp"})
        """
        self.operator_ip = operator_ip
        # Ensure SSH is included and restricted to operator IP
        if "22" not in inbound_ports:
            inbound_ports["22"] = "tcp"
        self.inbound_ports = inbound_ports
        print(f"[*] Firewall configured: Operator IP={operator_ip}, Ports={list(inbound_ports.keys())}")

    @staticmethod
    def _print_deployment_summary(droplet: Droplet) -> None:
        """Pretty-print deployment summary."""
        print("=" * 70)
        print("[+] DEPLOYMENT COMPLETE!")
        print("=" * 70)
        print(f"\nDroplet Details:")
        print(f"  Name:         {droplet.name}")
        print(f"  ID:           {droplet.id}")
        print(f"  IP Address:   {droplet.ip}")
        print(f"  Region:       {droplet.region}")
        print(f"  Role:         {droplet.role}")
        print(f"  Profile:      {droplet.profile}")
        print(f"  Status:       {droplet.status}")
        print(f"\nSSH Access:")
        print(f"  Command:      {droplet.ssh_command()}")
        print(f"  Private Key:  {droplet.private_key_path}")
        print(f"\nCloud-Init Logs:")
        print(f"  ssh -i {droplet.private_key_path} root@{droplet.ip} 'tail -f /var/log/cloud-init-output.log'")
        print("=" * 70 + "\n")

    @staticmethod
    def _print_droplet_info(droplet: Droplet) -> None:
        """Pretty-print droplet information."""
        print(f"\nDroplet: {droplet.name}")
        print(f"  ID:           {droplet.id}")
        print(f"  IP:           {droplet.ip}")
        print(f"  Region:       {droplet.region}")
        print(f"  Role:         {droplet.role}")
        print(f"  Status:       {droplet.status}")
        print(f"  Created:      {droplet.created_at}")
        print(f"  SSH Command:  {droplet.ssh_command()}\n")

    def open_firewall_port(self, droplet_id: int, port: int, protocol: str = "tcp", source_ip: str = "0.0.0.0/0") -> bool:
        """
        Open a port on a droplet's firewall (add inbound rule).
        
        If no firewall exists for the droplet, creates one first.
        
        Args:
            droplet_id (int): The droplet ID
            port (int): Port number to open (1-65535)
            protocol (str): Protocol (tcp or udp)
            source_ip (str): Source IP/CIDR to allow
        
        Returns:
            bool: True if successful
        """
        try:
            firewall_id = self.firewall.get_firewall_id_for_droplet(droplet_id)
            
            # If no firewall exists, create one with this port rule
            if not firewall_id:
                print(f"[*] No firewall found for droplet {droplet_id}. Creating one...")
                
                # Get droplet info for firewall name
                api_droplet = self.api.get_droplet(droplet_id)
                if not api_droplet:
                    print(f"[-] Could not fetch droplet info")
                    return False
                
                droplet_name = api_droplet.get("name", f"droplet-{droplet_id}")
                
                # Create firewall with the requested port
                firewall_config = {
                    "name": f"{Config.FIREWALL_NAME_PREFIX}-{droplet_id}",
                    "inbound_rules": [
                        {
                            "protocol": protocol,
                            "ports": str(port),
                            "sources": {"addresses": [source_ip]}
                        }
                    ],
                    "outbound_rules": [
                        {
                            "protocol": "tcp",
                            "ports": "all",
                            "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}
                        },
                        {
                            "protocol": "udp",
                            "ports": "all",
                            "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}
                        }
                    ],
                    "droplet_ids": [droplet_id]
                }
                
                firewall_id = self.api.create_firewall(firewall_config)
                if not firewall_id:
                    print(f"[-] Failed to create firewall")
                    return False
                
                print(f"[+] Created firewall {firewall_id}")
            
            # Add the port rule (or update if firewall already exists)
            return self.firewall.add_inbound_port(firewall_id, port, protocol, source_ip)
        except Exception as e:
            print(f"[-] Error opening port: {e}")
            return False

    def get_firewall_rules(self, droplet_id: int) -> Optional[Dict]:
        """
        Get firewall rules for a droplet.
        
        Args:
            droplet_id (int): The droplet ID
        
        Returns:
            Optional[Dict]: Firewall configuration or None
        """
        try:
            firewall_id = self.firewall.get_firewall_id_for_droplet(droplet_id)
            if not firewall_id:
                return None
            
            return self.api.get_firewall(firewall_id)
        except Exception as e:
            print(f"[-] Error getting firewall rules: {e}")
            return None
