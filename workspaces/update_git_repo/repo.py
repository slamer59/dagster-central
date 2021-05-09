from dagster import pipeline, repository, schedule, solid
import os
import git
from dotenv import dotenv_values
import git
from pathlib import Path
import shutil
import logging
import requests
from os import walk

def get_repo_name_from_url(url: str) -> str:
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1:last_suffix_index]

# https://docs.dagster.io/tutorial/intro-tutorial/configuring-solids
@solid(config_schema={"urls": list})
def check_git_status(context):    
    # https://www.devdungeon.com/content/working-git-repositories-python

    # Check out via HTTPS
    # git.Repo.clone_from(envs['GIT_REMOTE'], 'Cookbook-https')
    
    for repo_url in context.solid_config["urls"]:
        
        local_repo_dir = "TEMP_GIT/" + get_repo_name_from_url(repo_url) 
        # branch = "main"
        # repo_url += "/archive/refs/heads/%s.zip" % branch #envs['GIT_REMOTE']
        
        # fname = branch + ".zip"

        # r = requests.get(repo_url)
        # open(fname , 'wb').write(r.content)
        # import zipfile
        # with zipfile.ZipFile(fname, 'r') as zip_ref:
        #     zip_ref.extractall(local_repo_dir)

        # # envs['GIT_LOCAL']
        

        # context.log.info("Clone %s in %s" %(repo_url, local_repo_dir))
        repo = git.Repo.clone_from(repo_url, local_repo_dir, depth=1)
        f = []
        for (dirpath, dirnames, filenames) in walk("TEMP_GIT"):
            f.extend(filenames)
            break
        context.log.info(str(dirnames))


    # return sha


@pipeline
def update_git_repo_pipeline():
    check_git_status()


@schedule(cron_schedule="* * * * *", pipeline_name="update_git_repo_pipeline", execution_timezone="Europe/Paris")
def schedule_update_repo(_context):
    return {}


@repository
def deploy_git_repository():
    return [update_git_repo_pipeline, schedule_update_repo]
