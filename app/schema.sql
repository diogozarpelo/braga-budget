CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    business_name TEXT NOT NULL DEFAULT 'Vidraçaria Braga',
    phone TEXT NOT NULL DEFAULT '',
    cnpj TEXT NOT NULL DEFAULT '',
    logo_path TEXT,
    default_validity_days INTEGER NOT NULL DEFAULT 10,
    default_execution_days INTEGER NOT NULL DEFAULT 15,
    warranty_text TEXT NOT NULL DEFAULT 'Garantia de seis meses sobre o funcionamento da instalação, conforme as condições descritas nesta proposta.',
    next_quote_number INTEGER NOT NULL DEFAULT 522,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_number INTEGER UNIQUE,
    client_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'approved', 'rejected', 'cancelled')),
    issued_at TEXT,
    validity_days INTEGER NOT NULL DEFAULT 10
        CHECK (validity_days > 0),
    execution_days INTEGER NOT NULL DEFAULT 15
        CHECK (execution_days > 0),
    payment_terms TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    warranty_text TEXT NOT NULL DEFAULT
        'Garantia de seis meses sobre o funcionamento da instalação, conforme as condições descritas nesta proposta.',
    labor_percentage REAL NOT NULL DEFAULT 50
        CHECK (labor_percentage >= 0),
    difficulty_percentage REAL NOT NULL DEFAULT 0
        CHECK (difficulty_percentage BETWEEN 0 AND 100),
    discount_percentage REAL NOT NULL DEFAULT 0
        CHECK (discount_percentage BETWEEN 0 AND 100),
    manual_total_cents INTEGER
        CHECK (manual_total_cents IS NULL OR manual_total_cents >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS quotes_client_id_index
    ON quotes (client_id);

CREATE INDEX IF NOT EXISTS quotes_status_index
    ON quotes (status);

CREATE TABLE IF NOT EXISTS quote_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    service_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 1
        CHECK (quantity > 0),
    width_mm INTEGER
        CHECK (width_mm IS NULL OR width_mm > 0),
    height_mm INTEGER
        CHECK (height_mm IS NULL OR height_mm > 0),
    exact_area_m2 REAL NOT NULL DEFAULT 0
        CHECK (exact_area_m2 >= 0),
    charged_area_m2 REAL NOT NULL DEFAULT 0
        CHECK (charged_area_m2 >= 0),
    glass_type TEXT NOT NULL DEFAULT '',
    thickness_mm REAL
        CHECK (thickness_mm IS NULL OR thickness_mm > 0),
    glass_color TEXT NOT NULL DEFAULT '',
    finish TEXT NOT NULL DEFAULT '',
    glass_price_per_m2_cents INTEGER NOT NULL DEFAULT 0
        CHECK (glass_price_per_m2_cents >= 0),
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quote_id) REFERENCES quotes (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS quote_items_quote_id_index
    ON quote_items (quote_id);

CREATE TABLE IF NOT EXISTS quote_item_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_item_id INTEGER NOT NULL,
    category TEXT NOT NULL
        CHECK (category IN ('kit', 'accessory', 'other')),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1
        CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL DEFAULT 0
        CHECK (unit_price_cents >= 0),
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quote_item_id) REFERENCES quote_items (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS quote_item_components_item_id_index
    ON quote_item_components (quote_item_id);


CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_item_insert
AFTER INSERT ON quote_items
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = NEW.quote_id
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_item_update
AFTER UPDATE ON quote_items
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = NEW.quote_id
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_item_delete
AFTER DELETE ON quote_items
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = OLD.quote_id
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_component_insert
AFTER INSERT ON quote_item_components
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = (
            SELECT quote_id
            FROM quote_items
            WHERE id = NEW.quote_item_id
        )
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_component_update
AFTER UPDATE ON quote_item_components
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = (
            SELECT quote_id
            FROM quote_items
            WHERE id = NEW.quote_item_id
        )
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_component_delete
AFTER DELETE ON quote_item_components
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = (
            SELECT quote_id
            FROM quote_items
            WHERE id = OLD.quote_item_id
        )
        AND manual_total_cents IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS reset_manual_total_after_price_conditions
AFTER UPDATE OF
    labor_percentage,
    difficulty_percentage,
    discount_percentage
ON quotes
WHEN
    OLD.labor_percentage IS NOT NEW.labor_percentage
    OR OLD.difficulty_percentage IS NOT NEW.difficulty_percentage
    OR OLD.discount_percentage IS NOT NEW.discount_percentage
BEGIN
    UPDATE quotes
    SET
        manual_total_cents = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE
        id = NEW.id
        AND manual_total_cents IS NOT NULL;
END;
