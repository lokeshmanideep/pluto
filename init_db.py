#!/usr/bin/env python3
"""
Database initialization script for the Legal Document Processing API.
This script creates the database tables and can be used to set up the database.
"""

import sys
import os

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base

def init_database():
    """Initialize the database by creating all tables."""
    print("Creating database tables...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        
        # Print created tables
        print("\nCreated tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
            
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False
    
    return True

def drop_database():
    """Drop all database tables."""
    print("Dropping database tables...")
    
    try:
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("✅ Database tables dropped successfully!")
        
    except Exception as e:
        print(f"❌ Error dropping database tables: {e}")
        return False
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database management script")
    parser.add_argument(
        "action", 
        choices=["init", "drop", "reset"], 
        help="Action to perform (init: create tables, drop: drop tables, reset: drop and recreate)"
    )
    
    args = parser.parse_args()
    
    if args.action == "init":
        init_database()
    elif args.action == "drop":
        drop_database()
    elif args.action == "reset":
        print("Resetting database...")
        if drop_database():
            init_database()
    
    print("Done!")