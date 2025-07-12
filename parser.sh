#!/bin/sh

Xvfb :99 -screen 0 1920x1980x24 &

export DISPLAY=:99

PYTHONPATH=. taskiq worker src.scheduler.task_queue:broker