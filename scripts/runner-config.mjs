import {readFile,writeFile} from 'node:fs/promises';
const origin=new URL(process.env.OTA_PUBLIC_ORIGIN);
if(origin.protocol!=='https:'||origin.pathname!=='/'||origin.search||origin.hash||origin.username||origin.password) throw new Error('OTA_PUBLIC_ORIGIN must be an HTTPS origin');
const config=JSON.parse(await readFile('distribution/wrangler.jsonc','utf8'));
config.account_id=process.env.CLOUDFLARE_ACCOUNT_ID;
config.r2_buckets[0].bucket_name=process.env.OTA_R2_BUCKET;
if(!config.account_id||!config.r2_buckets[0].bucket_name) throw new Error('Account and bucket are required');
await writeFile('distribution/wrangler.production.json',JSON.stringify(config,null,2)+'\n');
