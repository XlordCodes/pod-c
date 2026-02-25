# app/seeds/__main__.py
"""
Module: Main Seed Runner
Context: Pod B - Module 6 (Data Fixtures).

Orchestrates the execution of data seeding scripts.
Ensures dependencies are met (e.g., Users must exist before Inventory).

Usage:
    python -m app.seeds           # Run all seeds
    python -m app.seeds database  # Reset core DB (Users, Roles)
    python -m app.seeds inventory # Add Products/Stock
    python -m app.seeds analytics # Simulate traffic (Requires Server Up)

ERROR HANDLING:
    - Any seed failure triggers immediate exit with non-zero status code
    - Errors are logged before exit for debugging
    - No "Completed" message is shown on failure
"""

import sys
import logging
import time
from typing import Callable

# Import Seed Modules
try:
    from app.seeds import seed_database
    from app.seeds import seed_inventory
    from app.seeds import seed_analytics
except ImportError as e:
    sys.exit(f"❌ Error importing seed modules: {e}")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SeedRunner")

# --- Helper Functions ---

def run_step(name: str, func: Callable, *args, **kwargs):
    """
    Executes a seed step with strict error handling.
    
    On failure:
    - Logs the error with full details
    - Exits immediately with non-zero status code
    
    Args:
        name (str): Human-readable name for the seed step
        func (Callable): The seed function to execute
        *args, **kwargs: Arguments to pass to the function
        
    Raises:
        SystemExit: Always exits with code 1 on any exception
    """
    logger.info(f"⏳ Starting: {name}...")
    try:
        start_time = time.time()
        func(*args, **kwargs)
        elapsed = time.time() - start_time
        logger.info(f"✅ Completed: {name} (in {elapsed:.2f}s)\n")
    except Exception as e:
        logger.error(f"❌ Failed: {name}")
        logger.error(f"   Reason: {str(e)}")
        # Strict error handling: exit immediately with non-zero status
        sys.exit(1)

def run_database():
    """Wrapper for seed_database.py"""
    run_step("Core Database Seed (Users/Roles)", seed_database.seed)

def run_inventory():
    """Wrapper for seed_inventory.py"""
    run_step("Inventory Seed (Products/Stock)", seed_inventory.seed_inventory)

def run_analytics():
    """Wrapper for seed_analytics.py"""
    logger.info("ℹ️  Note: Analytics seed requires the API server to be running at localhost:8000.")
    run_step("Analytics Simulation (Webhooks)", seed_analytics.run_simulation)

def run_all():
    """
    Executes all seeds in strict dependency order.
    1. Database (Clears DB, creates Users/Roles)
    2. Inventory (Creates Products, links to Users)
    3. Analytics (Simulates traffic against the system)
    
    Any failure stops the entire process immediately.
    """
    logger.info("🚀 Starting Full System Seeding\n")
    
    run_database()
    run_inventory()
    run_analytics()
    
    logger.info("✨ All seeding operations completed.")

# --- Main Execution ---

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if len(args) == 0:
        # Default: Run everything
        run_all()
    else:
        # Target specific seeds
        target = args[0].lower()
        
        if target == "database":
            run_database()
        elif target == "inventory":
            run_inventory()
        elif target == "analytics":
            run_analytics()
        else:
            logger.error(f"Unknown seed target: '{target}'")
            print("\nAvailable commands:")
            print("  python -m app.seeds            (Run all)")
            print("  python -m app.seeds database   (Reset Users/Roles)")
            print("  python -m app.seeds inventory  (Add Products)")
            print("  python -m app.seeds analytics  (Simulate Traffic)")
            sys.exit(1)
