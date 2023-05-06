#!/bin/bash

docker run -v ./request_cache:/src/request_cache \
           -v ./tokens:/src/tokens \
           -w /src \
           enlighten python monitor.py
