from app.web import main

from app.views import clients as _clients_routes
from app.views import components as _components_routes
from app.views import home as _home_routes
from app.views import quote_items as _quote_item_routes
from app.views import quote_workflow as _quote_workflow_routes
from app.views import quotes as _quote_routes
from app.views import settings as _settings_routes


__all__ = ["main"]
