from sqlalchemy import text
from db.session import engine, Base
import db.models  # Import to register models

def init_db():
    print("Initializing Database...")
    if engine.dialect.name == "sqlite":
        print("SQLite detected. Skipping pgvector extension creation.")
    else:
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    
    # Create all tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Run column dimension migration on PostgreSQL in case it was created as 768 previously
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE photos ALTER COLUMN clip_embedding TYPE vector(512);"))
                conn.commit()
                print("Database migration: Successfully verified/altered clip_embedding to 512 dimensions.")
        except Exception as e:
            print(f"PostgreSQL migration notice (already correct size or minor issue): {e}")
            
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
