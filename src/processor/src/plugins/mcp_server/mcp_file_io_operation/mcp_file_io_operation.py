import contextlib
from datetime import datetime
import os
import shutil
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP(
    name="file_operation_service",
    instructions="""
[START] COMPREHENSIVE FILE & DIRECTORY OPERATIONS MCP SERVER
================================================================

A powerful MCP server providing complete file and directory management capabilities for AI agents and automation workflows.

[CLIPBOARD] CORE FUNCTIONS
=================

[FOLDER] BASIC FILE OPERATIONS
------------------------
• save_content_to_file(file_name, content, file_path?)
  → Save content to file with automatic directory creation
• open_file_content(file_name, file_path?)
  → Read complete file contents as text
• check_file_exists(file_name, file_path?)
  → Verify file/directory existence with detailed metadata
• delete_file(file_name, file_path?)
  → Permanently delete individual files
• move_file(file_name, source_path?, target_path?, new_name?)
  → Move/rename files between locations

[FOLDER] DIRECTORY OPERATIONS
-----------------------
• list_files_in_directory(directory_path?)
  → Comprehensive directory listing with file details
• create_directory(dir_name, dir_path?)
  → Create new directories with parent structure
• delete_folder(folder_name, folder_path?)
  → Delete empty directories safely
• delete_directory_recursive(dir_name, dir_path?)
  → [WARNING] DANGER: Recursively delete directories and all contents
• clear_folder(folder_name, folder_path?)
  → Empty directory contents while preserving structure
• copy_directory(source_dir, target_dir, source_path?, target_path?, recursive?)
  → Copy entire directory structures

[SEARCH] SEARCH & DISCOVERY
--------------------
• find_files(pattern, search_path?, recursive?)
  → Search files using wildcards (*.yaml, test*, *config*)
• search_file_content(search_term, file_pattern?, search_path?)
  → Grep-style content search with line numbers and context

[CLIPBOARD] BATCH OPERATIONS
------------------
• copy_file(source_file, target_file, source_path?, target_path?)
  → Copy individual files with metadata preservation
• copy_multiple_files(file_patterns, source_path, target_path)
  → Batch copy files matching patterns
• delete_multiple_files(file_patterns, file_path?)
  → [WARNING] DANGER: Batch delete files matching patterns

[TOOLS] ADVANCED ANALYSIS
--------------------
• generate_git_diff(source_file?, target_file?, source_path?, target_path?)
  → Professional git-style file comparison
• analyze_file_quality(file_name, file_path?, quality_standards?)
  → Comprehensive file metrics and quality analysis
• verify_directory_cleanup(directory_path?, cleanup_report?)
  → Validate directory cleanup operations
• get_workspace_info()
  → Discover workspace structure and available paths

[TARGET] KEY FEATURES
===============

[SUCCESS] INTELLIGENT PATH HANDLING
• Auto-detects container paths (/workspace, /app) → current directory
• Creates missing directory structures automatically
• Supports both relative (./data) and absolute (/tmp/files) paths
• Smart path suggestions for typos and missing directories

[SUCCESS] ENTERPRISE SAFETY
• Detailed error messages with actionable suggestions
• Prevents accidental overwrites with existence checks
• Comprehensive logging and operation tracking
• Permission validation before destructive operations

[SUCCESS] PRODUCTIVITY ENHANCEMENTS
• Wildcard pattern matching for bulk operations
• Recursive directory traversal with depth control
• File metadata extraction (size, permissions, timestamps)
• Cross-platform path normalization

[WARNING] CRITICAL SAFETY NOTICES
==========================
• File deletions are PERMANENT and cannot be undone
• Always verify paths before recursive delete operations
• Use check_file_exists() to validate before destructive operations
• Backup important data before bulk operations

[IDEA] PRACTICAL USAGE EXAMPLES
===========================

[NOTES] CONTENT MANAGEMENT
---------------------
# Save configuration files
save_content_to_file("config.yaml", "apiVersion: v1\nkind: Config", "./output")
save_content_to_file("docs/README.md", "# Project Documentation", "./project")

# Read and analyze content
content = open_file_content("deployment.yaml", "./kubernetes")
quality = analyze_file_quality("large-config.json", "./configs")

[FOLDER] DIRECTORY OPERATIONS
-----------------------
# Organize project structure
create_directory("converted", "./migration/output")
create_directory("backups", "./project")

# Copy project templates
copy_directory("templates", "my-project", "./source", "./projects")
copy_multiple_files("*.yaml,*.json", "./source/configs", "./output/configs")

[SEARCH] DISCOVERY & SEARCH
---------------------
# Find configuration files
yaml_files = find_files("*.yaml", "./kubernetes", recursive=True)
configs = find_files("*config*", "./", recursive=False)

# Search for specific patterns
api_usage = search_file_content("apiVersion", "*.yaml", "./manifests")
secrets = search_file_content("password", "*.env", "./configs")

[CLEANUP] CLEANUP OPERATIONS
---------------------
# Clean temporary files
delete_multiple_files("*.tmp,*.log", "./temp")
clear_folder("cache", "./application")

# Project cleanup
verify_directory_cleanup("./temp")
delete_directory_recursive("old-migration", "./projects") # [WARNING] PERMANENT!

[INFO] ANALYSIS & COMPARISON
------------------------
# File comparison and analysis
diff = generate_git_diff("old-config.yaml", "new-config.yaml", "./v1", "./v2")
workspace = get_workspace_info()

[TARGET] MIGRATION WORKFLOW EXAMPLE
=============================
1. create_directory("converted", "./migration")
2. find_files("*.yaml", "./source", recursive=True)
3. copy_multiple_files("*.yaml", "./source", "./migration/backup")
4. For each file: generate_git_diff(source, converted)
5. save_content_to_file("migration_report.md", report_content, "./migration")
6. verify_directory_cleanup("./temp")

[TOOLS] PARAMETER CONVENTIONS
========================
• file_name: Just the filename (e.g., "config.yaml", "report.md")
• file_path: Directory path (e.g., "./output", "/tmp", defaults to ".")
• Optional parameters marked with ? can be omitted
• Patterns support wildcards: *, ?, [chars], **/ (recursive)
• Comma-separated patterns: "*.yaml,*.json,config*"

This MCP server provides enterprise-grade file operations with safety, intelligence, and productivity features for complex automation workflows.
""",
)


@mcp.tool()
def save_content_to_file(
    file_name: str, content: str, file_path: str | None = None
) -> str:
    """Save content to a file at the specified path.

    Args:
        file_name: Name of the file to create (e.g., 'document.txt', 'az-deployment.yaml')
        content: Content to write to the file
        file_path: Directory path where file should be saved (e.g., './migration/converted').
                  If None, uses current directory ('.')

    Returns:
        Success message with the full file path where content was saved

    Note:
        Creates directory structure if it doesn't exist. Overwrites existing files.
        Automatically converts absolute container paths to relative paths when appropriate.
    """
    if file_path is None:
        file_path = "."

    # Handle container internal paths by converting to relative paths
    if (
        file_name.startswith("/workspace")
        or file_name.startswith("/app")
        or file_name.startswith("/opt")
    ):
        # Convert container paths to relative paths for local development
        file_name = os.path.basename(file_name)
        print(f"Note: Converted container path to relative path: {file_name}")

    # Combine the base path with the file name (which may contain folders)
    full_file_path = os.path.join(file_path, file_name)

    # Extract the directory part from the full file path
    directory = os.path.dirname(full_file_path)

    # Create the directory structure if it doesn't exist
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    # Save the file
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Content successfully saved to: {os.path.abspath(full_file_path)}"


