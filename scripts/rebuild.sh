#!/bin/bash
# Rebuild Docker containers

cd /home/leadokol/magnum-opus-project/repo

echo "Stopping containers..."
docker-compose down

echo "Rebuilding and starting containers..."
docker-compose up -d --build

echo "Waiting for services to start..."
sleep 10

echo "Checking status..."
docker ps --format "table {{.Names}}\t{{.Status}}"

echo "Done!"
