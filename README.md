# Whale Tracker Server

## Installation

1. Install python **3.11**

    `sudo yum install python3.11`

2. Create virtual environment

    `python -m venv .venv`

3. Activate virtual environment

    `source .venv/bin/activate`

4. Install dependencies

    `pip install -r requirements.txt`

5. Set environment variables

    `nano .env`

6. Create state directory

    `mkdir .state`
    `mkdir .state/tracked_wallets`
