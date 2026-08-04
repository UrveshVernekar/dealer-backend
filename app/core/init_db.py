from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal, Base
from app.models.user import User
from app.models.scheme import Scheme
from app.models.sales_data import SalesData
from app.models.target_data import TargetData
from app.models.import_mapping import ImportTableMapping
from app.core.security import hash_password

def init_db():
    if engine is None or SessionLocal is None:
        print("Database engine is not available; skipping initialization.")
        return

    try:
        # Create all tables in the database
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating database tables: {e}")
        return

    # Add product_category column to sales_data if it does not exist
    db = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("ALTER TABLE sales_data ADD COLUMN IF NOT EXISTS product_category VARCHAR(50)"))
        db.commit()
    except Exception as e:
        print(f"Error migrating sales_data table: {e}")
        db.rollback()
    finally:
        db.close()

    db = SessionLocal()
    try:
        # Seed default admin user
        admin_email = "dealer_admin@ifbglobal.com"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            hashed = hash_password("admin1234$#")
            new_admin = User(
                first_name="Dealer",
                last_name="Admin",
                email=admin_email,
                password_hash=hashed,
                role="admin"
            )
            db.add(new_admin)
            db.commit()
            print("Default admin user seeded successfully.")

        # Seed some default dealer schemes if empty
        schemes_count = db.query(Scheme).count()
        if schemes_count == 0:
            default_schemes = [
                Scheme(
                    scheme_code="SCH-2026-MONSOON",
                    name="Monsoon Dealer Bonanza",
                    description="Special monsoon incentive scheme offering a 5% discount on bulk purchases of washing machines.",
                    discount_percentage=5.0,
                    incentive_amount=0.0,
                    is_active=True
                ),
                Scheme(
                    scheme_code="SCH-2026-FESTIVE",
                    name="Festive Season Super Incentive",
                    description="Earn an additional ₹10,000 for every 50 microwave oven units sold during the festive period.",
                    discount_percentage=0.0,
                    incentive_amount=10000.0,
                    is_active=True
                ),
                Scheme(
                    scheme_code="SCH-2026-CLEARANCE",
                    name="Clearance Sale Discount",
                    description="End of season clearance sale offering 8% discount on older inventory lines.",
                    discount_percentage=8.0,
                    incentive_amount=0.0,
                    is_active=False
                )
            ]
            db.add_all(default_schemes)
            db.commit()
            print("Default schemes seeded successfully.")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()
