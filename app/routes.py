import fitz
from PIL import Image as PILImage
from html import escape
from pathlib import Path
from io import BytesIO
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, abort, redirect, render_template, request, send_file, url_for


from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from reportlab.platypus import KeepTogether

from app.db import get_db


main = Blueprint("main", __name__)

COMPONENTS_PER_PAGE = 15
CLIENTS_PER_PAGE = 15
ISSUED_QUOTES_PER_PAGE = 15

CLIENT_PHONE_DIGITS_SQL = """
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(clients.phone, '(', ''),
                        ')',
                        ''
                    ),
                    '-',
                    ''
                ),
                ' ',
                ''
            ),
            '.',
            ''
        ),
        '+',
        ''
    )
"""


def parse_decimal(value):
    text = value.strip()

    if not text:
        raise InvalidOperation

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    return Decimal(text)


def money_to_cents(value):
    amount = parse_decimal(value)

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def normalize_comparison_text(value):
    return " ".join((value or "").split()).casefold()


def phone_digits(value):
    return "".join(
        character
        for character in (value or "")
        if character.isdigit()
    )


def get_pagination(total_count, per_page):
    page = request.args.get("page", default=1, type=int) or 1
    page = max(page, 1)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    return page, total_pages, offset


def find_duplicate_client(db, name, phone, address, exclude_client_id=None):
    query = """
        SELECT id, name, phone, address, active
        FROM clients
    """
    query_params = []

    if exclude_client_id is not None:
        query += " WHERE id != ?"
        query_params.append(exclude_client_id)

    query += " ORDER BY active DESC, id"

    normalized_name = normalize_comparison_text(name)
    normalized_phone = phone_digits(phone)
    normalized_address = normalize_comparison_text(address)

    for client in db.execute(query, query_params).fetchall():
        if normalize_comparison_text(client["name"]) != normalized_name:
            continue

        existing_phone = phone_digits(client["phone"])

        if normalized_phone and existing_phone == normalized_phone:
            return client

        if (
            not normalized_phone
            and not existing_phone
            and normalize_comparison_text(client["address"])
            == normalized_address
        ):
            return client

    return None


def duplicate_client_error(duplicate):
    if duplicate["active"]:
        return "Já existe um cliente ativo com esses mesmos dados."

    return (
        "Este cliente já existe na lista de desativados e pode ser "
        "reativado."
    )


def get_components_page(active):
    db = get_db()
    search = request.args.get("q", "").strip()

    where_parts = ["active = ?"]
    query_params = [active]

    if search:
        escaped_search = escape_like(search)
        where_parts.append("name LIKE ? ESCAPE '\\' COLLATE NOCASE")
        query_params.append(f"%{escaped_search}%")

    where_clause = " AND ".join(where_parts)
    total_count = db.execute(
        f"SELECT COUNT(*) FROM components WHERE {where_clause}",
        query_params,
    ).fetchone()[0]
    page, total_pages, offset = get_pagination(
        total_count,
        COMPONENTS_PER_PAGE,
    )

    components_list = db.execute(
        f"""
        SELECT id, name, unit_price_cents, active
        FROM components
        WHERE {where_clause}
        ORDER BY name COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (*query_params, COMPONENTS_PER_PAGE, offset),
    ).fetchall()

    return components_list, search, page, total_pages, total_count


@main.get("/")
def index():
    db = get_db()
    recent_quotes = db.execute(
        """
        SELECT
            quotes.id,
            quotes.quote_number,
            quotes.status,
            quotes.issued_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.status != 'draft'
        ORDER BY quotes.issued_at DESC, quotes.id DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "index.html",
        recent_quotes=recent_quotes,
    )


@main.route("/clientes", methods=("GET", "POST"))
def clients():
    db = get_db()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            error = "Informe o nome do cliente."
        else:
            duplicate = find_duplicate_client(
                db,
                name,
                phone,
                address,
            )

            if duplicate is not None:
                error = duplicate_client_error(duplicate)

        if error is None:
            db.execute(
                "INSERT INTO clients (name, phone, address) VALUES (?, ?, ?)",
                (name, phone, address),
            )
            db.commit()

            return redirect(url_for("main.clients"))

    search = request.args.get("q", "").strip()
    where_parts = ["clients.active = 1"]
    query_params = []

    if search:
        escaped_search = escape_like(search)
        search_pattern = f"%{escaped_search}%"
        search_conditions = [
            "clients.name LIKE ? ESCAPE '\\' COLLATE NOCASE",
            "clients.address LIKE ? ESCAPE '\\' COLLATE NOCASE",
        ]
        query_params.extend((search_pattern, search_pattern))

        normalized_search_phone = phone_digits(search)
        if normalized_search_phone:
            search_conditions.append(
                f"{CLIENT_PHONE_DIGITS_SQL} LIKE ? ESCAPE '\\'"
            )
            query_params.append(f"%{normalized_search_phone}%")

        where_parts.append(f"({' OR '.join(search_conditions)})")

    where_clause = " AND ".join(where_parts)
    total_count = db.execute(
        f"SELECT COUNT(*) FROM clients WHERE {where_clause}",
        query_params,
    ).fetchone()[0]
    page, total_pages, offset = get_pagination(
        total_count,
        CLIENTS_PER_PAGE,
    )
    clients_list = db.execute(
        f"""
        SELECT id, name, phone, address
        FROM clients
        WHERE {where_clause}
        ORDER BY name COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (*query_params, CLIENTS_PER_PAGE, offset),
    ).fetchall()

    return render_template(
        "clients.html",
        clients=clients_list,
        error=error,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@main.route("/clientes/<int:client_id>/editar", methods=("GET", "POST"))
def edit_client(client_id):
    db = get_db()
    client = db.execute(
        """
        SELECT id, name, phone, address
        FROM clients
        WHERE id = ? AND active = 1
        """,
        (client_id,),
    ).fetchone()

    if client is None:
        abort(404)

    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            error = "Informe o nome do cliente."
        else:
            duplicate = find_duplicate_client(
                db,
                name,
                phone,
                address,
                exclude_client_id=client_id,
            )

            if duplicate is not None:
                error = duplicate_client_error(duplicate)

        if error is None:
            db.execute(
                """
                UPDATE clients
                SET name = ?, phone = ?, address = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, phone, address, client_id),
            )
            db.commit()

            return redirect(url_for("main.clients"))

    return render_template(
        "client_edit.html",
        client=client,
        error=error,
    )


