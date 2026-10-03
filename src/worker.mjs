import { Hono } from 'hono';
import {bodyLimit} from 'hono/body-limit';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPTransport } from '@hono/mcp';
import { z } from 'zod';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import { projects, dispatchBuild, getBuild } from './builds.mjs';
import { installationToken, githubClient } from './github.mjs';
export async function authenticate(request,env,keys) {
 const token=request.headers.get('Cf-Access-Jwt-Assertion');
 if(!token || !env.ACCESS_ISSUER || !env.ACCESS_AUD) throw new Error('Unauthorized');
 const {payload}=await jwtVerify(token,keys??createRemoteJWKSet(new URL(`${env.ACCESS_ISSUER}/cdn-cgi/access/certs`)),{issuer:env.ACCESS_ISSUER,audience:env.ACCESS_AUD,algorithms:['RS256']});
 if(!payload.sub) throw new Error('Unauthorized');
 return payload.sub;
}
export function createApp({verify=authenticate,githubFactory=async env=>githubClient(await installationToken(env))}={}) {
 const app=new Hono();
 app.get('/health',c=>c.json({status:'ok',service:'asc-mcp'}));
 app.use('/mcp',bodyLimit({maxSize:65536}));
 app.all('/mcp',async c=> {
  const origin=c.req.header('Origin');
  if(origin && origin!==new URL(c.req.url).origin) return c.json({error:'Invalid origin'},403);
  let owner;
  try { owner=await verify(c.req.raw,c.env); } catch { return c.json({error:'Unauthorized'},401); }
  const server=new McpServer({name:'asc-mcp',version:'0.1.0'});
  const result=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
  const guarded=handler=>async input=> {try {return result(await handler(input));}catch(error){console.error(JSON.stringify({event:'tool_failure',error:error.message}));return {isError:true,content:[{type:'text',text:error.message}]};}};
  server.registerTool('list_apps',{description:'List configured iOS apps available for private builds.',inputSchema:{},annotations:{readOnlyHint:true}},guarded(async()=>Object.entries(projects(c.env.PROJECTS_JSON)).map(([name,p])=>({project:name,repository:p.repository,install_url:`${c.env.PUBLIC_ORIGIN}/${name}/`}))));
  server.registerTool('build_app',{description:'Build and privately distribute one trusted PR or full commit SHA. Returns a job ID, not a completed build.',inputSchema:{project:z.string(),pr:z.number().int().positive().optional(),commit:z.string().optional()},annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:false}},guarded(async input=>dispatchBuild({env:c.env,owner,input,github:await githubFactory(c.env)})));
  server.registerTool('get_build',{description:'Inspect a build owned by the signed-in user, including GitHub logs and install URL on success.',inputSchema:{job_id:z.string().uuid()},annotations:{readOnlyHint:true}},guarded(async input=>getBuild({env:c.env,owner,id:input.job_id,github:await githubFactory(c.env)})));
  const transport=new StreamableHTTPTransport({enableJsonResponse:true,strictAcceptHeader:true});
  await server.connect(transport);
  return await transport.handleRequest(c) ?? c.json({error:'Transport failed'},500);
 });
 app.onError((error,c)=>{console.error(JSON.stringify({event:'request_failure',error:error.message}));return c.json({error:'Service unavailable'},503);});
 return app;
}
export default createApp();
