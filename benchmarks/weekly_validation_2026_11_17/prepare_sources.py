"""Deterministic unused-source selection; never calls a model or reads .env."""
import hashlib
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write(name, data):
    path = BASE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        if value and all(isinstance(s, str) for s in value):
            yield '\n'.join(value)
        for item in value:
            yield from strings(item)

def grams(text):
    words = re.findall(r'\w+', text.lower())
    return set(zip(*(words[i:] for i in range(5))))

def main():
    prior_files = sorted(p for folder in ('benchmarks', 'experiments') for p in (ROOT/folder).rglob('*.json') if BASE not in p.parents)
    texts, hashes, manifest = set(), set(), []
    for path in prior_files:
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        manifest.append({'path':path.relative_to(ROOT).as_posix(), 'sha256':sha(raw)})
        for text in strings(value):
            if re.fullmatch('[0-9a-f]{64}', text):
                hashes.add(text)
            if len(text.split()) >= 150:
                texts.add(text)
                hashes.add(sha(text.encode()))
    previous = [(text, grams(text)) for text in texts]
    dataset = ROOT/'data/macsum/dataset/macdoc/val.json'
    records = json.loads(dataset.read_bytes())
    eligible=[]
    for index, record in enumerate(records):
        source='\n'.join(record['source'])
        if 250 <= len(source.split()) <= 650 and len(record['source']) >= 8 and len(source) <= 12000:
            eligible.append((index,record,source))
    random.Random(20261117).shuffle(eligible)
    selected=[]; rejects=[]
    for index,record,source in eligible:
        digest=sha(source.encode()); sg=grams(source)
        overlap=max((len(sg & pg)/len(sg | pg) for _,pg in previous), default=0)
        exact=digest in hashes or any(source in text for text,_ in previous)
        if exact or overlap >= .1:
            rejects.append({'record_index':index,'exact_seen':exact,'max_word5gram_jaccard':overlap})
            continue
        selected.append({'id':f'S{len(selected)+1:02d}','record_index':index,'metadata':record['metadata'],
                         'source':source,'source_sha256':digest,'source_words':len(source.split()),
                         'max_prior_word5gram_jaccard':overlap})
        previous.append((source,sg))
        if len(selected)==6:
            break
    assert len(selected)==6
    write('summary_sources.json',selected)
    write('source_sampling.json',{'seed':20261117,'dataset':dataset.relative_to(ROOT).as_posix(),
        'dataset_sha256':sha(dataset.read_bytes()),'eligibility':'250-650 whitespace words, >=8 original units, <=12000 code points',
        'scan_scope':'All existing benchmark and experiment JSON strings/list-joins of >=150 whitespace words and recorded 64-hex hashes; exact substring rejection plus word5gram Jaccard < .1 against prior strings and already selected sources.',
        'limitation':'Proves newness relative to preserved local JSON evidence, not unknown external training or unrecorded use.',
        'prior_json_files':manifest,'long_unique_strings':len(texts),'rejections_before_selection':rejects})
    print([(r['id'],r['record_index'],r['source_words']) for r in selected])

if __name__=='__main__':
    main()
