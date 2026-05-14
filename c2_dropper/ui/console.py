"""
Interactive Console UI

Menu-driven interface for managing C2 Dropper deployments.
"""

from ..config import Config
from ..provisioning.templates import list_available_roles
from ..orchestration.orchestration import DeploymentOrchestrator


class InteractiveConsole:
	"""Interactive command-line interface for managing deployments."""

	def __init__(self, orchestrator: DeploymentOrchestrator):
		self.orchestrator = orchestrator

	def run(self) -> None:
		print("\n" + "=" * 70)
		print("DigitalOcean Red Team Infrastructure Manager")
		print("=" * 70)

		while True:
			self._display_menu()
			choice = input("\n[?] Enter your choice (1-6): ").strip()

			if choice == "1":
				self._menu_deploy()
			elif choice == "2":
				self._menu_list_deployments()
			elif choice == "3":
				self._menu_monitor_droplet()
			elif choice == "4":
				self._menu_firewall_management()
			elif choice == "5":
				self._menu_destroy_droplet()
			elif choice == "6":
				print("\n[*] Exiting. Goodbye!")
				break
			else:
				print("[-] Invalid choice. Please try again.")

	def _display_menu(self) -> None:
		print("\n" + "-" * 70)
		print("1. Deploy new droplet")
		print("2. List all deployments")
		print("3. Monitor droplet status")
		print("4. Manage firewall rules")
		print("5. Destroy droplet")
		print("6. Exit")
		print("-" * 70)

	def _menu_deploy(self) -> None:
		print("\n[*] Deploy New Droplet")
		print("-" * 70)

		droplet_name = input("Droplet name (e.g., 'sliver-test'): ").strip()
		if not droplet_name:
			print("[-] Droplet name cannot be empty")
			return

		available_roles = list_available_roles()
		print(f"\nAvailable roles: {', '.join(available_roles)}")
		role = input("Role (default: sliver): ").strip() or "sliver"

		if role not in available_roles:
			print(f"[-] Unknown role: {role}")
			return

		print(f"Available profiles: {', '.join(Config.list_profiles())}")
		profile = input("Profile (default: sydney-small): ").strip() or "sydney-small"

		if profile not in Config.list_profiles():
			print(f"[-] Unknown profile: {profile}")
			return

		# Detect operator's public IP for firewall whitelisting
		operator_ip = self.orchestrator.detect_operator_ip()
		if operator_ip:
			print(f"\n[*] Detected your public IP: {operator_ip}")
			custom_ip = input("Use this IP for firewall whitelist? (yes/no, default: yes): ").strip().lower()
			if custom_ip == "no":
				operator_ip = input("Enter your IP address to whitelist: ").strip()
		else:
			print("[!] Could not auto-detect your public IP")
			operator_ip = input("Enter your IP address to whitelist (e.g., 203.0.113.42): ").strip()
			if not operator_ip:
				print("[-] IP address required for firewall configuration")
				return

		# Ask about additional C2 ports
		inbound_ports = {"22": "tcp"}  # SSH always restricted to operator IP
		
		print("\n[*] Configure Inbound Rules")
		print("-" * 70)
		print("Port 22 (SSH) is always restricted to your IP: " + operator_ip)
		
		add_more = input("Add additional C2 ports? (yes/no, default: no): ").strip().lower()
		if add_more == "yes":
			while True:
				port_input = input("Enter port (or press Enter to finish): ").strip()
				if not port_input:
					break
				if port_input.isdigit() and 1 <= int(port_input) <= 65535 and port_input != "22":
					protocol = input(f"Protocol for port {port_input} (tcp/udp, default: tcp): ").strip().lower() or "tcp"
					inbound_ports[port_input] = protocol
					print(f"[+] Added port {port_input}/{protocol}")
				else:
					print("[-] Invalid port (must be 1-65535 and not 22)")

		# Store operator IP and inbound ports for deployment
		self.orchestrator.set_firewall_config(operator_ip, inbound_ports)

		droplet = self.orchestrator.deploy(droplet_name, role, profile)
		if droplet:
			print("[+] Deployment successful!")
		else:
			print("[-] Deployment failed!")

	def _menu_list_deployments(self) -> None:
		print("\n[*] Active Deployments")
		print("-" * 70)

		try:
			droplets = self.orchestrator.list_deployments()
			if not droplets:
				print("[*] No droplets found in your DigitalOcean account")
				return

			print(f"\nTotal: {len(droplets)} droplet(s)\n")
			for droplet in droplets:
				if droplet:  # Skip None entries from parsing errors
					print(f"  {droplet.name} (ID: {droplet.id})")
					print(f"    IP: {droplet.ip}, Role: {droplet.role}, Status: {droplet.status}")
					print()
		except Exception as e:
			print(f"[-] Error listing deployments: {e}")
			print("[*] Try checking your DigitalOcean dashboard directly")

	def _menu_monitor_droplet(self) -> None:
		print("\n[*] Monitor Droplet")
		print("-" * 70)

		droplet_id = input("Droplet ID: ").strip()
		if not droplet_id.isdigit():
			print("[-] Invalid droplet ID")
			return

		self.orchestrator.monitor_droplet(int(droplet_id))

	def _menu_firewall_management(self) -> None:
		print("\n[*] Manage Firewall Rules")
		print("-" * 70)

		droplet_id = input("Droplet ID: ").strip()
		if not droplet_id.isdigit():
			print("[-] Invalid droplet ID")
			return

		droplet_id = int(droplet_id)

		while True:
			print("\n" + "-" * 70)
			print("1. Open a port")
			print("2. View firewall rules")
			print("3. Back to main menu")
			print("-" * 70)

			choice = input("[?] Enter your choice (1-3): ").strip()

			if choice == "1":
				self._firewall_open_port(droplet_id)
			elif choice == "2":
				self._firewall_view_rules(droplet_id)
			elif choice == "3":
				break
			else:
				print("[-] Invalid choice")

	def _firewall_open_port(self, droplet_id: int) -> None:
		"""Open a port on the droplet's firewall."""
		try:
			port = input("Port number to open (e.g., 443): ").strip()
			if not port.isdigit() or not (1 <= int(port) <= 65535):
				print("[-] Invalid port number (must be 1-65535)")
				return

			protocol = input("Protocol (tcp/udp, default: tcp): ").strip().lower() or "tcp"
			if protocol not in ["tcp", "udp"]:
				print("[-] Invalid protocol")
				return

			# Ask user about source IP
			print("\n[*] Source IP Configuration")
			print("-" * 70)
			print("1. Use your own IP (auto-detected)")
			print("2. Specify a custom IP/CIDR")
			print("3. Allow all IPs (0.0.0.0/0)")
			print("-" * 70)
			
			ip_choice = input("[?] Choice (1-3, default: 1): ").strip() or "1"
			
			source_ip = None
			if ip_choice == "1":
				# Auto-detect operator IP
				operator_ip = self.orchestrator.detect_operator_ip()
				if operator_ip:
					print(f"[*] Detected your IP: {operator_ip}")
					source_ip = f"{operator_ip}/32"
				else:
					print("[-] Could not auto-detect IP")
					source_ip = input("Enter IP/CIDR manually: ").strip()
					if not source_ip:
						print("[-] No IP provided")
						return
			elif ip_choice == "2":
				# Custom IP
				source_ip = input("Enter IP/CIDR (e.g., 203.0.113.42/32): ").strip()
				if not source_ip:
					print("[-] No IP provided")
					return
			elif ip_choice == "3":
				# Allow all
				source_ip = "0.0.0.0/0"
			else:
				print("[-] Invalid choice")
				return

			if self.orchestrator.open_firewall_port(droplet_id, int(port), protocol, source_ip):
				print(f"[+] Successfully opened port {port}/{protocol} for {source_ip}")
			else:
				print("[-] Failed to open port")
		except Exception as e:
			print(f"[-] Error: {e}")

	def _firewall_view_rules(self, droplet_id: int) -> None:
		"""Display current firewall rules for a droplet."""
		try:
			rules = self.orchestrator.get_firewall_rules(droplet_id)
			if not rules:
				print("[*] No firewall found for this droplet")
				return

			print("\n[*] Firewall Rules")
			print("-" * 70)

			if "inbound_rules" in rules:
				print("\nInbound Rules:")
				for rule in rules["inbound_rules"]:
					protocol = rule.get("protocol", "?")
					ports = rule.get("ports", "all")
					sources = rule.get("sources", {}).get("addresses", ["all"])
					print(f"  {protocol.upper():5} | Port: {ports:10} | From: {', '.join(sources)}")

			if "outbound_rules" in rules:
				print("\nOutbound Rules:")
				for rule in rules["outbound_rules"]:
					protocol = rule.get("protocol", "?")
					ports = rule.get("ports", "all")
					destinations = rule.get("destinations", {}).get("addresses", ["all"])
					print(f"  {protocol.upper():5} | Port: {ports:10} | To: {', '.join(destinations)}")
		except Exception as e:
			print(f"[-] Error viewing rules: {e}")

	def _menu_destroy_droplet(self) -> None:
		print("\n[*] Destroy Droplet")
		print("-" * 70)

		droplet_id = input("Droplet ID to destroy: ").strip()
		if not droplet_id.isdigit():
			print("[-] Invalid droplet ID")
			return

		confirm = input(f"Are you sure you want to destroy droplet {droplet_id}? (yes/no): ").strip().lower()
		if confirm != "yes":
			print("[-] Cancelled")
			return

		if self.orchestrator.destroy_by_id(int(droplet_id)):
			print("[+] Droplet destroyed and cleaned up")
		else:
			print("[-] Failed to destroy droplet")
