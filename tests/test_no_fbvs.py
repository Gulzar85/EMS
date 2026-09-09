"""Phase 03's "0 unintended FBVs" gate, made a permanent regression test
rather than a one-time manual audit (Phase 03 plan §77).

Parses every apps/*/views.py and apps/*/views/*.py module and asserts no
module-level function takes `request` (or `self, request`) as a parameter
— i.e. no function-based view. Context processors (`func(request) -> dict`)
live in context_processors.py, not views.py, so they're naturally excluded
by only scanning files named views.py / under a views/ package.

ALLOWED_FBVS is the explicit exception list required by the FBV Exception
Policy (Phase 03 plan §3) — empty today. If a future FBV is ever genuinely
justified, add "apps.<app>.views.<function_name>" here with a comment
explaining why a CBV is inappropriate, per that policy — do not just widen
this test to pass.
"""

from __future__ import annotations

import ast
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BASE_DIR / "apps"

ALLOWED_FBVS: set[str] = set()


def _iter_view_modules():
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        single_file = app_dir / "views.py"
        if single_file.exists():
            yield single_file
        views_pkg = app_dir / "views"
        if views_pkg.is_dir():
            for py_file in sorted(views_pkg.glob("*.py")):
                if py_file.name != "__init__.py":
                    yield py_file


def _find_fbvs(module_path: Path) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    fbvs = []
    for node in tree.body:  # module-level only — methods inside a CBV class are fine
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            # A leading underscore is this codebase's existing convention for
            # "private helper, not URL-routed" (e.g. apps/core/views.py's
            # _render_health, called by HealthReadyView.get() — never bound
            # to a path() entry). Real views are never underscore-prefixed
            # here, so this is a precise exclusion, not a loophole.
            continue
        params = [arg.arg for arg in node.args.args]
        if params and params[0] == "request":
            fbvs.append(node.name)
    return fbvs


def test_no_unintended_function_based_views():
    offenders: dict[str, list[str]] = {}
    for module_path in _iter_view_modules():
        fbvs = _find_fbvs(module_path)
        rel = module_path.relative_to(BASE_DIR).as_posix()
        dotted_prefix = rel[:-3].replace("/", ".")
        unjustified = [name for name in fbvs if f"{dotted_prefix}.{name}" not in ALLOWED_FBVS]
        if unjustified:
            offenders[rel] = unjustified

    assert not offenders, (
        "Function-based views found outside the ALLOWED_FBVS exception list "
        f"(Phase 03 plan §3, §77): {offenders}"
    )
