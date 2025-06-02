import sys
import gkeepapi
from datetime import datetime, date
from collections import defaultdict
import os


def parse_german_date(date_str):
    """
    Parse a German-style date string that might be:
      - DD.MM
      - DD.MM.YY
      - DD.MM.YYYY
    If the year is missing, use the current year.
    If it's only 2 digits (YY), interpret as 20YY.
    Returns a datetime.date object.
    """
    # Remove any trailing period(s) like "03.03."
    date_str = date_str.rstrip(".")  # strip trailing dots

    parts = date_str.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid date format: {date_str}")

    day_str, month_str = parts[0], parts[1]
    day = int(day_str)
    month = int(month_str)

    if len(parts) == 2:
        # No year provided => default to current year
        year = datetime.now().year
    else:
        # Possibly have a year part
        year_str = parts[2]
        if not year_str:
            # e.g. "03.03." => parts=["03","03",""]
            # We consider that "no year" => current year
            year = datetime.now().year
        elif len(year_str) == 2:
            # e.g. '25' => 2025
            year = 2000 + int(year_str)
        else:
            year = int(year_str)

    return date(year, month, day)


class TimeTracker:
    """
    Parses and stores time tracking data from a Google Keep note or any raw text.

    Data Structure:
        self.hourly_rates: {task_code -> float}
        self.entries: {
           date_str(YYYY-MM-DD) -> {
               task_code -> [(start_dt, end_dt), (start_dt, end_dt), ...]
           }
        }
    """

    def __init__(self):
        self.hourly_rates = {}
        self.entries = defaultdict(lambda: defaultdict(list))

    def parse_note_content(self, note_content):
        lines = note_content.splitlines()
        current_date = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Lines starting with "+" define an hourly rate
            if line.startswith("+"):
                parts = line.split()
                task_code = parts[0][1:]
                hourly_rate = float(parts[1])
                self.hourly_rates[task_code] = hourly_rate

            # If the line starts with a digit, it's likely a date header (e.g., "03.03." or "03.03.2025")
            elif line[0].isdigit():
                try:
                    date_obj = parse_german_date(line.split()[0])
                    current_date = date_obj
                except ValueError:
                    current_date = None

            else:
                # It's a task line if current_date is set
                if current_date is None:
                    continue

                parts = line.split()
                task_code = parts[0]
                time_ranges = parts[1:]

                date_key = current_date.strftime("%Y-%m-%d")
                for time_range in time_ranges:
                    start_str, end_str = time_range.split("-")
                    start_dt = datetime.strptime(start_str, "%H:%M")
                    end_dt = datetime.strptime(end_str, "%H:%M")

                    # If it crosses midnight in a simplistic sense
                    if end_dt < start_dt:
                        # Time crosses midnight - add 1 day
                        from datetime import timedelta

                        end_dt = end_dt + timedelta(days=1)

                    self.entries[date_key][task_code].append((start_dt, end_dt))

    def get_date_range_in_entries(self):
        """
        Returns the earliest and latest date (as date objects) found in self.entries.
        If no entries exist, returns (None, None).
        """
        if not self.entries:
            return None, None

        all_dates = [
            datetime.strptime(d, "%Y-%m-%d").date() for d in self.entries.keys()
        ]
        return min(all_dates), max(all_dates)

    def filter_entries(self, start_date, end_date, task_codes=None):
        """
        Return a filtered structure of the entries limited to the given date range
        and the given tasks (if provided).
        If task_codes is None => all tasks are included.
        """
        filtered = defaultdict(lambda: defaultdict(list))

        for date_str, tasks in self.entries.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if start_date <= date_obj <= end_date:
                for t_code, intervals in tasks.items():
                    if task_codes is None or t_code in task_codes:
                        filtered[date_str][t_code].extend(intervals)
        return filtered

    def summarize(self, filtered_data):
        """
        Summarize total hours and total earnings for filtered data.
        Returns a dict {task_code -> (hours, earnings)} plus (grand_hours, grand_earnings).
        """
        summary = defaultdict(lambda: [0.0, 0.0])
        for date_str, tasks in filtered_data.items():
            for t_code, intervals in tasks.items():
                for start_dt, end_dt in intervals:
                    duration_minutes = (end_dt - start_dt).total_seconds() / 60.0
                    duration_hours = duration_minutes / 60.0
                    summary[t_code][0] += duration_hours
                    summary[t_code][1] += duration_hours * self.hourly_rates.get(
                        t_code, 0.0
                    )

        grand_hours = sum(v[0] for v in summary.values())
        grand_earnings = sum(v[1] for v in summary.values())
        return summary, grand_hours, grand_earnings

    def export_tasks_by_day(self, filtered_data, filename, filter_desc):
        """
        Write day-by-day tasks (date, task_code, start_time, end_time) to a text file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Filter: {filter_desc}\n\n")
            header = f"{'Date':<12} | {'Task':<8} | {'Start':<5} | {'End':<5}\n"
            f.write(header)
            f.write("-" * len(header) + "\n")

            for date_str in sorted(filtered_data.keys()):
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                for t_code, intervals in filtered_data[date_str].items():
                    intervals_sorted = sorted(intervals, key=lambda x: x[0])
                    for start_dt, end_dt in intervals_sorted:
                        start_s = start_dt.strftime("%H:%M")
                        end_s = end_dt.strftime("%H:%M")
                        line = f"{date_obj.strftime('%d.%m.%Y'):<12} | {t_code:<8} | {start_s:<5} | {end_s:<5}\n"
                        f.write(line)

        print(f"[OK] Exported tasks by day to: {filename}")


def input_german_date_or_skip(prompt_str, default_value=None):
    """
    Prompt the user for a German date like '01.03.' or '01.03.25'.
    If user presses Enter, return default_value (which can be None or a date).
    """
    while True:
        user_input = input(prompt_str).strip()
        if not user_input:
            return default_value
        try:
            return parse_german_date(user_input)
        except ValueError:
            print(
                "Invalid date format. Please try again (e.g. 01.03., 02.03.25, 15.03.2025)."
            )


def checkbox_select_task_codes(all_codes):
    """
    Basic textual simulation of selecting multiple task codes.
    Returns a list of selected codes or None if user chooses all.
    """
    if not all_codes:
        print("No task codes found.")
        return None

    print("\n-- Select Task Codes --")
    for i, code in enumerate(all_codes, 1):
        print(f"   {i}. {code}")
    print("   0. [All Codes]\n")
    selection_str = input("Enter comma-separated indices or '0' for all: ")
    if selection_str.strip() == "0":
        return None  # means all
    selected = []
    for idx_s in selection_str.split(","):
        idx_s = idx_s.strip()
        if idx_s.isdigit():
            idx = int(idx_s)
            if 1 <= idx <= len(all_codes):
                selected.append(all_codes[idx - 1])

    if not selected:
        return None
    return selected


def fetch_times_note(keep, query="TIMES"):
    """
    Fetch the first note that matches the query.
    Adjust your logic as needed.
    """
    found = keep.find(query)
    return next(found, None)


def main():

    # ------------------------
    # 1) Connect to Keep (example)
    # ------------------------
    # Obtain a master token for your account
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Read master token from file in parent directory
    token_path = os.path.join(script_dir, "..", "google_master_token.txt")
    if not os.path.exists(token_path):
        print(f"Error: Token file not found at {token_path}")
        sys.exit(1)
    with open(token_path, "r") as token_file:
        master_token = token_file.read().strip()

    keep = gkeepapi.Keep()
    email = os.environ.get("GOOGLE_KEEP_EMAIL", "tim.altendorf@gmail.com")
    keep.authenticate(email, master_token)

    # Fetch the note
    note = fetch_times_note(keep, "TIMES")
    if note is None:
        print("Error: No note with 'TIMES' in title found")
        sys.exit(1)

    # ----------------------------------------------------------------------
    # Build and parse
    # ----------------------------------------------------------------------
    tracker = TimeTracker()
    tracker.parse_note_content(note.text)

    # Ask user if they want to specify date range or skip => all time
    print("=== TimeTracker CLI ===")
    earliest, latest = tracker.get_date_range_in_entries()
    if not earliest or not latest:
        print("No data found in the entries. Exiting.")
        return

    print(
        "\nEnter start date (DD.MM / DD.MM.YY / DD.MM.YYYY) or press Enter to skip => earliest in data."
    )
    start_date = input_german_date_or_skip("Start Date: ", default_value=earliest)

    print(
        "\nEnter end date (DD.MM / DD.MM.YY / DD.MM.YYYY) or press Enter to skip => latest in data."
    )
    end_date = input_german_date_or_skip("End Date: ", default_value=latest)

    if end_date < start_date:
        print("End date is before start date. Exiting.")
        return

    # ----------------------------------------------------------------------
    # Task codes
    # ----------------------------------------------------------------------
    all_codes = sorted(
        list(
            set(tracker.hourly_rates.keys())
            | {tc for d in tracker.entries.values() for tc in d.keys()}
        )
    )
    selected_codes = checkbox_select_task_codes(all_codes)  # None => all

    # Filter the data
    filtered_data = tracker.filter_entries(start_date, end_date, selected_codes)

    # Check if there's anything in filtered_data
    if not filtered_data:
        print("No entries found for the given filters.")
        return

    # ----------------------------------------------------------------------
    # Choose summary or tasks-by-day export
    # ----------------------------------------------------------------------
    print("\nSelect output:")
    print("1) Print summary (hours, earnings) to screen")
    print("2) Export tasks-by-day listing to a .txt file")
    choice = input("Choice (1 or 2): ").strip()

    if choice == "1":
        # Summarize
        summary, grand_hours, grand_earnings = tracker.summarize(filtered_data)
        print("\n-- SUMMARY --")
        print(f"{'Task Code':<10} {'Hours':>8} {'Earnings':>10}")
        print("-" * 30)
        for t_code in sorted(summary.keys()):
            hrs, earn = summary[t_code]
            print(f"{t_code:<10} {hrs:8.2f} {earn:10.2f}")
        print("-" * 30)
        print(f"{'TOTAL':<10} {grand_hours:8.2f} {grand_earnings:10.2f}")

    elif choice == "2":
        # Export
        filter_desc = f"Start: {start_date}, End: {end_date}, "
        filter_desc += f"Tasks: {selected_codes if selected_codes else 'All'}"
        filename = input("Enter output file name (e.g. export.txt): ").strip()
        if not filename:
            filename = "tasks_export.txt"
        tracker.export_tasks_by_day(filtered_data, filename, filter_desc)
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
