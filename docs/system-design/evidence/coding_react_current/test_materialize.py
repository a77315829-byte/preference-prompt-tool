import pytest
from benchmarks.coding_react_current.materialize import apply, apply_unified, blocks


def test_complete_source_retains_literal_content_and_offsets():
    answer = 'Component.tsx\n```tsx\nexport const Component = () => <p>안녕</p>;\n```\n설명'
    result = apply(answer, {}, [{'path': 'Component.tsx', 'mode': 'replace_file', 'block': 0, 'reason': 'named file'}])
    assert result['files']['Component.tsx'] == 'export const Component = () => <p>안녕</p>;\n'
    trace = result['provenance'][0]
    assert answer[trace['answer_start']:trace['answer_end']] == result['files']['Component.tsx']


def test_partial_replacement_keeps_unmodified_imports():
    source = "import React from 'react';\nexport function Component() { return null; }\n"
    answer = 'Component 함수를 교체\n```tsx\nexport function Component() { return <p>Fixed</p>; }\n```'
    result = apply(answer, {'Component.tsx': source}, [{'path':'Component.tsx','mode':'replace_span','block':0,
        'anchor':'export function Component() { return null; }\n','reason':'explicit complete function replacement'}])
    assert result['files']['Component.tsx'].startswith("import React from 'react';\n")
    assert result['files']['Component.tsx'].endswith(blocks(answer)[0]['text'])


@pytest.mark.parametrize('anchor', ['missing', 'x'])
def test_ambiguous_or_absent_anchor_is_not_guessed(anchor):
    with pytest.raises(ValueError, match='anchor'):
        apply('```tsx\ny\n```', {'Component.tsx': 'xx'}, [{'path':'Component.tsx','mode':'replace_span',
            'block':0,'anchor':anchor,'reason':'test'}])


@pytest.mark.parametrize('path', ['../outside.tsx', 'C:/outside.tsx', '.env', '/root.tsx', 'x/../../y.tsx'])
def test_output_paths_cannot_escape_task(path):
    with pytest.raises(ValueError, match='path'):
        apply('```tsx\ncode\n```', {}, [{'path':path,'mode':'replace_file','block':0,'reason':'test'}])


def test_unified_patch_applies_exact_old_context():
    patch = '--- a/Component.tsx\n+++ b/Component.tsx\n@@ -1,2 +1,2 @@\n keep\n-old\n+new\n'
    assert apply_unified('keep\nold\n', patch) == 'keep\nnew\n'
    with pytest.raises(ValueError, match='context'):
        apply_unified('keep\ndifferent\n', patch)


def test_malformed_patch_does_not_get_repaired():
    with pytest.raises(ValueError, match='count'):
        apply_unified('old\n', '@@ -1,2 +1,1 @@\n-old\n+new\n')


def test_no_generated_code_is_a_delivery_failure():
    with pytest.raises(ValueError, match='block'):
        apply('Try updating the state.', {}, [{'path':'Component.tsx','mode':'replace_file','block':0,'reason':'test'}])
