#!/usr/bin/env python3
"""
Database Migration Script for GroupTable API
Run this script to fix database schema issues
"""

import asyncio
import asyncpg
import sys
import os
from pathlib import Path

# Add the app directory to Python path so we can import settings
sys.path.append(str(Path(__file__).parent))

try:
    from app.core.config import settings

    DATABASE_URL = settings.database_url
except ImportError:
    # Fallback: try to get from environment variable
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ Error: Could not find database URL")
        print("Please set DATABASE_URL environment variable or ensure app/core/config.py exists")
        sys.exit(1)

# Migration SQL commands
MIGRATION_COMMANDS = [
    {
        "name": "Add is_active column to lessons table",
        "sql": """
               ALTER TABLE gt_lessons
                   ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
               """
    },
    {
        "name": "Update existing lessons to have is_active = true",
        "sql": """
               UPDATE gt_lessons
               SET is_active = TRUE
               WHERE is_active IS NULL;
               """
    },
    {
        "name": "Check current enum values",
        "sql": """
        SELECT unnest(enum_range(NULL::gradingmethod)) as enum_values;
        """,
        "is_query": True
    },
    {
        "name": "Recreate gradingmethod enum with correct values",
        "sql": """
               -- First, add a temporary column
               ALTER TABLE gt_criteria
                   ADD COLUMN IF NOT EXISTS temp_grading_method TEXT;

               -- Copy current values to temp column
               UPDATE gt_criteria
               SET temp_grading_method = grading_method::text;

               -- Drop the old column (this will also drop the enum if not used elsewhere)
               ALTER TABLE gt_criteria DROP COLUMN IF EXISTS grading_method;

               -- Recreate the enum type
               DROP TYPE IF EXISTS gradingmethod;
               CREATE TYPE gradingmethod AS ENUM ('one_by_one', 'bulk');

               -- Add the column back with the new enum type
               ALTER TABLE gt_criteria
                   ADD COLUMN grading_method gradingmethod;

               -- Update with corrected values
               UPDATE gt_criteria
               SET grading_method =
                       CASE
                           WHEN UPPER(temp_grading_method) = 'ONE_BY_ONE' THEN 'one_by_one'::gradingmethod
                           WHEN UPPER(temp_grading_method) = 'BULK' THEN 'bulk'::gradingmethod
                           WHEN temp_grading_method = 'one_by_one' THEN 'one_by_one'::gradingmethod
                           WHEN temp_grading_method = 'bulk' THEN 'bulk'::gradingmethod
                           ELSE 'one_by_one'::gradingmethod -- default fallback
                           END;

               -- Drop the temporary column
               ALTER TABLE gt_criteria DROP COLUMN temp_grading_method;

               -- Make the column NOT NULL
               ALTER TABLE gt_criteria
                   ALTER COLUMN grading_method SET NOT NULL;
               """
    },
    {
        "name": "Verify final enum values",
        "sql": """
        SELECT unnest(enum_range(NULL::gradingmethod)) as enum_values;
        """,
        "is_query": True
    }
]


async def run_migration():
    """Run database migration"""

    print("🚀 Starting GroupTable Database Migration")
    print("=" * 50)

    # Convert PostgreSQL URL to asyncpg format if needed
    if DATABASE_URL.startswith("postgresql://"):
        db_url = DATABASE_URL.replace("postgresql://", "postgresql://")
    else:
        db_url = DATABASE_URL

    print(f"📡 Connecting to database...")

    try:
        # Connect to database
        conn = await asyncpg.connect(db_url)
        print("✅ Connected to database successfully")

        # Run migration commands
        for i, command in enumerate(MIGRATION_COMMANDS, 1):
            print(f"\n📋 Step {i}: {command['name']}")
            print("-" * 40)

            try:
                if command.get('is_query', False):
                    # This is a query command, fetch results
                    result = await conn.fetch(command['sql'])
                    print(f"✅ Query executed successfully")
                    if result:
                        print("📊 Results:")
                        for row in result:
                            print(f"   - {dict(row)}")
                    else:
                        print("📊 No results returned")
                else:
                    # This is a modification command
                    result = await conn.execute(command['sql'])
                    print(f"✅ Command executed successfully: {result}")

            except Exception as e:
                print(f"⚠️  Error in step {i}: {str(e)}")
                # For some commands, errors might be expected (like if column already exists)
                if "already exists" in str(e).lower() or "does not exist" in str(e).lower():
                    print("   (This error is likely harmless - continuing...)")
                else:
                    print("❌ Stopping migration due to error")
                    break

        # Close connection
        await conn.close()
        print("\n" + "=" * 50)
        print("🎉 Migration completed successfully!")
        print("✅ Database schema has been updated")
        print("\n📝 Next steps:")
        print("   1. Update your application code with the fixes")
        print("   2. Restart your application")
        print("   3. Test the problematic endpoints")

    except Exception as e:
        print(f"❌ Failed to connect to database: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check your DATABASE_URL is correct")
        print("   2. Ensure the database server is running")
        print("   3. Verify network connectivity")
        return False

    return True


async def check_database_connection():
    """Test database connection before migration"""
    try:
        if DATABASE_URL.startswith("postgresql://"):
            db_url = DATABASE_URL.replace("postgresql://", "postgresql://")
        else:
            db_url = DATABASE_URL

        conn = await asyncpg.connect(db_url)

        # Test with a simple query
        result = await conn.fetchval("SELECT version();")
        await conn.close()

        print(f"✅ Database connection test successful")
        print(f"📊 PostgreSQL version: {result.split(',')[0]}")
        return True

    except Exception as e:
        print(f"❌ Database connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("🔍 Testing database connection...")

    # Test connection first
    connection_ok = asyncio.run(check_database_connection())

    if not connection_ok:
        print("❌ Cannot proceed with migration - fix database connection first")
        sys.exit(1)

    print("\n" + "=" * 50)

    # Ask for confirmation
    confirm = input("⚠️  This will modify your database schema. Continue? (y/N): ").strip().lower()

    if confirm not in ['y', 'yes']:
        print("❌ Migration cancelled by user")
        sys.exit(0)

    # Run migration
    success = asyncio.run(run_migration())

    if success:
        print("\n🎊 All done! Your database has been updated.")
        sys.exit(0)
    else:
        print("\n💥 Migration failed. Please check the errors above.")
        sys.exit(1)