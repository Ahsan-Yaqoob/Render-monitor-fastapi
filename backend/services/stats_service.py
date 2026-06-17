from datetime import datetime, timedelta
from backend.database.csv_handler import CSVHandler
from backend.database.models import ServiceStatusRecord, MonitorStats
from backend.utils.logger import logger


class StatsService:
    """Service for calculating and retrieving statistics."""
    
    def __init__(self, csv_handler: CSVHandler):
        self.csv_handler = csv_handler
    
    def get_all_stats(self):
        """Get comprehensive statistics about service monitoring."""
        try:
            records = self.csv_handler.read_all_records()
            
            if not records:
                return MonitorStats(
                    total_checks=0,
                    total_failures=0,
                    total_recovery=0,
                    total_downtime_minutes=0,
                    uptime_percentage=100,
                    most_common_issue='N/A',
                    issue_frequency={}
                )
            
            total_checks = len(records)
            total_failures = len([r for r in records if r.status == 'FAILED'])
            total_recovery = len([r for r in records if r.status == 'RECOVERED'])
            
            total_downtime = sum(
                r.duration for r in records 
                if r.status == 'FAILED' and r.duration > 0
            )
            
            issue_freq = {}
            for record in records:
                if record.status == 'FAILED':
                    issue_type = record.issue_type or 'UNKNOWN'
                    issue_freq[issue_type] = issue_freq.get(issue_type, 0) + 1
            
            most_common_issue = max(issue_freq, key=issue_freq.get) if issue_freq else 'N/A'
            
            uptime_pct = self._calculate_uptime_percentage(total_failures, total_downtime)
            
            stats = MonitorStats(
                total_checks=total_checks,
                total_failures=total_failures,
                total_recovery=total_recovery,
                total_downtime_minutes=total_downtime,
                uptime_percentage=uptime_pct,
                most_common_issue=most_common_issue,
                issue_frequency=issue_freq
            )
            
            logger.debug(f"Calculated stats: {stats.to_dict()}")
            return stats
        
        except Exception as e:
            logger.error(f"Error calculating stats: {str(e)}")
            return MonitorStats(0, 0, 0, 0, 100, 'N/A', {})
    
    def get_stats_by_period(self, days=30):
        """Get statistics for a specific period."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            records = self.csv_handler.read_all_records()
            
            filtered_records = []
            for record in records:
                try:
                    record_date = datetime.fromisoformat(record.timestamp)
                    if record_date >= cutoff_date:
                        filtered_records.append(record)
                except Exception:
                    continue
            
            if not filtered_records:
                return MonitorStats(0, 0, 0, 0, 100, 'N/A', {})
            
            total_checks = len(filtered_records)
            total_failures = len([r for r in filtered_records if r.status == 'FAILED'])
            total_recovery = len([r for r in filtered_records if r.status == 'RECOVERED'])
            
            total_downtime = sum(
                r.duration for r in filtered_records 
                if r.status == 'FAILED' and r.duration > 0
            )
            
            issue_freq = {}
            for record in filtered_records:
                if record.status == 'FAILED':
                    issue_type = record.issue_type or 'UNKNOWN'
                    issue_freq[issue_type] = issue_freq.get(issue_type, 0) + 1
            
            most_common_issue = max(issue_freq, key=issue_freq.get) if issue_freq else 'N/A'
            uptime_pct = self._calculate_uptime_percentage(total_failures, total_downtime)
            
            return MonitorStats(
                total_checks=total_checks,
                total_failures=total_failures,
                total_recovery=total_recovery,
                total_downtime_minutes=total_downtime,
                uptime_percentage=uptime_pct,
                most_common_issue=most_common_issue,
                issue_frequency=issue_freq
            )
        
        except Exception as e:
            logger.error(f"Error calculating stats by period: {str(e)}")
            return MonitorStats(0, 0, 0, 0, 100, 'N/A', {})
    
    def get_issue_frequency(self):
        """Get frequency of each issue type."""
        try:
            records = self.csv_handler.read_all_records()
            
            issue_freq = {}
            for record in records:
                if record.status == 'FAILED':
                    issue_type = record.issue_type or 'UNKNOWN'
                    issue_freq[issue_type] = issue_freq.get(issue_type, 0) + 1
            
            sorted_issues = sorted(issue_freq.items(), key=lambda x: x[1], reverse=True)
            return dict(sorted_issues)
        
        except Exception as e:
            logger.error(f"Error getting issue frequency: {str(e)}")
            return {}
    
    def get_daily_failures(self, days=30):
        """Get failure count per day."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            records = self.csv_handler.read_all_records()
            
            daily_failures = {}
            
            for record in records:
                if record.status == 'FAILED':
                    try:
                        record_date = datetime.fromisoformat(record.timestamp)
                        if record_date >= cutoff_date:
                            date_key = record_date.strftime('%Y-%m-%d')
                            daily_failures[date_key] = daily_failures.get(date_key, 0) + 1
                    except Exception:
                        continue
            
            sorted_daily = sorted(daily_failures.items())
            return dict(sorted_daily)
        
        except Exception as e:
            logger.error(f"Error getting daily failures: {str(e)}")
            return {}
    
    def get_downtime_by_issue(self):
        """Get total downtime by issue type."""
        try:
            records = self.csv_handler.read_all_records()
            
            downtime_by_issue = {}
            
            for record in records:
                if record.status == 'FAILED' and record.duration > 0:
                    issue_type = record.issue_type or 'UNKNOWN'
                    downtime_by_issue[issue_type] = downtime_by_issue.get(issue_type, 0) + record.duration
            
            sorted_downtime = sorted(downtime_by_issue.items(), key=lambda x: x[1], reverse=True)
            return dict(sorted_downtime)
        
        except Exception as e:
            logger.error(f"Error getting downtime by issue: {str(e)}")
            return {}
    
    def _calculate_uptime_percentage(self, total_failures, total_downtime):
        """Calculate uptime percentage."""
        try:
            if total_failures == 0:
                return 100.0
            
            max_possible_minutes = total_failures * 5
            uptime = 100 - ((total_downtime / max(max_possible_minutes, 1)) * 100)
            return max(0, min(100, uptime))
        
        except Exception:
            return 100.0
    
    def get_recovery_time_avg(self):
        """Get average recovery time."""
        try:
            records = self.csv_handler.read_all_records()
            recovered_records = [r for r in records if r.status == 'RECOVERED']
            
            if not recovered_records:
                return 0
            
            total_time = sum(r.duration for r in recovered_records if r.duration > 0)
            avg_time = total_time / len(recovered_records) if recovered_records else 0
            
            return avg_time
        
        except Exception as e:
            logger.error(f"Error calculating average recovery time: {str(e)}")
            return 0