@mcp.tool()
def open_file_content(file_name: str, file_path: str | None = None) -> str:
    """Read and return the content of a file.

    Args:
        file_name: Name of the file to read (e.g., 'migration_report.md', 'az-deployment.yaml')
        file_path: Directory path where the file is located (e.g., './migration/converted').
                  If None, uses current directory ('.')

    Returns:
        Complete file content as a string, or error message if file cannot be read

    Note:
        No exceptions are raised - all errors are returned as informative messages.
    """
    if file_path is None:
        file_path = "."

    full_file_path = os.path.join(file_path, file_name)

    if not os.path.exists(full_file_path):
        return f"""[FAILED] FILE READ FAILED

File: {full_file_path}
Reason: File does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{file_name}'
- Verify the file path is correct: '{file_path}'
- Use list_files() to see available files in the directory
- The file may have been moved or deleted"""

    if not os.path.isfile(full_file_path):
        return f"""[FAILED] FILE READ FAILED

Path: {full_file_path}
Reason: This is a directory, not a file

[IDEA] SOLUTION:
- Use list_directories() to explore directory contents
- Or specify a file name within this directory"""

    try:
        with open(full_file_path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        return f"""[FAILED] FILE READ FAILED

File: {full_file_path}
Reason: Unable to decode file as UTF-8 text

[IDEA] SUGGESTIONS:
- This might be a binary file (image, executable, etc.)
- Try checking the file type first
- Consider if this file should be opened with a different tool
- Error details: {e}"""
    except PermissionError as e:
        return f"""[FAILED] FILE READ FAILED

File: {full_file_path}
Reason: Permission denied

[IDEA] SUGGESTIONS:
- Check if you have read permissions for this file
- The file might be locked by another process
- Error details: {e}"""
    except Exception as e:
        return f"""[FAILED] FILE READ FAILED

File: {full_file_path}
Reason: Unexpected error occurred

[IDEA] SUGGESTIONS:
- Try the operation again
- Check if the file system is healthy
- Error details: {e}"""


@mcp.tool()
def check_file_exists(file_name: str, file_path: str | None = None) -> dict[str, Any]:
    """Check if a file or directory exists at the specified path and get detailed information.

    Args:
        file_name: Name of the file or directory to check (e.g., 'report.txt', 'docs/', 'az-deployment.yaml')
        file_path: Directory path where to look for the file/directory (e.g., './migration/converted').
                  If None, uses current directory ('.')

    Returns:
        Dictionary containing existence status and detailed information about the file/directory

    This is useful for:
    - Verifying files exist before attempting to read or delete them
    - Getting file information like size, type, and permissions
    - Checking directory contents before operations
    - Preventing FileNotFoundError exceptions
    """
    if file_path is None:
        file_path = "."

    full_file_path = os.path.join(file_path, file_name)

    result = {
        "file_name": file_name,
        "file_path": file_path,
        "full_path": full_file_path,
        "absolute_path": os.path.abspath(full_file_path),
        "exists": os.path.exists(full_file_path),
        "is_file": False,
        "is_directory": False,
        "is_symlink": False,
        "readable": False,
        "writable": False,
        "size_bytes": None,
        "size_human": None,
    }

    if result["exists"]:
        try:
            # Check file type
            result["is_file"] = os.path.isfile(full_file_path)
            result["is_directory"] = os.path.isdir(full_file_path)
            result["is_symlink"] = os.path.islink(full_file_path)

            # Check permissions
            result["readable"] = os.access(full_file_path, os.R_OK)
            result["writable"] = os.access(full_file_path, os.W_OK)

            # Get size information for files
            if result["is_file"]:
                try:
                    size_bytes = os.path.getsize(full_file_path)
                    result["size_bytes"] = size_bytes

                    # Human readable size
                    if size_bytes < 1024:
                        result["size_human"] = f"{size_bytes}B"
                    elif size_bytes < 1024 * 1024:
                        result["size_human"] = f"{size_bytes // 1024}KB"
                    elif size_bytes < 1024 * 1024 * 1024:
                        result["size_human"] = f"{size_bytes // (1024 * 1024)}MB"
                    else:
                        result["size_human"] = f"{size_bytes // (1024 * 1024 * 1024)}GB"

                except (OSError, PermissionError):
                    result["size_error"] = "Unable to get file size"

            # Get directory contents count for directories
            if result["is_directory"]:
                try:
                    contents = os.listdir(full_file_path)
                    files_count = len(
                        [
                            item
                            for item in contents
                            if os.path.isfile(os.path.join(full_file_path, item))
                        ]
                    )
                    dirs_count = len(
                        [
                            item
                            for item in contents
                            if os.path.isdir(os.path.join(full_file_path, item))
                        ]
                    )

                    result["directory_contents"] = {
                        "total_items": len(contents),
                        "files_count": files_count,
                        "directories_count": dirs_count,
                        "is_empty": len(contents) == 0,
                    }
                except (OSError, PermissionError):
                    result["directory_error"] = "Unable to access directory contents"

            # Add helpful suggestions based on what was found
            if result["is_file"]:
                result["suggestions"] = {
                    "read_file": f"open_file_content('{file_name}', '{file_path}')",
                    "delete_file": f"delete_file('{file_name}', '{file_path}')",
                }
            elif result["is_directory"]:
                result["suggestions"] = {
                    "list_contents": f"list_files_in_directory('{full_file_path}')",
                    "delete_directory": f"delete_folder('{file_name}', '{file_path}') # Only if empty",
                }

        except (OSError, PermissionError) as e:
            result["error"] = f"Error accessing file/directory: {e}"

    else:
        # File doesn't exist - provide helpful suggestions
        result["suggestions"] = []

        # Look for similar files in the directory
        try:
            if os.path.exists(file_path):
                items = os.listdir(file_path)
                file_name_lower = file_name.lower()

                # Find similar file names
                similar_files = []
                for item in items:
                    if (
                        file_name_lower in item.lower()
                        or item.lower() in file_name_lower
                        or abs(len(item) - len(file_name)) <= 2
                    ):  # Similar length
                        item_path = os.path.join(file_path, item)
                        item_type = "directory" if os.path.isdir(item_path) else "file"
                        similar_files.append(f"{item} ({item_type})")

                if similar_files:
                    result["similar_items"] = similar_files[:5]  # Show top 5 matches
                    result["suggestions"].append(
                        "Check the 'similar_items' list for possible matches"
                    )

                result["suggestions"].extend(
                    [
                        f"Create file: save_content_to_file('{file_name}', 'your_content', '{file_path}')",
                        f"List directory: list_files_in_directory('{file_path}')",
                    ]
                )
            else:
                result["path_error"] = f"Directory '{file_path}' does not exist"
                result["suggestions"].append(
                    f"Check if directory exists: check_file_exists('.', '{os.path.dirname(file_path)}')"
                )

        except (OSError, PermissionError):
            result["suggestions"].append(
                "Unable to scan directory for similar files due to permissions"
            )

    return result


@mcp.tool()
def list_files_in_directory(
    directory_path: str | None = None,
) -> str:
    """List all files and directories in the specified directory.

    Args:
        directory_path: Path to the directory to list (e.g., './data', '/home/user/projects').
                       If None, uses current directory ('.')

    Returns:
        Clear, human-readable string listing all files and directories with their details,
        or error message if directory cannot be accessed

    Note:
        No exceptions are raised - all errors are returned as informative messages.
    """
    if directory_path is None:
        directory_path = "."

    # Debug information
    original_path = directory_path

    # Try to resolve common container path patterns dynamically
    if not os.path.exists(directory_path):
        # Check if this looks like a container internal path
        container_path_patterns = [
            "/workspace",
            "/app",
            "/opt",
            "/usr/src",
            "/home/runner",
        ]
        is_container_path = any(
            directory_path.startswith(pattern) for pattern in container_path_patterns
        )

        if is_container_path:
            # Try to find equivalent paths in current working environment
            current_workdir = os.getcwd()

            # For /workspace patterns, try the current working directory
            if directory_path.startswith("/workspace"):
                # Extract the path after /workspace
                relative_part = directory_path.replace("/workspace", "").lstrip("/")
                if relative_part:
                    potential_path = os.path.join(current_workdir, relative_part)
                else:
                    potential_path = current_workdir

                if os.path.exists(potential_path):
                    directory_path = potential_path
                    print(
                        f"Note: Redirected container path '{original_path}' to '{directory_path}'"
                    )
                else:
                    return f"""
DIRECTORY NOT FOUND: {original_path}

Attempted to redirect container path to: {potential_path}
But this directory doesn't exist either.

Current working directory: {current_workdir}
This appears to be a container internal path that doesn't exist in the current environment.
"""

    # Final check if directory exists
    if not os.path.exists(directory_path):
        # Provide generic suggestions without hardcoded paths
        suggestions = []

        # Look for similar directory names in current directory and parent directories
        try:
            # Extract directory name from path
            target_dir_name = os.path.basename(directory_path.rstrip("/"))

            # Search in current directory
            current_items = os.listdir(".")
            matching_dirs = [
                item
                for item in current_items
                if os.path.isdir(item) and target_dir_name.lower() in item.lower()
            ]
            suggestions.extend([f"./{item}" for item in matching_dirs])

            # Search in parent directory if we're not at root
            if os.path.dirname(os.getcwd()) != os.getcwd():
                try:
                    parent_items = os.listdir("..")
                    matching_parent_dirs = [
                        item
                        for item in parent_items
                        if os.path.isdir(f"../{item}")
                        and target_dir_name.lower() in item.lower()
                    ]
                    suggestions.extend([f"../{item}" for item in matching_parent_dirs])
                except (PermissionError, OSError):
                    pass

        except (PermissionError, OSError):
            pass

        error_msg = f"""[FAILED] DIRECTORY LISTING FAILED

Directory: {directory_path}
Reason: Directory does not exist

[IDEA] SUGGESTIONS:"""
        if suggestions:
            error_msg += "\n\nDid you mean one of these similar directories?"
            for i, suggestion in enumerate(suggestions[:5], 1):
                error_msg += f"\n  {i}. {suggestion}"

        error_msg += f"\n\nCurrent working directory: {os.getcwd()}"
        error_msg += "\n\n[IDEA] ACTIONS YOU CAN TRY:"
        error_msg += "\n- Check the directory path spelling"
        error_msg += "\n- Use get_workspace_info() to see available paths"
        error_msg += (
            "\n- Try listing the current directory first with list_files_in_directory()"
        )

        return error_msg

    if not os.path.isdir(directory_path):
        return f"""[FAILED] DIRECTORY LISTING FAILED

Path: {directory_path}
Reason: This is a file, not a directory

[IDEA] SOLUTION:
- Use open_file_content() to read file contents
- Or specify a directory path instead"""

    try:
        # List all items in the directory
        all_items = os.listdir(directory_path)

        # Separate files and directories
        files = []
        directories = []

        for item in all_items:
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path):
                # Get file size for additional context
                try:
                    file_size = os.path.getsize(item_path)
                    if file_size < 1024:
                        size_str = f"{file_size}B"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size // 1024}KB"
                    else:
                        size_str = f"{file_size // (1024 * 1024)}MB"
                    files.append(f"{item} ({size_str})")
                except (OSError, PermissionError):
                    files.append(item)
            elif os.path.isdir(item_path):
                # Count items in subdirectory for context
                try:
                    subdir_count = len(os.listdir(item_path))
                    directories.append(f"{item}/ ({subdir_count} items)")
                except (OSError, PermissionError):
                    directories.append(f"{item}/")

        # Build a clear, human-readable response
        response_lines = []

        # Header with path information
        response_lines.append(f"[FOLDER] DIRECTORY LISTING: {directory_path}")
        response_lines.append(f"[PIN] Full path: {os.path.abspath(directory_path)}")

        if original_path != directory_path:
            response_lines.append(f"[PROCESSING] Redirected from: {original_path}")

        response_lines.append("")  # Empty line

        # Summary
        total_files = len(
            [f for f in all_items if os.path.isfile(os.path.join(directory_path, f))]
        )
        total_dirs = len(
            [d for d in all_items if os.path.isdir(os.path.join(directory_path, d))]
        )

        response_lines.append(
            f"[INFO] SUMMARY: {total_files} files, {total_dirs} directories, {len(all_items)} total items"
        )
        response_lines.append("")

        # List files
        if files:
            response_lines.append("[DOCUMENT] FILES:")
            for i, file_info in enumerate(sorted(files), 1):
                response_lines.append(f"  {i}. {file_info}")
        else:
            response_lines.append("[DOCUMENT] FILES: (none)")

        response_lines.append("")  # Empty line between sections

        # List directories
        if directories:
            response_lines.append("[FOLDER] DIRECTORIES:")
            for i, dir_info in enumerate(sorted(directories), 1):
                response_lines.append(f"  {i}. {dir_info}")
        else:
            response_lines.append("[FOLDER] DIRECTORIES: (none)")

        # Add helpful usage information
        if files or directories:
            response_lines.append("")
            response_lines.append("[IDEA] USAGE:")
            if files:
                first_file = files[0].split(" (")[0]  # Remove size info
                response_lines.append(
                    f"   • To read a file: open_file_content('{first_file}', '{directory_path}')"
                )
            if directories:
                first_dir = directories[0].split("/")[0]  # Remove count info
                dir_path = (
                    f"{directory_path}/{first_dir}"
                    if directory_path != "."
                    else f"./{first_dir}"
                )
                response_lines.append(
                    f"   • To explore subdirectory: list_files_in_directory('{dir_path}')"
                )

        return "\n".join(response_lines)

    except PermissionError as e:
        return f"""
[FAILED] PERMISSION DENIED

Directory: {directory_path}
Error: {e}

You don't have permission to access this directory.
Current working directory: {os.getcwd()}
"""


@mcp.tool()
def delete_file(file_name: str, file_path: str | None = None) -> str:
    """Delete a file from the specified path.

    Args:
        file_name: Name of the file to delete (e.g., 'old-config.yaml', 'temp-report.md')
        file_path: Directory path where the file is located (e.g., './migration/converted').
                  If None, uses current directory ('.')

    Returns:
        Success message confirming file deletion, or detailed error message explaining
        what went wrong and how to resolve it.

    Note:
        No exceptions are raised - all errors are returned as informative messages.
        This operation permanently deletes the specified file and cannot be undone.
    """
    if file_path is None:
        file_path = "."

    full_file_path = os.path.join(file_path, file_name)

    # Check if file exists before attempting to delete
    if not os.path.exists(full_file_path):
        return f"""ERROR: File not found: '{full_file_path}'

The file you're trying to delete doesn't exist at the specified location.

Possible solutions:
- Check if the file name is correct (case-sensitive on some systems)
- Verify the directory path is correct
- Use list_files_in_directory to see what files are available
- The file may have already been deleted

Current working directory: {os.getcwd()}
Requested file path: {os.path.abspath(full_file_path)}
"""

    if not os.path.isfile(full_file_path):
        return f"""ERROR: Path is not a file: '{full_file_path}'

The specified path exists but it's a directory, not a file.

To handle this:
- Use delete_folder() to delete directories
- Use list_files_in_directory() to see directory contents
- Check if you meant to specify a file within this directory

Path type: {"Directory" if os.path.isdir(full_file_path) else "Other"}
Current working directory: {os.getcwd()}
"""

    try:
        # Delete the file
        os.remove(full_file_path)
        return f"File successfully deleted: {os.path.abspath(full_file_path)}"
    except PermissionError as e:
        return f"""ERROR: Permission denied deleting file: '{full_file_path}'

You don't have permission to delete this file.

Troubleshooting steps:
- Check if the file is currently open in an application
- Verify you have write permissions to the directory
- Try running with elevated permissions if necessary
- Check if the file is read-only

Error details: {e}
Current working directory: {os.getcwd()}
"""
    except Exception as e:
        return f"""ERROR: Unexpected error deleting file: '{full_file_path}'

An unexpected error occurred while trying to delete the file.

Error details: {e}
Error type: {type(e).__name__}
Current working directory: {os.getcwd()}

Suggestions:
- Check if the file system is writable
- Verify the storage device has space
- Try the operation again after a moment
"""


@mcp.tool()
def delete_folder(folder_name: str, folder_path: str | None = None) -> str:
    """Delete an empty folder/directory from the specified path.

    Args:
        folder_name: Name of the folder to delete (e.g., 'temp_dir', 'old_migration')
        folder_path: Directory path where the folder is located (e.g., './cache', './working').
                    If None, uses current directory ('.')

    Returns:
        Success or error message explaining what happened and how to proceed

    Note:
        Only deletes empty directories. If the directory contains files or subdirectories,
        returns an error message with detailed contents and suggested actions.
        No exceptions are raised - all errors are returned as informative messages.
    """
    if folder_path is None:
        folder_path = "."

    full_folder_path = os.path.join(folder_path, folder_name)

    # Check if folder exists
    if not os.path.exists(full_folder_path):
        return f"""[FAILED] FOLDER DELETION FAILED

Folder: {full_folder_path}
Reason: Folder does not exist

[IDEA] SUGGESTIONS:
- Check if the folder name is spelled correctly: '{folder_name}'
- Verify the folder path is correct: '{folder_path}'
- Use list_directories() to see available folders in the path
- The folder may have already been deleted"""

    # Check if it's actually a directory
    if not os.path.isdir(full_folder_path):
        return f"""[FAILED] FOLDER DELETION FAILED

Path: {full_folder_path}
Reason: This is not a directory, it's a file

[IDEA] SOLUTION:
- Use delete_file('{folder_name}', '{folder_path}') instead to delete files
- Or check if you meant to delete a different folder"""

    # Check if directory is empty
    try:
        contents = os.listdir(full_folder_path)
        if contents:
            # Directory is not empty, provide detailed error message
            files = []
            directories = []

            for item in contents:
                item_path = os.path.join(full_folder_path, item)
                if os.path.isfile(item_path):
                    files.append(item)
                elif os.path.isdir(item_path):
                    directories.append(item)

            error_msg = f"""[FAILED] FOLDER DELETION FAILED

Folder: {full_folder_path}
Reason: Directory is not empty

[FOLDER] CONTENTS THAT MUST BE DELETED FIRST:"""

            if files:
                error_msg += f"\n\n[DOCUMENT] FILES ({len(files)}):"
                for i, file_name in enumerate(sorted(files), 1):
                    error_msg += f"\n  {i}. {file_name}"
                error_msg += f"\n\n[IDEA] Delete files using: delete_file(file_name, '{full_folder_path}')"

            if directories:
                error_msg += f"\n\n[FOLDER] SUBDIRECTORIES ({len(directories)}):"
                for i, dir_name in enumerate(sorted(directories), 1):
                    error_msg += f"\n  {i}. {dir_name}/"
                error_msg += f"\n\n[IDEA] Delete subdirectories using: delete_folder(folder_name, '{full_folder_path}')"

            error_msg += "\n\n[PROCESSING] SUGGESTED WORKFLOW:"
            error_msg += "\n1. First delete all files in the directory"
            error_msg += "\n2. Then delete all subdirectories (recursively if needed)"
            error_msg += "\n3. Finally delete the empty directory"

            return error_msg

    except PermissionError as e:
        return f"""[FAILED] FOLDER DELETION FAILED

Folder: {full_folder_path}
Reason: Permission denied

[IDEA] SUGGESTIONS:
- Check if you have write permissions to the parent directory
- The folder might be in use by another process
- Try closing any programs that might be using files in this folder
- Error details: {e}"""

    # Delete the empty directory
    try:
        os.rmdir(full_folder_path)
        return f"[SUCCESS] Folder successfully deleted: {os.path.abspath(full_folder_path)}"
    except OSError as e:
        # This shouldn't happen if we checked properly above, but just in case
        return f"""[FAILED] FOLDER DELETION FAILED

Folder: {full_folder_path}
Reason: Unexpected error during deletion

[IDEA] SUGGESTIONS:
- The folder might have become non-empty after our check
- Try running the command again
- Check if any processes are using the folder
- Error details: {e}"""


