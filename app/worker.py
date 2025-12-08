# app/worker.py
"""
Module: Background Worker
Context: Pod C - Module 2 (Bulk Messaging).

This script runs in a separate process (container). It continuously checks 
the database for 'queued' bulk jobs and processes them.
"""
import time
import logging
from app.database import SessionLocal
from app.models import BulkJob
from app.services.bulk_service import BulkService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("worker")

def worker_loop(poll_interval=5):
    logger.info("🚀 Bulk Worker started. Polling for jobs...")
    
    while True:
        db = SessionLocal()
        try:
            # 1. Find a queued job (FIFO)
            job = db.query(BulkJob).filter(BulkJob.status == "queued").order_by(BulkJob.created_at.asc()).first()
            
            if job:
                logger.info(f"Found Job {job.id} ({job.template_name}). Processing...")
                # 2. Hand off to the service logic
                svc = BulkService(db)
                svc.run_job(job.id)
                logger.info(f"Job {job.id} completed.")
            else:
                # No work found, sleep to save CPU
                pass
                
        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            time.sleep(5)
        finally:
            db.close()
        
        time.sleep(poll_interval)

if __name__ == "__main__":
    worker_loop()