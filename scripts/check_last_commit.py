import os
import git
from dotenv import dotenv_values
envs = dotenv_values()

# https://www.devdungeon.com/content/working-git-repositories-python


# Check out via HTTPS
# git.Repo.clone_from(envs['GIT_REMOTE'], 'Cookbook-https')
import git
from pathlib import Path
import shutil


repo_url = envs['GIT_REMOTE']
local_repo_dir = Path(envs['GIT_LOCAL'])

# delete the repo if it exists, perform shallow clone, get SHA, delete repo
shutil.rmtree(local_repo_dir)
local_repo_dir.unlink(missing_ok=True)

repo = git.Repo.clone_from(repo_url, local_repo_dir, depth=1)
sha = repo.rev_parse(envs['GIT_BRANCH'])
# local_repo_dir.unlink()
print(sha)

# List remotes
print('Remotes:')
for remote in repo.remotes:
    print(f'- {remote.name} {remote.url}')

# Create a new remote
try:
    remote = repo.create_remote('origin', url=envs['GIT_REMOTE'])
except git.exc.GitCommandError as error:
    print(f'Error creating remote: {error}')

# Reference a remote by its name as part of the object
print(f'Remote name: {repo.remotes.origin.name}')
print(f'Remote URL: {repo.remotes.origin.url}')

# Hash from commit
sha = repo.head.object.hexsha
print(f'Commit hash URL: {sha}')
# Delete a remote
# repo.delete_remote('myremote')

# Pull from remote repo
print(repo.remotes.origin.pull())
# Push changes
print(repo.remotes.origin.push())

# diff = repo.git.diff('HEAD~1..HEAD', name_only=True)

####################
# Using usbprocess

import subprocess
import re

repo_url = envs['GIT_REMOTE']
process = subprocess.Popen(["git", "ls-remote", repo_url], stdout=subprocess.PIPE)
stdout, stderr = process.communicate()
sha = re.split(r'\t+', stdout.decode('ascii'))[0]
print(sha)
