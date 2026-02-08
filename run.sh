#!/bin/bash

abort()
{
    echo "*** FAILED ***" >&2
    exit 1
}

if [ "$#" -eq 0 ]; then
    echo "No arguments provided. Usage: 
    1. '-local' to build local environment
    2. '-docker' to build and run docker container
    3. '-test' to run linter, formatter and tests
    4. '-benchmark' to run benchmark tests
    5. '-run-server' to run fastapi server
    6. '-setup' to run package setup
    7. '-run-gui' to launch the GTK4 desktop application"
elif [ $1 = "-local" ]; then
    trap 'abort' 0
    set -e
    echo "Running format, linter and tests"
    rm -rf .venv
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install setuptools
    pip install -r ./requirements.txt

    black wisprtux tests
    pylint --fail-under=9.9 wisprtux tests
    pytest --ignore=tests/benchmark --cov-fail-under=95 --cov wisprtux -v tests
elif [ $1 = "-test" ]; then
    trap 'abort' 0
    set -e
    
    echo "Running format, linter and tests"
    source .venv/bin/activate
    black wisprtux tests
    pylint --fail-under=9.9 wisprtux tests
    pytest --ignore=tests/benchmark --cov-fail-under=95 --cov --log-cli-level=INFO wisprtux -v tests
elif [ $1 = "-docker" ]; then
    echo "Building and running docker image"
    docker stop wisprtux-container
    docker rm wisprtux-container
    docker rmi wisprtux-image
    # build docker and run
    docker build --tag wisprtux-image --build-arg CACHEBUST=$(date +%s) . --file Dockerfile.test
    docker run --name wisprtux-container -p 8888:8888 -d wisprtux-image
elif [ $1 = "-benchmark" ]; then
    echo "Running WisprTux Server"
    source .venv/bin/activate
    kill $(lsof -t -i:8181) 
    nohup uvicorn wisprtux.fast_server:app --host 0.0.0.0 --port 8181 &
    sleep 2s
    echo "Running WisprTux benchmark tests"
    pytest -v -s tests/benchmark
    kill $(lsof -t -i:8181)
elif [ $1 = "-run-server" ]; then
    echo "Running WisprTux server"
    source .venv/bin/activate
    kill $(lsof -t -i:8181) 
    uvicorn wisprtux.fast_server:app --host 0.0.0.0 --port 8181
elif [ $1 = "-run-gui" ]; then
    source .venv/bin/activate
    python3 -m wisprtux.gui
elif [ $1 = "-test-package" ]; then
    echo "Running WisprTux package setup"
    # pip install twine
    # pip install wheel
    python setup.py sdist bdist_wheel
    rm -rf .venv_test
    python3 -m venv .venv_test
    source .venv_test/bin/activate
    pip install ./dist/wisprtux-1.0.0-py3-none-any.whl
    pytest --ignore=tests/benchmark --cov-fail-under=95 --cov wisprtux -v tests
    # twine upload ./dist/*
else
  echo "Wrong argument is provided. Usage:
    1. '-local' to build local environment
    2. '-docker' to build and run docker container
    3. '-test' to run linter, formatter and tests
    4. '-benchmark' to run benchmark tests
    5. '-run-server' to run fastapi server
    6. '-setup' to run package setup
    7. '-run-gui' to launch the GTK4 desktop application"
fi

trap : 0
echo >&2 '*** DONE ***'