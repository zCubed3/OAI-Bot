#!/bin/bash

docker run --restart=always --network=host -dit -v "$(pwd):/bot" --name "openai-bot" zcubed/openai-bot:latest