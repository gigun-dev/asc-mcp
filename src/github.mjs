import { SignJWT, importPKCS8 } from 'jose';
export async function installationToken(env, fetcher = fetch) {
 const now = Math.floor(Date.now()/1000);
 const key = await importPKCS8(env.GITHUB_APP_PRIVATE_KEY, 'RS256');
 const jwt = await new SignJWT({}).setProtectedHeader({alg:'RS256'}).setIssuer(env.GITHUB_APP_ID).setIssuedAt(now-60).setExpirationTime(now+540).sign(key);
 const response = await fetcher(`https://api.github.com/app/installations/${env.GITHUB_INSTALLATION_ID}/access_tokens`, {
  method:'POST', headers:headers(jwt), body:JSON.stringify({repositories:[env.CONTROL_REPOSITORY.split('/')[1], ...new Set(Object.values(JSON.parse(env.PROJECTS_JSON)).map(p=>p.repository.split('/')[1]))]})
 });
 if (!response.ok) throw new Error(`GitHub installation authentication failed (${response.status})`);
 return (await response.json()).token;
}
function headers(token) { return {'Authorization':`Bearer ${token}`, 'Accept':'application/vnd.github+json','User-Agent':'ios-build','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'}; }
export function githubClient(token, fetcher = fetch) {
 return async (path, body) => {
  const r=await fetcher(`https://api.github.com${path}`, {method:body===undefined?'GET':'POST',headers:headers(token), ...(body===undefined?{}:{body:JSON.stringify(body)}), signal:AbortSignal.timeout(20000)});
  if (!r.ok) throw new Error(`GitHub request failed (${r.status})`);
  return r.status===204 ? null : r.json();
 };
}
