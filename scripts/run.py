#!/usr/bin/env python3
"""Build only a locally registered project; never execute a caller-supplied command."""
import json,os,re,subprocess,sys,tempfile
from pathlib import Path

def run(argv, cwd, env=None):
    subprocess.run(argv,cwd=cwd,env=env,check=True)

def settings(path,project,sha,job):
    if not re.fullmatch(r"[a-f0-9]{40}",sha):raise ValueError("Expected full commit SHA")
    if not re.fullmatch(r"[a-f0-9-]{36}",job):raise ValueError("Expected job UUID")
    if not re.fullmatch(r"[a-z0-9-]+",project):raise ValueError("Invalid project")
    value=json.loads(Path(path).read_text())[project]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+",value["repository"]):raise ValueError("Invalid repository")
    for key in ("project","scheme","teamId"):
        if not isinstance(value[key],str) or not value[key] or value[key].startswith('-'):raise ValueError("Invalid "+key)
    if Path(value['project']).is_absolute() or '..' in Path(value['project']).parts:raise ValueError("Project path must stay inside checkout")
    return value

def main():
    project,sha,job=sys.argv[1:4]
    cfg=settings(os.environ.get('PROJECTS_FILE','projects.json'),project,sha,job)
    service=Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix='asc-mcp-') as tmp:
        root=Path(tmp);checkout=root/'source';checkout.mkdir()
        # The credential is provided via the process environment, never a remote URL or argv.
        env=os.environ.copy()
        if env.get('SOURCE_TOKEN'):
            helper=root/'askpass';helper.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s" "x-access-token";; *) printf "%s" "$SOURCE_TOKEN";; esac\n');helper.chmod(0o700)
            env.update(GIT_ASKPASS=str(helper),GIT_TERMINAL_PROMPT='0')
        run(['git','init','-q'],checkout)
        run(['git','remote','add','origin','https://github.com/'+cfg['repository']+'.git'],checkout)
        run(['git','fetch','--depth=1','origin',sha],checkout,env)
        run(['git','checkout','--detach','FETCH_HEAD'],checkout)
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()!=sha:raise RuntimeError('Source revision mismatch')
        archive=root/'app.xcarchive';ipa=root/'app.ipa'
        build_env=os.environ.copy()
        for name in ['SOURCE_TOKEN','CLOUDFLARE_API_TOKEN','GITHUB_TOKEN','BARK_IDENTITY','BARK_ENV_FILE','BARK_ENV']:build_env.pop(name,None)
        if not (checkout/cfg['project']).exists() and (checkout/'project.yml').is_file():
            run(['xcodegen','generate','--spec','project.yml'],checkout,build_env)
        run(['asc','xcode','archive','--project',cfg['project'],'--scheme',cfg['scheme'],'--archive-path',str(archive),'--xcodebuild-flag=-destination','--xcodebuild-flag=generic/platform=iOS','--xcodebuild-flag','CURRENT_PROJECT_VERSION='+str(os.environ.get('GITHUB_RUN_NUMBER','1')),'--output','json'],checkout,build_env)
        run(['asc','xcode','export','--archive-path',str(archive),'--ipa-path',str(ipa),'--method','release-testing','--team-id',cfg['teamId'],'--output','json'],checkout,build_env)
        # ASC validates the profile and nested code before the accepted publisher changes latest.json.
        run(['asc','distribute','prepare','--ipa',str(ipa),'--output-dir',str(root/'verified'),'--source-revision',sha,'--channel',project,'--output','json'],checkout,build_env)
        public=root/'public';public.mkdir();ipa.rename(public/'app.ipa')
        publish_env=os.environ.copy()
        publish_env.update(APP_SLUG=project,APP_NAME=cfg.get('name',project),BUILT='ios',BUILD=os.environ.get('GITHUB_RUN_NUMBER','1'),OTA_MESSAGE='Source '+sha,OTA_WRANGLER_CONFIG=str(service/'distribution/wrangler.production.json'))
        run([sys.executable,str(service/'distribution/publish.py'),str(public)],service,publish_env)
if __name__=='__main__':main()
