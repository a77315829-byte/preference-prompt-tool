"""Literal answer-to-files application. Never repair candidate code or infer imports."""
from __future__ import annotations
import re


def blocks(answer):
    """Preserve fenced body bytes except a CRLF -> LF newline normalization."""
    answer = answer.replace('\r\n', '\n')
    return [{'language': m.group(1).strip(), 'text': m.group(2),
             'start': m.start(2), 'end': m.end(2)}
            for m in re.finditer(r'^```([^\n]*)\n(.*?)^```[ \t]*$', answer, re.M | re.S)]


def safe_path(name):
    if isinstance(name, str) and name.startswith('./'):
        name = name[2:]
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*\.(?:tsx|ts)', name):
        raise ValueError('Unsupported source path')
    if any(re.match(r'^(con|prn|aux|nul|com\d|lpt\d)(\.|$)', part, re.I) for part in name.split('/')):
        raise ValueError('Reserved source path')
    if name.endswith('.d.ts'):
        raise ValueError('Declaration files are outside the executable-source task scope')
    return name


def apply_unified(original, patch):
    """Strict single-file unified diff. Exact old text/context, no fuzzy offsets."""
    original = original.replace('\r\n', '\n')
    src = original.splitlines(keepends=True)
    lines = patch.replace('\r\n', '\n').splitlines(keepends=True)
    result = []; cursor = 0; i = 0; hunks = 0
    while i < len(lines) and lines[i].startswith(('diff ', 'index ', '--- ', '+++ ')):
        i += 1
    while i < len(lines):
        match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[i])
        if not match:
            raise ValueError('Expected an exact unified hunk')
        old_start = int(match[1]); old_count = int(match[2] or '1')
        new_start = int(match[3]); new_count = int(match[4] or '1')
        start = old_start - 1 if old_count else old_start
        if start < cursor or start > len(src):
            raise ValueError('Overlapping/out-of-range patch')
        result.extend(src[cursor:start]); cursor = start; removed = added = 0; i += 1
        expected_new_start = len(result) + (1 if new_count else 0)
        if expected_new_start != new_start:
            raise ValueError('Patch new line offset mismatch')
        while i < len(lines) and not lines[i].startswith('@@ '):
            line = lines[i]; i += 1
            if not line or line[0] not in ' +-':
                raise ValueError('Unsupported patch marker (including no-newline markers)')
            prefix, content = line[0], line[1:]
            if prefix in ' -':
                if cursor >= len(src) or src[cursor] != content:
                    raise ValueError('Patch context mismatch; no repairs permitted')
                cursor += 1; removed += 1
            if prefix in ' +':
                result.append(content); added += 1
        if removed != old_count or added != new_count:
            raise ValueError('Patch hunk count mismatch')
        hunks += 1
    if not hunks:
        raise ValueError('No patch hunks')
    result.extend(src[cursor:])
    return ''.join(result)


def apply(answer, starter_files, operations):
    """Operations must be independently justified by the answer's visible placement instructions.

    replace_file: exact code fence. replace_span: replace one unique literal old
    source span with exact fence body; may include multiple declarations. insert:
    exact fence body before/after one literal unique anchor. unified_diff: exact
    one-file diff. A fence is applied as a whole; unsupported partial-file formats
    remain unresolved. No synthesized imports, names, punctuation, wrappers, types
    or function bodies are allowed.
    """
    if not isinstance(operations, list) or not operations:
        raise ValueError('No unambiguous application operations')
    files = {safe_path(k): v.replace('\r\n', '\n') for k, v in starter_files.items()}
    fences = blocks(answer); provenance = []
    for op in operations:
        path = safe_path(op['path'])
        if not isinstance(op.get('reason'), str) or not op['reason'].strip():
            raise ValueError('Application location must be justified')
        index = op['block']
        if type(index) is not int or not 0 <= index < len(fences):
            raise ValueError('Missing literal code block')
        text = fences[index]['text']
        mode = op['mode']; before = files.get(path)
        if mode == 'replace_file':
            files[path] = text
        elif mode == 'unified_diff':
            if before is None: raise ValueError('Missing file to patch')
            files[path] = apply_unified(before, text)
        elif mode in ('replace_span', 'insert_before', 'insert_after'):
            anchor = op['anchor']
            if not isinstance(anchor, str) or not anchor or before is None or before.count(anchor) != 1:
                raise ValueError('Missing/non-unique literal placement anchor')
            replacement = text if mode == 'replace_span' else text + anchor if mode == 'insert_before' else anchor + text
            files[path] = before.replace(anchor, replacement, 1)
        else:
            raise ValueError('Unsupported application mode')
        provenance.append(dict(op, answer_start=fences[index]['start'], answer_end=fences[index]['end']))
    if 'Component.tsx' not in files or len(files) > 10:
        raise ValueError('Missing entry or too many files')
    return {'files': files, 'provenance': provenance}