@mcp.tool()
def move_file(
    file_name: str,
    source_path: str | None = None,
    target_path: str | None = None,
    new_name: str | None = None,
) -> str:
    """Move a file from source to target location, optionally renaming it.

    Args:
        file_name: Name of the file to move (e.g., 'report.md', 'config.yaml')
        source_path: Directory path where the file currently exists (e.g., './working').
                    If None, uses current directory ('.')
        target_path: Directory path where the file should be moved to (e.g., './converted').
                    If None, uses current directory ('.')
        new_name: Optional new name for the file after moving. If None, keeps original name.

    Returns:
        Success or error message explaining what happened and the final file location

    Note:
        Creates target directory structure if it doesn't exist.
        Will fail if target file already exists to prevent accidental overwrites.
        No exceptions are raised - all errors are returned as informative messages.
    """

    if source_path is None:
        source_path = "."
    if target_path is None:
        target_path = "."

    source_file = os.path.join(source_path, file_name)
    final_name = new_name if new_name else file_name
    target_file = os.path.join(target_path, final_name)

    # Check if source file exists
    if not os.path.exists(source_file):
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Reason: Source file does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{file_name}'
- Verify the source path is correct: '{source_path}'
- Use list_files_in_directory('{source_path}') to see available files
- The file may have already been moved or deleted"""

    # Check if source is actually a file
    if not os.path.isfile(source_file):
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Reason: This is not a file, it's a directory

[IDEA] SOLUTION:
- Use list_files_in_directory() to see contents of the directory
- Or specify a file name within this directory"""

    # Check if target already exists
    if os.path.exists(target_file):
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Target: {target_file}
Reason: Target file already exists

[IDEA] SUGGESTIONS:
- Choose a different target name using the new_name parameter
- Delete the existing target file first if you want to replace it
- Use a different target directory"""

    # Create target directory if it doesn't exist
    target_dir = os.path.dirname(target_file)
    if target_dir and not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except PermissionError as e:
            return f"""[FAILED] FILE MOVE FAILED

Target directory: {target_dir}
Reason: Cannot create target directory - permission denied

[IDEA] SUGGESTIONS:
- Check if you have write permissions to create directories
- Try a different target location
- Error details: {e}"""

    # Check permissions
    if not os.access(source_file, os.R_OK):
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Reason: No read permission for source file

[IDEA] SUGGESTIONS:
- Check file permissions
- The file might be locked by another process"""

    if not os.access(os.path.dirname(source_file), os.W_OK):
        return f"""[FAILED] FILE MOVE FAILED

Source directory: {os.path.dirname(source_file)}
Reason: No write permission to remove file from source directory

[IDEA] SUGGESTIONS:
- Check directory permissions
- The directory might be read-only"""

    # Perform the move operation
    try:
        shutil.move(source_file, target_file)

        # Get file size for reporting
        try:
            size_bytes = os.path.getsize(target_file)
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes // 1024}KB"
            else:
                size_str = f"{size_bytes // (1024 * 1024)}MB"
        except:
            size_str = "unknown size"

        return f"""[SUCCESS] FILE MOVED SUCCESSFULLY

Source: {source_file}
Target: {target_file}
Size: {size_str}
Operation: File moved from '{source_path}' to '{target_path}'

[FOLDER] FINAL LOCATION: {os.path.abspath(target_file)}"""

    except PermissionError as e:
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Target: {target_file}
Reason: Permission denied during move operation

[IDEA] SUGGESTIONS:
- Check if you have write permissions to both source and target locations
- The file might be locked by another process
- Try closing any programs that might be using this file
- Error details: {e}"""

    except OSError as e:
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Target: {target_file}
Reason: System error during move operation

[IDEA] SUGGESTIONS:
- Check if there's enough disk space in the target location
- Verify the file system is healthy
- Try the operation again
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] FILE MOVE FAILED

Source: {source_file}
Target: {target_file}
Reason: Unexpected error during move operation

[IDEA] SUGGESTIONS:
- Try the operation again
- Check system resources and file system health
- Error details: {e}"""