@main.post("/clientes/<int:client_id>/desativar")
def deactivate_client(client_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE clients
        SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 1
        """,
        (client_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.clients"))


@main.get("/clientes/inativos")
def inactive_clients():
    db = get_db()
    clients_list = db.execute(
        """
        SELECT id, name, phone, address
        FROM clients
        WHERE active = 0
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    return render_template(
        "inactive_clients.html",
        clients=clients_list,
    )


@main.post("/clientes/<int:client_id>/reativar")
def reactivate_client(client_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE clients
        SET active = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 0
        """,
        (client_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.inactive_clients"))


@main.get("/orcamentos")
def quotes():
    db = get_db()

    drafts = db.execute(
        """
        SELECT
            quotes.id,
            quotes.created_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.status = 'draft'
        ORDER BY quotes.created_at DESC, quotes.id DESC
        """
    ).fetchall()

    issued_search = request.args.get("q", "").strip()
    issued_where_parts = ["quotes.status != 'draft'"]
    issued_query_params = []

    if issued_search:
        escaped_search = escape_like(issued_search)
        search_pattern = f"%{escaped_search}%"
        search_conditions = [
            "CAST(quotes.quote_number AS TEXT) LIKE ? ESCAPE '\\'",
            "clients.name LIKE ? ESCAPE '\\' COLLATE NOCASE",
        ]
        issued_query_params.extend((search_pattern, search_pattern))

        normalized_search_phone = phone_digits(issued_search)
        if normalized_search_phone:
            search_conditions.append(
                f"{CLIENT_PHONE_DIGITS_SQL} LIKE ? ESCAPE '\\'"
            )
            issued_query_params.append(f"%{normalized_search_phone}%")

        issued_where_parts.append(f"({' OR '.join(search_conditions)})")

    issued_where_clause = " AND ".join(issued_where_parts)
    issued_total_count = db.execute(
        f"""
        SELECT COUNT(*)
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE {issued_where_clause}
        """,
        issued_query_params,
    ).fetchone()[0]
    issued_page, issued_total_pages, issued_offset = get_pagination(
        issued_total_count,
        ISSUED_QUOTES_PER_PAGE,
    )
    issued_quotes = db.execute(
        f"""
        SELECT
            quotes.id,
            quotes.quote_number,
            quotes.status,
            quotes.issued_at,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE {issued_where_clause}
        ORDER BY quotes.issued_at DESC, quotes.id DESC
        LIMIT ? OFFSET ?
        """,
        (*issued_query_params, ISSUED_QUOTES_PER_PAGE, issued_offset),
    ).fetchall()

    return render_template(
        "quotes.html",
        drafts=drafts,
        issued_quotes=issued_quotes,
        issued_search=issued_search,
        issued_page=issued_page,
        issued_total_pages=issued_total_pages,
        issued_total_count=issued_total_count,
    )


@main.route("/orcamentos/novo", methods=("GET", "POST"))
def new_quote():
    db = get_db()
    error = None

    clients_list = db.execute(
        """
        SELECT id, name
        FROM clients
        WHERE active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)

        client = None

        if client_id is not None:
            client = db.execute(
                """
                SELECT id
                FROM clients
                WHERE id = ? AND active = 1
                """,
                (client_id,),
            ).fetchone()

        if client is None:
            error = "Selecione um cliente ativo."
        else:
            settings = db.execute(
                """
                SELECT
                    default_validity_days,
                    default_execution_days,
                    warranty_text
                FROM settings
                WHERE id = 1
                """
            ).fetchone()

            result = db.execute(
                """
                INSERT INTO quotes (
                    client_id,
                    validity_days,
                    execution_days,
                    warranty_text
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    client_id,
                    settings["default_validity_days"],
                    settings["default_execution_days"],
                    settings["warranty_text"],
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=result.lastrowid)
            )

    return render_template(
        "new_quote.html",
        clients=clients_list,
        error=error,
    )


@main.get("/orcamentos/<int:quote_id>")
def quote_detail(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name,
            clients.phone AS client_phone,
            clients.address AS client_address
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    items = db.execute(
        """
        SELECT
            id,
            service_type,
            description,
            quantity,
            width_mm,
            height_mm,
            exact_area_m2,
            charged_area_m2,
            glass_type,
            thickness_mm,
            glass_color,
            finish,
            glass_price_per_m2_cents,
            manual_labor_cents,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE quote_id = ?
        ORDER BY position, id
        """,
        (quote_id,),
    ).fetchall()

    components = db.execute(
        """
        SELECT
            quote_item_components.id,
            quote_item_components.quote_item_id,
            quote_item_components.category,
            quote_item_components.description,
            quote_item_components.quantity,
            quote_item_components.unit_price_cents,
            (
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ) AS total_cents
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        ORDER BY
            quote_item_components.position,
            quote_item_components.id
        """,
        (quote_id,),
    ).fetchall()

    components_by_item = {
        item["id"]: []
        for item in items
    }

    for component in components:
        components_by_item[component["quote_item_id"]].append(component)

    items = calculate_items_pricing(
        items,
        components_by_item,
    )

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )
    components_subtotal_cents = sum(
        item["components_total_cents"]
        for item in items
    )
    materials_subtotal_cents = sum(
        item["materials_total_cents"]
        for item in items
    )
    labor_cents = sum(
        item["labor_cents"]
        for item in items
    )

    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_cents,
    )
    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]
    display_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    items = distribute_final_total_between_items(
        items,
        display_total_cents,
    )
    manual_adjustment_cents = (
        display_total_cents
        - calculated_total_cents
    )

    return render_template(
        "quote_detail.html",
        quote=quote,
        items=items,
        components_by_item=components_by_item,
        glass_subtotal_cents=glass_subtotal_cents,
        components_subtotal_cents=components_subtotal_cents,
        materials_subtotal_cents=materials_subtotal_cents,
        labor_cents=price_breakdown["labor_cents"],
        difficulty_cents=price_breakdown["difficulty_cents"],
        discount_cents=price_breakdown["discount_cents"],
        calculated_total_cents=calculated_total_cents,
        display_total_cents=display_total_cents,
        manual_adjustment_cents=manual_adjustment_cents,
        final_total_cents=display_total_cents,
    )






@main.get("/orcamentos/<int:quote_id>/exportar/pdf")
def export_quote_pdf(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name,
            clients.phone AS client_phone,
            clients.address AS client_address
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    business = db.execute(
        """
        SELECT business_name, phone, cnpj, warranty_text
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    items = db.execute(
        """
        SELECT
            id,
            service_type,
            description,
            quantity,
            width_mm,
            height_mm,
            exact_area_m2,
            charged_area_m2,
            glass_type,
            thickness_mm,
            glass_color,
            finish,
            glass_price_per_m2_cents,
            manual_labor_cents,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE quote_id = ?
        ORDER BY position, id
        """,
        (quote_id,),
    ).fetchall()

    components = db.execute(
        """
        SELECT
            quote_item_components.quote_item_id,
            quote_item_components.description,
            quote_item_components.quantity,
            quote_item_components.unit_price_cents,
            (
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ) AS total_cents
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        ORDER BY
            quote_item_components.position,
            quote_item_components.id
        """,
        (quote_id,),
    ).fetchall()

    components_by_item = {
        item["id"]: []
        for item in items
    }

    for component in components:
        components_by_item[component["quote_item_id"]].append(component)

    items = calculate_items_pricing(
        items,
        components_by_item,
    )

    glass_subtotal_cents = sum(
        item["glass_total_cents"]
        for item in items
    )
    components_subtotal_cents = sum(
        item["components_total_cents"]
        for item in items
    )
    materials_subtotal_cents = sum(
        item["materials_total_cents"]
        for item in items
    )
    labor_cents = sum(
        item["labor_cents"]
        for item in items
    )

    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_cents,
    )

    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]

    display_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    items = distribute_final_total_between_items(
        items,
        display_total_cents,
    )

    def brl(cents):
        value = cents / 100
        formatted = f"{value:,.2f}"
        formatted = (
            formatted
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        return f"R$ {formatted}"

    def safe(value, fallback=""):
        if value is None or str(value).strip() == "":
            value = fallback

        return escape(str(value))

    # --------------------------------------------------------
    # Fonte Unicode
    # --------------------------------------------------------

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"

    arial_regular = Path("C:/Windows/Fonts/arial.ttf")
    arial_bold = Path("C:/Windows/Fonts/arialbd.ttf")

    if arial_regular.exists() and arial_bold.exists():
        if "BragaArial" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont("BragaArial", str(arial_regular))
            )

        if "BragaArialBold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont("BragaArialBold", str(arial_bold))
            )

        font_regular = "BragaArial"
        font_bold = "BragaArialBold"

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=11 * mm,
        bottomMargin=11 * mm,
        title=f"Orcamento {quote['quote_number']}",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BragaTitle",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#7A2028"),
        spaceBefore=2,
        spaceAfter=7,
    )

    section_style = ParagraphStyle(
        "BragaSection",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#7A2028"),
        spaceBefore=13,
        spaceAfter=6,
        keepWithNext=True,
    )

    normal_style = ParagraphStyle(
        "BragaNormal",
        parent=styles["BodyText"],
        fontName=font_regular,
        fontSize=8.5,
        leading=11,
        spaceAfter=0,
    )

    bold_style = ParagraphStyle(
        "BragaBold",
        parent=normal_style,
        fontName=font_bold,
    )

    small_style = ParagraphStyle(
        "BragaSmall",
        parent=normal_style,
        fontSize=7.8,
        leading=10,
    )

    right_style = ParagraphStyle(
        "BragaRight",
        parent=normal_style,
        alignment=TA_RIGHT,
    )

    business_style = ParagraphStyle(
        "BragaBusiness",
        parent=normal_style,
        alignment=TA_CENTER,
        fontSize=9.5,
        leading=14,
    )

    story = []

    # --------------------------------------------------------
    # Cabe?alho: logo esquerda / dados direita
    # --------------------------------------------------------

    logo_path = Path("app/static/images/logo-braga.png")

    logo = ""

    if logo_path.exists():
        logo = Image(
            str(logo_path),
            width=32 * mm,
            height=32 * mm,
        )

    business_name = (
        business["business_name"]
        if business and business["business_name"]
        else "Vidra\u00e7aria Braga"
    )

    business_lines = [
        f'<font name="{font_bold}" size="17" color="#7A2028"><b>{safe(business_name)}</b></font>',
    ]

    if business and business["phone"]:
        business_lines.append(
            f"Telefone: {safe(business['phone'])}"
        )

    if business and business["cnpj"]:
        business_lines.append(
            f"CNPJ: {safe(business['cnpj'])}"
        )

    header = Table(
        [
            [
                logo,
                Paragraph(
                    "<br/>".join(business_lines),
                    business_style,
                ),
                "",
            ]
        ],
        colWidths=[34 * mm, 113 * mm, 34 * mm],
    )

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    1,
                    colors.HexColor("#7A2028"),
                ),
            ]
        )
    )

    story.append(header)
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph(
            f"OR\u00c7AMENTO N\u00ba {quote['quote_number']}",
            title_style,
        )
    )

    # --------------------------------------------------------
    # Cliente
    # --------------------------------------------------------

    client_data = [
        [
            Paragraph("Nome", bold_style),
            Paragraph(
                safe(quote["client_name"]),
                normal_style,
            ),
        ],
        [
            Paragraph("Telefone", bold_style),
            Paragraph(
                safe(
                    quote["client_phone"],
                    "N\u00e3o informado",
                ),
                normal_style,
            ),
        ],
        [
            Paragraph("Endere\u00e7o", bold_style),
            Paragraph(
                safe(
                    quote["client_address"],
                    "N\u00e3o informado",
                ),
                normal_style,
            ),
        ],
    ]

    client_table = Table(
        client_data,
        colWidths=[28 * mm, 153 * mm],
    )

    client_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#DDDDDD"),
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                Paragraph("CLIENTE", section_style),
                client_table,
            ]
        )
    )

    # --------------------------------------------------------
    # Condi??es / observa??es / garantia
    # Mantidas juntas para evitar subt?tulos ?rf?os.
    # --------------------------------------------------------

    conditions = [
        [
            Paragraph("Validade", bold_style),
            Paragraph(
                f"{quote['validity_days']} dias",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "Prazo de execu\u00e7\u00e3o",
                bold_style,
            ),
            Paragraph(
                f"{quote['execution_days']} dias",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "Formas de pagamento",
                bold_style,
            ),
            Paragraph(
                safe(
                    quote["payment_terms"],
                    "N\u00e3o informado",
                ),
                normal_style,
            ),
        ],
    ]

    conditions_table = Table(
        conditions,
        colWidths=[
            48 * mm,
            133 * mm,
        ],
    )

    conditions_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#DDDDDD"),
                ),
            ]
        )
    )

    conditions_block = [
        Paragraph(
            "CONDI\u00c7\u00d5ES",
            section_style,
        ),
        conditions_table,
    ]

    if quote["notes"]:
        conditions_block.extend(
            [
                Spacer(1, 2 * mm),
                Paragraph(
                    "<b>Observa\u00e7\u00f5es</b>",
                    normal_style,
                ),
                Paragraph(
                    safe(quote["notes"]),
                    normal_style,
                ),
            ]
        )

    warranty = (
        quote["warranty_text"]
        or (
            business["warranty_text"]
            if business
            else None
        )
    )

    story.append(
        KeepTogether(conditions_block)
    )


    # --------------------------------------------------------
    # Itens comerciais
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "ITENS DO OR\u00c7AMENTO",
            section_style,
        )
    )

    commercial_rows = [
        [
            Paragraph("<b>SERVI\u00c7O</b>", bold_style),
            Paragraph("<b>DESCRI\u00c7\u00c3O</b>", bold_style),
            Paragraph("<b>VALOR</b>", right_style),
        ]
    ]

    for item in items:
        service_text = safe(
            item["service_type"],
            "-",
        )

        description_parts = []

        if item["description"]:
            description_parts.append(
                safe(item["description"])
            )

        technical_parts = []

        if item["quantity"]:
            technical_parts.append(
                f"{item['quantity']} un."
            )

        if item["width_mm"] and item["height_mm"]:
            technical_parts.append(
                f"{item['width_mm']} x {item['height_mm']} mm"
            )

        if item["glass_type"]:
            technical_parts.append(
                safe(item["glass_type"])
            )

        if item["thickness_mm"]:
            technical_parts.append(
                f"{item['thickness_mm']} mm"
            )

        if item["glass_color"]:
            technical_parts.append(
                safe(item["glass_color"])
            )

        if item["finish"]:
            technical_parts.append(
                safe(item["finish"])
            )

        if technical_parts:
            description_parts.append(
                " | ".join(technical_parts)
            )

        description_text = (
            "<br/>".join(description_parts)
            if description_parts
            else "-"
        )

        commercial_rows.append(
            [
                Paragraph(
                    service_text,
                    normal_style,
                ),
                Paragraph(
                    description_text,
                    small_style,
                ),
                Paragraph(
                    f'<font name="{font_bold}"><b>'
                    f'{brl(item["commercial_total_cents"])}'
                    f'</b></font>',
                    right_style,
                ),
            ]
        )

    commercial_table = Table(
        commercial_rows,
        colWidths=[
            42 * mm,
            100 * mm,
            39 * mm,
        ],
        repeatRows=1,
    )

    commercial_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#F4ECE9"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#7A2028"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D8C7C2"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#E9DEDA"),
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story.append(commercial_table)
    story.append(Spacer(1, 5 * mm))

    final_total_table = Table(
        [
            [
                Paragraph(
                    "<b>VALOR TOTAL</b>",
                    bold_style,
                ),
                Paragraph(
                    f'<font name="{font_bold}" size="12" '
                    f'color="#7A2028"><b>'
                    f'{brl(display_total_cents)}'
                    f'</b></font>',
                    right_style,
                ),
            ]
        ],
        colWidths=[
            126 * mm,
            55 * mm,
        ],
    )

    final_total_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F4ECE9"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.75,
                    colors.HexColor("#7A2028"),
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#7A2028"),
                ),
            ]
        )
    )

    story.append(final_total_table)
    story.append(Spacer(1, 3 * mm))


    if warranty:
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        "GARANTIA",
                        section_style,
                    ),
                    Paragraph(
                        safe(warranty),
                        normal_style,
                    ),
                ]
            )
        )

    document.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=(
            f"orcamento-{quote['quote_number']}.pdf"
        ),
    )



