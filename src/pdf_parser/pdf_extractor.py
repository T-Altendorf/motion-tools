import re


class FileExtractor:
    @staticmethod
    def extract_week_number_and_name(
        filename, regex_week=r"(\d+)[-_]*(.*)\.*", regex_task=r"^[-_]+"
    ):
        match = re.search(regex_week, filename, re.IGNORECASE)
        if match:
            week_number = int(match.group(1))
            # Remove leading minuses or underscores
            remaining_filename = re.search(regex_task, filename).group(1)
            return week_number, remaining_filename
        else:
            return None, None
