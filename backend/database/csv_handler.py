import csv
import os
import uuid
from backend.database.models import ServiceStatusRecord
from backend.utils.logger import logger


class CSVHandler:
    """Fallback storage when Supabase is not configured."""

    CSV_HEADERS = ['id', 'timestamp', 'service_name', 'status', 'issue_type', 'duration', 'resolved_at']

    def __init__(self, file_path):
        self.file_path = file_path
        self._ensure_csv_exists()

    def _ensure_csv_exists(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            try:
                with open(self.file_path, 'w', newline='') as f:
                    csv.writer(f).writerow(self.CSV_HEADERS)
                logger.info(f"Created CSV file: {self.file_path}")
            except Exception as e:
                logger.error(f"Error creating CSV file: {e}")
                raise

    def add_record(self, record: ServiceStatusRecord):
        try:
            with open(self.file_path, 'a', newline='') as f:
                csv.writer(f).writerow(record.to_csv_row())
            logger.debug(f"CSV record added: {record.id}")
        except Exception as e:
            logger.error(f"Error writing CSV record: {e}")
            raise

    def read_all_records(self) -> list[ServiceStatusRecord]:
        records = []
        try:
            if not os.path.exists(self.file_path):
                return records
            with open(self.file_path, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if row and row[0]:
                        try:
                            records.append(ServiceStatusRecord.from_csv_row(row))
                        except Exception as e:
                            logger.warning(f"Skipping malformed CSV row: {e}")
            return records
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return []

    def generate_unique_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def clear_all_records(self):
        try:
            with open(self.file_path, 'w', newline='') as f:
                csv.writer(f).writerow(self.CSV_HEADERS)
            logger.info("CSV records cleared")
        except Exception as e:
            logger.error(f"Error clearing CSV: {e}")
            raise
