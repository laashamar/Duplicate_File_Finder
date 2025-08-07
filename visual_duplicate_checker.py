# visual_duplicate_checker.py
# Focuses now only on image processing (hashing) and comparison.

import os
import logging
import time
import multiprocessing

import imagehash
import pyvips
from PIL import Image
import pybktree

from data_models import FileMetadata
from group_match_engine import GroupMatchEngine
from config import MIN_SIZE_BYTES

def _hash_file_standalone(file_path):
    """
    Validates and hashes a single file. Returns a FileMetadata object or None on error.
    """
    try:
        # Step 1: Quick validation
        stat_info = os.stat(file_path)
        if stat_info.st_size < MIN_SIZE_BYTES:
            # Ignoring files that are too small
            return None

        # Step 2: Deeper validation and hashing
        img = Image.open(file_path)
        # Checks that the file is not corrupt
        img.verify()

        img = Image.open(file_path)
        # CHANGE: Switching to Difference Hash (dhash) for more accurate comparison.
        img_hash_obj = imagehash.dhash(img)

        # Step 3: Get metadata
        vips_img = pyvips.Image.new_from_file(file_path, access="sequential")
        resolution = vips_img.width * vips_img.height

        hash_as_int = int(str(img_hash_obj), 16)

        return FileMetadata(
            path=file_path, hash=hash_as_int, resolution=resolution,
            size=stat_info.st_size, mod_time=stat_info.st_mtime
        )
    except Exception as e:
        logging.warning(f"Could not process the file {os.path.basename(file_path)}: {e}")
        return None

def batch_duplicate_check(image_paths, threshold, progress_callback):
    """
    Takes a list of validated files, hashes them, finds duplicates, and returns the results.
    """
    stats = {
        "files_processed": len(image_paths), "failed_files": 0, "images_hashed": 0,
        "hashing_time": 0, "comparison_time": 0
    }
    all_file_data = {}
    groups = []

    try:
        pyvips.cache_set_max(0)

        if not image_paths:
            progress_callback(100, "No image files to check.")
            return stats, all_file_data, groups

        # Step 1: Validation and Hashing (parallel)
        start_time = time.monotonic()

        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=os.cpu_count()) as pool:
            async_results = [pool.apply_async(_hash_file_standalone, (path,)) for path in image_paths]
            for i, future in enumerate(async_results):
                metadata = future.get()
                if metadata:
                    all_file_data[metadata.path] = metadata

                processed_count = i + 1
                progress_value = int(10 + 65 * (processed_count / len(image_paths)))
                progress_text = f"🔄 Processing image {processed_count} of {len(image_paths)}..."
                progress_callback(progress_value, progress_text)

        stats["hashing_time"] = time.monotonic() - start_time
        stats["images_hashed"] = len(all_file_data)
        stats["failed_files"] = len(image_paths) - len(all_file_data)
        logging.info(f"Validation and hashing completed in {stats['hashing_time']:.2f} seconds.")

        # Step 2: Comparison and grouping
        start_time = time.monotonic()
        progress_callback(75, "Building BK-tree for fast search...")

        if not all_file_data:
            progress_callback(100, "No images could be hashed.")
            return stats, all_file_data, groups

        hash_to_paths = {}
        for path, data in all_file_data.items():
            if data.hash not in hash_to_paths:
                hash_to_paths[data.hash] = []
            hash_to_paths[data.hash].append(path)

        unique_hashes = list(hash_to_paths.keys())
        def hamming_distance(h1, h2):
            return bin(h1 ^ h2).count('1')
        tree = pybktree.BKTree(hamming_distance, unique_hashes)

        progress_callback(80, "Comparing images and building groups...")

        group_engine = GroupMatchEngine(threshold)
        processed_hashes = set()
        for i, h in enumerate(unique_hashes):
            if h in processed_hashes:
                continue
            found_matches_with_dist = tree.find(h, threshold)
            for dist, match_h in found_matches_with_dist:
                path1 = hash_to_paths[h][0]
                path2 = hash_to_paths[match_h][0]
                if path1 != path2:
                    group_engine.add_match(path1, path2, dist)
            for _, match_h in found_matches_with_dist:
                processed_hashes.add(match_h)
            if (i + 1) % 50 == 0:
                progress_callback(
                    int(80 + 20 * ((i + 1) / len(unique_hashes))),
                    f"Comparing group {i + 1}/{len(unique_hashes)}..."
                )

        final_groups = []
        raw_groups = group_engine.get_groups()
        for group in raw_groups:
            expanded_group = set()
            for path in group:
                # Use .get() to avoid KeyError if a path is somehow not in all_file_data
                metadata = all_file_data.get(path)
                if metadata and metadata.hash:
                    expanded_group.update(hash_to_paths[metadata.hash])
            if len(expanded_group) > 1:
                final_groups.append(list(expanded_group))

        groups = final_groups
        stats["comparison_time"] = time.monotonic() - start_time
        logging.info(f"Comparison completed in {stats['comparison_time']:.2f} seconds. Found {len(groups)} duplicate groups.")
        progress_callback(100, "Check complete.")

        return stats, all_file_data, groups

    except Exception as e:
        logging.critical(f"An unexpected error occurred in batch_duplicate_check: {e}", exc_info=True)
        raise e
