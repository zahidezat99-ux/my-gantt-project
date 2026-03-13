def find_mentions(text: str) -> List[str]:
    """Return all @username strings (without the @) found in a piece of text."""
    return [m[1:] for m in re.findall(r'@([^\s"\'`<>]+)', text)]


def replace_usernames(text: str, valid_users: List[str]) -> Tuple[str, List[str]]:
    """Replace invalid usernames with closest match if similarity >= threshold."""
    unresolved = []
    mentions = find_mentions(text)
    for username in mentions:
        if username in valid_users:
            continue
        match = get_close_matches(username, valid_users, n=1, cutoff=SIMILARITY_THRESHOLD)
        if match:
            text = text.replace(f"@{username}", f"@{match[0]}")
            print(f"🔧 Replaced @{username} → @{match[0]}")
        else:
            unresolved.append(username)
            print(f"❌ Unresolved @{username}")
    return text, unresolved


def process_svg(file_path: Path, valid_users: List[str]) -> List[str]:
    """Process a single SVG file: backup, fix usernames, and save."""
    unresolved_total = []

    if not file_path.exists():
        print(f"⚠️ File not found: {file_path}")
        return unresolved_total

    backup = timestamped_backup(file_path)

    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}

    # Fix all text elements
    for text_elem in root.findall(".//svg:text", ns):
        orig_text = text_elem.text or ""
        new_text, unresolved = replace_usernames(orig_text, valid_users)
        text_elem.text = new_text
        unresolved_total.extend(unresolved)

    # Optional: fix attributes containing usernames
    for elem in root.iter():
        for attr, val in elem.attrib.items():
            new_val, unresolved = replace_usernames(val, valid_users)
            elem.set(attr, new_val)
            unresolved_total.extend(unresolved)

    tree.write(file_path)
    print(f"✅ Processed {file_path}")
    return unresolved_total


def main():
    all_files = [BASE_SVG] + [
        BASE_SVG.with_name(f"{BASE_SVG.stem}{suffix}{BASE_SVG.suffix}")
        for suffix in BUFFER_SUFFIXES
    ]

    unresolved_all = []
    for svg_file in all_files:
        unresolved = process_svg(svg_file, NOTION_USERS)
        unresolved_all.extend(unresolved)

    if unresolved_all:
        print("❌ Some usernames remain unresolved:", set(unresolved_all))
        sys.exit(1)
    else:
        print("✅ All usernames resolved successfully.")


if __name__ == "__main__":
    main()
