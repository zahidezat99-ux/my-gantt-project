#!/usr/bin/env python3
"""
fix_svg_usernames_bulk_buffers.py

Bulk‑clean a primary SVG and all its buffer‑variant copies (yellow, red).

- Creates a timestamped backup for each file.
- Detects @username mentions in text nodes and every attribute.
- Replaces invalid usernames automatically with the closest matching
  Notion username (similarity >= SIMILARITY_THRESHOLD).
- Leaves names with no close match untouched and logs them.
- Writes the corrected files back in place.
"""

import re
import shutil
import sys
import time
from difflib import get_close_matches
from pathlib import Path
from typing import List, Tuple

import xml.etree.ElementTree as ET

# --------------------------------------------------------------
# === CONFIGURATION =================================================
# --------------------------------------------------------------

# Base SVG (the one you embed in Notion)
BASE_SVG = Path("preseed-gantt.svg")

# The buffer‑variant suffixes you use – adapt if you have other colours.
BUFFER_SUFFIXES = ["-yellow", "-red"]   # will become preseed-gantt-yellow.svg, etc.

# Your exact Notion usernames (without the leading @)
NOTION_USERS = [
    "john-doe",
    "fatima-khan",
    "ahmad-azizi",
    "sara-noor",
    "bilal-hosseini",
]

# Minimum similarity for an automatic suggestion (0‑1).
SIMILARITY_THRESHOLD = 0.6

# --------------------------------------------------------------
# === HELPERS ======================================================
# --------------------------------------------------------------

def timestamped_backup(file_path: Path) -> Path:
    """Create a timestamped backup of `file_path`."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = file_path.with_name(f"{file_path.stem}.bak.{ts}{file_path.suffix}")
    shutil.copy2(file_path, backup_path)
    print(f"💾 Backup → {backup_path}")
    return backup_path


def find_mentions(text: str) -> List[str]:
    """Return every @username (without @) inside the provided text."""
    return re.findall(r"@([A-Za-z0-9\-_]+)", text)


def suggest_username(invalid: str, valid: List[str]) -> Tuple[bool, str | None]:
    """Return (has_match, best_match) for an invalid username."""
    matches = get_close_matches(invalid, valid, n=1, cutoff=SIMILARITY_THRESHOLD)
    return (bool(matches), matches[0] if matches else None)


def replace_in_element(elem: ET.Element, old_user: str, new_user: str) -> bool:
    """
    Replace all occurrences of @old_user with @new_user in the element's
    text and in any attribute that contains the old name.
    Returns True if any substitution occurred.
    """
    changed = False

    # Text node
    if elem.text:
        new_text, count = re.subn(rf"@{re.escape(old_user)}", f"@{new_user}", elem.text)
        if count:
            elem.text = new_text
            changed = True

    # All attributes (id, data‑*, etc.)
    for attr, val in list(elem.attrib.items()):
        if old_user in val:
            elem.attrib[attr] = val.replace(old_user, new_user)
            changed = True

    return changed


def process_svg(file_path: Path) -> Tuple[int, set]:
    """
    Clean a single SVG file.
    Returns (num_replacements, set_of_unresolved_usernames).
    """
    # 1️⃣ Backup
    timestamped_backup(file_path)

    # 2️⃣ Parse SVG (namespace‑aware)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Gather all invalid usernames and their suggested replacements
    to_replace: dict[str, str] = {}
    unresolved: set[str] = set()

    for elem in root.iter():
        # Combine text + attribute values for scanning
        combined = (elem.text or "") + " " + " ".join(elem.attrib.values())
        for user in find_mentions(combined):
            if user not in NOTION_USERS:
                has_match, suggestion = suggest_username(user, NOTION_USERS)
                if has_match:
                    to_replace[user] = suggestion
                else:
                    unresolved.add(user)

    # 3️⃣ Apply the replacements everywhere
    replacements_done = 0
    for old_user, new_user in to_replace.items():
        for elem in root.iter():
            if replace_in_element(elem, old_user, new_user):
                replacements_done += 1
        print(f"✅ Replaced @{old_user} → @{new_user}")

    # 4️⃣ Write the updated SVG back
    tree.write(file_path, xml_declaration=True, encoding="utf-8")
    print(f"🖊️ Updated SVG saved → {file_path}")

    return replacements_done, unresolved


# --------------------------------------------------------------
# === MAIN =========================================================
# --------------------------------------------------------------

def main() -> None:
    # Build the list of SVGs to process: base + each buffer variant
    svg_files: List[Path] = [BASE_SVG]
    for suffix in BUFFER_SUFFIXES:
        variant = BASE_SVG.with_name(f"{BASE_SVG.stem}{suffix}{BASE_SVG.suffix}")
        if variant.is_file():
            svg_files.append(variant)
        else:
            print(f"⚠️ Buffer file not found (skipping): {variant}")

    total_replacements = 0
    total_unresolved: set[str] = set()

    for svg_path in svg_files:
        print("\n=== Processing:", svg_path.name, "===")
        repl, unresolved = process_svg(svg_path)
        total_replacements += repl
        total_unresolved.update(unresolved)

    # Summary
    print("\n🚦 Summary")
    print(f"  • SVG files processed : {len(svg_files)}")
    print(f"  • Total replacements : {total_replacements}")
    if total_unresolved:
        print("  • Unresolved usernames (left unchanged):")
        for u in sorted(total_unresolved):
            print(f"      – @{u}")
    else:
        print("  • All usernames matched a Notion user!")

    print("\n✅ Done. Backups are timestamped and kept beside each SVG.")
    print("   If you need to revert, simply copy the .bak file back over the .svg.")


if __name__ == "__main__":
    main()
