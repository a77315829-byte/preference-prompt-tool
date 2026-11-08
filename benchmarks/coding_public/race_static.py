"""Unmodified static functions extracted from RACE (Apache-2.0).

Source: jszheng21/RACE, commit 3b8ee591abd5febd8ae8ec17c7b9907949c5e1d5
File: race/codeeval/metrics_utils.py
Modification: retained seven functions and stdlib imports; trimmed trailing whitespace.
See LICENSE-RACE. No candidate code is executed by these functions.
"""
import ast
import re


def extract_function_names(code):
    try:
        code_bytes = bytes(code, "utf8")
        tree = ast.parse(code_bytes)
    except SyntaxError:
        return []

    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)

    return names


def extract_function_bodies(code):
    try:
        code_bytes = bytes(code, "utf8")
        tree = ast.parse(code_bytes)
    except SyntaxError:
        return []

    function_bodies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            function_name = node.name
            function_body = ast.get_source_segment(code, node)

            function_bodies.append((function_name, function_body))

    return function_bodies


def metrics_for_readability_function_snake(code):
    pattern = re.compile(r'^(?![0-9])_?[a-z0-9]+(?:_[a-z0-9]+)*$')

    names = extract_function_names(code)
    if len(names) == 0:
        return False
    for name in names:
        if not bool(pattern.match(name)):
            return False

    return True


def metrics_for_readability_length(code, max_line_length=100, max_function_length=40):
    splitted_code = code.split('\n')
    for line in splitted_code:
        if len(line) > max_line_length:
            return False

    functions = extract_function_bodies(code)
    if len(functions) == 0:
        return False
    for _, function_body in functions:
        if len(function_body.split('\n')) > max_function_length:
            return False

    return True


def metrics_for_readability_comment_by_function(code):
    try:
        code_bytes = bytes(code, "utf8")
        tree = ast.parse(code_bytes)
    except SyntaxError:
        return False

    if isinstance(tree, ast.Module) and tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Str):
        return True

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str)):
                return False

    return True


def metrics_for_readability_comment_by_line(code, threshold=0.75):
    def backup_metrics_for_readability_comment_by_line(code):
        def has_comment(line):
            line = line.strip()
            if not line:
                return True
            if line.startswith('#'):
                return True
            if '#' in line:
                code_part = line.split('#')[0].strip()
                if code_part:
                    return True
            return False

        lines = code.split('\n')
        lines_without_comments = [line for line in lines if not has_comment(line)]
        if len(lines_without_comments) / len(lines) < 1-threshold:
            return True

        return False

    def merge_lines(code):
        class LineMerger(ast.NodeVisitor):
            def __init__(self):
                self.line_map = {}
                self.current_line = 1

            def visit(self, node):
                if hasattr(node, 'lineno'):
                    self.line_map[node.lineno] = self.current_line
                self.generic_visit(node)

            def generic_visit(self, node):
                if hasattr(node, 'lineno'):
                    self.current_line = node.lineno
                super().generic_visit(node)

        class LineMergerTransformer(ast.NodeTransformer):
            def __init__(self, line_map):
                self.line_map = line_map

            def visit(self, node):
                if hasattr(node, 'lineno'):
                    node.lineno = self.line_map.get(node.lineno, node.lineno)
                return super().visit(node)

        tree = ast.parse(code)
        line_merger = LineMerger()
        line_merger.visit(tree)

        transformer = LineMergerTransformer(line_merger.line_map)
        new_tree = transformer.visit(tree)

        return ast.fix_missing_locations(new_tree)

    try:
        comment_line_cnt = len(re.findall(r'\s#+\s', code))
        match = re.search(r'""".*?"""', code, flags=re.DOTALL)
        if match:
            comment_line_cnt += 1

        code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL).strip()

        merged_code = merge_lines(code)
        merged_code = ast.unparse(merged_code)

        splitted_merged_code = merged_code.split('\n')
        total_line_cnt = sum(1 for line in splitted_merged_code if line.strip()
                             and 'def' not in line
                             and 'class' not in line
                             and 'import' not in line)

        if comment_line_cnt / total_line_cnt >= threshold:
            return True

        return False
    except:
        return backup_metrics_for_readability_comment_by_line(code)


def metrics_for_maintainability_module_count(code, module_count=1):
    return len(extract_function_names(code)) == module_count
