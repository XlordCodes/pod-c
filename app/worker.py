# app/worker.py
"""
Background Worker Module.
Processes queued bulk messaging jobs from the database.
"""
import time
import logging
from app.database import SessionLocal
from app.models import BulkJob
from app.services.bulk_service import BulkService
from app.core.logging import configure_logging

# Apply application-wide logging configuration (JSON format)
configure_logging()
logger = logging.getLogger("worker")

def worker_loop(poll_interval=5):
    logger.info("Bulk Worker started. Polling for jobs...")
    
    while True:
        db = SessionLocal()
        try:
            # Fetch the oldest queued job (FIFO)
            job = db.query(BulkJob).filter(BulkJob.status == "queued").order_by(BulkJob.created_at.asc()).first()
            
            if job:
                logger.info(f"Found Job {job.id} ({job.template_name}). Processing...")
                svc = BulkService(db)
                svc.run_job(job.id)
                logger.info(f"Job {job.id} completed.")
            else:
                # No jobs found; wait for the next poll interval
                pass
                
        except Exception as e:
            logger.error(f"Worker process encountered an error: {e}")
            time.sleep(5)
        finally:
            db.close()
        
        time.sleep(poll_interval)

if __name__ == "__main__":
    worker_loop()