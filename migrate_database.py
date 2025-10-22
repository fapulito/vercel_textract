#!/usr/bin/env python3
"""
Database migration script to add new LLM-related columns and tables
Run this to update your existing database schema
"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

print("🔄 Starting database migration...")
print(f"Database: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'local'}")

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("\n1️⃣ Checking existing schema...")
    
    # Check if llm_analyses_this_month column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='llm_analyses_this_month'
    """)
    
    if cur.fetchone() is None:
        print("   Adding llm_analyses_this_month column...")
        cur.execute("""
            ALTER TABLE users 
            ADD COLUMN llm_analyses_this_month INTEGER NOT NULL DEFAULT 0
        """)
        print("   ✅ Added llm_analyses_this_month")
    else:
        print("   ✅ llm_analyses_this_month already exists")
    
    # Check if api_key column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='api_key'
    """)
    
    if cur.fetchone() is None:
        print("   Adding api_key column...")
        cur.execute("""
            ALTER TABLE users 
            ADD COLUMN api_key VARCHAR(64) UNIQUE
        """)
        print("   ✅ Added api_key")
    else:
        print("   ✅ api_key already exists")
    
    # Check if api_key_created column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='api_key_created'
    """)
    
    if cur.fetchone() is None:
        print("   Adding api_key_created column...")
        cur.execute("""
            ALTER TABLE users 
            ADD COLUMN api_key_created TIMESTAMP
        """)
        print("   ✅ Added api_key_created")
    else:
        print("   ✅ api_key_created already exists")
    
    # Check if document_history table exists
    print("\n2️⃣ Checking document_history table...")
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'document_history'
        )
    """)
    
    if not cur.fetchone()[0]:
        print("   Creating document_history table...")
        cur.execute("""
            CREATE TABLE document_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                filename VARCHAR(255) NOT NULL,
                upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                analysis_type VARCHAR(50),
                textract_job_id VARCHAR(100) NOT NULL,
                csv_filename VARCHAR(255) NOT NULL,
                json_filename VARCHAR(255),
                file_size INTEGER NOT NULL,
                page_count INTEGER,
                processing_cost FLOAT
            )
        """)
        print("   ✅ Created document_history table")
    else:
        print("   ✅ document_history table already exists")
    
    # Commit all changes
    conn.commit()
    
    print("\n✅ Migration completed successfully!")
    print("\nYou can now run the Flask app:")
    print("  flask --app api.index:create_app run --debug")
    
except Exception as e:
    print(f"\n❌ Migration failed: {str(e)}")
    if conn:
        conn.rollback()
    raise
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
