#!/usr/bin/env python

import argparse
import os
import stat


def main():
    parser = argparse.ArgumentParser(description="Set setgid bit on all subdirectories within a specified path")
    parser.add_argument('--path', required=True, help="Path to the directory containing group subdirectories")

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist.")
        exit(1)
    if not os.path.isdir(args.path):
        print(f"Error: Path '{args.path}' is not a directory.")
        exit(1)

    subdirs = []
    try:
        with os.scandir(args.path) as entries:
            for entry in entries:
                if entry.is_dir():
                    subdirs.append(entry.path)
    except OSError as e:
        print(f"Error: Failed to scan '{args.path}': {str(e)}.")
        exit(1)

    if not subdirs:
        print(f"No subdirectories found in '{args.path}'.")
        return

    for subdir in subdirs:
        try:
            current_mode = os.stat(subdir).st_mode
            if current_mode & stat.S_ISGID:
                continue
            new_mode = current_mode | stat.S_ISGID
            os.chmod(subdir, new_mode)
            print(f"setgid on '{subdir}'.")
        except PermissionError:
            print(f"Error: Insufficient permissions to setgid on '{subdir}'.")
        except OSError as e:
            print(f"Error: Failed to setgid on '{subdir}': {str(e)}.")


if __name__ == "__main__":
    main()
