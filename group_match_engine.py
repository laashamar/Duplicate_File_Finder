# group_match_engine.py

class GroupMatchEngine:
    """
    A more efficient implementation of the Group Engine that uses a dictionary
    for quick lookup of which group a file belongs to.
    This approach uses a Disjoint Set Union (DSU) or Union-Find data structure concept.
    """
    def __init__(self, threshold):
        self.threshold = threshold
        # Maps a file path to the set representing its group
        self.file_to_group_map = {}
        # A list of all the group sets
        self.groups = []

    def add_match(self, file1, file2, dist):
        """
        Adds a match between file1 and file2 and groups them efficiently.
        """
        group1 = self.file_to_group_map.get(file1)
        group2 = self.file_to_group_map.get(file2)

        if group1 and group2:
            # Both files are already in groups, merge them if they are different
            if group1 is not group2:
                # Merge the smaller group into the larger one for efficiency
                if len(group1) < len(group2):
                    smaller_group, larger_group = group1, group2
                else:
                    larger_group, smaller_group = group1, group2

                larger_group.update(smaller_group)
                # Update the mapping for all files in the merged group
                for file in smaller_group:
                    self.file_to_group_map[file] = larger_group

                # Remove the now-empty smaller group
                self.groups.remove(smaller_group)

        elif group1:
            # Only file1 is in a group, add file2 to it
            group1.add(file2)
            self.file_to_group_map[file2] = group1

        elif group2:
            # Only file2 is in a group, add file1 to it
            group2.add(file1)
            self.file_to_group_map[file1] = group2

        else:
            # Neither file is in a group, create a new one
            new_group = {file1, file2}
            self.groups.append(new_group)
            self.file_to_group_map[file1] = new_group
            self.file_to_group_map[file2] = new_group

    def get_groups(self):
        """
        Returns a list of groups, where each group is a sorted list of file paths.
        """
        return [sorted(list(group)) for group in self.groups]
