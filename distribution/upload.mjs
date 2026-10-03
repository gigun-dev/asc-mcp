import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {S3Client,PutObjectCommand} from '@aws-sdk/client-s3';

try {
 const [file,bucket,key]=process.argv.slice(2);
 const account=process.env.CLOUDFLARE_ACCOUNT_ID,accessKeyId=process.env.R2_ACCESS_KEY_ID,token=process.env.CLOUDFLARE_API_TOKEN;
 if(!/^[a-f0-9]{32}$/.test(account||'') || !/^[a-f0-9]{32}$/.test(accessKeyId||'') || !token)throw new Error('Missing R2 credentials');
 // Bucket-scoped tokens are supported by S3, not Wrangler's REST object API.
 // Cloudflare defines the S3 secret as SHA-256 of the API token value.
 const client=new S3Client({region:'auto',endpoint:`https://${account}.r2.cloudflarestorage.com`,forcePathStyle:true,credentials:{accessKeyId,secretAccessKey:createHash('sha256').update(token).digest('hex')},requestChecksumCalculation:'WHEN_REQUIRED'});
 try {
  await client.send(new PutObjectCommand({Bucket:bucket,Key:key,Body:await readFile(file),ContentType:key.endsWith('.json')?'application/json':'application/octet-stream'}));
 } finally {client.destroy();}
} catch(error) {
 // Never emit credential-bearing SDK request objects or response bodies.
 console.error(`S3 upload failed: ${error.name} (HTTP ${error.$metadata?.httpStatusCode||'unavailable'})`);
 process.exitCode=1;
}
