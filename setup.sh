#!/bin/bash

mkdir -p lambda_example/package
cd lambda_example/package
pip install --target . -r ../../requirements.txt
zip -r ../my-package.zip .
cd ..
zip -g my-package.zip index.py
