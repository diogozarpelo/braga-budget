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
