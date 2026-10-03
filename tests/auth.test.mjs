import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPair,SignJWT,createLocalJWKSet,exportJWK} from 'jose';
import {authenticate,createApp} from '../src/worker.mjs';
test('JWT must match issuer, audience, expiry, signature and subject',async()=> {
 const {publicKey,privateKey}=await generateKeyPair('RS256');
 const keys=createLocalJWKSet({keys:[{...await exportJWK(publicKey),alg:'RS256',kid:'test'}]});
 const env={ACCESS_ISSUER:'https://team.cloudflareaccess.com',ACCESS_AUD:'mcp-audience'};
 const token=async aud=>new SignJWT({sub:'user'}).setProtectedHeader({alg:'RS256',kid:'test'}).setIssuer(env.ACCESS_ISSUER).setAudience(aud).setExpirationTime('1m').sign(privateKey);
 const request=t=>new Request('https://build.example/mcp',{headers:{'Cf-Access-Jwt-Assertion':t}});
 assert.equal(await authenticate(request(await token(env.ACCESS_AUD)),env,keys),'user');
 await assert.rejects(authenticate(request(await token('install-audience')),env,keys));
 await assert.rejects(authenticate(new Request('https://build.example/mcp'),env,keys));
});
test('unauthenticated MCP cannot list tools',async()=> {
 const app=createApp();const r=await app.request('/mcp',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'},{});assert.equal(r.status,401);
});
test('real MCP transport initializes and lists only bounded tools',async()=> {
 const app=createApp({verify:async()=> 'fixture-subject'}),env={PROJECTS_JSON:'{}'};
 const call=async(method,params)=>app.request('/mcp',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})},env);
 const init=await call('initialize',{protocolVersion:'2025-03-26',capabilities:{},clientInfo:{name:'test',version:'1'}});assert.equal(init.status,200);assert.equal((await init.json()).result.serverInfo.name,'asc-mcp');
 const tools=await call('tools/list',{});assert.deepEqual((await tools.json()).result.tools.map(t=>t.name).sort(),['build_app','get_build','list_apps']);
});
