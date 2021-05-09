from dagster import (
    Any,
    Bool,
    Enum,
    EnumValue,
    Field,
    Output,
    OutputDefinition,
    PresetDefinition,
    PythonObjectDagsterType,
    Selector,
    String,
    execute_pipeline,
    pipeline,
    repository,
    schedule,
    solid,
)
import os
import git
from dotenv import dotenv_values
import git
from pathlib import Path
import shutil
import logging
import requests
from pathlib import Path

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
    for repo_url in context.solid_config["urls"]:
        try:
            local_repo_dir = "/workspaces/" + get_repo_name_from_url(repo_url) 
            context.log.info("Cloning %s in %s" %(repo_url, local_repo_dir))
            repo = git.Repo.clone_from(repo_url, local_repo_dir, depth=1)
            f = []
            for (dirpath, dirnames, filenames) in os.walk("/workspaces"):
                f.extend(filenames)
                break
            context.log.info(str(dirnames))
            Path(local_repo_dir+'/yes.txt').touch()
        except Exception as e:
            context.log.error("Cloning fail %s" % repo_url)
            context.log.error(" %s" % e)
            pass

    Path('/workspaces/yes.txt').touch()
    f = []
    for (dirpath, dirnames, filenames) in os.walk("/workspaces"):
        f.extend(filenames)
        break
    context.log.info(str(dirnames))

    # return sha


@pipeline(preset_defs=[
        PresetDefinition.from_files(
            "dev",
            config_files=["git_urls.yaml"],
        )
    ])
def update_git_repo_pipeline():
    check_git_status()


@schedule(cron_schedule="* * * * *", pipeline_name="update_git_repo_pipeline", execution_timezone="Europe/Paris")
def schedule_update_repo(_context):
    return {}


@repository
def deploy_git_repository():
    return [update_git_repo_pipeline, schedule_update_repo]
