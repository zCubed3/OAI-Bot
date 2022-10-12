#!/bin/bash

if [ $(docker images -q zcubed/openai-bot:latest 2> /dev/null) = "" ]; then
    docker zcubed/openai-bot:latest
fi

if [ $(docker inspect -f '{{.State.Running}}' openai-bot:latest) = "true" ]; then
    docker stop openai-bot
    docker container rm openai-bot
fi

git pull
docker build --tag zcubed/openai-bot .
docker run --restart=always --network=host -dit -v "$(pwd):/bot" --name "openai-bot" zcubed/openai-bot:latest