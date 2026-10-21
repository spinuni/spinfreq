"""Portable capability selection; importing the web never imports Linux APIs."""
import sys


def capabilities(mode="auto", platform_name=None):
    if mode not in ("auto", "landing", "compute"):
        raise ValueError("Require mode auto, landing or compute")
    name = sys.platform if platform_name is None else platform_name
    linux = name.startswith('linux')
    windows = name == 'win32'
    if mode == "compute" and not (linux or windows):
        raise ValueError("Protected workers require Linux or Windows; use --mode landing on this platform")
    enabled = (linux and mode != 'landing') or (windows and mode == 'compute')
    experimental = windows and enabled
    return {"platform": name, "mode": "compute" if enabled else "landing",
            "simulation_enabled": enabled, "configuration_export_enabled": True,
            "experimental": experimental,
            "message": ("Experimental native Windows computation with Job Object controls; native qualification is pending." if experimental else
                        "Calculations use this Linux server's CPU and RAM." if enabled else
                        "Configuration preview: export SI JSON for Linux/WSL2, or explicitly opt into experimental Windows computation with --mode compute.")}
