import { readFile,writeFile } from 'node:fs/promises';
const config=JSON.parse(await readFile(process.argv[2]??'config.local.json','utf8'));
for(const key of ['accountId','mcpOrigin','installOrigin','accessIssuer','accessAudience','installAudience','databaseId','controlRepository','projects']) if(!config[key]) throw new Error(`Missing ${key}`);
for(const key of ['mcpOrigin','installOrigin','accessIssuer']) {const u=new URL(config[key]);if(u.protocol!=='https:'||u.pathname!=='/'||u.search||u.hash||u.username||u.password) throw new Error(`${key} must be an HTTPS origin`);config[key]=u.origin;}
const wrangler=JSON.parse(await readFile('wrangler.jsonc','utf8'));
wrangler.account_id=config.accountId;
wrangler.routes=[{pattern:new URL(config.mcpOrigin).hostname,custom_domain:true}];
wrangler.d1_databases[0].database_id=config.databaseId;
wrangler.vars={ACCESS_ISSUER:config.accessIssuer,ACCESS_AUD:config.accessAudience,CONTROL_REPOSITORY:config.controlRepository,PUBLIC_ORIGIN:config.installOrigin,PROJECTS_JSON:JSON.stringify(Object.fromEntries(Object.entries(config.projects).map(([name,{repository,trustedRef,trustedAuthors}])=>[name,{repository,trustedRef,trustedAuthors}])))};
await writeFile('wrangler.production.json',JSON.stringify(wrangler,null,2)+'\n');
const distribution=JSON.parse(await readFile('distribution/wrangler.jsonc','utf8'));
distribution.account_id=config.accountId;
distribution.routes=[{pattern:new URL(config.installOrigin).hostname,custom_domain:true}];
distribution.r2_buckets[0].bucket_name=config.artifactBucket??'ios-build-artifacts';
distribution.vars={ACCESS_ISSUER:config.accessIssuer,ACCESS_AUD:config.installAudience,PUBLIC_ORIGIN:config.installOrigin};
await writeFile('distribution/wrangler.production.json',JSON.stringify(distribution,null,2)+'\n');
console.log('Generated wrangler.production.json; secrets remain separate.');
