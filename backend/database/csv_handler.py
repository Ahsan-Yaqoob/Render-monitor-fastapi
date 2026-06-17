import csv
import os
from datetime import datetime
from backend.database.models import ServiceStatusRecord
from backend.utils.logger import logger
import uuid


class CSVHandler:
    """Handler for reading and writing CSV logs."""
    
    CSV_HEADERS = ['id', 'timestamp', 'service_name', 'status', 'issue_type', 'duration', 'resolved_at']
    
    def __init__(self, file_path):
        self.file_path = file_path
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            try:
                with open(self.file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
                logger.info(f"Created new CSV file: {self.file_path}")
            except Exception as e:
                logger.error(f"Error creating CSV file: {str(e)}")
                raise
    
    def add_record(self, record: ServiceStatusRecord):
        """Add a new record to the CSV file."""
        try:
            with open(self.file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(record.to_csv_row())
            logger.debug(f"Added record to CSV: {record.id}")
        except Exception as e:
            logger.error(f"Error adding record to CSV: {str(e)}")
            raise
    
    def read_all_records(self):
        """Read all records from CSV file."""
        records = []
        try:
            if not os.path.exists(self.file_path):
                return records
            
            with open(self.file_path, 'r', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if headers is None:
                    return records
                
                for row in reader:
                    if row and len(row) > 0 and row[0] != '':
                        try:
                            record = ServiceStatusRecord.from_csv_row(row)
                            records.append(record)
                        except Exception as e:
                            logger.warning(f"Skipping malformed row: {row}, Error: {str(e)}")
                            continue
            
            logger.debug(f"Read {len(records)} records from CSV")
            return records
        except Exception as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            return []
    
    def get_records_by_status(self, status):
        """Get all records with specific status."""
        all_records = self.read_all_records()
        return [r for r in all_records if r.status == status]
    
    def get_last_record(self):
        """Get the last record from CSV."""
        records = self.read_all_records()
        return records[-1] if records else None
    
    def get_failed_records(self):
        """Get all failed status records."""
        return self.get_records_by_status('FAILED')
    
    def get_recovered_records(self):
        """Get all recovered status records."""
        return self.get_records_by_status('RECOVERED')
    
    def get_running_records(self):
        """Get all running status records."""
        return self.get_records_by_status('RUNNING')
    
    def get_latest_by_date(self, days=30):
        """Get records from last N days."""
        from datetime import datetime, timedelta
        all_records = self.read_all_records()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        filtered = []
        for record in all_records:
            try:
                record_date = datetime.fromisoformat(record.timestamp)
                if record_date >= cutoff_date:
                    filtered.append(record)
            except Exception:
                continue
        
        return filtered
    
    def calculate_statistics(self):
        """Calculate statistics from all records."""
        all_records = self.read_all_records()
        
        if not all_records:
            return {
                'total_records': 0,
                'total_failures': 0,
                'total_recoveries': 0,
                'total_downtime_minutes': 0,
                'uptime_percentage': 100,
                'most_common_issue': 'N/A',
                'issue_frequency': {}
            }
        
        total_downtime = 0
        failed_count = 0
        recovered_count = 0
        issue_freq = {}
        
        for record in all_records:
            if record.status == 'FAILED':
                failed_count += 1
                issue_type = record.issue_type or 'UNKNOWN'
                issue_freq[issue_type] = issue_freq.get(issue_type, 0) + 1
                if record.duration > 0:
                    total_downtime += record.duration
            elif record.status == 'RECOVERED':
                recovered_count += 1
        
        uptime_pct = 100 if failed_count == 0 else max(0, 100 - ((total_downtime / (total_downtime + 1)) * 100))
        most_common_issue = max(issue_freq, key=issue_freq.get) if issue_freq else 'N/A'
        
        return {
            'total_records': len(all_records),
            'total_failures': failed_count,
            'total_recoveries': recovered_count,
            'total_downtime_minutes': total_downtime,
            'uptime_percentage': round(uptime_pct, 2),
            'most_common_issue': most_common_issue,
            'issue_frequency': issue_freq
        }
    
    def generate_unique_id(self):
        """Generate a unique ID for a record."""
        return str(uuid.uuid4())[:8]
    
    def clear_all_records(self):
        """Clear all records from CSV file, keeping only headers."""
        try:
            with open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
            logger.info(f"All records cleared from CSV file: {self.file_path}")
        except Exception as e:
            logger.error(f"Error clearing CSV file: {str(e)}")
            raise
