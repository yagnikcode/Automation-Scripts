#!/bin/bash

# Source directory to back up
SOURCE_DIR="/home/user/data"

# Backup destination
BACKUP_DIR="/home/user/backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Date format
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Backup file name
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

# Create compressed backup
tar -czf "$BACKUP_FILE" "$SOURCE_DIR"

# Check backup status
if [ $? -eq 0 ]; then
    echo "Backup completed successfully: $BACKUP_FILE"
else
    echo "Backup failed!"
fi

# Delete backups older than 7 days
find "$BACKUP_DIR" -type f -name "*.tar.gz" -mtime +7 -delete