@main.get("/orcamentos/<int:quote_id>/exportar/imagem")
def export_quote_image(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, quote_number, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    # Reaproveita exatamente o PDF definitivo.
    pdf_response = export_quote_pdf(quote_id)

    # send_file usa streaming; desabilitamos apenas aqui para
    # acessar os bytes em mem?ria e convert?-los para PNG.
    pdf_response.direct_passthrough = False
    pdf_bytes = pdf_response.get_data()

    pdf_document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    rendered_pages = []

    try:
        # 2x = boa defini??o para leitura e compartilhamento.
        matrix = fitz.Matrix(2, 2)

        for page in pdf_document:
            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            page_png = BytesIO(
                pixmap.tobytes("png")
            )

            image = PILImage.open(page_png).convert("RGB")
            rendered_pages.append(image.copy())
            image.close()

    finally:
        pdf_document.close()

    if not rendered_pages:
        abort(500)

    if len(rendered_pages) == 1:
        final_image = rendered_pages[0]
    else:
        final_width = max(
            image.width
            for image in rendered_pages
        )

        final_height = sum(
            image.height
            for image in rendered_pages
        )

        final_image = PILImage.new(
            "RGB",
            (final_width, final_height),
            "white",
        )

        current_y = 0

        for image in rendered_pages:
            current_x = (
                final_width - image.width
            ) // 2

            final_image.paste(
                image,
                (current_x, current_y),
            )

            current_y += image.height

    output = BytesIO()

    final_image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    for image in rendered_pages:
        if image is not final_image:
            image.close()

    final_image.close()

    return send_file(
        output,
        mimetype="image/png",
        as_attachment=True,
        download_name=(
            f"orcamento-{quote['quote_number']}.png"
        ),
    )


@main.route("/orcamentos/<int:quote_id>/itens/novo", methods=("GET", "POST"))
def new_quote_item(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT quotes.id, quotes.status, clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        service_type = request.form.get("service_type", "").strip()
        description = request.form.get("description", "").strip()
        glass_type = request.form.get("glass_type", "").strip()
        glass_color = request.form.get("glass_color", "").strip()
        finish = request.form.get("finish", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            width_mm = int(request.form.get("width_mm", ""))
            height_mm = int(request.form.get("height_mm", ""))
            thickness_mm = parse_decimal(
                request.form.get("thickness_mm", "")
            )
            glass_price_per_m2_cents = money_to_cents(
                request.form.get("glass_price_per_m2", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente as medidas, quantidades e valores."

        if error is None and not service_type:
            error = "Informe o tipo de serviço."
        elif error is None and not glass_type:
            error = "Informe o tipo de vidro."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and (width_mm <= 0 or height_mm <= 0):
            error = "A largura e a altura devem ser maiores que zero."
        elif error is None and thickness_mm <= 0:
            error = "A espessura deve ser maior que zero."
        elif error is None and glass_price_per_m2_cents <= 0:
            error = "O preço do vidro deve ser maior que zero."

        if error is None:
            exact_area_m2 = (
                Decimal(width_mm)
                * Decimal(height_mm)
                / Decimal("1000000")
            ).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
            charged_area_m2 = exact_area_m2

            db.execute(
                """
                INSERT INTO quote_items (
                    quote_id,
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    exact_area_m2,
                    charged_area_m2,
                    glass_type,
                    thickness_mm,
                    glass_color,
                    finish,
                    glass_price_per_m2_cents
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote_id,
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    float(exact_area_m2),
                    float(charged_area_m2),
                    glass_type,
                    float(thickness_mm),
                    glass_color,
                    finish,
                    glass_price_per_m2_cents,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    return render_template(
        "new_quote_item.html",
        quote=quote,
        error=error,
    )



@main.app_template_filter("brl")
def format_brl(cents):
    value = cents / 100
    formatted = f"{value:,.2f}"

    return (
        "R$ "
        + formatted
        .replace(",", "#")
        .replace(".", ",")
        .replace("#", ".")
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/novo",
    methods=("GET", "POST"),
)
def new_quote_item_component(quote_id, item_id):
    db = get_db()

    item = db.execute(
        """
        SELECT
            quote_items.id,
            quote_items.service_type,
            quote_items.quantity AS item_quantity,
            quote_items.width_mm,
            quotes.id AS quote_id,
            quotes.status,
            clients.name AS client_name
        FROM quote_items
        JOIN quotes ON quotes.id = quote_items.quote_id
        JOIN clients ON clients.id = quotes.client_id
        WHERE quote_items.id = ? AND quotes.id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if item is None:
        abort(404)

    if item["status"] != "draft":
        abort(400)

    available_components = db.execute(
        """
        SELECT id, name, unit_price_cents
        FROM components
        WHERE active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    existing_components = db.execute(
        """
        SELECT id, description, quantity, unit_price_cents
        FROM quote_item_components
        WHERE quote_item_id = ?
        ORDER BY id
        """,
        (item_id,),
    ).fetchall()

    error = None
    component_rows = []

    if request.method == "POST":
        descriptions = request.form.getlist("description")
        quantities = request.form.getlist("quantity")
        unit_prices = request.form.getlist("unit_price")

        if not (
            len(descriptions)
            == len(quantities)
            == len(unit_prices)
        ):
            error = "Os dados dos componentes estao incompletos."

        if error is None:
            for description, quantity_raw, unit_price_raw in zip(
                descriptions,
                quantities,
                unit_prices,
            ):
                description = description.strip()

                component_rows.append(
                    {
                        "description": description,
                        "quantity": quantity_raw,
                        "unit_price": unit_price_raw,
                    }
                )

                try:
                    quantity = int(quantity_raw)
                    unit_price_cents = money_to_cents(unit_price_raw)
                except (ValueError, InvalidOperation):
                    error = "Preencha corretamente quantidade e valor."
                    break

                if not description:
                    error = "Selecione um componente."
                    break

                if quantity <= 0:
                    error = "A quantidade deve ser maior que zero."
                    break

                if unit_price_cents <= 0:
                    error = "O valor unitario deve ser maior que zero."
                    break

        if error is None and not component_rows:
            error = "Adicione pelo menos um componente."

        if error is None:
            rows_to_save = []

            for row in component_rows:
                rows_to_save.append(
                    (
                        item_id,
                        "other",
                        row["description"],
                        int(row["quantity"]),
                        money_to_cents(row["unit_price"]),
                    )
                )

            db.execute(
                """
                DELETE FROM quote_item_components
                WHERE quote_item_id = ?
                """,
                (item_id,),
            )

            db.executemany(
                """
                INSERT INTO quote_item_components (
                    quote_item_id,
                    category,
                    description,
                    quantity,
                    unit_price_cents
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                rows_to_save,
            )

            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-items",
                )
            )

    else:
        for component in existing_components:
            component_rows.append(
                {
                    "description": component["description"],
                    "quantity": str(component["quantity"]),
                    "unit_price": (
                        f"{component['unit_price_cents'] / 100:.2f}"
                        .replace(".", ",")
                    ),
                }
            )

    if not component_rows:
        component_rows = [
            {
                "description": "",
                "quantity": "1",
                "unit_price": "",
            }
        ]

    return render_template(
        "new_quote_item_component.html",
        item=item,
        available_components=available_components,
        component_rows=component_rows,
        error=error,
    )


def percentage_of_cents(base_cents, percentage):
    amount = (
        Decimal(base_cents)
        * Decimal(str(percentage))
        / Decimal("100")
    )

    return int(
        amount.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_items_pricing(items, components_by_item):
    priced_items = []

    for item_row in items:
        item = dict(item_row)
        item_components = components_by_item.get(
            item["id"],
            [],
        )
        components_total_cents = sum(
            component["total_cents"]
            for component in item_components
        )
        materials_total_cents = (
            item["glass_total_cents"]
            + components_total_cents
        )
        automatic_labor_cents = percentage_of_cents(
            materials_total_cents,
            50,
        )
        labor_cents = (
            item["manual_labor_cents"]
            if item["manual_labor_cents"] is not None
            else automatic_labor_cents
        )

        item["components_total_cents"] = components_total_cents
        item["materials_total_cents"] = materials_total_cents
        item["automatic_labor_cents"] = automatic_labor_cents
        item["labor_cents"] = labor_cents
        item["labor_is_manual"] = (
            item["manual_labor_cents"] is not None
        )
        item["total_cents"] = (
            materials_total_cents
            + labor_cents
        )
        priced_items.append(item)

    return priced_items

def distribute_final_total_between_items(
    items,
    final_total_cents,
):
    if not items:
        return items

    unit_cents = (
        100
        if final_total_cents % 100 == 0
        else 1
    )
    final_units = final_total_cents // unit_cents
    weights = [
        max(item["total_cents"], 0)
        for item in items
    ]
    total_weight = sum(weights)

    if total_weight == 0:
        weights = [1 for item in items]
        total_weight = len(items)

    allocated_units = []
    remainders = []

    for weight in weights:
        proportional_value = final_units * weight
        allocated_units.append(
            proportional_value // total_weight
        )
        remainders.append(
            proportional_value % total_weight
        )

    remaining_units = (
        final_units
        - sum(allocated_units)
    )
    priority_order = sorted(
        range(len(items)),
        key=lambda index: (
            remainders[index],
            weights[index],
            -index,
        ),
        reverse=True,
    )

    for index in priority_order[:remaining_units]:
        allocated_units[index] += 1

    for index, item in enumerate(items):
        commercial_total_cents = (
            allocated_units[index]
            * unit_cents
        )
        item["commercial_total_cents"] = (
            commercial_total_cents
        )
        item["commercial_adjustment_cents"] = (
            commercial_total_cents
            - item["total_cents"]
        )

    return items

@main.route(
    "/orcamentos/<int:quote_id>/condicoes",
    methods=("GET", "POST"),
)
def edit_quote_conditions(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        payment_terms = request.form.get("payment_terms", "").strip()
        notes = request.form.get("notes", "").strip()
        warranty_text = request.form.get("warranty_text", "").strip()

        try:
            validity_days = int(
                request.form.get("validity_days", "")
            )
            execution_days = int(
                request.form.get("execution_days", "")
            )
            difficulty_percentage = parse_decimal(
                request.form.get("difficulty_percentage", "")
            )
            discount_percentage = parse_decimal(
                request.form.get("discount_percentage", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente os prazos e percentuais."

        if error is None and validity_days <= 0:
            error = "A validade deve ser maior que zero."
        elif error is None and execution_days <= 0:
            error = "O prazo de execução deve ser maior que zero."
        elif error is None and not 0 <= difficulty_percentage <= 100:
            error = "O adicional de dificuldade deve ficar entre 0% e 100%."
        elif error is None and not 0 <= discount_percentage <= 100:
            error = "O desconto deve ficar entre 0% e 100%."

        if error is None:
            db.execute(
                """
                UPDATE quotes
                SET
                    validity_days = ?,
                    execution_days = ?,
                    payment_terms = ?,
                    notes = ?,
                    warranty_text = ?,
                    difficulty_percentage = ?,
                    discount_percentage = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    validity_days,
                    execution_days,
                    payment_terms,
                    notes,
                    warranty_text,
                    float(difficulty_percentage),
                    float(discount_percentage),
                    quote_id,
                ),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-conditions",
                )
            )

    return render_template(
        "edit_quote_conditions.html",
        quote=quote,
        error=error,
    )



@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/mao-de-obra",
    methods=("GET", "POST"),
)
def edit_quote_item_labor(quote_id, item_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT
            quotes.id,
            quotes.status,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    item = db.execute(
        """
        SELECT
            quote_items.*,
            CAST(
                ROUND(
                    charged_area_m2
                    * quantity
                    * glass_price_per_m2_cents
                )
                AS INTEGER
            ) AS glass_total_cents
        FROM quote_items
        WHERE id = ? AND quote_id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if quote is None or item is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    components_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(quantity * unit_price_cents),
            0
        )
        FROM quote_item_components
        WHERE quote_item_id = ?
        """,
        (item_id,),
    ).fetchone()[0]

    materials_total_cents = (
        item["glass_total_cents"]
        + components_total_cents
    )
    automatic_labor_cents = percentage_of_cents(
        materials_total_cents,
        50,
    )
    current_labor_cents = (
        item["manual_labor_cents"]
        if item["manual_labor_cents"] is not None
        else automatic_labor_cents
    )

    error = None

    if request.method == "POST":
        labor_mode = request.form.get("labor_mode", "manual")

        if labor_mode == "automatic":
            manual_labor_cents = None
        else:
            try:
                manual_labor_cents = money_to_cents(
                    request.form.get("labor_value", "")
                )
            except InvalidOperation:
                error = "Informe corretamente o valor da mão de obra."
                manual_labor_cents = None

            if error is None and manual_labor_cents < 0:
                error = "A mão de obra não pode ser negativa."

        if error is None:
            db.execute(
                """
                UPDATE quote_items
                SET
                    manual_labor_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_id = ?
                """,
                (
                    manual_labor_cents,
                    item_id,
                    quote_id,
                ),
            )
            db.execute(
                """
                UPDATE quotes
                SET
                    manual_total_cents = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (quote_id,),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor=f"quote-item-{item_id}",
                )
            )

    return render_template(
        "edit_quote_item_labor.html",
        quote=quote,
        item=item,
        components_total_cents=components_total_cents,
        materials_total_cents=materials_total_cents,
        automatic_labor_cents=automatic_labor_cents,
        current_labor_cents=current_labor_cents,
        error=error,
    )

@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/editar",
    methods=("GET", "POST"),
)
def edit_quote_item(quote_id, item_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.id,
            quotes.status,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    item = db.execute(
        """
        SELECT *
        FROM quote_items
        WHERE id = ? AND quote_id = ?
        """,
        (item_id, quote_id),
    ).fetchone()

    if quote is None or item is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        service_type = request.form.get("service_type", "").strip()
        description = request.form.get("description", "").strip()
        glass_type = request.form.get("glass_type", "").strip()
        glass_color = request.form.get("glass_color", "").strip()
        finish = request.form.get("finish", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            width_mm = int(request.form.get("width_mm", ""))
            height_mm = int(request.form.get("height_mm", ""))
            thickness_mm = parse_decimal(
                request.form.get("thickness_mm", "")
            )
            glass_price_per_m2_cents = money_to_cents(
                request.form.get("glass_price_per_m2", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente as medidas, quantidades e valores."

        if error is None and not service_type:
            error = "Informe o tipo de serviço."
        elif error is None and not glass_type:
            error = "Informe o tipo de vidro."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and (width_mm <= 0 or height_mm <= 0):
            error = "A largura e a altura devem ser maiores que zero."
        elif error is None and thickness_mm <= 0:
            error = "A espessura deve ser maior que zero."
        elif error is None and glass_price_per_m2_cents <= 0:
            error = "O preço do vidro deve ser maior que zero."

        if error is None:
            exact_area_m2 = (
                Decimal(width_mm)
                * Decimal(height_mm)
                / Decimal("1000000")
            ).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
            charged_area_m2 = exact_area_m2

            db.execute(
                """
                UPDATE quote_items
                SET
                    service_type = ?,
                    description = ?,
                    quantity = ?,
                    width_mm = ?,
                    height_mm = ?,
                    exact_area_m2 = ?,
                    charged_area_m2 = ?,
                    glass_type = ?,
                    thickness_mm = ?,
                    glass_color = ?,
                    finish = ?,
                    glass_price_per_m2_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_id = ?
                """,
                (
                    service_type,
                    description,
                    quantity,
                    width_mm,
                    height_mm,
                    float(exact_area_m2),
                    float(charged_area_m2),
                    glass_type,
                    float(thickness_mm),
                    glass_color,
                    finish,
                    glass_price_per_m2_cents,
                    item_id,
                    quote_id,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    charged_area_for_input = (
        f"{item['charged_area_m2']:.2f}"
        .replace(".", ",")
    )
    glass_price_for_input = (
        f"{item['glass_price_per_m2_cents'] / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_item.html",
        quote=quote,
        item=item,
        charged_area_for_input=charged_area_for_input,
        glass_price_for_input=glass_price_for_input,
        error=error,
    )


@main.route(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/<int:component_id>/editar",
    methods=("GET", "POST"),
)
def edit_quote_item_component(
    quote_id,
    item_id,
    component_id,
):
    db = get_db()
    component = db.execute(
        """
        SELECT
            quote_item_components.*,
            quote_items.service_type,
            quotes.id AS quote_id,
            quotes.status,
            clients.name AS client_name
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        JOIN quotes
            ON quotes.id = quote_items.quote_id
        JOIN clients
            ON clients.id = quotes.client_id
        WHERE
            quote_item_components.id = ?
            AND quote_items.id = ?
            AND quotes.id = ?
        """,
        (component_id, item_id, quote_id),
    ).fetchone()

    if component is None:
        abort(404)

    if component["status"] != "draft":
        abort(400)

    error = None

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            unit_price_cents = money_to_cents(
                request.form.get("unit_price", "")
            )
        except (ValueError, InvalidOperation):
            error = "Preencha corretamente a quantidade e o valor."

        if error is None and category not in {"kit", "accessory", "other"}:
            error = "Selecione o tipo do componente."
        elif error is None and not description:
            error = "Informe a descrição do componente."
        elif error is None and quantity <= 0:
            error = "A quantidade deve ser maior que zero."
        elif error is None and unit_price_cents <= 0:
            error = "O valor unitário deve ser maior que zero."

        if error is None:
            db.execute(
                """
                UPDATE quote_item_components
                SET
                    category = ?,
                    description = ?,
                    quantity = ?,
                    unit_price_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND quote_item_id = ?
                """,
                (
                    category,
                    description,
                    quantity,
                    unit_price_cents,
                    component_id,
                    item_id,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
            )

    unit_price_for_input = (
        f"{component['unit_price_cents'] / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_item_component.html",
        component=component,
        unit_price_for_input=unit_price_for_input,
        error=error,
    )


@main.post(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/remover"
)
def remove_quote_item(quote_id, item_id):
    db = get_db()
    result = db.execute(
        """
        DELETE FROM quote_items
        WHERE
            id = ?
            AND quote_id = ?
            AND EXISTS (
                SELECT 1
                FROM quotes
                WHERE
                    quotes.id = quote_items.quote_id
                    AND quotes.status = 'draft'
            )
        """,
        (item_id, quote_id),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(
        url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
    )


@main.post(
    "/orcamentos/<int:quote_id>/itens/<int:item_id>/componentes/<int:component_id>/remover"
)
def remove_quote_item_component(
    quote_id,
    item_id,
    component_id,
):
    db = get_db()
    result = db.execute(
        """
        DELETE FROM quote_item_components
        WHERE
            id = ?
            AND quote_item_id = ?
            AND EXISTS (
                SELECT 1
                FROM quote_items
                JOIN quotes
                    ON quotes.id = quote_items.quote_id
                WHERE
                    quote_items.id = quote_item_components.quote_item_id
                    AND quote_items.quote_id = ?
                    AND quotes.status = 'draft'
            )
        """,
        (component_id, item_id, quote_id),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(
        url_for("main.quote_detail", quote_id=quote_id, _anchor="quote-items")
    )



def calculate_price_breakdown(
    materials_subtotal_cents,
    quote,
    labor_cents=None,
):
    if labor_cents is None:
        labor_cents = percentage_of_cents(
            materials_subtotal_cents,
            quote["labor_percentage"],
        )

    subtotal_with_labor_cents = (
        materials_subtotal_cents
        + labor_cents
    )
    difficulty_cents = percentage_of_cents(
        subtotal_with_labor_cents,
        quote["difficulty_percentage"],
    )
    subtotal_before_discount_cents = (
        subtotal_with_labor_cents
        + difficulty_cents
    )
    discount_cents = percentage_of_cents(
        subtotal_before_discount_cents,
        quote["discount_percentage"],
    )
    calculated_total_cents = (
        subtotal_before_discount_cents
        - discount_cents
    )

    return {
        "labor_cents": labor_cents,
        "difficulty_cents": difficulty_cents,
        "discount_cents": discount_cents,
        "calculated_total_cents": calculated_total_cents,
    }


@main.post("/orcamentos/<int:quote_id>/remover-rascunho")
def delete_draft_quote(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    db.execute(
        """
        DELETE FROM quote_item_components
        WHERE quote_item_id IN (
            SELECT id
            FROM quote_items
            WHERE quote_id = ?
        )
        """,
        (quote_id,),
    )

    db.execute(
        """
        DELETE FROM quote_items
        WHERE quote_id = ?
        """,
        (quote_id,),
    )

    db.execute(
        """
        DELETE FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    )

    db.commit()

    return redirect(url_for("main.quotes"))


@main.post("/orcamentos/<int:quote_id>/status")
def update_quote_status(quote_id):
    db = get_db()

    quote = db.execute(
        """
        SELECT id, status
        FROM quotes
        WHERE id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] == "draft":
        abort(400)

    new_status = request.form.get("status", "").strip()

    if new_status not in {"issued", "approved", "rejected"}:
        abort(400)

    db.execute(
        """
        UPDATE quotes
        SET
            status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_status, quote_id),
    )

    db.commit()

    return redirect(
        url_for(
            "main.quotes",
        )
    )


@main.post("/orcamentos/<int:quote_id>/emitir")
def issue_quote(quote_id):
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        quote = db.execute(
            """
            SELECT id, status
            FROM quotes
            WHERE id = ?
            """,
            (quote_id,),
        ).fetchone()

        if quote is None:
            db.rollback()
            abort(404)

        if quote["status"] != "draft":
            db.rollback()
            abort(400)

        item_count = db.execute(
            """
            SELECT COUNT(*)
            FROM quote_items
            WHERE quote_id = ?
            """,
            (quote_id,),
        ).fetchone()[0]

        if item_count == 0:
            db.rollback()
            abort(400)

        settings = db.execute(
            """
            SELECT next_quote_number
            FROM settings
            WHERE id = 1
            """
        ).fetchone()

        if settings is None:
            db.rollback()
            abort(500)

        quote_number = settings["next_quote_number"]

        db.execute(
            """
            UPDATE quotes
            SET
                quote_number = ?,
                status = 'issued',
                issued_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (quote_number, quote_id),
        )

        db.execute(
            """
            UPDATE settings
            SET
                next_quote_number = next_quote_number + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return redirect(
        url_for(
            "main.quote_detail",
            quote_id=quote_id,
        )
    )


@main.route(
    "/orcamentos/<int:quote_id>/valor-final",
    methods=("GET", "POST"),
)
def edit_quote_final_total(quote_id):
    db = get_db()
    quote = db.execute(
        """
        SELECT
            quotes.*,
            clients.name AS client_name
        FROM quotes
        JOIN clients ON clients.id = quotes.client_id
        WHERE quotes.id = ?
        """,
        (quote_id,),
    ).fetchone()

    if quote is None:
        abort(404)

    if quote["status"] != "draft":
        abort(400)

    glass_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                CAST(
                    ROUND(
                        charged_area_m2
                        * quantity
                        * glass_price_per_m2_cents
                    )
                    AS INTEGER
                )
            ),
            0
        )
        FROM quote_items
        WHERE quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    components_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                quote_item_components.quantity
                * quote_item_components.unit_price_cents
            ),
            0
        )
        FROM quote_item_components
        JOIN quote_items
            ON quote_items.id = quote_item_components.quote_item_id
        WHERE quote_items.quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    labor_total_cents = db.execute(
        """
        SELECT COALESCE(
            SUM(
                COALESCE(
                    quote_items.manual_labor_cents,
                    CAST(
                        ROUND(
                            (
                                CAST(
                                    ROUND(
                                        quote_items.charged_area_m2
                                        * quote_items.quantity
                                        * quote_items.glass_price_per_m2_cents
                                    )
                                    AS INTEGER
                                )
                                + COALESCE(
                                    (
                                        SELECT SUM(
                                            component.quantity
                                            * component.unit_price_cents
                                        )
                                        FROM quote_item_components AS component
                                        WHERE component.quote_item_id = quote_items.id
                                    ),
                                    0
                                )
                            )
                            * 0.5
                        )
                        AS INTEGER
                    )
                )
            ),
            0
        )
        FROM quote_items
        WHERE quote_items.quote_id = ?
        """,
        (quote_id,),
    ).fetchone()[0]

    materials_subtotal_cents = (
        glass_total_cents
        + components_total_cents
    )
    price_breakdown = calculate_price_breakdown(
        materials_subtotal_cents,
        quote,
        labor_total_cents,
    )
    calculated_total_cents = price_breakdown[
        "calculated_total_cents"
    ]

    error = None

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "use_calculated":
            manual_total_cents = None
        else:
            try:
                manual_total_cents = money_to_cents(
                    request.form.get("manual_total", "")
                )
            except InvalidOperation:
                error = "Informe corretamente o valor final."

            if error is None and manual_total_cents <= 0:
                error = "O valor final deve ser maior que zero."
            elif error is None and manual_total_cents % 100 != 0:
                error = "Informe um valor inteiro, sem centavos."

        if error is None:
            db.execute(
                """
                UPDATE quotes
                SET
                    manual_total_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (manual_total_cents, quote_id),
            )
            db.commit()

            return redirect(
                url_for(
                    "main.quote_detail",
                    quote_id=quote_id,
                    _anchor="quote-total",
                )
            )

    current_total_cents = (
        quote["manual_total_cents"]
        if quote["manual_total_cents"] is not None
        else calculated_total_cents
    )
    current_total_for_input = (
        f"{current_total_cents / 100:.2f}"
        .replace(".", ",")
    )

    return render_template(
        "edit_quote_final_total.html",
        quote=quote,
        calculated_total_cents=calculated_total_cents,
        current_total_for_input=current_total_for_input,
        error=error,
    )



@main.route(
    "/configuracoes",
    methods=("GET", "POST"),
)
def settings():
    db = get_db()
    current_settings = db.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    if current_settings is None:
        abort(404)

    error = None

    if request.method == "POST":
        business_name = request.form.get(
            "business_name",
            "",
        ).strip()
        phone = request.form.get("phone", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        warranty_text = request.form.get(
            "warranty_text",
            "",
        ).strip()

        try:
            default_validity_days = int(
                request.form.get(
                    "default_validity_days",
                    "",
                )
            )
            default_execution_days = int(
                request.form.get(
                    "default_execution_days",
                    "",
                )
            )
        except ValueError:
            error = "Preencha corretamente os prazos padrão."

        if error is None and not business_name:
            error = "Informe o nome da vidraçaria."
        elif error is None and default_validity_days <= 0:
            error = "A validade padrão deve ser maior que zero."
        elif error is None and default_execution_days <= 0:
            error = "O prazo de execução padrão deve ser maior que zero."

        if error is None:
            db.execute(
                """
                UPDATE settings
                SET
                    business_name = ?,
                    phone = ?,
                    cnpj = ?,
                    default_validity_days = ?,
                    default_execution_days = ?,
                    warranty_text = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (
                    business_name,
                    phone,
                    cnpj,
                    default_validity_days,
                    default_execution_days,
                    warranty_text,
                ),
            )
            db.commit()

            return redirect(
                url_for("main.settings", saved=1)
            )

    return render_template(
        "settings.html",
        settings=current_settings,
        error=error,
    )


@main.route("/componentes", methods=("GET", "POST"))
def components():
    db = get_db()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit_price = request.form.get("unit_price", "").strip()

        if not name:
            error = "Informe o nome do componente."

        if error is None:
            try:
                unit_price_cents = money_to_cents(unit_price)
            except (InvalidOperation, ValueError):
                error = "Informe corretamente o valor unitário."

        if error is None and unit_price_cents < 0:
            error = "O valor unitário não pode ser negativo."

        if error is None:
            existing_component = db.execute(
                """
                SELECT id
                FROM components
                WHERE name = ? COLLATE NOCASE
                """,
                (name,),
            ).fetchone()

            if existing_component is not None:
                error = "Já existe um componente com esse nome."

        if error is None:
            db.execute(
                """
                INSERT INTO components (name, unit_price_cents)
                VALUES (?, ?)
                """,
                (name, unit_price_cents),
            )
            db.commit()

            return redirect(url_for("main.components", saved=1))

    components_list, search, page, total_pages, total_count = (
        get_components_page(active=1)
    )

    return render_template(
        "components.html",
        components=components_list,
        error=error,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@main.route(
    "/componentes/<int:component_id>/editar",
    methods=("GET", "POST"),
)
def edit_component(component_id):
    db = get_db()
    component = db.execute(
        """
        SELECT id, name, unit_price_cents, active
        FROM components
        WHERE id = ? AND active = 1
        """,
        (component_id,),
    ).fetchone()

    if component is None:
        abort(404)

    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        unit_price = request.form.get("unit_price", "").strip()

        if not name:
            error = "Informe o nome do componente."

        if error is None:
            try:
                unit_price_cents = money_to_cents(unit_price)
            except (InvalidOperation, ValueError):
                error = "Informe corretamente o valor unitário."

        if error is None and unit_price_cents < 0:
            error = "O valor unitário não pode ser negativo."

        if error is None:
            duplicate = db.execute(
                """
                SELECT id
                FROM components
                WHERE name = ? COLLATE NOCASE
                    AND id != ?
                """,
                (name, component_id),
            ).fetchone()

            if duplicate is not None:
                error = "Já existe outro componente com esse nome."

        if error is None:
            db.execute(
                """
                UPDATE components
                SET
                    name = ?,
                    unit_price_cents = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, unit_price_cents, component_id),
            )
            db.commit()

            return redirect(url_for("main.components", updated=1))

    return render_template(
        "edit_component.html",
        component=component,
        error=error,
    )


@main.post("/componentes/<int:component_id>/desativar")
def deactivate_component(component_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE components
        SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 1
        """,
        (component_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.components", deactivated=1))


@main.post("/componentes/<int:component_id>/reativar")
def reactivate_component(component_id):
    db = get_db()
    result = db.execute(
        """
        UPDATE components
        SET active = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND active = 0
        """,
        (component_id,),
    )

    if result.rowcount == 0:
        abort(404)

    db.commit()

    return redirect(url_for("main.inactive_components", reactivated=1))


@main.get("/componentes/desativados")
def inactive_components():
    components_list, search, page, total_pages, total_count = (
        get_components_page(active=0)
    )

    return render_template(
        "inactive_components.html",
        components=components_list,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )
