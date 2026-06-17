from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from backend.services.monitor_service import get_monitor_service
from backend.utils.logger import logger
from backend.config.settings import settings
import threading


class MonitorScheduler:
    """Scheduler for running periodic service checks."""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.monitor_service = get_monitor_service()
        self.is_running = False
        self.check_interval = settings.CHECK_INTERVAL_MINUTES
        self.last_check_time = None
        self.lock = threading.Lock()
    
    def start(self):
        """Start the scheduler."""
        try:
            if self.is_running:
                logger.warning("Scheduler already running")
                return False
            
            self.scheduler.add_job(
                self.check_service,
                IntervalTrigger(minutes=self.check_interval),
                id='service_monitor',
                name='Service Status Monitor',
                misfire_grace_time=15
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info(f"Scheduler started. Check interval: {self.check_interval} minutes")
            
            self.check_service()
            
            return True
        
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            return False
    
    def stop(self):
        """Stop the scheduler."""
        try:
            if not self.is_running:
                logger.warning("Scheduler not running")
                return False
            
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")
            return True
        
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
            return False
    
    def check_service(self):
        """Perform service check (called by scheduler)."""
        with self.lock:
            try:
                check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Running scheduled service check at {check_time}")
                
                status_changed, current_status = self.monitor_service.check_and_update_status()
                
                if status_changed:
                    logger.warning(f"Service status changed to: {current_status}")
                else:
                    logger.debug(f"Service status unchanged: {current_status}")
                
                self.last_check_time = check_time
                
            except Exception as e:
                logger.error(f"Error in scheduled check: {str(e)}")
    
    def get_status(self):
        """Get scheduler status."""
        return {
            'is_running': self.is_running,
            'check_interval_minutes': self.check_interval,
            'last_check_time': self.last_check_time,
            'scheduled_jobs': len(self.scheduler.get_jobs()) if self.scheduler.running else 0
        }
    
    def run_immediate_check(self):
        """Run an immediate service check outside of schedule."""
        try:
            logger.info("Running immediate service check")
            status_changed, current_status = self.monitor_service.check_and_update_status()
            return {
                'status_changed': status_changed,
                'current_status': current_status,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error in immediate check: {str(e)}")
            return {
                'status_changed': False,
                'error': str(e)
            }


_scheduler_instance = None


def get_scheduler():
    """Get or create the scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MonitorScheduler()
    return _scheduler_instance
