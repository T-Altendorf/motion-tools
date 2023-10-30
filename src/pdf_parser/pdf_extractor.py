import re

class FileExtractor:
    @staticmethod
    def extract_week_number_and_name(filename):
        match = re.search(r'(\d+)[-_]*(.*)\.*', filename, re.IGNORECASE)
        if match:
            week_number = int(match.group(1))
            remaining_filename = match.group(2)
            # Remove leading minuses or underscores
            remaining_filename = re.sub(r'^[-_]+', '', remaining_filename)
            return week_number, remaining_filename
        else:
            return None, None