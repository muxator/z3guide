#!/usr/bin/env python
#
# This script goes through the z3guide (https://github.com/microsoft/z3guide)
# python documentation, extracts the z3 snippets and executes them in a
# subintepreter, reporting errors.
#
# This is a follow-up to: https://github.com/microsoft/z3guide/pull/206
#
# Requires python >= 3.14

from __future__ import annotations

import dataclasses
import sys
import textwrap
from concurrent import interpreters
from pathlib import Path
from typing import TYPE_CHECKING, override

import mistletoe
import mistletoe.ast_renderer

if TYPE_CHECKING:
    from collections.abc import Generator

interp = interpreters.create()


@dataclasses.dataclass(kw_only=True)
class ExecutionResults:
    file_name: str
    snippet_id: int
    error: interpreters.ExecutionFailed | None

    @property
    def was_successful(self) -> bool:
        return self.error is None


class RawAstRenderer(mistletoe.ast_renderer.AstRenderer):
    @override
    def render(self, token) -> dict:
        return mistletoe.ast_renderer.get_ast(token)


def z3_snippets_from_ast(mistletoe_ast: dict) -> Generator[str]:
    for child in mistletoe_ast["children"]:
        if child["type"] != "CodeFence":
            continue
        if child["language"] != "z3-python":
            continue
        assert len(child["children"]) == 1
        code_block = child["children"][0]
        assert code_block["type"] == "RawText"
        z3_snippet = code_block["content"]
        yield z3_snippet


def execute_snippet(z3_snippet: str) -> None:
    """Execute the z3_snippet program in a python 3.14 subintepreter.
    If the execution fails, an ExecutionFailed exception is thrown.
    Currently, the output of the execution is not captured. It could eventually
    be captured in order to verify the results are as expected.
    """
    src = textwrap.dedent(
        """\
        from z3 import *
        """,
    )
    src += z3_snippet
    print("```z3-python")
    print(src)
    print("```")
    print("RESULT:")
    interp.exec(src)


def do_stats(execution_results: list[ExecutionResults]) -> tuple[str, int]:
    s = "=== EXECUTION STATS ===\n"
    total_count = 0
    error_count = 0
    for execution_result in execution_results:
        total_count += 1
        if not execution_result.was_successful:
            error_count += 1
            s += f"{execution_result}\n"
    s += f"There were {error_count} errors over {total_count} snippets\n"
    return (s, error_count)


def main() -> int:
    base_path = Path("website/docs-programming/02 - Z3 Python - Readonly").resolve(
        strict=True,
    )
    execution_results: list[ExecutionResults] = []
    for md_file in base_path.glob("*.md"):
        print(f"=== VALIDATING FILE {md_file.name} - START ===")
        with md_file.open("r") as fin:
            rendered = mistletoe.markdown(fin, renderer=RawAstRenderer)
        for i, z3_snippet in enumerate(z3_snippets_from_ast(rendered), start=1):
            print(f'=== Executing snippet #{i} in "{md_file.name}" ===')
            execution_result = ExecutionResults(
                file_name=md_file.name,
                snippet_id=i,
                error=None,
            )
            try:
                execute_snippet(z3_snippet)
            except interpreters.ExecutionFailed as e:
                execution_result.error = e
            finally:
                execution_results.append(execution_result)
        print(f"=== FINISHED VALIDATING {md_file.name} ===")
    (msg, error_count) = do_stats(execution_results)
    print(msg)
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
