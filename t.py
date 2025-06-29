#!/usr/bin/env python3
"""
Database Enum Fix Script for GroupTable API
This script fixes the gradingmethod enum values in the database
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


async def fix_database_enum():
    """Fix the gradingmethod enum in the database"""

    print("🔧 Starting Database Enum Fix")
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

        # Step 1: Check current enum values
        print("\n📋 Step 1: Checking current enum values")
        print("-" * 40)
        try:
            result = await conn.fetch("SELECT unnest(enum_range(NULL::gradingmethod)) as enum_values;")
            print("📊 Current enum values:")
            for row in result:
                print(f"   - {row['enum_values']}")
        except Exception as e:
            print(f"⚠️  Could not check enum values: {e}")

        # Step 2: Check if any criteria exist
        print("\n📋 Step 2: Checking existing criteria")
        print("-" * 40)
        criteria_result = await conn.fetch("SELECT id, grading_method FROM gt_criteria;")
        print(f"📊 Found {len(criteria_result)} existing criteria:")
        for row in criteria_result:
            print(f"   - ID {row['id']}: {row['grading_method']}")

        # Step 3: Backup and recreate the enum
        print("\n📋 Step 3: Fixing the enum")
        print("-" * 40)

        # Create a transaction to ensure atomicity
        async with conn.transaction():

            # If there are existing criteria, we need to handle them carefully
            if criteria_result:
                print("🔄 Adding temporary column for data migration...")
                await conn.execute("ALTER TABLE gt_criteria ADD COLUMN temp_grading_method TEXT;")

                print("🔄 Copying current values to temporary column...")
                await conn.execute("UPDATE gt_criteria SET temp_grading_method = grading_method::text;")

                print("🔄 Dropping the grading_method column...")
                await conn.execute("ALTER TABLE gt_criteria DROP COLUMN grading_method;")

            print("🔄 Dropping old enum type...")
            await conn.execute("DROP TYPE IF EXISTS gradingmethod CASCADE;")

            print("🔄 Creating new enum type with correct values...")
            await conn.execute("CREATE TYPE gradingmethod AS ENUM ('one_by_one', 'bulk');")

            print("🔄 Adding grading_method column back...")
            await conn.execute("ALTER TABLE gt_criteria ADD COLUMN grading_method gradingmethod;")

            if criteria_result:
                print("🔄 Converting old values to new format...")
                await conn.execute("""
                                   UPDATE gt_criteria
                                   SET grading_method =
                                           CASE
                                               WHEN UPPER(temp_grading_method) = 'ONE_BY_ONE' THEN 'one_by_one'::gradingmethod
                                               WHEN UPPER(temp_grading_method) = 'BULK' THEN 'bulk'::gradingmethod
                                               WHEN temp_grading_method = 'one_by_one' THEN 'one_by_one'::gradingmethod
                                               WHEN temp_grading_method = 'bulk' THEN 'bulk'::gradingmethod
                                               ELSE 'one_by_one'::gradingmethod -- default fallback
                                               END;
                                   """)

                print("🔄 Dropping temporary column...")
                await conn.execute("ALTER TABLE gt_criteria DROP COLUMN temp_grading_method;")

            print("🔄 Making grading_method column NOT NULL...")
            await conn.execute("ALTER TABLE gt_criteria ALTER COLUMN grading_method SET NOT NULL;")

        # Step 4: Verify the fix
        print("\n📋 Step 4: Verifying the fix")
        print("-" * 40)

        # Check new enum values
        result = await conn.fetch("SELECT unnest(enum_range(NULL::gradingmethod)) as enum_values;")
        print("📊 New enum values:")
        for row in result:
            print(f"   - {row['enum_values']}")

        # Check updated criteria
        criteria_result = await conn.fetch("SELECT id, grading_method FROM gt_criteria;")
        print(f"📊 Updated criteria ({len(criteria_result)} total):")
        for row in criteria_result:
            print(f"   - ID {row['id']}: {row['grading_method']}")

        # Step 5: Test the enum
        print("\n📋 Step 5: Testing enum insertion")
        print("-" * 40)
        try:
            # Test if we can insert the enum values
            test_result = await conn.fetchval("SELECT 'one_by_one'::gradingmethod;")
            print(f"✅ Test 'one_by_one': {test_result}")

            test_result = await conn.fetchval("SELECT 'bulk'::gradingmethod;")
            print(f"✅ Test 'bulk': {test_result}")

        except Exception as e:
            print(f"❌ Enum test failed: {e}")
            raise

        # Close connection
        await conn.close()
        print("\n" + "=" * 50)
        print("🎉 Database enum fix completed successfully!")
        print("✅ The gradingmethod enum now uses lowercase values")
        print("\n📝 Next steps:")
        print("   1. Restart your FastAPI application")
        print("   2. Test creating criteria")
        print("   3. Should work now! 🚀")

    except Exception as e:
        print(f"❌ Failed to fix database enum: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check your DATABASE_URL is correct")
        print("   2. Ensure the database server is running")
        print("   3. Verify you have permission to modify schema")
        return False

    return True


async def check_database_connection():
    """Test database connection before making changes"""
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
        print("❌ Cannot proceed with enum fix - fix database connection first")
        sys.exit(1)

    print("\n" + "=" * 50)

    # Ask for confirmation
    confirm = input("⚠️  This will modify your database enum. Continue? (y/N): ").strip().lower()

    if confirm not in ['y', 'yes']:
        print("❌ Enum fix cancelled by user")
        sys.exit(0)

    # Run the fix
    success = asyncio.run(fix_database_enum())

    if success:
        print("\n🎊 All done! Your database enum has been fixed.")
        sys.exit(0)
    else:
        print("\n💥 Enum fix failed. Please check the errors above.")
        sys.exit(1)