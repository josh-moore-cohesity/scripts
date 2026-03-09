#!/usr/bin/env python
import subprocess
import sys
import os
import datetime

def get_crontab():
    """Return current user crontab as list of lines (including newline)."""
    try:
        output = subprocess.check_output(["crontab", "-l"])
        # Handle Python 2 (bytes) vs Python 3 (bytes/str)
        if not isinstance(output, str):
            output = output.decode("utf-8")
        return output.splitlines(True)  # keepends=True
    except subprocess.CalledProcessError:
        # No crontab exists
        return []

def install_crontab(lines):
    """Install given lines as the new user crontab."""
    text = "".join(lines)
    if not isinstance(text, str):
        text = text.decode("utf-8")
    proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE)
    proc.communicate(input=text)
    if proc.returncode != 0:
        raise RuntimeError("Failed to install new crontab")

def backup_crontab(lines):
    """Write a backup file in $HOME with timestamp."""
    home = os.path.expanduser("~")
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = os.path.join(home, "crontab.backup." + ts)
    with open(backup_file, "w") as f:
        f.writelines(lines)
    print("Backup written to: {0}".format(backup_file))

def comment_all(lines):
    """
    Comment every non-empty, non-commented line.
    Keep existing comments and blank lines as-is.
    """
    new_lines = []
    for line in lines:
        # preserve line endings
        stripped = line.lstrip()

        # blank line
        if stripped == "" or stripped == "\n":
            new_lines.append(line)
            continue

        # already a comment
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        # comment this line
        indent_len = len(line) - len(stripped)
        indent = line[:indent_len]
        new_line = indent + "# " + stripped
        new_lines.append(new_line)
    return new_lines

def uncomment_all(lines):
    """
    Uncomment every commented line.
    Only touches lines that start with '#' (after optional whitespace).
    """
    new_lines = []
    for line in lines:
        stripped = line.lstrip()

        # not a comment, keep as-is
        if not stripped.startswith("#"):
            new_lines.append(line)
            continue

        # remove first '#' and an optional following space
        without_hash = stripped[1:]
        if without_hash.startswith(" "):
            without_hash = without_hash[1:]

        indent_len = len(line) - len(stripped)
        indent = line[:indent_len]
        new_line = indent + without_hash
        new_lines.append(new_line)
    return new_lines

def main():
    if len(sys.argv) != 2:
        print("Usage: {0} <pause|resume>".format(sys.argv[0]))
        sys.exit(1)

    action = sys.argv[1]

    lines = get_crontab()
    backup_crontab(lines)

    if action == "pause":
        new_lines = comment_all(lines)
    elif action == "resume":
        new_lines = uncomment_all(lines)
    else:
        print("Action must be 'pause' or 'resume'")
        sys.exit(1)

    install_crontab(new_lines)
    print("Crontab updated successfully.")

if __name__ == "__main__":
    main()
