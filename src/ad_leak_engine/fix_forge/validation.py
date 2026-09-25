"""Syntax validation for generated fix code [SEED: 2399]."""


def validate_python(code: str) -> bool:
    """True if code is syntactically valid Python (real compile check)."""
    try:
        compile(code, "<fix>", "exec")
        return True
    except SyntaxError:
        return False


def validate_php(code: str) -> bool:
    """Structural check: balanced braces + WordPress/PHP markers."""
    if code.count("{") != code.count("}"):
        return False
    if "add_action" not in code and "<?php" not in code:
        return False
    return True


def validate_javascript(code: str) -> bool:
    """Structural check: balanced braces and parentheses."""
    if code.count("{") != code.count("}"):
        return False
    if code.count("(") != code.count(")"):
        return False
    return True


def validate_liquid(code: str) -> bool:
    """Structural check: balanced Liquid block tags."""
    if code.count("{%") != code.count("%}"):
        return False
    return True


def validate_code_block(block: dict) -> bool:
    """Validate a single code block based on its language."""
    lang = block.get("language", "")
    code = block.get("code", "")
    if not code:
        return False
    if lang == "python":
        return validate_python(code)
    if lang == "php":
        return validate_php(code)
    if lang in ("javascript", "html"):
        return validate_javascript(code)
    if lang == "liquid":
        return validate_liquid(code)
    return True


def validate_fix(fix) -> bool:
    """Validate all code blocks in a Fix."""
    for block in fix.code_blocks:
        if not validate_code_block(block):
            return False
    return True
