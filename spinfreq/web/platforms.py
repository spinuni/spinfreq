"""Portable capability selection; importing the web never imports Linux APIs."""
import sys


def capabilities(mode="auto", platform_name=None):
    if mode not in ("auto", "landing", "compute"):
        raise ValueError("Require mode auto, landing or compute")
    name = sys.platform if platform_name is None else platform_name
    supported = name.startswith("linux")
    if mode == "compute" and not supported:
        raise ValueError("Protected simulation workers require Linux/WSL2; use --mode landing on this platform")
    enabled = supported and mode != "landing"
    return {"platform": name, "mode": "compute" if enabled else "landing",
            "simulation_enabled": enabled, "configuration_export_enabled": True,
            "message": ("Calculations use this Linux server's CPU and RAM." if enabled else
                        "Configuration preview: native simulation workers are not enabled here. Export your SI configuration and run it on Linux or Windows with WSL2.")}
