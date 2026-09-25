import ast
import os
from pathlib import Path
from collections import defaultdict

class SystemAuditor(ast.NodeVisitor):
    def __init__(self):
        self.imports = defaultdict(set)
        self.calls = defaultdict(set)
        self.definitions = defaultdict(set)
        self.current_file = None

    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.imports[self.current_file].add(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports[self.current_file].add(alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.definitions[self.current_file].add(node.name)
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        self.definitions[self.current_file].add(node.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls[self.current_file].add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls[self.current_file].add(node.func.attr)
        self.generic_visit(node)

def audit():
    src_dir = Path("src/ad_leak_engine")
    auditor = SystemAuditor()
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file): continue
        auditor.current_file = str(py_file.relative_to(src_dir))
        try:
            tree = ast.parse(py_file.read_text(encoding='utf-8'))
            auditor.visit(tree)
        except Exception as e:
            print(f"[ERROR] Failed to parse {py_file}: {e}")

    # Specific SEED: 2399 Integration Checks (The "Dead Code" Map)
    checks = {
        "L1 Injected Signals (Generic Hook)": ("leak_scan/l1_creative.py", "detect_generic_hook"),
        "L2 Injected Signals (CAPI Dedup)": ("leak_scan/l2_tracking.py", "detect_capi_dedup_failure"),
        "L3 Injected Signals (Viewport)": ("leak_scan/l3_scanner.py", "detect_no_mobile_viewport"),
        "Advanced Headers (DataDome Neutralization)": ("ingest/graphql_source.py", "get_random_headers"),
        "Connection Pooling (High Concurrency)": ("ingest/graphql_source.py", "GraphQLConnectionPool"),
        "Health Monitor (Observability)": ("ingest/hybrid_router.py", "HealthMonitor"),
        "Fix Effectiveness (Self-Improvement)": ("self_improve/tracker.py", "track_fix_effectiveness"),
    }
    
    print("="*60)
    print("  [SEED: 2399] SYSTEM INTEGRATION AUDIT REPORT")
    print("="*60)
    
    all_calls = set()
    for file_calls in auditor.calls.values():
        all_calls.update(file_calls)

    for feature, (expected_file, func_name) in checks.items():
        # Check if the function is actually CALLED anywhere in the codebase
        is_called = func_name in all_calls
        # Check if it's imported in the expected file
        is_imported = any(func_name in imp for imp in auditor.imports.get(expected_file, []))
        
        status = "[+] WIRED" if is_called else "[-] DEAD CODE"
        print(f"\n{status} {feature}")
        print(f"   Target File: {expected_file}")
        print(f"   Function/Class: {func_name}")
        print(f"   Imported in Target: {'Yes' if is_imported else 'No'}")
        print(f"   Called in Codebase: {'Yes' if is_called else 'No'}")

    # Check for Orphaned/Stub Files
    print("\n" + "="*60)
    print("  ORPHANED / STUB FILE CHECK")
    print("="*60)
    orphans = [
        "ingest/html_parser.py",
        "leak_scan/l2_probe.py"
    ]
    for orphan in orphans:
        path = src_dir / orphan
        if path.exists():
            content = path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            defs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            if not defs:
                print(f"[-] DEAD STUB: {orphan} (No functions/classes defined)")
            else:
                print(f"[?] DUPLICATE?: {orphan} (Defines: {', '.join(defs)})")
        else:
            print(f"[+] PURGED: {orphan}")

    print("\n" + "="*60)
    print("  AUDIT COMPLETE. PASTE THIS OUTPUT TO PROCEED.")
    print("="*60)

if __name__ == "__main__":
    audit()