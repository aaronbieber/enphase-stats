#!/bin/bash

docker run -v ${PWD}/config.py:/src/config.py \
           -v ${PWD}/request_cache:/src/request_cache \
           -v ${PWD}/tokens:/src/tokens \
           -w /src \
           enlighten python monitor.py
