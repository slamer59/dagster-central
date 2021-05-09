from dagster import pipeline, repository, schedule, solid


@solid
def hello_local(_):
    return 1


@pipeline
def my_pipline_local_code():
    hello_local()


@schedule(cron_schedule="* * * * *", pipeline_name="my_pipline_local_code", execution_timezone="US/Central")
def my_schedule_local_code(_context):
    return {}


@repository
def deploy_docker_repository():
    return [my_pipline_local_code, my_schedule_local_code]