@mcp.tool()
def clear_folder(folder_name: str, folder_path: str | None = None) -> str:
    """Clear all contents (files and subdirectories) from a folder, leaving the folder empty.

    Args:
        folder_name: Name of the folder to clear (e.g., 'temp_work', 'cache')
        folder_path: Directory path where the folder is located (e.g., './working').
                    If None, uses current directory ('.')

    Returns:
        Success or error message explaining what was deleted and the final status

    Note:
        This operation is PERMANENT and cannot be undone.
        Recursively deletes all files and subdirectories within the specified folder.
        The folder itself remains but becomes empty.
        No exceptions are raised - all errors are returned as informative messages.
    """

    if folder_path is None:
        folder_path = "."

    full_folder_path = os.path.join(folder_path, folder_name)

    # Check if folder exists
    if not os.path.exists(full_folder_path):
        return f"""[FAILED] FOLDER CLEAR FAILED

Folder: {full_folder_path}
Reason: Folder does not exist

[IDEA] SUGGESTIONS:
- Check if the folder name is spelled correctly: '{folder_name}'
- Verify the folder path is correct: '{folder_path}'
- Use list_files_in_directory('{folder_path}') to see available folders
- The folder may have already been deleted"""

    # Check if it's actually a directory
    if not os.path.isdir(full_folder_path):
        return f"""[FAILED] FOLDER CLEAR FAILED

Path: {full_folder_path}
Reason: This is not a directory, it's a file

[IDEA] SOLUTION:
- Use delete_file('{folder_name}', '{folder_path}') instead to delete files
- Or check if you meant to clear a different folder"""

    # Get inventory of what will be deleted
    try:
        contents = os.listdir(full_folder_path)
        if not contents:
            return f"""[SUCCESS] FOLDER ALREADY CLEAR

Folder: {full_folder_path}
Status: Folder is already empty

[FOLDER] FINAL STATE: Empty directory ready for use"""

        # Count files and directories
        files_count = 0
        dirs_count = 0
        total_size = 0

        files_list = []
        dirs_list = []

        for item in contents:
            item_path = os.path.join(full_folder_path, item)
            if os.path.isfile(item_path):
                files_count += 1
                files_list.append(item)
                with contextlib.suppress(Exception):
                    total_size += os.path.getsize(item_path)
            elif os.path.isdir(item_path):
                dirs_count += 1
                dirs_list.append(item)
                # Calculate directory size recursively
                try:
                    for dirpath, _dirnames, filenames in os.walk(item_path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            with contextlib.suppress(Exception):
                                total_size += os.path.getsize(filepath)
                except:
                    pass

    except PermissionError as e:
        return f"""[FAILED] FOLDER CLEAR FAILED

Folder: {full_folder_path}
Reason: Permission denied - cannot access folder contents

[IDEA] SUGGESTIONS:
- Check if you have read permissions for this folder
- The folder might be locked by another process
- Error details: {e}"""

    # Format total size
    if total_size < 1024:
        size_str = f"{total_size}B"
    elif total_size < 1024 * 1024:
        size_str = f"{total_size // 1024}KB"
    elif total_size < 1024 * 1024 * 1024:
        size_str = f"{total_size // (1024 * 1024)}MB"
    else:
        size_str = f"{total_size // (1024 * 1024 * 1024)}GB"

    # Show what will be deleted before proceeding

    # Perform the clearing operation
    deleted_files = 0
    deleted_dirs = 0
    errors = []

    try:
        for item in contents:
            item_path = os.path.join(full_folder_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    deleted_files += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_dirs += 1
            except Exception as e:
                errors.append(f"Failed to delete {item}: {e}")

        # Generate final report
        if not errors:
            return f"""[SUCCESS] FOLDER CLEARED SUCCESSFULLY

Folder: {full_folder_path}
Deleted: {deleted_files} files, {deleted_dirs} directories
Space freed: {size_str}

[FOLDER] FINAL STATE: Empty directory ready for use
[CLEANUP]  ALL CONTENTS PERMANENTLY DELETED"""

        else:
            error_details = "\n".join(f"  - {error}" for error in errors)
            return f"""[WARNING]  FOLDER PARTIALLY CLEARED

Folder: {full_folder_path}
Successfully deleted: {deleted_files} files, {deleted_dirs} directories
Space freed: {size_str}

[FAILED] ERRORS ENCOUNTERED:
{error_details}

[IDEA] SUGGESTIONS:
- Some files might be locked by running processes
- Try closing any programs that might be using files in this folder
- Run the operation again to attempt clearing remaining items"""

    except PermissionError as e:
        return f"""[FAILED] FOLDER CLEAR FAILED

Folder: {full_folder_path}
Reason: Permission denied during clearing operation

[IDEA] SUGGESTIONS:
- Check if you have write permissions to delete files in this folder
- Some files might be locked by another process
- Try closing any programs that might be using files in this folder
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] FOLDER CLEAR FAILED

Folder: {full_folder_path}
Reason: Unexpected error during clearing operation

[IDEA] SUGGESTIONS:
- Check system resources and file system health
- Try the operation again
- Error details: {e}"""


@mcp.tool()
def rename_file(current_name: str, new_name: str, file_path: str | None = None) -> str:
    """Rename a file in the same directory without moving it.

    Args:
        current_name: Current name of the file (e.g., 'old_report.md', 'temp.yaml')
        new_name: New name for the file (e.g., 'final_report.md', 'production.yaml')
        file_path: Directory path where the file is located (e.g., './converted').
                  If None, uses current directory ('.')

    Returns:
        Success or error message explaining what happened and the final file name

    Note:
        File remains in the same directory, only the name changes.
        Will fail if a file with the new name already exists to prevent accidental overwrites.
        No exceptions are raised - all errors are returned as informative messages.
    """
    import os

    if file_path is None:
        file_path = "."

    current_file = os.path.join(file_path, current_name)
    new_file = os.path.join(file_path, new_name)

    # Check if source file exists
    if not os.path.exists(current_file):
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
Reason: File does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{current_name}'
- Verify the file path is correct: '{file_path}'
- Use list_files_in_directory('{file_path}') to see available files
- The file may have already been renamed or deleted"""

    # Check if source is actually a file
    if not os.path.isfile(current_file):
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
Reason: This is not a file, it's a directory

[IDEA] SOLUTION:
- Use list_files_in_directory() to see contents of the directory
- Files and directories cannot be renamed with this function
- Or specify a file name within this directory"""

    # Check if target name already exists
    if os.path.exists(new_file):
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
New name: {new_file}
Reason: A file with the new name already exists

[IDEA] SUGGESTIONS:
- Choose a different new name
- Delete the existing file first if you want to replace it: delete_file('{new_name}', '{file_path}')
- Use move_file() if you want to move to a different directory"""

    # Validate new name doesn't contain path separators
    if os.sep in new_name or (os.altsep and os.altsep in new_name):
        return f"""[FAILED] FILE RENAME FAILED

New name: {new_name}
Reason: New name contains directory separators (/ or \\)

[IDEA] SOLUTION:
- Use only the file name without path separators
- If you want to move to a different directory, use move_file() instead
- Example: rename_file('old.txt', 'new.txt', './directory')"""

    # Check permissions
    if not os.access(current_file, os.R_OK):
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
Reason: No read permission for current file

[IDEA] SUGGESTIONS:
- Check file permissions
- The file might be locked by another process"""

    if not os.access(os.path.dirname(current_file), os.W_OK):
        return f"""[FAILED] FILE RENAME FAILED

Directory: {os.path.dirname(current_file)}
Reason: No write permission to rename file in this directory

[IDEA] SUGGESTIONS:
- Check directory permissions
- The directory might be read-only"""

    # Perform the rename operation
    try:
        os.rename(current_file, new_file)

        # Get file size for reporting
        try:
            size_bytes = os.path.getsize(new_file)
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes // 1024}KB"
            else:
                size_str = f"{size_bytes // (1024 * 1024)}MB"
        except:
            size_str = "unknown size"

        return f"""[SUCCESS] FILE RENAMED SUCCESSFULLY

Original: {current_name}
New name: {new_name}
Location: {file_path}
Size: {size_str}

[FOLDER] FULL PATH: {os.path.abspath(new_file)}"""

    except PermissionError as e:
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
New name: {new_file}
Reason: Permission denied during rename operation

[IDEA] SUGGESTIONS:
- Check if you have write permissions to the directory
- The file might be locked by another process
- Try closing any programs that might be using this file
- Error details: {e}"""

    except OSError as e:
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
New name: {new_file}
Reason: System error during rename operation

[IDEA] SUGGESTIONS:
- Check if the file system supports the new file name
- Verify the file system is healthy
- Some characters might not be allowed in file names
- Try the operation again
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] FILE RENAME FAILED

Current file: {current_file}
New name: {new_file}
Reason: Unexpected error during rename operation

[IDEA] SUGGESTIONS:
- Try the operation again
- Check system resources and file system health
- Error details: {e}"""


@mcp.tool()
def get_workspace_info() -> dict[str, any]:
    """Get information about the current workspace structure and common paths.

    Returns:
        Dictionary containing workspace information, common paths, and directory listings

    This is helpful for understanding the workspace structure and finding the right paths.
    """
    current_dir = os.getcwd()

    # Dynamic path discovery - no hardcoded paths
    workspace_info = {
        "current_directory": {
            "path": ".",
            "absolute_path": current_dir,
            "exists": True,
            "is_directory": True,
        }
    }

    # Get current directory contents
    try:
        items = os.listdir(".")
        files = []
        directories = []

        for item in items:
            if os.path.isfile(item):
                files.append(item)
            elif os.path.isdir(item):
                directories.append(item)

        workspace_info["current_directory"].update(
            {
                "files": sorted(files)[:10],  # Show first 10 files
                "directories": sorted(directories),
                "total_files": len(files),
                "total_directories": len(directories),
            }
        )

        if len(files) > 10:
            workspace_info["current_directory"]["note"] = (
                f"Showing first 10 of {len(files)} files"
            )

    except PermissionError:
        workspace_info["current_directory"]["error"] = "Permission denied"

    # Discover common directory types dynamically
    common_directory_patterns = {
        "source_code": ["src", "source", "code", "lib", "libs"],
        "documentation": ["docs", "doc", "documentation", "readme"],
        "tests": ["test", "tests", "testing", "__tests__"],
        "configuration": ["config", "conf", "settings", ".vscode", ".git"],
        "data": ["data", "datasets", "files", "assets"],
        "output": ["output", "out", "build", "dist", "target"],
        "migration": ["migration", "migrate", "transform", "convert"],
    }

    discovered_directories = {}

    try:
        current_items = os.listdir(".")
        for category, patterns in common_directory_patterns.items():
            matching_dirs = []
            for item in current_items:
                if os.path.isdir(item):
                    item_lower = item.lower()
                    if any(pattern in item_lower for pattern in patterns):
                        matching_dirs.append(item)

            if matching_dirs:
                discovered_directories[category] = matching_dirs

    except PermissionError:
        pass

    # Check parent directory info (if accessible)
    parent_info = None
    try:
        parent_dir = os.path.dirname(current_dir)
        if parent_dir != current_dir:  # Not at filesystem root
            parent_info = {
                "path": "..",
                "absolute_path": parent_dir,
                "exists": os.path.exists(".."),
                "accessible": True,
            }
            try:
                parent_items = os.listdir("..")
                parent_dirs = [
                    item for item in parent_items if os.path.isdir(f"../{item}")
                ]
                parent_info["directories"] = sorted(parent_dirs)[:10]
                if len(parent_dirs) > 10:
                    parent_info["note"] = (
                        f"Showing first 10 of {len(parent_dirs)} directories"
                    )
            except PermissionError:
                parent_info["accessible"] = False
                parent_info["error"] = "Permission denied"
    except Exception:
        pass

    return {
        "workspace_structure": workspace_info,
        "discovered_directories": discovered_directories,
        "parent_directory": parent_info,
        "helpful_commands": {
            "list_current_directory": "list_files_in_directory('.')",
            "list_parent_directory": "list_files_in_directory('..')",
            "check_file_exists": "check_file_exists('filename.txt', '.')",
            "save_to_current": "save_content_to_file('filename.txt', content, '.')",
            "explore_subdirectory": "list_files_in_directory('./subdirectory_name')",
            "delete_empty_folder": "delete_folder('folder_name', './parent_directory')",
            "move_file_to_folder": "move_file('filename.txt', './source', './target')",
            "move_and_rename": "move_file('old.txt', './source', './target', 'new.txt')",
            "clear_working_folder": "clear_folder('temp_work', './cache')",
        },
        "navigation_tips": [
            "Use '.' for current directory, '..' for parent directory",
            "Always check file existence with check_file_exists() before delete/read operations",
            "Relative paths like './subdirectory' work from current location",
            "Absolute paths start with '/' (Unix) or 'C:\\' (Windows)",
            "The function will suggest similar directory names if path not found",
            "Use move_file() to organize files between directories (safer than delete+save)",
            "Use clear_folder() to completely empty working directories when cleaning up",
        ],
    }


@mcp.tool()
def generate_git_diff(
    source_file: str | None = None,
    target_file: str | None = None,
    source_path: str | None = None,
    target_path: str | None = None,
) -> str:
    """Generate professional git-style diff between two files with comprehensive analysis.

    Args:
        source_file: Name of the original file (e.g., 'original.yaml', 'old-deployment.yaml')
        target_file: Name of the modified file (e.g., 'converted.yaml', 'new-deployment.yaml')
        source_path: Directory path where the source file is located (e.g., './working').
                    If None, uses current directory ('.')
        target_path: Directory path where the target file is located (e.g., './converted').
                    If None, uses current directory ('.')

    Returns:
        Professional git-style diff with statistics, change analysis, and enterprise formatting
        suitable for migration reports and technical documentation

    Note:
        Generates unified diff format with context lines, line numbers, and change statistics.
        Includes comprehensive analysis of additions, deletions, and modifications.
        Returns detailed error messages with suggestions if files cannot be compared.
    """
    if source_path is None:
        source_path = "."
    if target_path is None:
        target_path = "."

    # Handle case where we're comparing the same file in different locations
    if source_file is None and target_file is None:
        return """[FAILED] GIT DIFF GENERATION FAILED

Reason: Both source_file and target_file are required

[IDEA] USAGE EXAMPLES:
- generate_git_diff('original.yaml', 'converted.yaml') -> compare files in current directory
- generate_git_diff('app.yaml', 'app.yaml', './working', './converted') -> same file, different locations
- generate_git_diff('old-config.yml', 'new-config.yml', './source', './target') -> different files, different locations"""

    if source_file is None:
        source_file = target_file
    if target_file is None:
        target_file = source_file

    source_full_path = os.path.join(source_path, source_file)
    target_full_path = os.path.join(target_path, target_file)

    # Verify both files exist
    if not os.path.exists(source_full_path):
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Source file: {source_full_path}
Reason: Source file does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{source_file}'
- Verify the source path is correct: '{source_path}'
- Use list_files_in_directory('{source_path}') to see available files"""

    if not os.path.exists(target_full_path):
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Target file: {target_full_path}
Reason: Target file does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{target_file}'
- Verify the target path is correct: '{target_path}'
- Use list_files_in_directory('{target_path}') to see available files"""

    # Check if both are actually files
    if not os.path.isfile(source_full_path):
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Source: {source_full_path}
Reason: This is not a file, it's a directory

[IDEA] SOLUTION:
- Specify a file name within this directory"""

    if not os.path.isfile(target_full_path):
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Target: {target_full_path}
Reason: This is not a file, it's a directory

[IDEA] SOLUTION:
- Specify a file name within this directory"""

    try:
        # Read both files
        with open(source_full_path, encoding="utf-8") as f:
            source_content = f.readlines()
        with open(target_full_path, encoding="utf-8") as f:
            target_content = f.readlines()

        # Generate unified diff using git diff format
        import difflib

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create file headers with git-style paths
        source_label = f"a/{source_file}"
        target_label = f"b/{target_file}"

        if source_path != target_path:
            source_label = f"a/{source_path}/{source_file}".replace("./", "")
            target_label = f"b/{target_path}/{target_file}".replace("./", "")

        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                source_content,
                target_content,
                fromfile=source_label,
                tofile=target_label,
                lineterm="",
                n=3,  # 3 lines of context
            )
        )

        # Calculate statistics
        additions = sum(
            1
            for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1
            for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        )
        source_lines = len(source_content)
        target_lines = len(target_content)

        # Check if files are identical
        if not diff_lines:
            return f"""[SUCCESS] FILES ARE IDENTICAL

Source: {source_full_path}
Target: {target_full_path}
Lines: {source_lines}
Status: No differences found

[INFO] COMPARISON SUMMARY:
- Files have identical content
- Total lines: {source_lines}
- Generated on: {timestamp}"""

        # Build comprehensive diff report
        diff_report = []

        # Header with file information
        diff_report.append("=" * 80)
        diff_report.append("[PROCESSING] ENTERPRISE GIT DIFF ANALYSIS")
        diff_report.append("=" * 80)
        diff_report.append("")
        diff_report.append(f"[CALENDAR] Generated: {timestamp}")
        diff_report.append(f"[FOLDER] Source: {source_full_path}")
        diff_report.append(f"[FOLDER] Target: {target_full_path}")
        diff_report.append("")

        # Statistics summary
        diff_report.append("[INFO] DIFF STATISTICS:")
        diff_report.append(f"  • Source lines: {source_lines:,}")
        diff_report.append(f"  • Target lines: {target_lines:,}")
        diff_report.append(f"  • Lines added: +{additions:,}")
        diff_report.append(f"  • Lines removed: -{deletions:,}")
        diff_report.append(f"  • Net change: {target_lines - source_lines:+,}")

        # Change percentage
        if source_lines > 0:
            change_percent = ((additions + deletions) / source_lines) * 100
            diff_report.append(f"  • Change percentage: {change_percent:.1f}%")
        diff_report.append("")

        # Change analysis
        diff_report.append("[SEARCH] CHANGE ANALYSIS:")
        if additions > deletions:
            diff_report.append(
                f"  • Net additions: Content expanded by {additions - deletions} lines"
            )
        elif deletions > additions:
            diff_report.append(
                f"  • Net deletions: Content reduced by {deletions - additions} lines"
            )
        else:
            diff_report.append("  • Balanced changes: Equal additions and deletions")

        # Identify major change patterns
        config_changes = sum(
            1
            for line in diff_lines
            if ("config" in line.lower() or "setting" in line.lower())
            and (line.startswith("+") or line.startswith("-"))
        )
        if config_changes > 0:
            diff_report.append(
                f"  • Configuration changes detected: {config_changes} lines"
            )

        diff_report.append("")

        # The actual diff content
        diff_report.append("[NOTES] UNIFIED DIFF:")
        diff_report.append("-" * 60)

        if diff_lines:
            diff_report.extend(diff_lines)

        diff_report.append("-" * 60)
        diff_report.append("")

        # Summary and recommendations
        diff_report.append("[IDEA] MIGRATION INSIGHTS:")
        if change_percent > 50:
            diff_report.append(
                "  [WARNING]  MAJOR TRANSFORMATION: Over 50% of content modified"
            )
            diff_report.append("  [CLIPBOARD] Recommendation: Thorough testing required")
        elif change_percent > 20:
            diff_report.append(
                "  [INFO] SIGNIFICANT CHANGES: Moderate transformation detected"
            )
            diff_report.append("  [CLIPBOARD] Recommendation: Careful validation needed")
        else:
            diff_report.append("  [SUCCESS] MINOR CHANGES: Limited modifications detected")
            diff_report.append("  [CLIPBOARD] Recommendation: Standard validation sufficient")

        diff_report.append("")
        diff_report.append("=" * 80)

        return "\n".join(diff_report)

    except UnicodeDecodeError as e:
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Source: {source_full_path}
Target: {target_full_path}
Reason: Unable to decode files as UTF-8 text

[IDEA] SUGGESTIONS:
- Files might be binary (images, executables, etc.)
- Try with text files only
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] GIT DIFF GENERATION FAILED

Source: {source_full_path}
Target: {target_full_path}
Reason: Unexpected error during diff generation

[IDEA] SUGGESTIONS:
- Check if files are accessible and readable
- Verify files contain valid text content
- Error details: {e}"""


@mcp.tool()
def analyze_file_quality(
    file_name: str,
    file_path: str | None = None,
    quality_standards: dict[str, Any] | None = None,
) -> str:
    """Comprehensive file analysis with enterprise quality metrics and validation.

    Args:
        file_name: Name of the file to analyze (e.g., 'migration_report.md', 'deployment.yaml')
        file_path: Directory path where the file is located (e.g., './converted').
                  If None, uses current directory ('.')
        quality_standards: Optional dictionary with quality criteria:
                          {"minimum_lines": 500, "required_sections": ["Executive Summary"],
                           "forbidden_words": ["TODO", "FIXME"], "max_line_length": 120}

    Returns:
        Comprehensive file quality analysis including structure, content metrics,
        compliance checks, and improvement recommendations

    Note:
        Analyzes file structure, content quality, readability metrics, and compliance
        with enterprise documentation standards. Provides actionable recommendations.
    """
    if file_path is None:
        file_path = "."

    full_file_path = os.path.join(file_path, file_name)

    # Check if file exists
    if not os.path.exists(full_file_path):
        return f"""[FAILED] FILE ANALYSIS FAILED

