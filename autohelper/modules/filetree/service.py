"""
Filetree service - builds hierarchical tree from indexed files.
"""

from pathlib import PurePosixPath
from typing import Any

from autohelper.db import get_db
from autohelper.shared.logging import get_logger

from .schemas import FiletreeNode

logger = get_logger(__name__)


class FiletreeService:
    """Service for building filetree from indexed files."""

    def __init__(self) -> None:
        self.db = get_db()

    def get_tree(
        self,
        root_id: str | None = None,
        max_depth: int = 10,
        extensions: list[str] | None = None,
    ) -> list[FiletreeNode]:
        """
        Build hierarchical tree from indexed files.

        Args:
            root_id: Filter to specific root (None = all roots)
            max_depth: Maximum tree depth to return
            extensions: Filter by file extension (e.g., [".pdf", ".txt"])

        Returns:
            List of root FiletreeNode objects with nested children
        """
        # 1. Get roots
        if root_id:
            roots_cursor = self.db.execute(
                "SELECT root_id, path FROM roots WHERE root_id = ? AND enabled = 1", (root_id,)
            )
        else:
            roots_cursor = self.db.execute("SELECT root_id, path FROM roots WHERE enabled = 1")

        roots = roots_cursor.fetchall()
        result: list[FiletreeNode] = []

        for root_row in roots:
            rid = root_row["root_id"]
            root_path = root_row["path"]
            root_name = PurePosixPath(root_path).name or root_path

            # 2. Query files for this root
            query = "SELECT rel_path, size, ext, is_dir FROM files WHERE root_id = ?"
            params: list[Any] = [rid]

            if extensions:
                # Filter by extensions
                placeholders = ",".join("?" for _ in extensions)
                query += f" AND ext IN ({placeholders})"
                params.extend(extensions)

            cursor = self.db.execute(query, tuple(params))
            files = cursor.fetchall()

            # 3. Build tree for this root
            root_node = self._build_tree(root_name, root_path, files, max_depth)
            result.append(root_node)

        return result

    def _build_tree(
        self,
        root_name: str,
        root_path: str,
        files: list[dict[str, Any]],
        max_depth: int,
    ) -> FiletreeNode:
        """Build a tree from a list of file records."""
        # Use a nested dict to build the tree structure
        tree: dict[str, Any] = {"__files__": [], "__dirs__": {}}

        for f in files:
            rel_path = f["rel_path"]
            # Normalize path separators
            rel_path = rel_path.replace("\\", "/")
            parts = rel_path.split("/")

            # Skip if deeper than max_depth
            if len(parts) > max_depth:
                continue

            # Navigate/create the tree structure
            current = tree
            for _i, part in enumerate(parts[:-1]):  # All but last (directories)
                if part not in current["__dirs__"]:
                    current["__dirs__"][part] = {"__files__": [], "__dirs__": {}}
                current = current["__dirs__"][part]

            # Add the file to the leaf directory
            filename = parts[-1]
            current["__files__"].append(
                {
                    "name": filename,
                    "path": rel_path,
                    "size": f["size"],
                    "ext": f["ext"],
                    "is_dir": bool(f["is_dir"]),
                }
            )

        # Convert dict tree to FiletreeNode
        return self._dict_to_node(root_name, root_path, tree)

    def _dict_to_node(
        self,
        name: str,
        path: str,
        tree_dict: dict[str, Any],
    ) -> FiletreeNode:
        """Recursively convert dict tree to FiletreeNode."""
        children: list[FiletreeNode] = []

        # Add subdirectories
        for dir_name, subtree in sorted(tree_dict["__dirs__"].items()):
            child_path = f"{path}/{dir_name}" if path else dir_name
            child_node = self._dict_to_node(dir_name, child_path, subtree)
            children.append(child_node)

        # Add files
        for f in sorted(tree_dict["__files__"], key=lambda x: x["name"]):
            children.append(
                FiletreeNode(
                    name=f["name"],
                    path=f["path"],
                    is_dir=f["is_dir"],
                    size=f["size"],
                    ext=f["ext"],
                    children=None,
                )
            )

        return FiletreeNode(
            name=name,
            path=path,
            is_dir=True,
            children=children if children else [],
            size=None,
            ext=None,
        )
