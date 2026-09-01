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