File: {full_file_path}
Reason: File does not exist

[IDEA] SUGGESTIONS:
- Check if the file name is spelled correctly: '{file_name}'
- Verify the file path is correct: '{file_path}'
- Use list_files_in_directory('{file_path}') to see available files"""

    if not os.path.isfile(full_file_path):
        return f"""[FAILED] FILE ANALYSIS FAILED

Path: {full_file_path}
Reason: This is not a file, it's a directory

[IDEA] SOLUTION:
- Specify a file name within this directory"""

    # Set default quality standards
    if quality_standards is None:
        quality_standards = {
            "minimum_lines": 100,
            "required_sections": ["Summary", "Overview"],
            "forbidden_words": ["TODO", "FIXME", "PLACEHOLDER"],
            "max_line_length": 120,
            "minimum_words": 500,
        }

    try:
        # Read and analyze file content
        with open(full_file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()

        file_size = os.path.getsize(full_file_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Basic metrics
        line_count = len(lines)
        word_count = len(content.split())
        char_count = len(content)
        non_empty_lines = len([line for line in lines if line.strip()])
        empty_lines = line_count - non_empty_lines

        # File extension analysis
        file_ext = os.path.splitext(file_name)[1].lower()
        file_type = {
            ".md": "Markdown Documentation",
            ".txt": "Text Document",
            ".yaml": "YAML Configuration",
            ".yml": "YAML Configuration",
            ".json": "JSON Configuration",
            ".py": "Python Source Code",
            ".js": "JavaScript Source Code",
            ".html": "HTML Document",
            ".xml": "XML Document",
        }.get(file_ext, f"Unknown ({file_ext})")

        # Build comprehensive analysis report
        analysis_report = []

        # Header
        analysis_report.append("=" * 90)
        analysis_report.append("[INFO] ENTERPRISE FILE QUALITY ANALYSIS")
        analysis_report.append("=" * 90)
        analysis_report.append("")
        analysis_report.append(f"[CALENDAR] Analysis Date: {timestamp}")
        analysis_report.append(f"[FOLDER] File Location: {full_file_path}")
        analysis_report.append(f"[DOCUMENT] File Type: {file_type}")
        analysis_report.append(f"[SAVE] File Size: {file_size:,} bytes")
        analysis_report.append("")

        # Basic content metrics
        analysis_report.append("[TRENDING_UP] CONTENT METRICS:")
        analysis_report.append(f"  • Total lines: {line_count:,}")
        analysis_report.append(f"  • Content lines: {non_empty_lines:,}")
        analysis_report.append(f"  • Empty lines: {empty_lines:,}")
        analysis_report.append(f"  • Word count: {word_count:,}")
        analysis_report.append(f"  • Character count: {char_count:,}")
        analysis_report.append(
            f"  • Average words per line: {word_count / non_empty_lines:.1f}"
            if non_empty_lines > 0
            else "  • Average words per line: 0"
        )
        analysis_report.append("")

        # Line length analysis
        line_lengths = [len(line) for line in lines]
        max_line_length = max(line_lengths) if line_lengths else 0
        avg_line_length = sum(line_lengths) / len(line_lengths) if line_lengths else 0
        long_lines = sum(
            1
            for length in line_lengths
            if length > quality_standards.get("max_line_length", 120)
        )

        analysis_report.append("[RULER] LINE ANALYSIS:")
        analysis_report.append(f"  • Maximum line length: {max_line_length}")
        analysis_report.append(f"  • Average line length: {avg_line_length:.1f}")
        analysis_report.append(
            f"  • Lines exceeding {quality_standards.get('max_line_length', 120)} chars: {long_lines}"
        )
        analysis_report.append("")

        # Quality compliance check
        analysis_report.append("[SUCCESS] QUALITY COMPLIANCE:")
        compliance_score = 100
        issues = []

        # Check minimum lines requirement
        min_lines = quality_standards.get("minimum_lines", 100)
        if line_count < min_lines:
            issues.append(
                f"[FAILED] Document too short: {line_count} lines (minimum: {min_lines})"
            )
            compliance_score -= 20
        else:
            analysis_report.append(
                f"  [SUCCESS] Line count requirement: {line_count:,} ≥ {min_lines}"
            )

        # Check minimum words requirement
        min_words = quality_standards.get("minimum_words", 500)
        if word_count < min_words:
            issues.append(
                f"[FAILED] Content too brief: {word_count} words (minimum: {min_words})"
            )
            compliance_score -= 15
        else:
            analysis_report.append(
                f"  [SUCCESS] Word count requirement: {word_count:,} ≥ {min_words}"
            )

        # Check for required sections (if Markdown)
        required_sections = quality_standards.get("required_sections", [])
        if file_ext in [".md", ".txt"] and required_sections:
            content_lower = content.lower()
            missing_sections = []
            for section in required_sections:
                if section.lower() not in content_lower:
                    missing_sections.append(section)

            if missing_sections:
                issues.append(
                    f"[FAILED] Missing required sections: {', '.join(missing_sections)}"
                )
                compliance_score -= 15
            else:
                analysis_report.append(
                    f"  [SUCCESS] Required sections present: {', '.join(required_sections)}"
                )

        # Check for forbidden words
        forbidden_words = quality_standards.get("forbidden_words", [])
        found_forbidden = []
        for word in forbidden_words:
            if word.upper() in content.upper():
                found_forbidden.append(word)

        if found_forbidden:
            issues.append(f"[FAILED] Forbidden words found: {', '.join(found_forbidden)}")
            compliance_score -= 10
        else:
            analysis_report.append("  [SUCCESS] No forbidden words detected")

        # Check line length compliance
        if long_lines > 0:
            issues.append(
                f"[FAILED] {long_lines} lines exceed maximum length of {quality_standards.get('max_line_length', 120)} characters"
            )
            compliance_score -= 5

        # Overall compliance score
        compliance_score = max(0, compliance_score)
        analysis_report.append(f"  [INFO] Overall Compliance Score: {compliance_score}/100")
        analysis_report.append("")

        # Content structure analysis (for Markdown)
        if file_ext == ".md":
            analysis_report.append("[NOTES] MARKDOWN STRUCTURE:")
            headers = [line for line in lines if line.strip().startswith("#")]
            code_blocks = content.count("```")
            links = content.count("](")
            lists = len(
                [
                    line
                    for line in lines
                    if line.strip().startswith(("- ", "* ", "+ "))
                    or line.strip().startswith(tuple(f"{i}." for i in range(10)))
                ]
            )

            analysis_report.append(f"  • Headers: {len(headers)}")
            analysis_report.append(
                f"  • Code blocks: {code_blocks // 2}"
            )  # Pairs of ```
            analysis_report.append(f"  • Links: {links}")
            analysis_report.append(f"  • List items: {lists}")

            if headers:
                analysis_report.append("  • Document outline:")
                for header in headers[:10]:  # Show first 10 headers
                    analysis_report.append(f"    {header}")
                if len(headers) > 10:
                    analysis_report.append(f"    ... and {len(headers) - 10} more")
            analysis_report.append("")

        # Issues and recommendations
        if issues:
            analysis_report.append("[WARNING]  QUALITY ISSUES IDENTIFIED:")
            for issue in issues:
                analysis_report.append(f"  {issue}")
            analysis_report.append("")

        analysis_report.append("[IDEA] IMPROVEMENT RECOMMENDATIONS:")
        if compliance_score < 70:
            analysis_report.append(
                "  [ALERT] CRITICAL: Document requires significant improvement"
            )
            if line_count < min_lines:
                analysis_report.append(
                    f"    • Expand content to meet {min_lines} line minimum"
                )
            if word_count < min_words:
                analysis_report.append(
                    f"    • Add detailed content to reach {min_words} word minimum"
                )
            if found_forbidden:
                analysis_report.append(
                    "    • Replace placeholder text with final content"
                )
        elif compliance_score < 85:
            analysis_report.append("  [WARNING]  MODERATE: Document needs some improvements")
            analysis_report.append("    • Address compliance issues listed above")
            analysis_report.append("    • Review content structure and organization")
        else:
            analysis_report.append(
                "  [SUCCESS] EXCELLENT: Document meets enterprise quality standards"
            )
            analysis_report.append("    • Consider final review and formatting check")

        # Add specific recommendations based on file type
        if file_ext == ".md":
            analysis_report.append(
                "    • Ensure proper heading hierarchy (H1 → H2 → H3)"
            )
            analysis_report.append(
                "    • Include executive summary for enterprise reports"
            )

        analysis_report.append("")
        analysis_report.append("=" * 90)

        return "\n".join(analysis_report)

    except UnicodeDecodeError as e:
        return f"""[FAILED] FILE ANALYSIS FAILED

File: {full_file_path}
Reason: Unable to decode file as UTF-8 text

[IDEA] SUGGESTIONS:
- File might be binary (image, executable, etc.)
- Try with text files only
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] FILE ANALYSIS FAILED

File: {full_file_path}
Reason: Unexpected error during analysis

[IDEA] SUGGESTIONS:
- Check if file is accessible and readable
- Try the analysis again
- Error details: {e}"""


@mcp.tool()
def verify_directory_cleanup(
    directory_path: str | None = None, cleanup_report: bool = True
) -> str:
    """Verify directory cleanup and generate comprehensive cleanup verification report.

    Args:
        directory_path: Path to directory to verify cleanup (e.g., './working', './temp').
                       If None, verifies current directory ('.')
        cleanup_report: Whether to generate detailed cleanup verification report.
                       If False, returns simple status only.

    Returns:
        Comprehensive cleanup verification report with directory status, remaining files,
        cleanup recommendations, and compliance assessment

    Note:
        Analyzes directory for remaining working files, temporary content, and cleanup completeness.
        Identifies files that should typically be cleaned up in migration workflows.
        Provides specific cleanup recommendations for enterprise compliance.
    """
    if directory_path is None:
        directory_path = "."

    if not os.path.exists(directory_path):
        return f"""[FAILED] CLEANUP VERIFICATION FAILED

Directory: {directory_path}
Reason: Directory does not exist

[IDEA] SUGGESTIONS:
- Check if the directory path is correct
- Use list_files_in_directory('./') to see available directories
- Directory may have already been deleted"""

    if not os.path.isdir(directory_path):
        return f"""[FAILED] CLEANUP VERIFICATION FAILED

Path: {directory_path}
Reason: This is not a directory, it's a file

