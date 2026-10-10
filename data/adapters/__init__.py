"""Data-service adapters: one interface, two implementations.

    from data.adapters import get_data_service
    svc = get_data_service()                      # Vlada if VLADA_API_KEY is set, else PublicExtracts
    rows = svc.get_table("nhamcs_ed_by_acuity", subset="metro_teaching")

Selection is decided purely by the presence of the VLADA_API_KEY environment variable. When Vlada is selected, any
failed call (network error, table not mapped, service busy) falls back to the public extracts for that call and the
fallback is recorded in `svc.status()`.
"""
from .base import DataService, TableNotFound
from .public_extracts import PublicExtracts
from .vlada import Vlada, VladaError
from .factory import get_data_service

__all__ = ["DataService", "TableNotFound", "PublicExtracts", "Vlada", "VladaError", "get_data_service"]
