"""
Database Backup and Restore Utility for Maintenance Tracker
Provides safe data management operations
"""

import os
import shutil
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Add parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def backup_database():
    """Create a timestamped backup of the database"""
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

def restore_database(backup_path):
    """Restore database from a backup file"""
    from app import app, db
    
    if not os.path.exists(backup_path):
        print(f"❌ Backup file not found: {backup_path}")
        return False
    
    # Current database path
    current_db = 'maintenance_tracker.db'
    
    # Backup current database before restore
    if os.path.exists(current_db):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_restore_backup = f'backups/pre_restore_{timestamp}.db'
        shutil.copy2(current_db, pre_restore_backup)
        print(f"🔄 Current database backed up to: {pre_restore_backup}")
    
    # Restore from backup
    shutil.copy2(backup_path, current_db)
    print(f"✅ Database restored from: {backup_path}")
    return True

def list_backups():
    """List all available database backups"""
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        print("📁 No backups directory found!")
        return []
    
    backups = []
    for file in os.listdir(backup_dir):
        if file.startswith('maintenance_tracker_backup_') and file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            stat = os.stat(file_path)
            backups.append({
                'name': file,
                'path': file_path,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime)
            })
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x['modified'], reverse=True)
    
    print(f"📦 Found {len(backups)} backups:")
    for i, backup in enumerate(backups[:10], 1):  # Show last 10
        size_mb = backup['size'] / (1024 * 1024)
        print(f"  {i}. {backup['name']} ({size_mb:.1f} MB) - {backup['modified'].strftime('%Y-%m-%d %H:%M')}")
    
    return backups

if __name__ == '__main__':
    print("🗄️  Maintenance Tracker Database Backup/Restore Tool")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_manager.py backup    - Create database backup")
        print("  python backup_manager.py restore N  - Restore backup N (from list)")
        print("  python backup_manager.py list      - List all backups")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'backup':
        backup_database()
    elif command == 'list':
        list_backups()
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ Please specify backup number to restore")
            sys.exit(1)
        
        backups = list_backups()
        backup_num = int(sys.argv[2]) - 1
        
        if 0 <= backup_num < len(backups):
            restore_database(backups[backup_num]['path'])
        else:
            print(f"❌ Invalid backup number: {sys.argv[2]}")
    else:
        print(f"❌ Unknown command: {command}")
