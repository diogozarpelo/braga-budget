import fitz
from PIL import Image as PILImage
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_quote_pdf(
    quote,
    business,
    items,
    display_total_cents,
):
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

    return buffer


def build_quote_png(pdf_bytes):
    pdf_document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    rendered_pages = []

    try:
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
        raise RuntimeError(
            "Nenhuma pagina foi renderizada."
        )

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

    return output
