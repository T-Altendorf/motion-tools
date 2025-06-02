import re


class FileExtractor:
    @staticmethod
    def extract_week_number_and_name(
        filename,
        number_pattern=r"week(\d+)",
        name_pattern=r"[-_]*(.*)",
        flags=re.IGNORECASE,
    ):
        """
        Extract number and name from a filename using customizable regex patterns.
        Each pattern is applied independently to the entire filename.

        Args:
            filename: The filename to parse
            number_pattern: Regex pattern to extract the number with one capture group
            name_pattern: Regex pattern to extract the name with one capture group
            flags: Regex flags to use

        Returns:
            Tuple of (number as int or None, name as string or None)
        """
        # Extract number using number_pattern
        number_match = re.search(number_pattern, filename, flags)
        number = None
        if number_match:
            try:
                number = int(number_match.group(1))
            except (IndexError, ValueError):
                pass

        # Extract name using name_pattern
        name_match = re.search(name_pattern, filename, flags)
        name = None
        if name_match:
            try:
                name = name_match.group(1)
                # Clean up the name
                name = re.sub(r"^[-_]+", "", name)
                name = re.sub(r"\..*$", "", name)
            except IndexError:
                pass

        return number, name
