# match_engine.py

class MatchEngine:
    """
    Keeps track of which files the user has chosen to remove.
    """
    def __init__(self):
        # Using a set to automatically avoid duplicates in the removal list
        self.files_for_removal = set()

    def add_file_for_removal(self, file_path):
        """Adds a file to the list of files to be removed."""
        self.files_for_removal.add(file_path)

    def get_files_for_removal(self):
        """Returns the final list of files to be removed."""
        return list(self.files_for_removal)

    def clear_list(self):
        """Resets the list for a new run."""
        self.files_for_removal.clear()
