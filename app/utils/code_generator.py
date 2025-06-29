import secrets
import string
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


class GroupCodeGenerator:
    """Smart group code generator with memorable patterns"""

    @staticmethod
    def base36_encode(number: int) -> str:
        """Convert number to base36 (0-9, A-Z)"""
        if number == 0:
            return '0'

        alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = ''
        while number:
            number, remainder = divmod(number, 36)
            result = alphabet[remainder] + result
        return result

    @staticmethod
    def generate_incremental_code(group_id: int) -> str:
        """Generate memorable code based on group ID with incremental pattern"""

        if group_id <= 9:
            # A1, B2, C3, etc. (single letter + digit)
            letter = chr(ord('A') + (group_id - 1) % 26)
            return f"{letter}{group_id}"

        elif group_id <= 99:
            # A10, A11, ..., A99, B10, B11, etc. (letter + 2 digits)
            letter = chr(ord('A') + ((group_id - 10) // 90) % 26)
            number = ((group_id - 10) % 90) + 10
            return f"{letter}{number}"

        elif group_id <= 999:
            # A100, A101, ..., A999, B100, etc. (letter + 3 digits)
            letter = chr(ord('A') + ((group_id - 100) // 900) % 26)
            number = ((group_id - 100) % 900) + 100
            return f"{letter}{number}"

        elif group_id <= 9999:
            # AA1, AA2, ..., AA99, AB1, etc. (2 letters + 2 digits)
            first_letter = chr(ord('A') + ((group_id - 1000) // (26 * 99)) % 26)
            second_letter = chr(ord('A') + ((group_id - 1000) // 99) % 26)
            number = ((group_id - 1000) % 99) + 1
            return f"{first_letter}{second_letter}{number:02d}"

        else:
            # For very large IDs, use base36 encoding
            return GroupCodeGenerator.base36_encode(group_id)

    @staticmethod
    def generate_teacher_based_code(teacher_id: int, group_sequence: int) -> str:
        """Generate code based on teacher ID + group sequence"""

        # Get teacher's initials-like code (base36 of teacher_id)
        teacher_code = GroupCodeGenerator.base36_encode(teacher_id)

        # Ensure teacher code is 1-2 characters
        if len(teacher_code) > 2:
            teacher_code = teacher_code[-2:]  # Take last 2 chars

        # Add group sequence
        if group_sequence <= 9:
            return f"{teacher_code}{group_sequence}"
        else:
            return f"{teacher_code}{group_sequence:02d}"

    @staticmethod
    def generate_human_friendly_code(group_id: int) -> str:
        """Generate very human-friendly codes"""

        # Word-like patterns that are easy to remember and type
        vowels = 'AEIOU'
        consonants = 'BCDFGHJKLMNPQRSTVWXYZ'

        if group_id <= 500:
            # Pattern: CONSONANT + VOWEL + NUMBER (e.g., BA7, FE12, MI345)
            consonant = consonants[(group_id - 1) % len(consonants)]
            vowel = vowels[((group_id - 1) // len(consonants)) % len(vowels)]
            number = group_id

            if number <= 9:
                return f"{consonant}{vowel}{number}"
            elif number <= 99:
                return f"{consonant}{vowel}{number:02d}"
            else:
                return f"{consonant}{vowel}{number:03d}"
        else:
            # For larger numbers, use double consonant-vowel pattern
            # Pattern: CV + CV + NUMBER (e.g., BAFE7, MIKU12)
            c1 = consonants[(group_id - 1) % len(consonants)]
            v1 = vowels[((group_id - 1) // len(consonants)) % len(vowels)]
            c2 = consonants[((group_id - 1) // (len(consonants) * len(vowels))) % len(consonants)]
            v2 = vowels[((group_id - 1) // (len(consonants) * len(vowels) * len(consonants))) % len(vowels)]

            number = ((group_id - 501) % 99) + 1
            return f"{c1}{v1}{c2}{v2}{number:02d}"


async def generate_unique_group_code(db: AsyncSession, teacher_id: int, strategy: str = "incremental") -> str:
    """
    Generate a unique group code using specified strategy

    Strategies:
    - "incremental": Based on total group count (A1, A2, B10, etc.)
    - "teacher_based": Based on teacher ID + their group sequence
    - "human_friendly": Easy to remember word-like patterns
    - "random": Original random 8-character code
    """

    max_attempts = 50

    for attempt in range(max_attempts):

        if strategy == "incremental":
            # Get total group count to determine next ID
            total_groups = await db.execute(select(func.count(Group.id)))
            next_id = total_groups.scalar() + 1
            code = GroupCodeGenerator.generate_incremental_code(next_id)

        elif strategy == "teacher_based":
            # Get this teacher's group count
            teacher_groups = await db.execute(
                select(func.count(Group.id)).filter(Group.teacher_id == teacher_id)
            )
            group_sequence = teacher_groups.scalar() + 1
            code = GroupCodeGenerator.generate_teacher_based_code(teacher_id, group_sequence)

        elif strategy == "human_friendly":
            # Get total group count for human-friendly pattern
            total_groups = await db.execute(select(func.count(Group.id)))
            next_id = total_groups.scalar() + 1
            code = GroupCodeGenerator.generate_human_friendly_code(next_id)

        else:  # "random" - original approach
            alphabet = string.ascii_uppercase + string.digits
            code = ''.join(secrets.choice(alphabet) for _ in range(8))

        # Check if code already exists
        existing = await db.execute(select(Group).filter(Group.code == code))
        if not existing.scalar_one_or_none():
            return code

        # If collision (rare), try again
        continue

    # Fallback to random if all attempts failed
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


# Examples of what each strategy produces:
"""
INCREMENTAL STRATEGY:
Group 1: A1
Group 2: B2  
Group 10: A10
Group 26: Z26
Group 27: A27
Group 100: A100
Group 1000: AA01
Group 1001: AA02

TEACHER_BASED STRATEGY:
Teacher ID 5, Group 1: 51
Teacher ID 5, Group 2: 52
Teacher ID 25, Group 1: P1 (25 in base36 = P)
Teacher ID 25, Group 3: P3

HUMAN_FRIENDLY STRATEGY:
Group 1: BA1
Group 2: CA2
Group 26: BA26
Group 100: BA100
Group 501: BAFE01
Group 502: CAFE02
"""