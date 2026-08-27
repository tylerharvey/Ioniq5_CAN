#!/bin/bash

# Set the desired quality percentage (0-100). 80 is a good balance of size and quality.
QUALITY=50

# Find all .jpg files (case-insensitive) over 1 Megabyte in the current directory
find . -maxdepth 1 -iname "*.jpg" -size +1M -print0 | while IFS= read -r -d '' file; do
    
    # Get original file size for comparison (optional, works on macOS/Linux)
    original_size=$(du -h "$file" | cut -f1)
    
    echo "Compressing: '$file' (Original Size: $original_size)"
    
    # Use ImageMagick to reduce quality. 
    # Note: If you are using ImageMagick v7+, you might need to use 'magick mogrify' instead of just 'mogrify'.
    mogrify -quality "$QUALITY" "$file"
    
done

echo "Compression complete!"
