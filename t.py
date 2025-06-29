import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from passlib.context import CryptContext

# Your database URL
DATABASE_URL = "postgresql+asyncpg://gen_user:(8Ah)S%24aY)lF6t@3d7780415a2721a636acfe11.twc1.net:5432/default_db"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_db():
    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as conn:
        print("Dropping tables...")

        drop_commands = [
            "DROP TABLE IF EXISTS gt_grades CASCADE",
            "DROP TABLE IF EXISTS gt_lessons CASCADE",
            "DROP TABLE IF EXISTS gt_criteria CASCADE",
            "DROP TABLE IF EXISTS gt_modules CASCADE",
            "DROP TABLE IF EXISTS gt_students CASCADE",
            "DROP TABLE IF EXISTS gt_groups CASCADE",
            "DROP TABLE IF EXISTS gt_teachers CASCADE",
            "DROP TABLE IF EXISTS gt_admins CASCADE",
            "DROP TYPE IF EXISTS gradingmethod CASCADE"
        ]

        for cmd in drop_commands:
            await conn.execute(text(cmd))

        print("Creating tables...")

        create_commands = [
            "CREATE TYPE gradingmethod AS ENUM ('one_by_one', 'bulk')",

            """CREATE TABLE gt_admins
               (
                   id              SERIAL PRIMARY KEY,
                   name            VARCHAR        NOT NULL,
                   email           VARCHAR UNIQUE NOT NULL,
                   hashed_password VARCHAR        NOT NULL,
                   created_at      TIMESTAMPTZ DEFAULT NOW()
               )""",

            """CREATE TABLE gt_teachers
               (
                   id              SERIAL PRIMARY KEY,
                   name            VARCHAR        NOT NULL,
                   email           VARCHAR UNIQUE NOT NULL,
                   hashed_password VARCHAR        NOT NULL,
                   created_at      TIMESTAMPTZ DEFAULT NOW(),
                   admin_id        INTEGER        NOT NULL REFERENCES gt_admins (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_groups
               (
                   id         SERIAL PRIMARY KEY,
                   name       VARCHAR        NOT NULL,
                   code       VARCHAR UNIQUE NOT NULL,
                   is_active  BOOLEAN     DEFAULT TRUE,
                   created_at TIMESTAMPTZ DEFAULT NOW(),
                   teacher_id INTEGER        NOT NULL REFERENCES gt_teachers (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_students
               (
                   id        SERIAL PRIMARY KEY,
                   full_name VARCHAR NOT NULL,
                   added_at  TIMESTAMPTZ DEFAULT NOW(),
                   group_id  INTEGER NOT NULL REFERENCES gt_groups (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_modules
               (
                   id          SERIAL PRIMARY KEY,
                   name        VARCHAR NOT NULL,
                   is_active   BOOLEAN     DEFAULT TRUE,
                   is_finished BOOLEAN     DEFAULT FALSE,
                   created_at  TIMESTAMPTZ DEFAULT NOW(),
                   group_id    INTEGER NOT NULL REFERENCES gt_groups (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_lessons
               (
                   id            SERIAL PRIMARY KEY,
                   name          VARCHAR NOT NULL,
                   lesson_number INTEGER NOT NULL,
                   is_active     BOOLEAN     DEFAULT TRUE,
                   created_at    TIMESTAMPTZ DEFAULT NOW(),
                   module_id     INTEGER NOT NULL REFERENCES gt_modules (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_criteria
               (
                   id             SERIAL PRIMARY KEY,
                   name           VARCHAR       NOT NULL,
                   max_points     INTEGER       NOT NULL,
                   grading_method gradingmethod NOT NULL,
                   created_at     TIMESTAMPTZ DEFAULT NOW(),
                   module_id      INTEGER       NOT NULL REFERENCES gt_modules (id) ON DELETE CASCADE
               )""",

            """CREATE TABLE gt_grades
               (
                   id            SERIAL PRIMARY KEY,
                   points_earned INTEGER NOT NULL,
                   created_at    TIMESTAMPTZ DEFAULT NOW(),
                   student_id    INTEGER NOT NULL REFERENCES gt_students (id) ON DELETE CASCADE,
                   criteria_id   INTEGER NOT NULL REFERENCES gt_criteria (id) ON DELETE CASCADE,
                   lesson_id     INTEGER NOT NULL REFERENCES gt_lessons (id) ON DELETE CASCADE
               )"""
        ]

        for cmd in create_commands:
            await conn.execute(text(cmd))

        print("Creating admin user...")
        hashed_password = pwd_context.hash("aishabintali")
        await conn.execute(text(
            "INSERT INTO gt_admins (name, email, hashed_password) VALUES (:name, :email, :password)"
        ), {"name": "Azim", "email": "azim@gmail.com", "password": hashed_password})

    await engine.dispose()
    print("Done! Admin: azim@gmail.com / aishabintali")


if __name__ == "__main__":
    asyncio.run(reset_db())