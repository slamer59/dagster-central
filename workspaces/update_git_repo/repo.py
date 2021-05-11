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
    """get_repo_name_from_url

    Args:
        url (str): [description]

    Raises:
        Exception: [description]

    Returns:
        str: [description]
    """
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1 : last_suffix_index]


def get_current_repo_name():
    return "update_git_repo"  #


# https://docs.dagster.io/tutorial/intro-tutorial/configuring-solids
@solid(config_schema={"urls": list})
def check_git_status(context):
    # https://www.devdungeon.com/content/working-git-repositories-python
    list_of_repo = [get_current_repo_name()]
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
                    "tag": repo.split("/")[-1] + ":latest",
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


@solid
def create_workspace(context, list_of_repo):
    import yaml
    import shutil
    import time

    timestr = time.strftime("%Y%m%d-%H%M%S")

    wk_filename = "/workspace.yaml"
    wk_old_filename = "/workspaces/workspace-%s.yaml" % timestr
    wk_new_filename = "/workspaces/workspace-new.yaml"

    context.log.info("Copy workspace: %s" % wk_old_filename)
    shutil.copy(wk_filename, wk_old_filename)

    context.log.info("Create new workspace:")
    list_configs = []

    for idx, val in enumerate(list_of_repo):
        conf = {
            "host": val.split("/")[-1],
            "port": 4000 + idx,
            "location_name": val.split("/")[-1],  # .replace("-", "_"),
        }
        list_configs.append({"grpc_server": conf})
        for k, v in conf.items():
            context.log.info(" - %s: %s" % (k, v))

    config = {"load_from": list_configs}

    with open(wk_new_filename, "w") as yml:
        yaml.dump(config, yml)

    return list_configs


@solid
def restart_dagit(context, _):
    client = docker.from_env()
    wk_filename = "/workspace.yaml"
    wk_new_filename = "/workspaces/workspace-new.yaml"

    for container in client.containers.list():
        name = container.name
        if "dagit" in name:
            context.log.info("Stop: %s" % name)
            client.api.stop(name)
            shutil.move(wk_new_filename, wk_filename)
            context.log.info("Start: %s" % name)
            client.api.start(name)
    return True

# https://github.com/dagster-io/dagster/blob/a57196c29d87e984ddd44c1ba9df06c012576c94/python_modules/libraries/dagster-celery-docker/dagster_celery_docker/executor.py#L281
@solid
def start_pipeline_containers(context, list_configs):
    client = docker.from_env()

    running_containers = {cont.name: cont for cont in client.containers.list()}
    context.log.info("Add containers - host port location")
    for conf in list_configs:
        host, port, location_name = conf["grpc_server"].values()
        # Don't touch running docker
        if host != "update_git_repo":
            if host in running_containers.keys():
                context.log.info("Stoping %s " % host)
                running_containers[host].stop()


            context.log.info("Start: %s %s %s" % (host, port, location_name))
            client.containers.run(
                host,
                ["sh", "-c", "dagster api grpc -h 0.0.0.0 -p %s -f repo.py" % port],
                detach=True,
                ports={port: port},
                auto_remove=True,
                environment=['%s=%s'% (k,v) for k,v in os.environ.items() if 'DAGSTER' in k] + ["DAGSTER_CURRENT_IMAGE=%s" % host],
                # publish_all_ports=True,
                volumes={
                    os.environ["DAGSTER_PWD"]
                    + "/workspaces/%s" % host: {"bind": "/opt/dagster/app"}
                },
                network="dagster_network",
                name=host
            )
    return


@pipeline(
    preset_defs=[PresetDefinition.from_files("dev", config_files=["git_urls.yaml"],)]
)
def update_git_repo_pipeline():
    git_status = check_git_status()
    create_docker_images(git_status)
    list_configs = create_workspace(git_status)
    restart_dagit(list_configs)
    start_pipeline_containers(list_configs)


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
