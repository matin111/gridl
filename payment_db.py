from subscription_admin_api import database


def initialize_payment_database():

    with database() as db:

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_transactions(
                id TEXT PRIMARY KEY,
                authority TEXT UNIQUE,
                email TEXT NOT NULL,
                plan_slug TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT NOT NULL
            )
            """
        )


initialize_payment_database()