[IDEA] SOLUTION:
- Specify a directory path for cleanup verification"""

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Recursively scan directory
        all_files = []
        all_dirs = []
        total_size = 0

        for root, dirs, files in os.walk(directory_path):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                rel_path = os.path.relpath(dir_path, directory_path)
                all_dirs.append(rel_path)

            for file_name in files:
                file_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(file_path, directory_path)
                try:
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    all_files.append(
                        {
                            "path": rel_path,
                            "size": file_size,
                            "name": file_name,
                            "directory": os.path.dirname(rel_path)
                            if os.path.dirname(rel_path) != "."
                            else "root",
                        }
                    )
                except (OSError, PermissionError):
                    all_files.append(
                        {
                            "path": rel_path,
                            "size": 0,
                            "name": file_name,
                            "directory": os.path.dirname(rel_path)
                            if os.path.dirname(rel_path) != "."
                            else "root",
                            "error": "Cannot access file",
                        }
                    )

        # Categorize files by cleanup priority
        working_files = []
        temp_files = []
        log_files = []
        backup_files = []
        config_files = []
        permanent_files = []

        # Define patterns for file categorization
        working_patterns = [
            "working",
            "temp",
            "tmp",
            "scratch",
            "draft",
            "wip",
            "migrate",
            "convert",
            "transform",
            "process",
        ]
        temp_patterns = [".tmp", ".temp", ".bak", ".backup", ".orig", ".cache"]
        log_patterns = [".log", ".logs", "debug", "trace", "output"]
        backup_patterns = [".backup", ".bak", ".orig", ".old", "_backup", "_old"]
        config_patterns = [".env", ".config", ".settings", ".properties"]

        for file_info in all_files:
            file_name = file_info["name"].lower()
            file_path = file_info["path"].lower()

            # Categorize files
            if any(pattern in file_path for pattern in working_patterns):
                working_files.append(file_info)
            elif any(file_name.endswith(pattern) for pattern in temp_patterns):
                temp_files.append(file_info)
            elif any(pattern in file_name for pattern in log_patterns):
                log_files.append(file_info)
            elif any(file_name.endswith(pattern) for pattern in backup_patterns):
                backup_files.append(file_info)
            elif any(pattern in file_name for pattern in config_patterns):
                config_files.append(file_info)
            else:
                permanent_files.append(file_info)

        # Format file size
        if total_size < 1024:
            size_str = f"{total_size}B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size // 1024}KB"
        elif total_size < 1024 * 1024 * 1024:
            size_str = f"{total_size // (1024 * 1024)}MB"
        else:
            size_str = f"{total_size // (1024 * 1024 * 1024)}GB"

        # Build cleanup verification report
        if not cleanup_report:
            # Simple status only
            total_items = len(all_files) + len(all_dirs)
            cleanup_items = (
                len(working_files)
                + len(temp_files)
                + len(log_files)
                + len(backup_files)
            )

            if total_items == 0:
                return f"[SUCCESS] DIRECTORY CLEAN: {directory_path} is empty"
            elif cleanup_items == 0:
                return f"[SUCCESS] CLEANUP VERIFIED: {directory_path} contains {len(permanent_files)} permanent files, no cleanup needed"
            else:
                return f"[WARNING] CLEANUP REQUIRED: {directory_path} contains {cleanup_items} items requiring cleanup"

        # Generate comprehensive report
        report = []

        # Header
        report.append("=" * 100)
        report.append("[CLEANUP] ENTERPRISE DIRECTORY CLEANUP VERIFICATION")
        report.append("=" * 100)
        report.append("")
        report.append(f"[CALENDAR] Verification Date: {timestamp}")
        report.append(f"[FOLDER] Directory: {os.path.abspath(directory_path)}")
        report.append("")

        # Directory summary
        report.append("[INFO] DIRECTORY SUMMARY:")
        report.append(f"  • Total files: {len(all_files):,}")
        report.append(f"  • Total directories: {len(all_dirs):,}")
        report.append(f"  • Total size: {size_str}")
        report.append("")

        # Cleanup analysis
        total_cleanup_items = (
            len(working_files) + len(temp_files) + len(log_files) + len(backup_files)
        )

        report.append("[SEARCH] CLEANUP ANALYSIS:")
        report.append(f"  • Working files: {len(working_files)}")
        report.append(f"  • Temporary files: {len(temp_files)}")
        report.append(f"  • Log files: {len(log_files)}")
        report.append(f"  • Backup files: {len(backup_files)}")
        report.append(f"  • Configuration files: {len(config_files)}")
        report.append(f"  • Permanent files: {len(permanent_files)}")
        report.append(f"  • Items requiring cleanup: {total_cleanup_items}")
        report.append("")

        # Cleanup status assessment
        if total_cleanup_items == 0:
            if len(all_files) == 0:
                report.append("[SUCCESS] CLEANUP STATUS: PERFECT")
                report.append("  • Directory is completely empty")
                report.append("  • No files require cleanup")
                report.append("  • Ready for next phase")
            else:
                report.append("[SUCCESS] CLEANUP STATUS: VERIFIED")
                report.append("  • No working or temporary files found")
                report.append("  • Only permanent files remain")
                report.append("  • Cleanup requirements satisfied")
        else:
            cleanup_percentage = (
                (total_cleanup_items / len(all_files)) * 100
                if len(all_files) > 0
                else 0
            )

            if cleanup_percentage > 50:
                report.append("[FAILED] CLEANUP STATUS: INCOMPLETE")
                report.append(f"  • {cleanup_percentage:.1f}% of files require cleanup")
                report.append("  • Significant cleanup work remaining")
                report.append("  • Directory not ready for next phase")
            elif cleanup_percentage > 10:
                report.append("[WARNING] CLEANUP STATUS: PARTIAL")
                report.append(f"  • {cleanup_percentage:.1f}% of files require cleanup")
                report.append("  • Minor cleanup work remaining")
                report.append("  • Review required before next phase")
            else:
                report.append("[SUCCESS] CLEANUP STATUS: MOSTLY CLEAN")
                report.append(
                    f"  • Only {cleanup_percentage:.1f}% of files require cleanup"
                )
                report.append("  • Minimal cleanup work remaining")

        # Detailed file listings
        def format_file_list(file_list, title):
            if not file_list:
                return []

            lines = [f"[CLIPBOARD] {title} ({len(file_list)} items):"]
            for file_info in sorted(file_list, key=lambda x: x["path"]):
                size_info = ""
                if file_info["size"] > 0:
                    if file_info["size"] < 1024:
                        size_info = f" ({file_info['size']}B)"
                    elif file_info["size"] < 1024 * 1024:
                        size_info = f" ({file_info['size'] // 1024}KB)"
                    else:
                        size_info = f" ({file_info['size'] // (1024 * 1024)}MB)"

                error_info = (
                    f" [ERROR: {file_info['error']}]" if "error" in file_info else ""
                )
                lines.append(f"  • {file_info['path']}{size_info}{error_info}")
            lines.append("")
            return lines

        # Add detailed file listings if items exist
        if working_files:
            report.extend(
                format_file_list(working_files, "WORKING FILES REQUIRING CLEANUP")
            )
        if temp_files:
            report.extend(
                format_file_list(temp_files, "TEMPORARY FILES REQUIRING CLEANUP")
            )
        if log_files:
            report.extend(format_file_list(log_files, "LOG FILES FOR REVIEW"))
        if backup_files:
            report.extend(format_file_list(backup_files, "BACKUP FILES FOR REVIEW"))

        # Cleanup recommendations
        report.append("[IDEA] CLEANUP RECOMMENDATIONS:")
        if total_cleanup_items == 0:
            report.append("  [SUCCESS] No cleanup actions required")
            report.append("  [SUCCESS] Directory meets enterprise cleanup standards")
        else:
            if working_files:
                report.append(f"  [CLEANUP]  Delete {len(working_files)} working files:")
                for file_info in working_files[:5]:  # Show first 5
                    report.append(
                        f"      delete_file('{file_info['name']}', '{os.path.dirname(os.path.join(directory_path, file_info['path']))}')"
                    )
                if len(working_files) > 5:
                    report.append(
                        f"      ... and {len(working_files) - 5} more working files"
                    )

            if temp_files:
                report.append(f"  [CLEANUP]  Delete {len(temp_files)} temporary files:")
                for file_info in temp_files[:3]:
                    report.append(
                        f"      delete_file('{file_info['name']}', '{os.path.dirname(os.path.join(directory_path, file_info['path']))}')"
                    )

            if log_files:
                report.append(f"  [CLIPBOARD] Review {len(log_files)} log files before deletion")

            if backup_files:
                report.append(
                    f"  [CLIPBOARD] Review {len(backup_files)} backup files - may be safely deleted"
                )

            # Bulk cleanup suggestion
            if total_cleanup_items > 10:
                report.append(
                    f"  [PROCESSING] Consider bulk cleanup: clear_folder('{os.path.basename(directory_path)}', '{os.path.dirname(directory_path) if os.path.dirname(directory_path) else '.'}')"
                )

        report.append("")
        report.append("=" * 100)

        return "\n".join(report)

    except PermissionError as e:
        return f"""[FAILED] CLEANUP VERIFICATION FAILED

Directory: {directory_path}
Reason: Permission denied

[IDEA] SUGGESTIONS:
- Check if you have read permissions for this directory
- Directory might be locked by another process
- Error details: {e}"""

    except Exception as e:
        return f"""[FAILED] CLEANUP VERIFICATION FAILED

Directory: {directory_path}
Reason: Unexpected error during verification

[IDEA] SUGGESTIONS:
- Check if directory is accessible
- Try the verification again
- Error details: {e}"""


# =====================================================================================
# HIGH PRIORITY FUNCTIONS - Essential for model file/folder control
# =====================================================================================


@mcp.tool()
def create_directory(dir_name: str, dir_path: str | None = None) -> str:
    """
    Create a new directory at specified path.

    Args:
        dir_name: Name of the directory to create
        dir_path: Optional path where to create directory (default: current directory)

    Returns:
        Success message with full directory path or error message
    """
    try:
        # Use current directory if no path specified
        if dir_path is None:
            dir_path = os.getcwd()

        # Resolve container paths
        if dir_path.startswith("/workspace"):
            dir_path = dir_path.replace("/workspace", os.getcwd(), 1)

        full_path = os.path.join(dir_path, dir_name)

        # Create directory (including parent directories if needed)
        os.makedirs(full_path, exist_ok=True)

        return f"""[SUCCESS] DIRECTORY CREATED SUCCESSFULLY

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Full Path: {os.path.abspath(full_path)}
[TARGET] Operation: New directory structure created

[IDEA] NEXT STEPS:
- Directory is ready for file operations
- Use save_content_to_file() to add files
- Use list_files_in_directory() to verify contents"""

    except PermissionError:
        return f"""[FAILED] DIRECTORY CREATION FAILED

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Target Path: {dir_path}
[NO_ENTRY] Error: Permission denied

[IDEA] SUGGESTIONS:
- Check directory write permissions
- Try a different target location
- Ensure parent directories are writable"""

    except Exception as e:
        return f"""[FAILED] DIRECTORY CREATION FAILED

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Target Path: {dir_path}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check path validity
- Verify parent directory exists and is accessible
- Try using absolute paths"""


@mcp.tool()
def copy_file(
    source_file: str,
    target_file: str,
    source_path: str | None = None,
    target_path: str | None = None,
) -> str:
    """
    Copy file from source to target location, optionally renaming it.

    Args:
        source_file: Name of the source file
        target_file: Name for the target file (can be same as source)
        source_path: Optional path to source file (default: current directory)
        target_path: Optional path for target file (default: current directory)

    Returns:
        Success message with file details or error message
    """
    try:
        # Use current directory if no path specified
        if source_path is None:
            source_path = os.getcwd()
        if target_path is None:
            target_path = os.getcwd()

        # Resolve container paths
        if source_path.startswith("/workspace"):
            source_path = source_path.replace("/workspace", os.getcwd(), 1)
        if target_path.startswith("/workspace"):
            target_path = target_path.replace("/workspace", os.getcwd(), 1)

        source_full_path = os.path.join(source_path, source_file)
        target_full_path = os.path.join(target_path, target_file)

        # Check if source file exists
        if not os.path.exists(source_full_path):
            return f"""[FAILED] FILE COPY FAILED

[DOCUMENT] Source File: {source_file}
[FOLDER_OPEN] Source Path: {source_path}
[NO_ENTRY] Error: Source file not found

[IDEA] SUGGESTIONS:
- Check source file name spelling
- Verify source path exists
- Use check_file_exists() to verify location"""

        # Create target directory if it doesn't exist
        os.makedirs(target_path, exist_ok=True)

        # Copy the file
        shutil.copy2(source_full_path, target_full_path)

        # Get file info
        file_size = os.path.getsize(target_full_path)

        return f"""[SUCCESS] FILE COPIED SUCCESSFULLY

[DOCUMENT] Source: {source_file} → {target_file}
[FOLDER_OPEN] From: {os.path.abspath(source_full_path)}
[FOLDER_OPEN] To: {os.path.abspath(target_full_path)}
[INFO] Size: {file_size} bytes
[TARGET] Operation: File copied with metadata preserved

[IDEA] NEXT STEPS:
- File is ready for use at target location
- Use open_file_content() to verify contents
- Original file remains at source location"""

    except PermissionError:
        return f"""[FAILED] FILE COPY FAILED

[DOCUMENT] File: {source_file} → {target_file}
[NO_ENTRY] Error: Permission denied

[IDEA] SUGGESTIONS:
- Check read permissions on source file
- Check write permissions on target directory
- Ensure target location is accessible"""

    except Exception as e:
        return f"""[FAILED] FILE COPY FAILED

[DOCUMENT] File: {source_file} → {target_file}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Verify both source and target paths are valid
- Check available disk space
- Ensure file is not in use by another process"""


@mcp.tool()
def delete_directory_recursive(dir_name: str, dir_path: str | None = None) -> str:
    """
    Delete directory and all contents recursively.
    WARNING: This operation is permanent and cannot be undone!

    Args:
        dir_name: Name of the directory to delete
        dir_path: Optional path containing the directory (default: current directory)

    Returns:
        Success message with deletion details or error message
    """
    try:
        # Use current directory if no path specified
        if dir_path is None:
            dir_path = os.getcwd()

        # Resolve container paths
        if dir_path.startswith("/workspace"):
            dir_path = dir_path.replace("/workspace", os.getcwd(), 1)

        full_path = os.path.join(dir_path, dir_name)

        # Check if directory exists
        if not os.path.exists(full_path):
            return f"""[FAILED] DIRECTORY DELETION FAILED

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Path: {dir_path}
[NO_ENTRY] Error: Directory not found

[IDEA] SUGGESTIONS:
- Check directory name spelling
- Verify parent path exists
- Use check_file_exists() to verify location"""

        if not os.path.isdir(full_path):
            return f"""[FAILED] DIRECTORY DELETION FAILED

[FOLDER] Target: {dir_name}
[FOLDER_OPEN] Path: {dir_path}
[NO_ENTRY] Error: Target is not a directory

[IDEA] SUGGESTIONS:
- Use delete_file() for files
- Check if target is actually a directory"""

        # Count contents before deletion
        total_items = 0
        for _root, dirs, files in os.walk(full_path):
            total_items += len(dirs) + len(files)

        # Delete the directory and all contents
        shutil.rmtree(full_path)

        return f"""[SUCCESS] DIRECTORY DELETED SUCCESSFULLY

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Full Path: {os.path.abspath(full_path)}
[CLEANUP] Items Deleted: {total_items} files and subdirectories
[TARGET] Operation: Recursive deletion completed

