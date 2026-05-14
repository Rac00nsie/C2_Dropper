"""Provisioning module - Cloud-init templates and role configurations"""

from provisioning.templates import get_template, list_available_roles

__all__ = ["get_template", "list_available_roles"]