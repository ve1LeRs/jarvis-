"""Lightweight fun / utility replies (no OS side effects)."""

from __future__ import annotations

import ast
import operator
import random
import re

_JOKES = (
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 октября равно 25 декабря.",
    "Сэр, мой процессор иногда шутит… но только в рамках спецификации.",
    "Два байта встречаются. Первый: «Ты выглядишь так себе». Второй: «Это у меня битый бит».",
    "Я бы рассказал шутку про UDP, но не уверен, что она дойдёт.",
    "Баг заходит в бар. Бармен: «Мы вас не обслуживаем». Баг: «Это не баг, это фича».",
    "Сэр, кофеин — это не баг в организме, это hotfix для понедельника.",
)

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def joke() -> str:
    return random.choice(_JOKES)


def coin_flip() -> str:
    return "Выпал орёл." if random.random() < 0.5 else "Выпала решка."


def roll_dice(sides: int = 6) -> str:
    sides = max(2, min(sides, 100))
    return f"Выпало {random.randint(1, sides)} из {sides}."


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))  # type: ignore[operator]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ZeroDivisionError
        return _OPS[type(node.op)](left, right)  # type: ignore[operator]
    raise ValueError("unsupported")


def calculate(expression: str) -> str:
    expr = (expression or "").strip().lower().replace("ё", "е")
    expr = expr.replace("x", "*").replace("х", "*").replace(",", ".")
    expr = re.sub(r"[^0-9+\-*/().%\s]", "", expr)
    if not expr:
        return "Нечего считать."
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_node(tree)
        if abs(value - round(value)) < 1e-9:
            return f"Получается {int(round(value))}."
        return f"Получается {value:.4g}."
    except ZeroDivisionError:
        return "Деление на ноль, сэр. Даже я так не могу."
    except Exception:
        return "Не смог посчитать это выражение."
