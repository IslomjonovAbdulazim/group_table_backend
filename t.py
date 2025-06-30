#!/usr/bin/env python3
"""
Simple script to convert grading_method from enum to string column
"""

import asyncio
import asyncpg
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

try:
    from app.core.config import settings

    DATABASE_URL = settings.database_url
except ImportError:
    DATABASE_URL = os.getenv('DATABASE_URL')


async def convert_to_string():
    """Convert grading_method column from enum to string"""

    print("🔄 Converting grading_method to STRING column")
    print("=" * 50)

    if DATABASE_URL.startswith("postgresql://"):
        db_url = DATABASE_URL.replace("postgresql://", "postgresql://")
    else:
        db_url = DATABASE_URL

    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Connected to database")

        # Step 1: Check current data
        print("\n📋 Step 1: Current data")
        print("-" * 30)

        current_data = await conn.fetch("SELECT id, name, grading_method FROM gt_criteria;")
        print(f"📊 Found {len(current_data)} criteria:")
        for row in current_data:
            print(f"   - ID {row['id']}: {row['name']} -> {row['grading_method']}")

        # Step 2: Convert column to string
        print("\n📋 Step 2: Converting to STRING column")
        print("-" * 30)

        async with conn.transaction():
            # Add new string column
            print("🔄 Adding new string column...")
            await conn.execute("ALTER TABLE gt_criteria ADD COLUMN grading_method_new VARCHAR;")

            # Copy data as strings
            print("🔄 Copying data to new column...")
            await conn.execute("UPDATE gt_criteria SET grading_method_new = grading_method::text;")

            # Drop old column
            print("🔄 Dropping old enum column...")
            await conn.execute("ALTER TABLE gt_criteria DROP COLUMN grading_method;")

            # Rename new column
            print("🔄 Renaming new column...")
            await conn.execute("ALTER TABLE gt_criteria RENAME COLUMN grading_method_new TO grading_method;")

            # Make it NOT NULL
            print("🔄 Setting NOT NULL constraint...")
            await conn.execute("ALTER TABLE gt_criteria ALTER COLUMN grading_method SET NOT NULL;")

        # Step 3: Verify conversion
        print("\n📋 Step 3: Verification")
        print("-" * 30)

        # Check new data
        new_data = await conn.fetch("SELECT id, name, grading_method FROM gt_criteria;")
        print(f"📊 Converted data ({len(new_data)} records):")
        for row in new_data:
            print(f"   - ID {row['id']}: {row['name']} -> {row['grading_method']}")

        # Check column type
        column_info = await conn.fetch("""
                                       SELECT column_name, data_type
                                       FROM information_schema.columns
                                       WHERE table_name = 'gt_criteria'
                                         AND column_name = 'grading_method';
                                       """)

        if column_info:
            print(f"✅ Column type: {column_info[0]['data_type']}")

        # Test inserting string values
        print("\n📋 Step 4: Testing string insertion")
        print("-" * 30)

        await conn.execute("""
                           INSERT INTO gt_criteria (name, max_points, grading_method, module_id)
                           VALUES ('TEST_STRING', 10, 'one_by_one', 1);
                           """)
        print("✅ Successfully inserted 'one_by_one' as string")

        await conn.execute("""
                           INSERT INTO gt_criteria (name, max_points, grading_method, module_id)
                           VALUES ('TEST_STRING2', 20, 'bulk', 1);
                           """)
        print("✅ Successfully inserted 'bulk' as string")

        # Clean up test records
        await conn.execute("DELETE FROM gt_criteria WHERE name LIKE 'TEST_STRING%';")
        print("✅ Cleaned up test records")

        await conn.close()

        print("\n" + "=" * 50)
        print("🎉 Conversion to STRING successful!")
        print("✅ grading_method is now a VARCHAR column")
        print("✅ All existing data preserved")
        print("\n📝 Next steps:")
        print("   1. Update your SQLAlchemy model to use String column")
        print("   2. Update your API functions")
        print("   3. Restart your FastAPI application")
        print("   4. Test creating criteria - should work perfectly!")

        return True

    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🔄 This will convert the grading_method column from enum to string")
    print("📊 Your existing data will be preserved")

    confirm = input("\n✅ Continue with conversion? (y/N): ").strip().lower()

    if confirm not in ['y', 'yes']:
        print("❌ Conversion cancelled")
        sys.exit(0)

    success = asyncio.run(convert_to_string())

    if success:
        print("\n🚀 Ready for string-based approach!")
    else:
        print("\n💥 Conversion failed.")
        sys.exit(1)