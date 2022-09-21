#!/bin/bash

docker run --restart=always --network=host -dit -v "$(pwd):/bot" --name "openai-bot-instance" zcubed/openai-bot:latest