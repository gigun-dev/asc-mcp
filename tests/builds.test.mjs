import {test} from 'node:test';
import assert from 'node:assert/strict';
import {projects,resolveSource,dispatchBuild,getBuild} from '../src/builds.mjs';
const p={repository:'owner/app',trustedRef:'main',trustedAuthors:['owner']},sha='a'.repeat(40);
test('reject fork or untrusted-author PR before any build',async()=> {
 for(const pr of [{head:{repo:{full_name:'fork/app'},sha},user:{login:'owner'},state:'open'},{head:{repo:{full_name:'owner/app'},sha},user:{login:'stranger'},state:'open'}]) await assert.rejects(resolveSource(p,{pr:1},async()=>pr));
 assert.equal(await resolveSource(p,{pr:1},async()=>({head:{repo:{full_name:'owner/app'},sha},user:{login:'owner'},state:'open'})),sha);
});
test('SHA must already belong to trusted branch; exactly one source',async()=> {
 await assert.rejects(resolveSource(p,{pr:1,commit:sha},async()=>{}));
 await assert.rejects(resolveSource(p,{commit:sha},async()=>({status:'diverged'})));
 assert.equal(await resolveSource(p,{commit:sha},async()=>({status:'ahead'})),sha);
});
test('lost dispatch response is persisted and not automatically retried',async()=> {
 const writes=[];
 const db={prepare:sql=>({bind:(...args)=>({run:async()=>{writes.push({sql,args});}})})};
 const env={PROJECTS_JSON:JSON.stringify({app:p}),CONTROL_REPOSITORY:'owner/control',JOBS:db};
 let calls=0;
 const job=await dispatchBuild({env,owner:'subject',input:{project:'app',commit:sha},github:async path=>{if(path.includes('compare'))return {status:'identical'};calls++;throw Error('Connection lost');}});
 assert.equal(calls,1);assert.match(writes[1].sql,/dispatch_unknown/);assert.ok(job.job_id);
});
test('other user cannot inspect a job or reach GitHub',async()=> {
 const env={JOBS:{prepare:()=>({bind:()=>({first:async()=>null})})}};
 await assert.rejects(getBuild({env,owner:'other',id:'id',github:()=>{throw Error('should not call');}}),/not found/);
});
test('project config rejects arbitrary command fields',()=>assert.throws(()=>projects(JSON.stringify({app:{...p,command:'rm -rf'}}))));
