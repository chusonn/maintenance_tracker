import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_database():
    """Run database migrations"""
    migration_needed = False
    
    # Import app configuration
    from app import app, db
    
    with app.app_context():
        print("🔄 Starting database migration...")
        
        # Check and add soft delete fields to flats table
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(flat)"))
                columns = [row[1] for row in result]
                
                if 'is_deleted' not in columns:
                    print("🔄 Adding soft delete fields to flats table...")
                    conn.execute(text("ALTER TABLE flat ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    conn.execute(text("ALTER TABLE flat ADD COLUMN deleted_at DATETIME"))
                    conn.execute(text("ALTER TABLE flat ADD COLUMN deleted_by VARCHAR(100)"))
                    conn.commit()
                    migration_needed = True
                    print("✅ Soft delete fields added to flats table")
        except Exception as e:
            print(f"❌ Error migrating flats table: {e}")
        
        # Check and add soft delete fields to contractors table
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(contractor)"))
                columns = [row[1] for row in result]
                
                if 'is_deleted' not in columns:
                    print("🔄 Adding soft delete fields to contractors table...")
                    conn.execute(text("ALTER TABLE contractor ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    conn.execute(text("ALTER TABLE contractor ADD COLUMN deleted_at DATETIME"))
                    conn.execute(text("ALTER TABLE contractor ADD COLUMN deleted_by VARCHAR(100)"))
                    conn.commit()
                    migration_needed = True
                    print("✅ Soft delete fields added to contractors table")
        except Exception as e:
            print(f"❌ Error migrating contractors table: {e}")
        
        # Check and add soft delete fields to maintenance_job table
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(maintenance_job)"))
                columns = [row[1] for row in result]
                
                if 'is_deleted' not in columns:
                    print("🔄 Adding soft delete fields to maintenance_job table...")
                    conn.execute(text("ALTER TABLE maintenance_job ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    conn.execute(text("ALTER TABLE maintenance_job ADD COLUMN deleted_at DATETIME"))
                    conn.execute(text("ALTER TABLE maintenance_job ADD COLUMN deleted_by VARCHAR(100)"))
                    conn.commit()
                    migration_needed = True
                    print("✅ Soft delete fields added to maintenance_job table")
        except Exception as e:
            print(f"❌ Error migrating maintenance_job table: {e}")
        
        # Check and add follow_up_count column (existing migration)
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(maintenance_job)"))
                columns = [row[1] for row in result]
                
                if 'follow_up_count' not in columns:
                    print("🔄 Adding follow_up_count column to maintenance_job table...")
                    conn.execute(text("ALTER TABLE maintenance_job ADD COLUMN follow_up_count INTEGER DEFAULT 0"))
                    conn.commit()
                    migration_needed = True
                    print("✅ follow_up_count column added to maintenance_job table")
                    
                    # Migrate data from follow_up_sent to follow_up_count
                    print("🔄 Migrating follow-up data...")
                    conn.execute(text("UPDATE maintenance_job SET follow_up_count = 1 WHERE follow_up_sent = 1"))
                    conn.commit()
                    print("✅ Follow-up data migrated")
        except Exception as e:
            print(f"❌ Error migrating follow-up data: {e}")
        
        if migration_needed:
            print("🎉 Migration completed successfully!")
            return True
        else:
            print("✅ Database already up to date!")
            return False

def backup_database():
    """Create a backup of current database"""
    import shutil
    from datetime import datetime
    
    from app import app, db
    with app.app_context():
        # Check both possible database locations
        db_files = ['maintenance_tracker.db', 'instance/maintenance_tracker.db']
        db_file = None
        
        for db_path in db_files:
            if os.path.exists(db_path):
                db_file = db_path
                break
        
        if db_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'backups/maintenance_tracker_backup_{timestamp}.db'
            
            # Create backups directory if it doesn't exist
            os.makedirs('backups', exist_ok=True)
            
            # Copy database to backup location
            shutil.copy2(db_file, backup_path)
            print(f"✅ Database backed up to: {backup_path}")
            return backup_path
        else:
            print("❌ No database file found to backup!")
            return None

if __name__ == "__main__":
    migrate_database()
