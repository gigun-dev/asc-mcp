import { z } from 'zod';
const projectSchema=z.object({repository:z.string().regex(/^[\w.-]+\/[\w.-]+$/), trustedRef:z.string().default('main'), trustedAuthors:z.array(z.string()).min(1)}).strict();
export function projects(raw) { return z.record(z.string().regex(/^[a-z0-9-]+$/),projectSchema).parse(JSON.parse(raw)); }
export async function resolveSource(project, input, github) {
 if ((input.pr===undefined)===(input.commit===undefined)) throw new Error('Specify exactly one of pr or commit');
 const base=`/repos/${project.repository}`;
 if (input.pr!==undefined) {
  const pr=await github(`${base}/pulls/${input.pr}`);
  // A repo allowlist alone is insufficient: a fork PR still executes foreign build scripts.
  if(pr.head.repo?.full_name!==project.repository || !project.trustedAuthors.includes(pr.user.login) || pr.state!=='open') throw new Error('PR must be open, from this repository, and by a configured trusted author');
  return pr.head.sha;
 }
 if(!/^[a-f0-9]{40}$/.test(input.commit)) throw new Error('commit must be a full SHA');
 const comparison=await github(`${base}/compare/${input.commit}...${encodeURIComponent(project.trustedRef)}`);
 if(!['ahead','identical'].includes(comparison.status)) throw new Error('commit must be an ancestor of the trusted branch; use pr for unmerged changes');
 return input.commit;
}
export async function dispatchBuild({env,owner,input,github}) {
 const project=projects(env.PROJECTS_JSON)[input.project];
 if(!project) throw new Error('Unknown project');
 const sha=await resolveSource(project,input,github);
 const id=crypto.randomUUID();
 await env.JOBS.prepare("INSERT INTO jobs(id,owner,project,sha,state) VALUES(?,?,?,?,'dispatching')").bind(id,owner,input.project,sha).run();
 let state='dispatched';
 try {
  await github(`/repos/${env.CONTROL_REPOSITORY}/actions/workflows/build.yml/dispatches`,{ref:'main',inputs:{job_id:id,project:input.project,commit:sha}});
  await env.JOBS.prepare("UPDATE jobs SET state='dispatched' WHERE id=?").bind(id).run();
 } catch {
  state='dispatch_unknown';
  // A lost response can follow an accepted dispatch. Do not blindly submit the same build again.
  await env.JOBS.prepare("UPDATE jobs SET state='dispatch_unknown' WHERE id=?").bind(id).run();
 }
 return {job_id:id,project:input.project,commit:sha,state,next:'Use get_build to check dispatch and execution; do not resubmit on a timeout.'};
}
export async function getBuild({env,owner,id,github}) {
 const job=await env.JOBS.prepare('SELECT id,project,sha,state,created_at FROM jobs WHERE id=? AND owner=?').bind(id,owner).first();
 if(!job) throw new Error('Build not found');
 // GitHub has no input filter for runs. Correlate the UUID in a fixed workflow run-name.
 for(let page=1;page<=5;page++) {
  const {workflow_runs:runs}=await github(`/repos/${env.CONTROL_REPOSITORY}/actions/workflows/build.yml/runs?event=workflow_dispatch&per_page=100&page=${page}`);
  const run=runs.find(r=>r.display_title===`ios-build ${id}`);
  if(run) return {...job,state:run.status,conclusion:run.conclusion,url:run.html_url,install_url:run.conclusion==='success'?`${env.PUBLIC_ORIGIN}/${job.project}/`:undefined};
  if(runs.length<100) break;
 }
 return {...job,message:'No matching run found in the latest 500 dispatches. Check GitHub before retrying.'};
}
