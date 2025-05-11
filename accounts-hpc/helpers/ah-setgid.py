#!/usr/bin/env python

import argparse
import os
import stat

from accounts_hpc.shared import Shared  # type: ignore


def main():
    parser = argparse.ArgumentParser(description="Set setgid bit on all subdirectories within a specified path")
    parser.add_argument('--path', required=True, help="Path to the directory containing group subdirectories")
    shared = Shared("cron-ah-setgid", False)
    logger = shared.log["cron-ah-setgid"].get()

    args = parser.parse_args()

    if not os.path.exists(args.path):
        msg = f"Error: Path '{args.path}' does not exist."
        print(msg)
        logger.error(msg)
        exit(1)
    if not os.path.isdir(args.path):
        msg = f"Error: Path '{args.path}' is not a directory."
        print(msg)
        logger.error(msg)
        exit(1)

    subdirs = []
    try:
        with os.scandir(args.path) as entries:
            for entry in entries:
                if entry.is_dir():
                    subdirs.append(entry.path)
    except OSError as e:
        msg = f"Error: Failed to scan '{args.path}': {str(e)}."
        print(msg)
        logger.error(msg)
        exit(1)

    if not subdirs:
        msg = f"No subdirectories found in '{args.path}'."
        print(msg)
        logger.error(msg)
        return

    for subdir in subdirs:
        try:
            current_mode = os.stat(subdir).st_mode
            if current_mode & stat.S_ISGID:
                continue
            new_mode = current_mode | stat.S_ISGID
            os.chmod(subdir, new_mode)
            msg = f"setgid on '{subdir}'."
            print(msg)
            logger.info(msg)
        except PermissionError:
            msg = f"Error: Insufficient permissions to setgid on '{subdir}'."
            print(msg)
            logger.error(msg)
        except OSError as e:
            msg = f"Error: Failed to setgid on '{subdir}': {str(e)}."
            print(msg)
            logger.error(msg)


if __name__ == "__main__":
    main()
