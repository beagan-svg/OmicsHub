"""
Django management command to optimize the database for production use.

Run with --create-indexes (recommended filter/lookup indexes),
--analyze-tables (refresh planner statistics), or --check-performance
(table sizes and index usage). --all runs every step.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Optimize database for production use'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create recommended database indexes',
        )
        parser.add_argument(
            '--analyze-tables',
            action='store_true',
            help='Analyze tables to update statistics',
        )
        parser.add_argument(
            '--check-performance',
            action='store_true',
            help='Check current database performance',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimization steps',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        
        if options['all']:
            options['create_indexes'] = True
            options['analyze_tables'] = True
            options['check_performance'] = True

        self.stdout.write(
            self.style.SUCCESS('Starting database optimization...')
        )

        if options['check_performance']:
            self.check_current_performance()

        if options['create_indexes']:
            self.create_indexes()

        if options['analyze_tables']:
            self.analyze_tables()

        self.stdout.write(
            self.style.SUCCESS('Database optimization completed!')
        )

    def check_current_performance(self):
        """Check current database performance metrics"""
        self.stdout.write('Checking current database performance...')
        
        with connection.cursor() as cursor:
            # Check table sizes
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY size_bytes DESC;
            """)
            
            self.stdout.write('\nTable Sizes:')
            for row in cursor.fetchall():
                self.stdout.write(f"  {row[1]}: {row[2]}")

            # Check index usage
            cursor.execute("""
                SELECT 
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC;
            """)
            
            self.stdout.write('\nIndex Usage (Top 10):')
            for i, row in enumerate(cursor.fetchall()[:10]):
                self.stdout.write(f"  {row[2]} on {row[1]}: {row[3]} scans")

            # Check slow queries (if pg_stat_statements is available)
            try:
                cursor.execute("""
                    SELECT 
                        query,
                        calls,
                        total_time,
                        mean_time,
                        rows
                    FROM pg_stat_statements 
                    WHERE query LIKE '%main%' OR query LIKE '%metadata%'
                    ORDER BY mean_time DESC 
                    LIMIT 5;
                """)
                
                self.stdout.write('\nSlowest Queries:')
                for row in cursor.fetchall():
                    self.stdout.write(f"  Mean time: {row[3]:.2f}ms, Calls: {row[1]}")
                    self.stdout.write(f"    {row[0][:100]}...")
                    
            except Exception:
                self.stdout.write('  pg_stat_statements not available')

    def create_indexes(self):
        """Create recommended database indexes"""
        self.stdout.write('Creating database indexes...')
        
        indexes = [
            # Main table indexes
            {
                'name': 'idx_main_study_set',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_study_set ON main(study_set) WHERE study_set IS NOT NULL;",
                'description': 'Index on main.study_set for filtering'
            },
            {
                'name': 'idx_main_library_prep_method',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_library_prep_method ON main(library_prep_method) WHERE library_prep_method IS NOT NULL;",
                'description': 'Index on main.library_prep_method for filtering'
            },
            {
                'name': 'idx_main_alignment_status',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_alignment_status ON main(alignment_status) WHERE alignment_status IS NOT NULL;",
                'description': 'Index on main.alignment_status for filtering'
            },
            {
                'name': 'idx_main_postqc_status',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_postqc_status ON main(postqc_status) WHERE postqc_status IS NOT NULL;",
                'description': 'Index on main.postqc_status for filtering'
            },
            {
                'name': 'idx_main_ingest_status',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_ingest_status ON main(ingest_status) WHERE ingest_status IS NOT NULL;",
                'description': 'Index on main.ingest_status for filtering'
            },
            
            # Metadata table indexes
            {
                'name': 'idx_metadata_organism_common_name',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metadata_organism_common_name ON metadata(organism_common_name) WHERE organism_common_name IS NOT NULL;",
                'description': 'Index on metadata.organism_common_name for filtering'
            },
            {
                'name': 'idx_metadata_batch_name_from_vendor',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metadata_batch_name_from_vendor ON metadata(batch_name_from_vendor) WHERE batch_name_from_vendor IS NOT NULL;",
                'description': 'Index on metadata.batch_name_from_vendor for filtering'
            },
            {
                'name': 'idx_metadata_library_prep_method_name',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metadata_library_prep_method_name ON metadata(library_prep_method_name) WHERE library_prep_method_name IS NOT NULL;",
                'description': 'Index on metadata.library_prep_method_name for filtering'
            },
            
            # Composite indexes for common filter combinations
            {
                'name': 'idx_main_status_composite',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_main_status_composite ON main(alignment_status, postqc_status, ingest_status);",
                'description': 'Composite index on all status fields'
            },
            {
                'name': 'idx_metadata_search_composite',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metadata_search_composite ON metadata(organism_common_name, batch_name_from_vendor, library_prep_method_name);",
                'description': 'Composite index for search functionality'
            },
            
            # LoadAssociation indexes
            {
                'name': 'idx_load_association_load_name',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_load_association_load_name ON load_association(load_name) WHERE load_name IS NOT NULL;",
                'description': 'Index on load_association.load_name for filtering'
            },
            
            # Status table indexes for FID lookups
            {
                'name': 'idx_ingest_fid',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingest_fid ON ingest(fid) WHERE fid IS NOT NULL;",
                'description': 'Index on ingest.fid for lookups'
            },
            {
                'name': 'idx_alignment_fid',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alignment_fid ON alignment(fid) WHERE fid IS NOT NULL;",
                'description': 'Index on alignment.fid for lookups'
            },
            {
                'name': 'idx_postqc_fid',
                'sql': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_postqc_fid ON postqc(fid) WHERE fid IS NOT NULL;",
                'description': 'Index on postqc.fid for lookups'
            },
            
            # Full-text search indexes
            {
                'name': 'idx_metadata_search_gin',
                'sql': """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metadata_search_gin ON metadata 
                         USING gin(to_tsvector('english', 
                         coalesce(organism_common_name, '') || ' ' || 
                         coalesce(batch_name_from_vendor, '') || ' ' || 
                         coalesce(library_prep_method_name, '')));""",
                'description': 'GIN index for full-text search'
            }
        ]
        
        for index in indexes:
            self.stdout.write(f"  Creating {index['name']}: {index['description']}")
            
            if self.dry_run:
                self.stdout.write(f"    [DRY RUN] {index['sql']}")
                continue
                
            try:
                start_time = time.time()
                with connection.cursor() as cursor:
                    cursor.execute(index['sql'])
                
                duration = time.time() - start_time
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Created in {duration:.2f}s")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠ Failed: {str(e)}")
                )

    def analyze_tables(self):
        """Analyze tables to update statistics"""
        self.stdout.write('Analyzing tables to update statistics...')
        
        tables = ['main', 'metadata', 'load_association', 'ingest', 'alignment', 'postqc']
        
        for table in tables:
            self.stdout.write(f"  Analyzing {table}...")
            
            if self.dry_run:
                self.stdout.write(f"    [DRY RUN] ANALYZE {table};")
                continue
                
            try:
                start_time = time.time()
                with connection.cursor() as cursor:
                    cursor.execute(f"ANALYZE {table};")
                
                duration = time.time() - start_time
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Analyzed in {duration:.2f}s")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠ Failed: {str(e)}")
                )
