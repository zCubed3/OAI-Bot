#!/bin/python3

import importlib

import bot_module

while 1:
    bot_module.run_bot()
    importlib.reload(bot_module)
    print("Reloading bot module")