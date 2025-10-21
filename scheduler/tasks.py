# src/scheduler/tasks.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime
from database import SessionLocal
from payment.models import Payment
from payment.services import PaymentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pending_payments():
    """Check and update pending payments."""
    logger.info("Starting check_pending_payments task")
    db: Session = SessionLocal()
    try:
        pending_payments = db.query(Payment).filter(Payment.status == "pending").all()
        payment_service = PaymentService()
        for payment in pending_payments:
            logger.info(f"Checking payment: {payment.payment_id}, expiration_time: {payment.expiration_time}")
            if payment.expiration_time is None or payment.expiration_time < datetime.utcnow():
                payment.status = "expired"
                db.commit()
                logger.info(f"Payment {payment.payment_id} marked as expired")
                continue
            if payment_service.check_payment(payment, db):
                logger.info(f"Payment {payment.payment_id} confirmed")
    except Exception as e:
        logger.error(f"Error in check_pending_payments: {str(e)}")
    finally:
        db.close()
    logger.info("Finished check_pending_payments task")

def archive_old_posts():
    """Archive posts older than 1 year."""
    logger.info("Starting archive_old_posts task")
    db: Session = SessionLocal()
    try:
        db.execute(
            "UPDATE posts SET content_type = 'archive' WHERE content_type = 'basic' AND created_at < NOW() - INTERVAL '1 year'"
        )
        db.commit()
        logger.info("Successfully archived old posts")
    except Exception as e:
        logger.error(f"Error in archive_old_posts: {str(e)}")
    finally:
        db.close()
    logger.info("Finished archive_old_posts task")

def start_scheduler():
    """Start the background scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_pending_payments, 'interval', minutes=5)
    scheduler.add_job(archive_old_posts, 'interval', days=1)
    scheduler.start()