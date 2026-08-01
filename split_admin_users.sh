#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/aistudio-api"
PYTHON="$ROOT/venv/bin/python"
SOURCE="$ROOT/admin/users.py"
TARGET="$ROOT/admin/users"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/users-package-$STAMP"
STAGING="$ROOT/admin/.users_staging_$STAMP"

cd "$ROOT"

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: Python environment not found: $PYTHON"
  exit 1
fi

if [[ ! -f "$SOURCE" ]]; then
  if [[ -d "$TARGET" ]]; then
    echo "Users is already a package: $TARGET"
    find "$TARGET" -maxdepth 1 -type f -print | sort
    exit 0
  fi
  echo "ERROR: $SOURCE not found"
  exit 1
fi

mkdir -p "$BACKUP"
cp -a "$SOURCE" "$BACKUP/users.py"
cp -a "$ROOT/admin_panel.py" "$BACKUP/admin_panel.py"
rm -rf "$STAGING"
mkdir -p "$STAGING"

echo "Backup: $BACKUP"

SOURCE="$SOURCE" STAGING="$STAGING" "$PYTHON" - <<'PY'
from __future__ import annotations

import ast
import os
from pathlib import Path

source_path = Path(os.environ["SOURCE"])
staging = Path(os.environ["STAGING"])
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(source_path))

wanted = {
    "list_page.py": ["users_page"],
    "detail_page.py": ["user_detail_page"],
    "actions.py": [
        "activate_user",
        "deactivate_user",
        "toggle_user_block",
        "reset_user_usage",
    ],
}

functions: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {}
for node in tree.body:
    if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
        functions[node.name] = node

required = {name for names in wanted.values() for name in names}
missing = sorted(required - functions.keys())
if missing:
    raise SystemExit(f"ERROR: required user functions not found: {missing}")

lines = source.splitlines(keepends=True)

def block_for(node: ast.AsyncFunctionDef | ast.FunctionDef) -> str:
    starts = [node.lineno]
    starts.extend(decorator.lineno for decorator in node.decorator_list)
    start = min(starts) - 1
    end = node.end_lineno
    return "".join(lines[start:end]).rstrip() + "\n"

module_header = '''from __future__ import annotations

from fastapi import APIRouter

from ..common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin", tags=["admin-panel"])


'''

for filename, names in wanted.items():
    content = module_header
    for index, name in enumerate(names):
        if index:
            content += "\n\n"
        content += block_for(functions[name])
    (staging / filename).write_text(content, encoding="utf-8")

init_content = '''"""مدیریت کاربران پنل رشد یار."""

from fastapi import APIRouter

from .actions import router as actions_router
from .detail_page import router as detail_router
from .list_page import router as list_router

router = APIRouter()
router.include_router(list_router)
router.include_router(detail_router)
router.include_router(actions_router)

__all__ = ["router"]
'''
(staging / "__init__.py").write_text(init_content, encoding="utf-8")

# Compile every generated module before touching live files.
for path in sorted(staging.glob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("Generated modules:")
for path in sorted(staging.glob("*.py")):
    print(" -", path.name)
PY

# Replace the single module with the package atomically enough for this deployment.
rm -rf "$TARGET"
mv "$STAGING" "$TARGET"
rm -f "$SOURCE"

rollback() {
  echo "ERROR: validation failed; restoring previous users.py"
  rm -rf "$TARGET"
  cp -a "$BACKUP/users.py" "$SOURCE"
  cp -a "$BACKUP/admin_panel.py" "$ROOT/admin_panel.py"
}
trap rollback ERR

"$PYTHON" -m py_compile \
  admin_panel.py \
  admin/common.py \
  admin/users/__init__.py \
  admin/users/list_page.py \
  admin/users/detail_page.py \
  admin/users/actions.py

"$PYTHON" - <<'PY'
import importlib

import admin_panel
import main

importlib.reload(admin_panel)

paths = {
    route.path
    for route in admin_panel.router.routes
    if hasattr(route, "path")
}

required = {
    "/admin/users",
    "/admin/users/{user_id}",
    "/admin/users/activate",
    "/admin/users/deactivate",
    "/admin/users/toggle-block",
    "/admin/users/reset-usage",
}
missing = sorted(required - paths)
if missing:
    raise SystemExit(f"ERROR: users routes missing: {missing}")

print("MAIN IMPORT OK")
print("USERS ROUTES OK:", len(required))
PY

systemctl restart aistudio-api
sleep 3
systemctl is-active --quiet aistudio-api
trap - ERR

echo
echo "Users modularization completed successfully."
echo "Backup: $BACKUP"
echo "Files:"
find "$TARGET" -maxdepth 1 -type f -print | sort
