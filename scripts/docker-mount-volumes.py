# https://docs.docker.com/engine/api/sdk/examples/
import docker
import os
client = docker.from_env()
client.containers.run(
    "docker_example_pipelines_image:latest", 
    ["sh", "-c", "dagster api grpc -h 0.0.0.0 -p 4001 -f repo.py"], 
    detach=True, 
    volumes={ os.getcwd() + "/workspaces/dagster-from-user-code":{"bind":"/opt/dagster/app"}}
)

print(client.containers.list())