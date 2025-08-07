# automatic_selector.py

import os
import logging
import re
from enum import Enum
from functools import cmp_to_key

from data_models import FileMetadata

class SelectionStrategy(Enum):
    """Defines the available, improved strategies for automatic selection."""
    KEEP_BEST_QUALITY = "Keep best quality"
    # --- NEW: Added the KEEP_LAST_EDITED strategy ---
    KEEP_LAST_EDITED = "Keep last edited"
    KEEP_ALL_UNIQUE_VERSIONS = "Keep unique versions (original + edited)"

    def __str__(self):
        return self.value

class AutomaticSelector:
    """
    Implements a robust, hierarchical model for automatic image selection
    based on a comprehensive quality assessment.
    """
    def __init__(self):
        # Defines a prioritized order for file formats. Lower number = higher priority.
        self.format_priority = {
            '.dng': 0, '.tiff': 1, '.png': 2,
            '.jpeg': 3, '.jpg': 3, '.heic': 4, '.webp': 5
        }
        # Regex to identify common suffixes for edited files or copies
        self.edit_suffix_regex = re.compile(r'[-_]\d+$|[-_]edit(ed)?$|[-_]copy$|\(\d+\)$', re.IGNORECASE)

    def _get_file_format_priority(self, path):
        """Gets the priority of a file format from the predefined list."""
        ext = os.path.splitext(path)[1].lower()
        # Unknown formats get the lowest priority
        return self.format_priority.get(ext, 99)

    def _is_likely_original_by_name(self, path):
        """Checks if a filename is likely an original (not a copy/edited)."""
        filename = os.path.splitext(os.path.basename(path))[0]
        return not self.edit_suffix_regex.search(filename)

    def _compare_files(self, meta1: FileMetadata, meta2: FileMetadata):
        """
        Compares two files based on the hierarchical quality model.
        Returns -1 if meta1 is better, 1 if meta2 is better, 0 if they are equal.
        """
        # 1. Prioritize highest resolution
        if meta1.resolution > meta2.resolution:
            return -1
        if meta1.resolution < meta2.resolution:
            return 1

        # 2. Tie-breaker: Largest file size
        if meta1.size > meta2.size:
            return -1
        if meta1.size < meta2.size:
            return 1

        # 3. Tie-breaker: File format priority
        priority1 = self._get_file_format_priority(meta1.path)
        priority2 = self._get_file_format_priority(meta2.path)
        if priority1 < priority2:
            return -1
        if priority1 > priority2:
            return 1

        # 4. Tie-breaker: Filename analysis (original vs. edited)
        is_orig1 = self._is_likely_original_by_name(meta1.path)
        is_orig2 = self._is_likely_original_by_name(meta2.path)
        if is_orig1 and not is_orig2:
            return -1
        if not is_orig1 and is_orig2:
            return 1

        # 5. Last resort: Oldest modification date
        if meta1.mod_time < meta2.mod_time:
            return -1
        if meta1.mod_time > meta2.mod_time:
            return 1

        return 0

    def _get_best_in_group(self, metadata_list):
        """Finds the objectively best image in a group using hierarchical sorting."""
        if not metadata_list:
            return None
        # Uses cmp_to_key to sort the list based on the complex comparison function
        sorted_list = sorted(metadata_list, key=cmp_to_key(self._compare_files))
        return sorted_list[0]

    def _strategy_keep_best_quality(self, metadata_list):
        """Strategy to keep only the single, best image."""
        best_file = self._get_best_in_group(metadata_list)
        return [best_file.path] if best_file else []

    # --- NEW: Implemented the KEEP_LAST_EDITED strategy ---
    def _strategy_keep_last_edited(self, metadata_list):
        """Strategy to keep only the file with the most recent modification time."""
        if not metadata_list:
            return []
        last_edited = max(metadata_list, key=lambda m: m.mod_time)
        return [last_edited.path]

    def _strategy_keep_unique_versions(self, metadata_list):
        """
        Strategy to keep the best "original" and the best "edited" version.
        """
        if len(metadata_list) <= 1:
            return [m.path for m in metadata_list]

        best_original = self._get_best_in_group(metadata_list)

        # Finds the last modified file, as a proxy for "last edited"
        last_edited = max(metadata_list, key=lambda m: m.mod_time)

        # Uses a set to handle cases where the original and edited are the same file
        files_to_keep = {best_original.path, last_edited.path}
        return list(files_to_keep)

    def run_automatic_selection(self, groups, strategy, all_file_data):
        """
        Main method that iterates through groups and selects files based on the chosen strategy.
        Returns two lists: files for removal, and files to sort (if applicable).
        """
        files_for_removal = set()
        files_to_sort = {'Originals': [], 'Last Edited': []}

        strategy_map = {
            SelectionStrategy.KEEP_BEST_QUALITY: self._strategy_keep_best_quality,
            # --- NEW: Added mapping for the new strategy ---
            SelectionStrategy.KEEP_LAST_EDITED: self._strategy_keep_last_edited,
            SelectionStrategy.KEEP_ALL_UNIQUE_VERSIONS: self._strategy_keep_unique_versions
        }

        strategy_func = strategy_map.get(strategy)
        if not strategy_func:
            logging.error(f"Unknown strategy: {strategy}. Cannot perform automatic selection.")
            return [], {}

        for group in groups:
            if len(group) < 2:
                continue

            metadata_list = [all_file_data.get(path) for path in group if all_file_data.get(path)]
            if len(metadata_list) < 2:
                logging.warning(f"Did not find enough valid metadata for group, skipping: {group}")
                continue

            files_in_group_to_keep = strategy_func(metadata_list)

            # --- NEW: Logic to handle sorting for KEEP_ALL_UNIQUE_VERSIONS ---
            if strategy == SelectionStrategy.KEEP_ALL_UNIQUE_VERSIONS:
                best_original = self._get_best_in_group(metadata_list)
                last_edited = max(metadata_list, key=lambda m: m.mod_time)
                
                # The best original file goes into the 'Originals' sort list
                if best_original.path in files_in_group_to_keep:
                    files_to_sort['Originals'].append(best_original.path)
                
                # The last edited file goes into the 'Last Edited' sort list
                if last_edited.path in files_in_group_to_keep and last_edited.path != best_original.path:
                    files_to_sort['Last Edited'].append(last_edited.path)

            for file_metadata in metadata_list:
                if file_metadata.path not in files_in_group_to_keep:
                    files_for_removal.add(file_metadata.path)

        return list(files_for_removal), files_to_sort
