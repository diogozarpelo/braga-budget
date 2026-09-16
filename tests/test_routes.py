from app import create_app


EXPECTED_ENDPOINTS = {
    "main.index",
    "main.clients",
    "main.edit_client",
    "main.deactivate_client",
    "main.inactive_clients",
    "main.reactivate_client",
    "main.quotes",
    "main.new_quote",
    "main.quote_detail",
    "main.export_quote_pdf",
    "main.export_quote_image",
    "main.new_quote_item",
    "main.new_quote_item_component",
    "main.edit_quote_conditions",
    "main.edit_quote_item_labor",
    "main.edit_quote_item",
    "main.edit_quote_item_component",
    "main.remove_quote_item",
    "main.remove_quote_item_component",
    "main.delete_draft_quote",
    "main.update_quote_status",
    "main.issue_quote",
    "main.edit_quote_final_total",
    "main.settings",
    "main.components",
    "main.edit_component",
    "main.deactivate_component",
    "main.reactivate_component",
    "main.inactive_components",
}


def test_all_application_routes_are_registered():
    app = create_app()

    rules = [
        rule
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
    ]

    assert len(rules) == 29

    endpoints = {
        rule.endpoint
        for rule in rules
    }

    assert endpoints == EXPECTED_ENDPOINTS


def test_important_route_paths_and_methods():
    app = create_app()

    rules = {
        rule.endpoint: rule
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
    }

    assert rules["main.index"].rule == "/"
    assert rules["main.clients"].rule == "/clientes"
    assert rules["main.components"].rule == "/componentes"
    assert rules["main.quotes"].rule == "/orcamentos"

    assert (
        rules["main.quote_detail"].rule
        == "/orcamentos/<int:quote_id>"
    )

    assert (
        rules["main.export_quote_pdf"].rule
        == "/orcamentos/<int:quote_id>/exportar/pdf"
    )

    assert (
        set(rules["main.new_quote"].methods)
        - {"HEAD", "OPTIONS"}
        == {"GET", "POST"}
    )


def test_brl_template_filter_is_registered():
    app = create_app()

    assert "brl" in app.jinja_env.filters
