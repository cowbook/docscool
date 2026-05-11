from flask import Blueprint

contracts_bp = Blueprint("contracts", __name__, url_prefix="/api")

# Route registration via import side effects
from . import contracts_routes_settings  # noqa: E402,F401
from . import contracts_routes_contracts  # noqa: E402,F401
