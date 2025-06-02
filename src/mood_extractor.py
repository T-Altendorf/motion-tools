import re
import pandas as pd
from datetime import datetime
import gkeepapi
import os


def get_next_nonempty_line(lines, start_index):
    """Return (index, line) for the next non-empty line starting at start_index."""
    for idx in range(start_index, len(lines)):
        line = lines[idx].strip()
        if line:
            return idx, line
    return None, None


def extract_mood_logs(text):
    """
    Extracts mood log entries from text.

    A mood log block consists of three consecutive non-empty lines:
      1. A date line (e.g. "19.02." or "7.03.2025" or "7.03")
      2. A time line (e.g. "23:33" or "3:45")
      3. A mood line starting with D and M values (e.g. "D2.8 M0" or "d1 m0.5 Extra comment")

    If the date line contains a year (e.g. "07.03.2025"), that year is used.
    Otherwise, the current year (two-digit) is assumed.

    Returns a tuple (mood_logs, non_mood_text) where:
      - mood_logs is a list of dict records.
      - non_mood_text is a string of the remaining lines.
    """
    lines = text.splitlines()
    mood_logs = []
    non_mood_lines = []

    # Regex patterns:
    # Date: one or two digits, dot, one or two digits, optional trailing dot, optional dot and optional year (2 to 4 digits)
    date_pattern = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?(?:\.?(\d{2,4}))?\s*$")
    # Time: e.g., "12:34" or "3:45" (optionally with seconds), with optional ? at beginning or end
    time_pattern = re.compile(r"^\s*(\?*)([\d]{1,2}:[\d]{2}(?::[\d]{2})?)(\?*)\s*$")
    # Mood: starting with D then a number, whitespace, M then a number, then optional comment.
    mood_pattern = re.compile(r"(?i)^\s*D\s*([\d\.]+)\s*M\s*([\d\.]+)(.*)$")

    i = 0
    while i < len(lines):
        current_line = lines[i].strip()
        date_match = date_pattern.match(current_line)
        if not date_match:
            non_mood_lines.append(lines[i])
            i += 1
            continue

        # Process date line
        day, month, year_given = date_match.groups()
        if year_given:
            # Use the provided year; if four digits, take the last two digits.
            year = year_given[-2:]
        else:
            year = f"{datetime.now().year % 100:02d}"
        date_formatted = f"{int(day):02d}.{int(month):02d}.{year}"

        # Get time line
        time_idx, time_line = get_next_nonempty_line(lines, i + 1)
        if not time_line:
            non_mood_lines.append(lines[i])
            i += 1
            continue

        # Modified time pattern to separate time and question marks
        time_match = time_pattern.match(time_line)
        if not time_match:
            non_mood_lines.append(lines[i])
            i += 1
            continue

        prefix_q, time_val, suffix_q = time_match.groups()
        med_intake = time_val
        uncertainty = (
            prefix_q + suffix_q
        )  # Combine question marks from beginning and end

        # Get mood line
        mood_idx, mood_line = get_next_nonempty_line(lines, time_idx + 1)
        if not mood_line:
            non_mood_lines.append(lines[i])
            i += 1
            continue
        mood_match = mood_pattern.match(mood_line)
        if not mood_match:
            non_mood_lines.append(lines[i])
            i += 1
            continue

        dep_val, man_val, extra = mood_match.groups()
        comment = extra.strip() if extra.strip() else ""

        # Build record with the desired format.
        record = {
            "Date": date_formatted,
            "Med intake": med_intake,
            "Uncertainty": uncertainty,
            "QTY THC": "",
            "Dep": float(dep_val),
            "Dep of": 8,
            "Man": float(man_val),
            "Man of": 8,
            "Direction": "",
            "Comment": comment,
        }
        mood_logs.append(record)
        # Skip processed lines (date, time, mood)
        i = mood_idx + 1

    # filter to not have more than one empty line between non-empty lines
    non_mood_lines = [
        line
        for idx, line in enumerate(non_mood_lines)
        if not (idx > 0 and not line and not non_mood_lines[idx - 1])
    ]

    return mood_logs, "\n".join(non_mood_lines)


def save_to_excel_and_return(input_text):
    # Extract mood logs and remaining text
    mood_logs, remaining_text = extract_mood_logs(input_text)

    # Create DataFrame with the desired columns
    columns = [
        "Date",
        "Med intake",
        "Uncertainty",
        "QTY THC",
        "Dep",
        "Dep of",
        "Man",
        "Man of",
        "Direction",
        "Comment",
    ]
    df = pd.DataFrame(mood_logs, columns=columns)

    # Save to Excel
    output_file = "extracted_mood_log.xlsx"
    df.to_excel(output_file, index=False)
    print(f"Mood logs extracted and saved to '{output_file}'.")
    return remaining_text


# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Read master token from file in parent directory
token_path = os.path.join(script_dir, "..", "google_master_token.txt")
with open(token_path, "r") as token_file:
    master_token = token_file.read().strip()

keep = gkeepapi.Keep()
email = os.environ.get("GOOGLE_KEEP_EMAIL", "tim.altendorf@gmail.com")
keep.authenticate(email, master_token)

notes = keep.find(func=lambda x: "Motion" in x.title)
first_note = next(notes)

# Parse the note content
note_content = first_note.text
remaining_text = save_to_excel_and_return(note_content)
first_note.text = remaining_text
keep.sync()
