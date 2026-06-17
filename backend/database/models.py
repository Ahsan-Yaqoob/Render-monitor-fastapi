from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class ServiceStatus(str, Enum):
    """Enum for service status values."""
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


class IssueType(str, Enum):
    """Enum for issue types."""
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class ServiceStatusRecord:
    """Data model for service status record."""
    id: str
    timestamp: str
    service_name: str
    status: str
    issue_type: str
    duration: float
    resolved_at: Optional[str] = None
    
    def to_dict(self):
        """Convert record to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'service_name': self.service_name,
            'status': self.status,
            'issue_type': self.issue_type,
            'duration': self.duration,
            'resolved_at': self.resolved_at or ''
        }
    
    def to_csv_row(self):
        """Convert record to CSV row format."""
        return [
            self.id,
            self.timestamp,
            self.service_name,
            self.status,
            self.issue_type,
            str(self.duration),
            self.resolved_at or ''
        ]
    
    @classmethod
    def from_dict(cls, data):
        """Create record from dictionary."""
        return cls(
            id=data.get('id', ''),
            timestamp=data.get('timestamp', ''),
            service_name=data.get('service_name', ''),
            status=data.get('status', ''),
            issue_type=data.get('issue_type', ''),
            duration=float(data.get('duration', 0)),
            resolved_at=data.get('resolved_at', None)
        )
    
    @classmethod
    def from_csv_row(cls, row):
        """Create record from CSV row."""
        return cls(
            id=row[0] if len(row) > 0 else '',
            timestamp=row[1] if len(row) > 1 else '',
            service_name=row[2] if len(row) > 2 else '',
            status=row[3] if len(row) > 3 else '',
            issue_type=row[4] if len(row) > 4 else '',
            duration=float(row[5]) if len(row) > 5 and row[5] else 0,
            resolved_at=row[6] if len(row) > 6 and row[6] else None
        )


@dataclass
class ServiceStatusSnapshot:
    """Data model for current service status snapshot."""
    is_running: bool
    last_status: str
    last_check_time: str
    failure_start_time: Optional[str] = None
    last_recovery_time: Optional[str] = None
    current_downtime_minutes: float = 0
    issue_type: str = "NONE"
    
    def to_dict(self):
        """Convert snapshot to dictionary."""
        return {
            'is_running': self.is_running,
            'last_status': self.last_status,
            'last_check_time': self.last_check_time,
            'failure_start_time': self.failure_start_time,
            'last_recovery_time': self.last_recovery_time,
            'current_downtime_minutes': self.current_downtime_minutes,
            'issue_type': self.issue_type
        }


@dataclass
class MonitorStats:
    """Data model for monitor statistics."""
    total_checks: int
    total_failures: int
    total_recovery: int
    total_downtime_minutes: float
    uptime_percentage: float
    most_common_issue: str
    issue_frequency: dict
    
    def to_dict(self):
        """Convert stats to dictionary."""
        return {
            'total_checks': self.total_checks,
            'total_failures': self.total_failures,
            'total_recovery': self.total_recovery,
            'total_downtime_minutes': self.total_downtime_minutes,
            'uptime_percentage': round(self.uptime_percentage, 2),
            'most_common_issue': self.most_common_issue,
            'issue_frequency': self.issue_frequency
        }
