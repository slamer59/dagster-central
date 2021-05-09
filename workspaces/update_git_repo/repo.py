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
import docker


def get_repo_name_from_url(url: str) -> str:
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1 : last_suffix_index]


# https://docs.dagster.io/tutorial/intro-tutorial/configuring-solids
@solid(config_schema={"urls": list})
def check_git_status(context):
    # https://www.devdungeon.com/content/working-git-repositories-python
    list_of_repo = []
    # Check out via HTTPS
    for repo_url in context.solid_config["urls"]:
        try:
            repo_name = get_repo_name_from_url(repo_url)
            local_repo_dir = "/workspaces/" + repo_name
            if Path(local_repo_dir).exists():
                context.log.info("Pull %s in %s" % (repo_url, local_repo_dir))
                repo = git.Repo(local_repo_dir)
                orig = repo.remotes.origin
                orig.pull()
                context.log.info("Success")
                list_of_repo.append(local_repo_dir)
            else:
                context.log.info("Cloning %s in %s" % (repo_url, local_repo_dir))
                repo = git.Repo.clone_from(repo_url, local_repo_dir, depth=1)
                list_of_repo.append(local_repo_dir)
        except Exception as e:
            context.log.error("Cloning fail %s" % repo_url)
            context.log.error(" %s" % e)
            pass
    return list_of_repo


@solid
def create_docker_images(context, list_of_repo):
    # https://docs.docker.com/engine/api/sdk/examples/

    import os
    import glob

    client = docker.from_env()
    context.log.info("Creating images:")
    for repo in list_of_repo:
        for dockerfile in glob.glob(repo + "/Dockerfile*"):
            context.log.info(" - %s: %s" % (repo, dockerfile))
            try:
                build_opts = {
                    "path": repo,
                    "dockerfile": dockerfile,
                    "tag": repo.split("/")[-1]+":auto",
                }
                context.log.info("Build options: ")
                for k, v in build_opts.items():
                    context.log.info(" - %s: %s" % (k, v))

                client.images.build(**build_opts)
            except Exception as e:
                context.log.error("Build fail %s" % repo)
                context.log.error(" %s" % e)
                pass

    # client.containers.run(
    #     "docker_example_pipelines_image:latest",
    #     ["sh", "-c", "dagster api grpc -h 0.0.0.0 -p 4001 -f repo.py"],
    #     detach=True,
    #     volumes={ os.getcwd() + "/workspaces/dagster-from-user-code":{"bind":"/opt/dagster/app"}}
    # )


@pipeline(
    preset_defs=[PresetDefinition.from_files("dev", config_files=["git_urls.yaml"],)]
)
def update_git_repo_pipeline():
    create_docker_images(check_git_status())


@schedule(
    cron_schedule="* * * * *",
    pipeline_name="update_git_repo_pipeline",
    execution_timezone="Europe/Paris",
)
def schedule_update_repo(_context):
    return {}


@repository
def deploy_git_repository():
    return [update_git_repo_pipeline, schedule_update_repo]
