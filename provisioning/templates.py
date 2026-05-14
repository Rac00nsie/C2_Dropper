"""
Cloud-Init Provisioning Templates

Role-based cloud-init configurations for droplet deployment.
Each role is a complete cloud-init YAML configuration that executes as root
on first boot, enabling immediate software installation and configuration.

To add a new role:
1. Create a new template string with the cloud-init YAML
2. Add it to the TEMPLATES dictionary
3. Update provisioning/__init__.py to export it

Example:
    new_role = '''#cloud-config
    # Your configuration here
    runcmd:
      - apt-get update -y
      - apt-get install -y myapp
    '''
    TEMPLATES["myapp"] = new_role
"""

# Sliver C2 Framework Deployment
SLIVER = """#cloud-config
# Cloud-init configuration for Sliver C2 deployment
# Sliver is a modern C2 framework written in Go with features like:
# - Lightweight agent (~5MB)
# - Multiplayer collaboration support
# - Automatic obfuscation
# - Built-in redirectors

runcmd:
  # Update package lists before installing anything
  - apt-get update -y
  
  # Install base dependencies required for Sliver and other tools
  - apt-get install -y curl wget git build-essential
  
  # Install Sliver C2 framework using the official installer
  # The installer handles downloading pre-built binaries or compiling from source
  - curl https://sliver.sh/install | bash
  
  # Log a completion message for verification
  - echo "Sliver installation complete" >> /var/log/provision.log
"""

# HTTP Redirector Configuration
REDIRECTOR = """#cloud-config
# Cloud-init configuration for HTTP Redirector
# A redirector transparently forwards traffic to your actual C2 server
# This provides operational security by obscuring your C2's true location

runcmd:
  # Update package lists
  - apt-get update -y
  
  # Install nginx web server for redirecting HTTP traffic
  - apt-get install -y nginx curl wget
  
  # Enable nginx to start on boot
  - systemctl enable nginx
  - systemctl start nginx
  
  # Log completion
  - echo "Redirector installation complete" >> /var/log/provision.log
"""

# Minimal Base System Setup
MINIMAL = """#cloud-config
# Cloud-init configuration for Minimal setup
# This role simply installs basic utilities without specialized C2 tools
# Useful for proxy servers or general-purpose infrastructure

runcmd:
  # Update package lists
  - apt-get update -y
  
  # Install common utilities for debugging and monitoring
  - apt-get install -y curl wget git htop net-tools
  
  # Log completion
  - echo "Minimal deployment complete" >> /var/log/provision.log
"""

# Apache Web Server with PHP
APACHE = """#cloud-config
# Cloud-init configuration for Apache Web Server with PHP
# Useful for hosting web applications or phishing pages

runcmd:
  # Update package lists
  - apt-get update -y
  
  # Install Apache and PHP
  - apt-get install -y apache2 php php-mysql curl wget
  
  # Enable Apache modules for PHP
  - a2enmod php8.2 || a2enmod php8.1 || a2enmod php
  
  # Enable Apache and start on boot
  - systemctl enable apache2
  - systemctl start apache2
  
  # Log completion
  - echo "Apache deployment complete" >> /var/log/provision.log
"""

# Template mapping for easy lookup
TEMPLATES = {
    "sliver": SLIVER,
    "redirector": REDIRECTOR,
    "minimal": MINIMAL,
    "apache": APACHE,
}


def get_template(role: str) -> str:
    """
    Retrieve a cloud-init template by role name.
    
    Args:
        role (str): Role name (e.g., "sliver", "redirector", "apache")
    
    Returns:
        str: Cloud-init YAML configuration
        
    Raises:
        ValueError: If role not found
        
    Example:
        >>> config = get_template("sliver")
        >>> print(config.startswith("#cloud-config"))
        True
    """
    if role not in TEMPLATES:
        raise ValueError(f"Unknown role: {role}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[role]


def list_available_roles() -> list:
    """Return list of all available provisioning roles."""
    return list(TEMPLATES.keys())