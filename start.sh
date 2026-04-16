#!/bin/bash
# Run this once to install deps and start the server
cd "$(dirname "$0")"
pip3 install -r requirements.txt
python3 app.py
