'use strict';
// Investigator-written local controls, manually reviewed before execution.
// Imports only React; no IO/timers/storage/network/dynamic candidate code.
const fs = require('node:fs');
const path = require('node:path');
const { evaluateCandidate } = require('../react_style_current/evaluate.cjs');
const runtime = require('./runtime.cjs');
const tasks = JSON.parse(fs.readFileSync(path.join(__dirname,'react_tasks.json'),'utf8'));
const bodies = {
reading_history: `
 const [input,setInput]=useState(''); const [history,setHistory]=useState<number[]>([]); const [latest,setLatest]=useState<number|null>(null); const [error,setError]=useState('');
 const record=()=>{const s=input.trim(), n=Number(s);if(!/^-?\\d+$/.test(s)||!Number.isSafeInteger(n)){setError('Invalid reading');return;}setHistory([...history,n]);setLatest(n);setInput('');setError('');props.onRecord(n);};
 return <div data-testid="panel"><input aria-label="Reading" value={input} onChange={e=>setInput(e.target.value)}/><button onClick={record}>Record</button><button onClick={()=>{setHistory([]);setLatest(null);setInput('');setError('');}}>Clear</button><output aria-label="Latest">{latest??'None'}</output><ul aria-label="History">{history.map((v,i)=><li key={i}>{v}</li>)}</ul>{error&&<p role="alert">{error}</p>}</div>;`,
cent_split: `
 const [c,setC]=useState(props.initialCents),[p,setP]=useState(props.initialPeople);const n=Number(c.trim()),k=Number(p.trim());const valid=/^\\d+$/.test(c.trim())&&/^\\d+$/.test(p.trim())&&Number.isSafeInteger(n)&&Number.isSafeInteger(k)&&n>=0&&k>=1&&k<=20;
 const result=valid?Array.from({length:k},(_,i)=>Math.floor(n/k)+(i<n%k?1:0)).join(', '):'Invalid allocation';
 return <div data-testid="panel"><input aria-label="Cents" value={c} onChange={e=>setC(e.target.value)}/><input aria-label="People" value={p} onChange={e=>setP(e.target.value)}/><output aria-label="Allocation">{result}</output></div>;`,
signal_cycle: `
 const [signal,setSignal]=useState<Signal>('stop');const change=(next:Signal)=>{setSignal(next);props.onChange(next);};
 return <div data-testid="panel"><output aria-label="Signal">{signal}</output><button onClick={()=>change(signal==='stop'?'ready':signal==='ready'?'go':'stop')}>Next</button><button disabled={signal==='stop'} onClick={()=>change('stop')}>Reset</button></div>;`,
text_normalizer: `
 const [text,setText]=useState(props.initialText),[mode,setMode]=useState('keep'),[trim,setTrim]=useState(false);const raw=trim?text.trim():text;const result=mode==='upper'?raw.toUpperCase():mode==='lower'?raw.toLowerCase():raw;
 return <div data-testid="panel"><textarea aria-label="Text" value={text} onChange={e=>setText(e.target.value)}/><select aria-label="Case" value={mode} onChange={e=>setMode(e.target.value)}><option value="keep">keep</option><option value="upper">upper</option><option value="lower">lower</option></select><input type="checkbox" aria-label="Trim" checked={trim} onChange={e=>setTrim(e.target.checked)}/><output aria-label="Result">{result}</output><output aria-label="Characters">{result.length}</output></div>;`,
question_deck: `
 const [deck]=useState(()=>[...props.cards]);const [index,setIndex]=useState(0);const next=()=>{if(index>=deck.length)return;const n=index+1;setIndex(n);if(n===deck.length)props.onFinish(deck.map(c=>c.id));};
 return <div data-testid="panel"><output aria-label="Current">{deck[index]?.text??'Done'}</output><output aria-label="Completed">{index}</output><button disabled={index>=deck.length} onClick={next}>Next</button><button onClick={()=>setIndex(0)}>Restart</button></div>;`,
weighted_counter: `
 const [baseline]=useState(props.initialValue),[value,setValue]=useState(props.initialValue);const change=(next:number)=>{setValue(next);props.onChange(next);};
 return <div data-testid="panel"><output aria-label="Value">{value}</output><button onClick={()=>change(value+props.step)}>Add</button><button onClick={()=>change(value-props.step)}>Subtract</button><button disabled={value===baseline} onClick={()=>change(baseline)}>Reset</button></div>;`,
comparison_snapshot: `
 const [left,setLeft]=useState(''),[right,setRight]=useState(''),[result,setResult]=useState<Relation|null>(null),[error,setError]=useState('');const compare=()=>{const a=Number(left.trim()),b=Number(right.trim());if(!/^-?\\d+$/.test(left.trim())||!/^-?\\d+$/.test(right.trim())||!Number.isSafeInteger(a)||!Number.isSafeInteger(b)){setError('Invalid integers');return;}const relation=a<b?'less':a>b?'greater':'equal';setResult(relation);setError('');props.onCompare(relation);};
 return <div data-testid="panel"><input aria-label="Left" value={left} onChange={e=>setLeft(e.target.value)}/><input aria-label="Right" value={right} onChange={e=>setRight(e.target.value)}/><button onClick={compare}>Compare</button><output aria-label="Result">{result??'Not compared'}</output>{error&&<p role="alert">{error}</p>}</div>;`,
item_reorder: `
 const [items,setItems]=useState(()=>[...props.initialItems]);const move=(index:number,delta:number)=>{const next=[...items];[next[index],next[index+delta]]=[next[index+delta],next[index]];setItems(next);props.onChange(next.map(x=>x.id));};
 return <div data-testid="panel"><ul aria-label="Items">{items.map((item,i)=><li key={item.id}><span>{item.label}</span><button disabled={i===0} onClick={()=>move(i,-1)}>Up {item.id}</button><button disabled={i===items.length-1} onClick={()=>move(i,1)}>Down {item.id}</button></li>)}</ul>{items.length===0&&<p role="status">No items</p>}</div>;`
};
const mutations = {
 reading_history:['setHistory([...history,n])','setHistory(history)'],
 cent_split:['(i<n%k?1:0)','0'],
 signal_cycle:["signal==='stop'?'ready':signal==='ready'?'go':'stop'","'ready'"],
 text_normalizer:['raw.toUpperCase()','raw.toLowerCase()'],
 question_deck:['if(n===deck.length)','if(n===1)'],
 weighted_counter:['value+props.step','value+1'],
 comparison_snapshot:["a<b?'less':a>b?'greater'","left<right?'less':left>right?'greater'"],
 item_reorder:['setItems(next)','setItems(items)']
};
async function main(){
 const rows=[];
 for(const task of tasks){
  const prefix="import { useState } from 'react';\n"+task.contract_types.replaceAll('ExpectedProps','Props')+'\nexport function Component(props:Props){';
  const code=prefix+bodies[task.id]+'\n}';
  const candidate={files:{'Component.tsx':code}};
  const good=await evaluateCandidate(task,candidate,{reviewed:true,runtime});
  const [from,to]=mutations[task.id];if(!code.includes(from))throw new Error('Missing mutation '+task.id);
  const mutant={files:{'Component.tsx':code.replace(from,to)}};
  const bad=await evaluateCandidate(task,mutant,{reviewed:true,runtime});
  rows.push({id:task.id,reference:{types:good.types,runtime:good.runtime,safety:good.safety},mutant:{types:bad.types,runtime:bad.runtime,safety:bad.safety},mutation:{from,to}});
 }
 const result={review:'Investigator manually reviewed all source strings and one-line mutations; candidate code uses only React state, local arithmetic, array/text processing and event callbacks.',all_references_pass:rows.every(r=>r.reference.types.passed&&r.reference.runtime.passed),all_mutants_detected:rows.every(r=>r.mutant.types.passed&&!r.mutant.runtime.passed),rows};
 fs.writeFileSync(path.join(__dirname,'controls_results.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({all_references_pass:result.all_references_pass,all_mutants_detected:result.all_mutants_detected,rows:rows.map(r=>({id:r.id,good:r.reference.runtime.checks?.filter(c=>c.passed).length,bad:r.mutant.runtime.checks?.filter(c=>!c.passed).map(c=>c.name)}))},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
