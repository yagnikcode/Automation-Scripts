#!/bin/bash Docker safe cleanup script Reclaims space from overlay2 without deleting needed data

set -e

echo "🔍 Starting Docker cleanup at $(date)"

# Current usgae of Docker system
echo "---*** Docker system usage before cleanup ***---"
docker system df

# Step 1: Remove stopped containers
echo "Removing stopped containers...."
docker container prune -f

# Step 2: Remove dangling (unused) images
echo "Removing dangling images...."
docker image prune -f

# Step 3: Remove unused networks
echo "Removing unused networks...."
docker network prune -f

# Step 4: Remove dangling volumes (not in use by any container)
echo "Removing dangling volumns...."
docker volume prune -f

# Step 5: Clean build cache
echo "Removing build cache...."
docker builder prune -f

# Optional: Clean all unused images (but keep those tied to running containers) docker image prune -a -f

echo "✅ Docker cleanup completed at $(date)"

# Step 6: Show current usage
echo "---*** Docker system usage after cleanup ***---"
docker system df
