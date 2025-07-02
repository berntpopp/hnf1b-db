#!/bin/bash

# Run code formatting and linting for the HNF1B-API project

echo "Running isort to sort imports..."
isort .

echo -e "\nRunning black to format code..."
black .

echo -e "\nRunning flake8 to check for linting errors..."
flake8 .

echo -e "\nLinting complete!"