[WARNING]  WARNING: This operation is permanent and cannot be undone!

[IDEA] VERIFICATION:
- Directory and all contents permanently removed
- Use check_file_exists() to confirm deletion"""

    except PermissionError:
        return f"""[FAILED] DIRECTORY DELETION FAILED

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Path: {dir_path}
[NO_ENTRY] Error: Permission denied

[IDEA] SUGGESTIONS:
- Check directory permissions
- Ensure no files are in use by other processes
- Try closing applications that might be accessing files"""

    except Exception as e:
        return f"""[FAILED] DIRECTORY DELETION FAILED

[FOLDER] Directory: {dir_name}
[FOLDER_OPEN] Path: {dir_path}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check if directory is accessible
- Ensure path is valid
- Verify directory is not in use"""


@mcp.tool()
def find_files(
    pattern: str, search_path: str | None = None, recursive: bool = True
) -> str:
    """
    Search for files matching pattern in specified directory.

    Args:
        pattern: File pattern to search for (supports wildcards like *.py, test*, etc.)
        search_path: Optional path to search in (default: current directory)
        recursive: Whether to search subdirectories (default: True)

    Returns:
        List of matching files with details or error message
    """
    import fnmatch

    try:
        # Use current directory if no path specified
        if search_path is None:
            search_path = os.getcwd()

        # Resolve container paths
        if search_path.startswith("/workspace"):
            search_path = search_path.replace("/workspace", os.getcwd(), 1)

        if not os.path.exists(search_path):
            return f"""[FAILED] FILE SEARCH FAILED

[FOLDER_OPEN] Search Path: {search_path}
[SEARCH] Pattern: {pattern}
[NO_ENTRY] Error: Search directory not found

[IDEA] SUGGESTIONS:
- Check search path spelling
- Use check_file_exists() to verify directory
- Try using absolute paths"""

        found_files = []

        if recursive:
            # Search recursively
            for root, _dirs, files in os.walk(search_path):
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, search_path)
                        file_size = os.path.getsize(full_path)
                        modified_time = datetime.fromtimestamp(
                            os.path.getmtime(full_path)
                        )

                        found_files.append(
                            {
                                "name": file,
                                "path": relative_path,
                                "full_path": full_path,
                                "size": file_size,
                                "modified": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
        else:
            # Search only in specified directory
            for file in os.listdir(search_path):
                file_path = os.path.join(search_path, file)
                if os.path.isfile(file_path) and fnmatch.fnmatch(file, pattern):
                    file_size = os.path.getsize(file_path)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))

                    found_files.append(
                        {
                            "name": file,
                            "path": file,
                            "full_path": file_path,
                            "size": file_size,
                            "modified": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

        if not found_files:
            return f"""[SEARCH] FILE SEARCH COMPLETED

[FOLDER_OPEN] Search Path: {os.path.abspath(search_path)}
[SEARCH] Pattern: {pattern}
[PROCESSING] Recursive: {recursive}
[INFO] Results: No files found

[IDEA] SUGGESTIONS:
- Try different search patterns (*.txt, test*, *config*)
- Check if files exist with list_files_in_directory()
- Verify pattern syntax and spelling"""

        # Format results
        result_lines = [
            f"""[SUCCESS] FILE SEARCH COMPLETED

[FOLDER_OPEN] Search Path: {os.path.abspath(search_path)}
[SEARCH] Pattern: {pattern}
[PROCESSING] Recursive: {recursive}
[INFO] Found: {len(found_files)} matching files

[CLIPBOARD] SEARCH RESULTS:"""
        ]

        for i, file in enumerate(found_files, 1):
            result_lines.append(f"""
{i:2d}. [DOCUMENT] {file["name"]}
    [FOLDER_OPEN] Path: {file["path"]}
    [INFO] Size: {file["size"]} bytes
    [CLOCK] Modified: {file["modified"]}""")

        result_lines.append("""
[IDEA] NEXT STEPS:
- Use open_file_content() to read specific files
- Use copy_file() to copy files to new locations
- Use full paths for file operations""")

        return "\n".join(result_lines)

    except Exception as e:
        return f"""[FAILED] FILE SEARCH FAILED

[FOLDER_OPEN] Search Path: {search_path}
[SEARCH] Pattern: {pattern}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check search path accessibility
- Verify pattern syntax
- Try simpler patterns first"""


# =====================================================================================
# MEDIUM PRIORITY FUNCTIONS - Batch operations and advanced functionality
# =====================================================================================


@mcp.tool()
def copy_directory(
    source_dir: str,
    target_dir: str,
    source_path: str | None = None,
    target_path: str | None = None,
    recursive: bool = True,
) -> str:
    """
    Copy entire directory structure from source to target location.

    Args:
        source_dir: Name of the source directory
        target_dir: Name for the target directory
        source_path: Optional path containing source directory (default: current directory)
        target_path: Optional path for target directory (default: current directory)
        recursive: Whether to copy subdirectories (default: True)

    Returns:
        Success message with copy details or error message
    """
    try:
        # Use current directory if no path specified
        if source_path is None:
            source_path = os.getcwd()
        if target_path is None:
            target_path = os.getcwd()

        # Resolve container paths
        if source_path.startswith("/workspace"):
            source_path = source_path.replace("/workspace", os.getcwd(), 1)
        if target_path.startswith("/workspace"):
            target_path = target_path.replace("/workspace", os.getcwd(), 1)

        source_full_path = os.path.join(source_path, source_dir)
        target_full_path = os.path.join(target_path, target_dir)

        # Check if source directory exists
        if not os.path.exists(source_full_path):
            return f"""[FAILED] DIRECTORY COPY FAILED

[FOLDER] Source Directory: {source_dir}
[FOLDER_OPEN] Source Path: {source_path}
[NO_ENTRY] Error: Source directory not found

[IDEA] SUGGESTIONS:
- Check source directory name spelling
- Verify source path exists
- Use check_file_exists() to verify location"""

        if not os.path.isdir(source_full_path):
            return f"""[FAILED] DIRECTORY COPY FAILED

[FOLDER] Source: {source_dir}
[NO_ENTRY] Error: Source is not a directory

[IDEA] SUGGESTIONS:
- Use copy_file() for individual files
- Check if source is actually a directory"""

        # Count items before copying
        total_items = 0
        for _root, dirs, files in os.walk(source_full_path):
            total_items += len(files)
            if recursive:
                total_items += len(dirs)

        # Create parent directory if needed
        os.makedirs(target_path, exist_ok=True)

        # Copy the directory
        if recursive:
            shutil.copytree(source_full_path, target_full_path, dirs_exist_ok=True)
        else:
            # Copy only files in root directory
            os.makedirs(target_full_path, exist_ok=True)
            for item in os.listdir(source_full_path):
                source_item = os.path.join(source_full_path, item)
                target_item = os.path.join(target_full_path, item)
                if os.path.isfile(source_item):
                    shutil.copy2(source_item, target_item)

        return f"""[SUCCESS] DIRECTORY COPIED SUCCESSFULLY

[FOLDER] Source: {source_dir} → {target_dir}
[FOLDER_OPEN] From: {os.path.abspath(source_full_path)}
[FOLDER_OPEN] To: {os.path.abspath(target_full_path)}
[PROCESSING] Recursive: {recursive}
[INFO] Items Copied: {total_items} files and directories
[TARGET] Operation: Directory structure copied with metadata preserved

[IDEA] NEXT STEPS:
- Directory is ready for use at target location
- Use list_files_in_directory() to verify contents
- Original directory remains at source location"""

    except Exception as e:
        return f"""[FAILED] DIRECTORY COPY FAILED

[FOLDER] Directory: {source_dir} → {target_dir}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check permissions on source and target locations
- Verify sufficient disk space
- Ensure target location is accessible"""


@mcp.tool()
def copy_multiple_files(file_patterns: str, source_path: str, target_path: str) -> str:
    """
    Copy multiple files matching patterns from source to target path.

    Args:
        file_patterns: Comma-separated list of file patterns (e.g., "*.py,*.md,config*")
        source_path: Path containing source files
        target_path: Path for target files

    Returns:
        Success message with copy details or error message
    """
    import fnmatch

    try:
        # Resolve container paths
        if source_path.startswith("/workspace"):
            source_path = source_path.replace("/workspace", os.getcwd(), 1)
        if target_path.startswith("/workspace"):
            target_path = target_path.replace("/workspace", os.getcwd(), 1)

        # Check if source directory exists
        if not os.path.exists(source_path):
            return f"""[FAILED] MULTIPLE FILE COPY FAILED

[FOLDER_OPEN] Source Path: {source_path}
[NO_ENTRY] Error: Source directory not found

[IDEA] SUGGESTIONS:
- Check source path spelling
- Use check_file_exists() to verify directory
- Try using absolute paths"""

        # Parse file patterns
        patterns = [pattern.strip() for pattern in file_patterns.split(",")]

        # Find matching files
        matching_files = []
        for pattern in patterns:
            for file in os.listdir(source_path):
                file_path = os.path.join(source_path, file)
                if os.path.isfile(file_path) and fnmatch.fnmatch(file, pattern):
                    if file not in [
                        f["name"] for f in matching_files
                    ]:  # Avoid duplicates
                        matching_files.append(
                            {"name": file, "source": file_path, "pattern": pattern}
                        )

        if not matching_files:
            return f"""[SEARCH] MULTIPLE FILE COPY COMPLETED

[FOLDER_OPEN] Source: {os.path.abspath(source_path)}
[FOLDER_OPEN] Target: {os.path.abspath(target_path)}
[SEARCH] Patterns: {file_patterns}
[INFO] Results: No matching files found

[IDEA] SUGGESTIONS:
- Check if files exist with list_files_in_directory()
- Verify pattern syntax (*.txt, test*, *config*)
- Try different patterns or individual file names"""

        # Create target directory if needed
        os.makedirs(target_path, exist_ok=True)

        # Copy matching files
        copied_files = []
        failed_files = []

        for file_info in matching_files:
            try:
                source_file = file_info["source"]
                target_file = os.path.join(target_path, file_info["name"])
                shutil.copy2(source_file, target_file)

                file_size = os.path.getsize(target_file)
                copied_files.append(
                    {
                        "name": file_info["name"],
                        "pattern": file_info["pattern"],
                        "size": file_size,
                    }
                )
            except Exception as copy_error:
                failed_files.append(
                    {"name": file_info["name"], "error": str(copy_error)}
                )

        # Format results
        result_lines = [
            f"""[SUCCESS] MULTIPLE FILE COPY COMPLETED

[FOLDER_OPEN] Source: {os.path.abspath(source_path)}
[FOLDER_OPEN] Target: {os.path.abspath(target_path)}
[SEARCH] Patterns: {file_patterns}
[INFO] Success: {len(copied_files)} files copied"""
        ]

        if failed_files:
            result_lines.append(f"[WARNING]  Failed: {len(failed_files)} files")

        result_lines.append("\n[CLIPBOARD] COPIED FILES:")
        for i, file in enumerate(copied_files, 1):
            result_lines.append(
                f"  {i:2d}. [DOCUMENT] {file['name']} ({file['size']} bytes) [Pattern: {file['pattern']}]"
            )

        if failed_files:
            result_lines.append("\n[FAILED] FAILED FILES:")
            for i, file in enumerate(failed_files, 1):
                result_lines.append(
                    f"  {i:2d}. [DOCUMENT] {file['name']} - Error: {file['error']}"
                )

        result_lines.append("""
[IDEA] NEXT STEPS:
- Files are ready for use at target location
- Use open_file_content() to verify copied contents
- Original files remain at source location""")

        return "\n".join(result_lines)

    except Exception as e:
        return f"""[FAILED] MULTIPLE FILE COPY FAILED

[FOLDER_OPEN] Paths: {source_path} → {target_path}
[SEARCH] Patterns: {file_patterns}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check source and target path accessibility
- Verify pattern syntax
- Ensure sufficient disk space"""


@mcp.tool()
def delete_multiple_files(file_patterns: str, file_path: str | None = None) -> str:
    """
    Delete multiple files matching patterns.
    WARNING: This operation is permanent and cannot be undone!

    Args:
        file_patterns: Comma-separated list of file patterns (e.g., "*.tmp,*.log,backup*")
        file_path: Optional path containing files (default: current directory)

    Returns:
        Success message with deletion details or error message
    """
    import fnmatch

    try:
        # Use current directory if no path specified
        if file_path is None:
            file_path = os.getcwd()

        # Resolve container paths
        if file_path.startswith("/workspace"):
            file_path = file_path.replace("/workspace", os.getcwd(), 1)

        if not os.path.exists(file_path):
            return f"""[FAILED] MULTIPLE FILE DELETION FAILED

[FOLDER_OPEN] Path: {file_path}
[NO_ENTRY] Error: Directory not found

