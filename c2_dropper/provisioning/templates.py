"""Cloud-init template helpers."""

_TEMPLATES = {
    "sliver": """#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - build-essential
  - mingw-w64
runcmd:
  - curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > /tmp/msfinstall
  - chmod 755 /tmp/msfinstall
  - /tmp/msfinstall
  - curl https://github.com/BishopFox/sliver/releases/download/v1.5.42/sliver-server_linux -o /tmp/sliver-server
  - chmod +x /tmp/sliver-server
  - /tmp/sliver-server &
""",
    "redirector": """#cloud-config
package_update: true
package_upgrade: true
packages:
  - nginx
runcmd:
  - systemctl enable nginx
  - systemctl start nginx
""",
}


def list_available_roles() -> list[str]:
	return sorted(_TEMPLATES.keys())


def get_template(role: str) -> str:
	try:
		return _TEMPLATES[role]
	except KeyError as exc:
		raise ValueError(f"Unknown role: {role}") from exc
