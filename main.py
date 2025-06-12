

#!/usr/bin/env python3
"""
Main script to fetch RSS feeds and generate translated summaries in one command.
"""

import os
import sys

# Ensure the current script's directory is in the module search path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from rss_fetch import main as fetch_main
from AI_summarize import main as summarize_main

def main():
    # Step 1: Fetch RSS feeds and save as Markdown
    fetch_main()
    # Step 2: Translate and summarize the generated Markdown files
    summarize_main()

if __name__ == "__main__":
    main()