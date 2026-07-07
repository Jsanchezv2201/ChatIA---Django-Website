#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Create a virtual environment to avoid conflicts with system packages
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies into the virtual environment
pip install -r requirements.txt

# Run Django migrations using the virtual environment's python
python manage.py migrate

# Create the output directory to satisfy the Vercel static-build process
mkdir staticfiles_build
