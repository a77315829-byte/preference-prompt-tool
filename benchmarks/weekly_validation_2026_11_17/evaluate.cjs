'use strict';
// Reuse unchanged safety/type compiler and loader; only task/runtime inputs are new.
const fs=require('node:fs');
const path=require('node:path');
const {inspectCandidate,evaluateCandidate}=require('../react_style_current/evaluate.cjs');
const runtime=require('./runtime.cjs');
async function main(){
 const [taskId,candidatePath,mode]=process.argv.slice(2);
 const task=JSON.parse(fs.readFileSync(path.join(__dirname,'react_tasks.json'),'utf8')).find(t=>t.id===taskId);
 if(!task)throw new Error('Unknown task');
 const candidate=JSON.parse(fs.readFileSync(candidatePath,'utf8'));
 const result=mode==='--inspect'?inspectCandidate(candidate):await evaluateCandidate(task,candidate,{reviewed:mode==='--reviewed',runtime});
 process.stdout.write(JSON.stringify(result));
}
main().catch(error=>{process.stderr.write(String(error.stack));process.exitCode=1;});
