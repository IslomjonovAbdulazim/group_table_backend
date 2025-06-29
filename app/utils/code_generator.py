# Replace your app/utils/code_generator.py with this simple version:

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models.group import Group


def generate_incremental_code(group_id: int) -> str:
    """
    Generate memorable incremental group codes:
    1-9: A1, B2, C3, D4, E5, F6, G7, H8, I9
    10-35: A10, A11, A12, ..., A35
    36-61: B10, B11, B12, ..., B35  
    62-87: C10, C11, C12, ..., C35
    And so on...

    For 100+: A100, A101, etc.
    For 1000+: AA01, AA02, etc.
    """

    if group_id <= 9:
        # Single letter + single digit: A1, B2, C3, etc.
        letter = chr(ord('A') + (group_id - 1))
        return f"{letter}{group_id}"

    elif group_id <= 35:
        # A + two digits: A10, A11, A12, ..., A35
        number = group_id
        return f"A{number}"

    elif group_id <= 999:
        # B10, B11, ..., B35, C10, C11, ..., C35, etc.
        # Then A100, A101, etc.
        if group_id <= 35 + (25 * 26):  # Up to Z35
            adjusted_id = group_id - 36
            letter = chr(ord('B') + (adjusted_id // 26))
            number = (adjusted_id % 26) + 10
            return f"{letter}{number}"
        else:
            # A100, A101, A102, etc.
            letter = chr(ord('A') + ((group_id - 100) // 900) % 26)
            number = group_id
            return f"{letter}{number}"

    else:
        # For 1000+: AA01, AA02, AB01, etc.
        first_letter = chr(ord('A') + ((group_id - 1000) // (26 * 99)) % 26)
        second_letter = chr(ord('A') + ((group_id - 1000) // 99) % 26)
        number = ((group_id - 1000) % 99) + 1
        return f"{first_letter}{second_letter}{number:02d}"


async def generate_group_code(db: AsyncSession) -> str:
    """
    Generate the next incremental group code based on total groups created
    """

    # Get total number of groups ever created (including deleted ones)
    # This ensures codes are always incremental and never reused
    total_groups_result = await db.execute(select(func.count(Group.id)))
    total_groups = total_groups_result.scalar()

    # Next group will be total + 1
    next_group_id = total_groups + 1

    max_attempts = 10

    for attempt in range(max_attempts):
        # Generate code for this group ID
        code = generate_incremental_code(next_group_id + attempt)

        # Check if code already exists (shouldn't happen with incremental, but safety check)
        existing_result = await db.execute(select(Group).filter(Group.code == code))
        existing = existing_result.scalar_one_or_none()

        if not existing:
            return code

    # Fallback (should never happen with incremental approach)
    return generate_incremental_code(next_group_id + max_attempts)