"""Calculator skill - arithmetic via a restricted AST evaluator.

Added because the LLM fallback got a plain multiplication wrong (and mixed in
a stray Chinese character) during testing - small local models are not
reliable at arithmetic. This never touches the LLM: it parses the expression
itself and evaluates only a safe, fixed set of operators (no eval() on
arbitrary text).
"""

import ast
import operator
import re
from .base import Skill

_LEAD_TRIGGERS = ["what is", "whats", "what's", "calculate", "how much is", "what would be"]

_WORD_OPS = [
    (re.compile(r"multiplied by|times"), "*"),
    (re.compile(r"divided by"), "/"),
    (re.compile(r"plus|added to"), "+"),
    (re.compile(r"minus|subtracted by"), "-"),
]

_PERCENT_OF = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*(\d+(?:\.\d+)?)")

_SAFE_EXPR = re.compile(r"^[\d\.\+\-\*/\(\)\s]+$")

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression node: {node!r}")


def safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)


class CalculatorSkill(Skill):
    name = "calculator"

    def _normalize(self, text: str) -> str:
        t = text.lower().strip().rstrip("?.! ")
        for lead in _LEAD_TRIGGERS:
            if t.startswith(lead):
                t = t[len(lead):].strip()
                break
        t = _PERCENT_OF.sub(lambda m: f"({m.group(1)}/100)*{m.group(2)}", t)
        for pattern, symbol in _WORD_OPS:
            t = pattern.sub(symbol, t)
        return t.strip()

    def matches(self, text: str) -> bool:
        expr = self._normalize(text)
        if not expr or not _SAFE_EXPR.match(expr):
            return False
        has_digit = any(c.isdigit() for c in expr)
        has_operator = any(op in expr for op in "+-*/")
        return has_digit and has_operator

    def handle(self, text: str) -> str:
        expr = self._normalize(text)
        try:
            result = safe_eval(expr)
        except (ValueError, SyntaxError, ZeroDivisionError):
            return "I couldn't work that out, sir."
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"That's {result}, sir."
