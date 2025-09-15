#!/bin/sh

echo "Updating APP Configuration Service URL in .env file..."
# This script updates the deployed APP Configuration Service URL in .env file.
sed -i "s|^APP_CONFIGURATION_URL=.*|APP_CONFIGURATION_URL=\"$(azd env get-value APP_CONFIGURATION_URL)\"|" ./src/.env