[IDEA] SUGGESTIONS:
- Check file path spelling
- Use check_file_exists() to verify directory
- Try using absolute paths"""

        # Parse file patterns
        patterns = [pattern.strip() for pattern in file_patterns.split(",")]

        # Find matching files
        matching_files = []
        for pattern in patterns:
            for file in os.listdir(file_path):
                full_file_path = os.path.join(file_path, file)
                if os.path.isfile(full_file_path) and fnmatch.fnmatch(file, pattern):
                    if file not in [
                        f["name"] for f in matching_files
                    ]:  # Avoid duplicates
                        matching_files.append(
                            {
                                "name": file,
                                "path": full_file_path,
                                "pattern": pattern,
                                "size": os.path.getsize(full_file_path),
                            }
                        )

        if not matching_files:
            return f"""[SEARCH] MULTIPLE FILE DELETION COMPLETED

[FOLDER_OPEN] Path: {os.path.abspath(file_path)}
[SEARCH] Patterns: {file_patterns}
[INFO] Results: No matching files found

[IDEA] SUGGESTIONS:
- Check if files exist with list_files_in_directory()
- Verify pattern syntax (*.tmp, test*, backup*)
- Files may have already been deleted"""

        # Delete matching files
        deleted_files = []
        failed_files = []
        total_size = 0

        for file_info in matching_files:
            try:
                os.remove(file_info["path"])
                deleted_files.append(file_info)
                total_size += file_info["size"]
            except Exception as delete_error:
                failed_files.append(
                    {"name": file_info["name"], "error": str(delete_error)}
                )

        # Format results
        result_lines = [
            f"""[SUCCESS] MULTIPLE FILE DELETION COMPLETED

[FOLDER_OPEN] Path: {os.path.abspath(file_path)}
[SEARCH] Patterns: {file_patterns}
[INFO] Deleted: {len(deleted_files)} files ({total_size} bytes)"""
        ]

        if failed_files:
            result_lines.append(f"[WARNING]  Failed: {len(failed_files)} files")

        result_lines.append("\n[CLEANUP]  DELETED FILES:")
        for i, file in enumerate(deleted_files, 1):
            result_lines.append(
                f"  {i:2d}. [DOCUMENT] {file['name']} ({file['size']} bytes) [Pattern: {file['pattern']}]"
            )

        if failed_files:
            result_lines.append("\n[FAILED] FAILED DELETIONS:")
            for i, file in enumerate(failed_files, 1):
                result_lines.append(
                    f"  {i:2d}. [DOCUMENT] {file['name']} - Error: {file['error']}"
                )

        result_lines.append("""
[WARNING]  WARNING: This operation is permanent and cannot be undone!

[IDEA] VERIFICATION:
- Use check_file_exists() to confirm deletions
- Files have been permanently removed from disk""")

        return "\n".join(result_lines)

    except Exception as e:
        return f"""[FAILED] MULTIPLE FILE DELETION FAILED

[FOLDER_OPEN] Path: {file_path}
[SEARCH] Patterns: {file_patterns}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check file path accessibility
- Verify pattern syntax
- Ensure files are not in use by other processes"""


@mcp.tool()
def search_file_content(
    search_term: str, file_pattern: str = "*", search_path: str | None = None
) -> str:
    """
    Search for content within files (grep equivalent).

    Args:
        search_term: Text to search for within files
        file_pattern: File pattern to search in (default: "*" for all files)
        search_path: Optional path to search in (default: current directory)

    Returns:
        Search results with file names, line numbers, and matching content
    """
    import fnmatch

    try:
        # Use current directory if no path specified
        if search_path is None:
            search_path = os.getcwd()

        # Resolve container paths
        if search_path.startswith("/workspace"):
            search_path = search_path.replace("/workspace", os.getcwd(), 1)

        if not os.path.exists(search_path):
            return f"""[FAILED] CONTENT SEARCH FAILED

[FOLDER_OPEN] Search Path: {search_path}
[NO_ENTRY] Error: Search directory not found

[IDEA] SUGGESTIONS:
- Check search path spelling
- Use check_file_exists() to verify directory
- Try using absolute paths"""

        # Find matching files
        search_files = []
        for file in os.listdir(search_path):
            file_path = os.path.join(search_path, file)
            if os.path.isfile(file_path) and fnmatch.fnmatch(file, file_pattern):
                search_files.append((file, file_path))

        if not search_files:
            return f"""[SEARCH] CONTENT SEARCH COMPLETED

[FOLDER_OPEN] Search Path: {os.path.abspath(search_path)}
[SEARCH] File Pattern: {file_pattern}
[SEARCH] Search Term: "{search_term}"
[INFO] Results: No matching files found

[IDEA] SUGGESTIONS:
- Check file pattern (*.txt, *.py, etc.)
- Use list_files_in_directory() to see available files
- Try different file patterns"""

        # Search for content in files
        matches = []
        searched_files = 0

        for file_name, file_path in search_files:
            try:
                # Try to read file as text
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                searched_files += 1

                for line_num, line in enumerate(lines, 1):
                    if search_term.lower() in line.lower():
                        matches.append(
                            {
                                "file": file_name,
                                "line_number": line_num,
                                "line_content": line.rstrip(),
                                "file_path": file_path,
                            }
                        )

            except Exception:
                # Skip binary files or files that can't be read
                continue

        # Format results
        if not matches:
            return f"""[SEARCH] CONTENT SEARCH COMPLETED

[FOLDER_OPEN] Search Path: {os.path.abspath(search_path)}
[SEARCH] File Pattern: {file_pattern}
[SEARCH] Search Term: "{search_term}"
[INFO] Files Searched: {searched_files}
[INFO] Matches: No content matches found

[IDEA] SUGGESTIONS:
- Check search term spelling
- Try case-insensitive search (already enabled)
- Search term may not exist in these files"""

        # Group matches by file
        files_with_matches = {}
        for match in matches:
            if match["file"] not in files_with_matches:
                files_with_matches[match["file"]] = []
            files_with_matches[match["file"]].append(match)

        result_lines = [
            f"""[SUCCESS] CONTENT SEARCH COMPLETED

[FOLDER_OPEN] Search Path: {os.path.abspath(search_path)}
[SEARCH] File Pattern: {file_pattern}
[SEARCH] Search Term: "{search_term}"
[INFO] Files Searched: {searched_files}
[INFO] Files with Matches: {len(files_with_matches)}
[INFO] Total Matches: {len(matches)}

[CLIPBOARD] SEARCH RESULTS:"""
        ]

        for file_name, file_matches in files_with_matches.items():
            result_lines.append(f"\n[DOCUMENT] {file_name} ({len(file_matches)} matches):")
            for match in file_matches[:5]:  # Limit to first 5 matches per file
                # Highlight search term in context
                highlighted_line = (
                    match["line_content"]
                    .replace(search_term, f"**{search_term}**")
                    .replace(search_term.lower(), f"**{search_term.lower()}**")
                    .replace(search_term.upper(), f"**{search_term.upper()}**")
                )
                result_lines.append(
                    f"  Line {match['line_number']:3d}: {highlighted_line}"
                )

            if len(file_matches) > 5:
                result_lines.append(f"  ... ({len(file_matches) - 5} more matches)")

        result_lines.append("""
[IDEA] NEXT STEPS:
- Use open_file_content() to examine full file contents
- Use line numbers to navigate to specific matches
- Refine search terms for more precise results""")

        return "\n".join(result_lines)

    except Exception as e:
        return f"""[FAILED] CONTENT SEARCH FAILED

[FOLDER_OPEN] Search Path: {search_path}
[SEARCH] Pattern: {file_pattern}
[SEARCH] Term: "{search_term}"
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check search path accessibility
- Verify file pattern syntax
- Try simpler search terms"""


@mcp.tool()
def replace_placeholders_in_file(
    file_name: str,
    placeholder_replacements: dict[str, str],
    file_path: str | None = None,
) -> str:
    """
    [PROCESSING] COLLABORATIVE PLACEHOLDER REPLACEMENT
    ======================================

    Replace multiple placeholders in a file atomically for team collaboration.
    Perfect for multi-agent workflows where agents fill in their sections.

    Args:
        file_name: Target file name to update
        placeholder_replacements: Dictionary of {placeholder: replacement_content}
        file_path: Optional directory path (defaults to current directory)

    Placeholder Format:
        Use [PLACEHOLDER_NAME] format to avoid conflicts with Semantic Kernel

    Example Usage:
        replace_placeholders_in_file(
            "migration_analysis.md",
            {
                "[EKS_EXPERT_ANALYSIS]": "## EKS Source Analysis\\n- Current version: 1.28\\n- Node groups: 3",
                "[AZURE_RECOMMENDATIONS]": "## Azure Services\\n- Compute: AKS\\n- Storage: Premium SSD",
                "[CURRENT_TIMESTAMP]": "2025-08-09T15:30:00Z"
            },
            "/workspaces/project/analysis/"
        )

    Returns:
        Success/failure message with replacement details
    """
    try:
        # Construct full file path
        full_path = os.path.join(file_path, file_name) if file_path else file_name

        # Check if file exists
        if not os.path.exists(full_path):
            return f"""[FAILED] PLACEHOLDER REPLACEMENT FAILED

[DOCUMENT] File: {file_name}
[FOLDER_OPEN] Path: {file_path or "current directory"}
[NO_ENTRY] Error: File not found

[IDEA] SUGGESTION: Create the file first or check the file path"""

        # Read current content
        with open(full_path, encoding="utf-8") as file:
            content = file.read()

        replacements_made = 0
        replacement_log = []

        # Replace each placeholder
        for placeholder, replacement in placeholder_replacements.items():
            if placeholder in content:
                content = content.replace(placeholder, replacement)
                replacements_made += 1
                replacement_log.append(f"[SUCCESS] {placeholder} → {len(replacement)} chars")
            else:
                replacement_log.append(f"[WARNING] {placeholder} → Not found in file")

        # Write updated content back to file
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(content)

        # Get file info
        file_info = os.stat(full_path)

        return f"""[SUCCESS] PLACEHOLDER REPLACEMENT COMPLETE

[DOCUMENT] File: {file_name}
[FOLDER_OPEN] Path: {file_path or "current directory"}
[PROCESSING] Replacements Made: {replacements_made}/{len(placeholder_replacements)}
[INFO] File Size: {file_info.st_size:,} bytes
[TIMEOUT] Updated: {datetime.fromtimestamp(file_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")}

[NOTES] REPLACEMENT DETAILS:
{chr(10).join(replacement_log)}

[IDEA] COLLABORATIVE SUCCESS: File ready for next agent to process!"""

    except Exception as e:
        return f"""[FAILED] PLACEHOLDER REPLACEMENT FAILED

[DOCUMENT] File: {file_name}
[FOLDER_OPEN] Path: {file_path or "current directory"}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check file permissions (read/write access)
- Verify placeholder format uses [PLACEHOLDER_NAME]
- Ensure replacement content is valid text
- Check available disk space"""


@mcp.tool()
def create_template_with_placeholders(
    file_name: str,
    template_content: str,
    placeholder_list: list[str],
    file_path: str | None = None,
) -> str:
    """
    [NOTES] CREATE COLLABORATIVE TEMPLATE
    ===============================

    Create a template file with placeholders for multi-agent collaboration.
    Automatically adds placeholder sections that other agents can fill.

    Args:
        file_name: Name of template file to create
        template_content: Base template content
        placeholder_list: List of placeholder names (without brackets)
        file_path: Optional directory path

    Example Usage:
        create_template_with_placeholders(
            "migration_analysis_template.md",
            "# Migration Analysis\\n\\nGenerated: [CURRENT_TIMESTAMP]\\n\\n",
            ["EKS_EXPERT_ANALYSIS", "AZURE_RECOMMENDATIONS", "YAML_CONVERSIONS"],
            "/workspaces/project/templates/"
        )

    Returns:
        Success message with template creation details
    """
    try:
        # Add placeholders to template content
        enhanced_content = template_content

        for placeholder in placeholder_list:
            placeholder_section = f"""
## {placeholder.replace("_", " ").title()}
[{placeholder}]

"""
            enhanced_content += placeholder_section

        # Save template file
        result = save_content_to_file(file_name, enhanced_content, file_path)

        return f"""[SUCCESS] COLLABORATIVE TEMPLATE CREATED

[DOCUMENT] Template: {file_name}
[FOLDER_OPEN] Path: {file_path or "current directory"}
[TAG] Placeholders Added: {len(placeholder_list)}

[NOTES] PLACEHOLDERS READY FOR AGENTS:
{chr(10).join(f"• [{p}]" for p in placeholder_list)}

[IDEA] NEXT STEPS:
1. Share template location with team agents
2. Each agent fills their assigned placeholder
3. Use replace_placeholders_in_file() to update sections
4. Collect completed analysis for final report

{result}"""

    except Exception as e:
        return f"""[FAILED] TEMPLATE CREATION FAILED

[DOCUMENT] File: {file_name}
[FOLDER_OPEN] Path: {file_path or "current directory"}
[NO_ENTRY] Error: {e}

[IDEA] SUGGESTIONS:
- Check directory permissions
- Verify placeholder names are valid
- Ensure template content is properly formatted"""


if __name__ == "__main__":
    mcp.run()
