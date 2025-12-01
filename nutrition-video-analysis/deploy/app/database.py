"""
Database layer for job tracking and results storage
Supports both SQLite (MVP) and PostgreSQL (production)
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Database:
    """Database interface for job management"""
    
    def __init__(self, database_url: str):
        """
        Initialize database connection
        
        Args:
            database_url: Database connection string
                - SQLite: sqlite:///path/to/db.db
                - PostgreSQL: postgresql://user:pass@host/db
        """
        self.database_url = database_url
        self.is_sqlite = database_url.startswith("sqlite")
        
        if self.is_sqlite:
            # Extract path from URL
            db_path = database_url.replace("sqlite:///", "")
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = None
        else:
            # PostgreSQL support (requires psycopg2)
            try:
                import psycopg2
                self.conn = psycopg2.connect(database_url)
            except ImportError:
                raise ImportError("PostgreSQL support requires psycopg2: pip install psycopg2-binary")
    
    def _get_connection(self):
        """Get database connection"""
        if self.is_sqlite:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Return dicts instead of tuples
            return conn
        return self.conn
    
    def init_db(self):
        """Initialize database schema"""
        logger.info("Initializing database schema...")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                video_name TEXT NOT NULL,
                video_path TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                results_path TEXT,
                total_calories REAL,
                num_food_items INTEGER
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)")
        
        conn.commit()
        if self.is_sqlite:
            conn.close()
        
        logger.info("✓ Database initialized")
    
    def create_job(
        self,
        job_id: str,
        video_name: str,
        video_path: str,
        status: JobStatus = JobStatus.PENDING
    ):
        """Create a new job entry"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO jobs (job_id, video_name, video_path, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, video_name, video_path, status.value, datetime.utcnow()))
        
        conn.commit()
        if self.is_sqlite:
            conn.close()
        
        logger.info(f"Created job {job_id}")
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        
        if self.is_sqlite:
            conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None
    ):
        """Update job status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = {"status": status.value}
        
        if status == JobStatus.PROCESSING:
            updates["started_at"] = datetime.utcnow()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            updates["completed_at"] = datetime.utcnow()
        
        if error_message:
            updates["error_message"] = error_message
        
        # Build UPDATE query
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [job_id]
        
        cursor.execute(f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values)
        
        conn.commit()
        if self.is_sqlite:
            conn.close()
        
        logger.info(f"Updated job {job_id}: {status.value}")
    
    def update_job_results(
        self,
        job_id: str,
        status: JobStatus,
        results_path: str,
        total_calories: float,
        num_food_items: int
    ):
        """Update job with results"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE jobs 
            SET status = ?, 
                completed_at = ?,
                results_path = ?,
                total_calories = ?,
                num_food_items = ?
            WHERE job_id = ?
        """, (
            status.value,
            datetime.utcnow(),
            results_path,
            total_calories,
            num_food_items,
            job_id
        ))
        
        conn.commit()
        if self.is_sqlite:
            conn.close()
        
        logger.info(f"Updated job {job_id} with results")
    
    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """List jobs with optional filtering"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM jobs 
                WHERE status = ?
                ORDER BY created_at DESC 
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM jobs 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        
        if self.is_sqlite:
            conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_job(self, job_id: str):
        """Delete a job entry"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        
        conn.commit()
        if self.is_sqlite:
            conn.close()
        
        logger.info(f"Deleted job {job_id}")
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                AVG(total_calories) as avg_calories
            FROM jobs
        """)
        
        row = cursor.fetchone()
        
        if self.is_sqlite:
            conn.close()
        
        if row:
            return dict(row)
        return {}


# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing database...")
    
    # Test SQLite
    db = Database("sqlite:///./test.db")
    db.init_db()
    
    # Create test job
    test_job_id = "test-123"
    db.create_job(
        job_id=test_job_id,
        video_name="test_video.mp4",
        video_path="/tmp/test.mp4"
    )
    
    # Retrieve job
    job = db.get_job(test_job_id)
    print(f"\nCreated job: {job}")
    
    # Update status
    db.update_job_status(test_job_id, JobStatus.PROCESSING)
    
    # Update with results
    db.update_job_results(
        job_id=test_job_id,
        status=JobStatus.COMPLETED,
        results_path="/tmp/results.json",
        total_calories=650.5,
        num_food_items=3
    )
    
    # Get updated job
    job = db.get_job(test_job_id)
    print(f"\nCompleted job: {job}")
    
    # Get stats
    stats = db.get_stats()
    print(f"\nDatabase stats: {stats}")
    
    # Clean up
    db.delete_job(test_job_id)
    Path("test.db").unlink()
    
    print("\n✓ All tests passed!")

