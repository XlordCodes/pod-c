# clean_duplicates.py
from app.database import SessionLocal
from sqlalchemy import text

def clean():
    db = SessionLocal()
    try:
        print("Removing duplicate embeddings...")
        
        # SQL to delete duplicates, keeping only the most recent one
        sql = """
        DELETE FROM message_embeddings a USING message_embeddings b
        WHERE a.id < b.id AND a.message_id = b.message_id;
        """
        
        db.execute(text(sql))
        db.commit()
        print("Duplicates removed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean()