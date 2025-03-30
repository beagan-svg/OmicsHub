from django.test import TestCase, Client
from django.urls import reverse
from viewer.models import Main, Metadata, LoadAssociation
from django.db import connection

class FilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test tables if they don't exist
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    fastq_name character varying(255) NOT NULL PRIMARY KEY,
                    organism_name character varying(255),
                    library_prep_method_name character varying(255),
                    studies jsonb DEFAULT '[]'::jsonb,
                    alignment_method character varying(255),
                    amplification_id bigint,
                    amplification_name character varying(255),
                    batch_name character varying(255),
                    batch_name_from_vendor character varying(255),
                    cell_capture integer,
                    cell_prep_type character varying(255),
                    library_prep_method_id bigint,
                    library_prep_name character varying(255),
                    organism_common_name character varying(255),
                    sample_id bigint,
                    sample_name character varying(255),
                    sample_type character varying(255),
                    sequencing_vendor character varying(255)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS load_association (
                    id serial PRIMARY KEY,
                    fastq_name character varying(255) REFERENCES metadata(fastq_name) ON DELETE CASCADE,
                    load_name character varying(255) NOT NULL DEFAULT '',
                    UNIQUE (fastq_name, load_name)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS main (
                    fastq_name character varying(255) NOT NULL PRIMARY KEY REFERENCES metadata(fastq_name) ON DELETE CASCADE,
                    study_set character varying(255),
                    organism character varying(255),
                    library_prep_method character varying(255),
                    alignment_status character varying(50),
                    postqc_status character varying(50),
                    ingest_status character varying(50)
                )
            """)
        
        # Create test data
        self.metadata1 = Metadata.objects.create(
            fastq_name="test_fastq1",
            organism_name="test_organism1",
            library_prep_method_name="test_method1",
            studies=["test_study1"]
        )
        
        self.metadata2 = Metadata.objects.create(
            fastq_name="test_fastq2",
            organism_name="test_organism2",
            library_prep_method_name="test_method2",
            studies=["test_study2"]
        )
        
        self.load_assoc1 = LoadAssociation.objects.create(
            fastq_name=self.metadata1,
            load_name="test_load1"
        )
        
        self.load_assoc2 = LoadAssociation.objects.create(
            fastq_name=self.metadata2,
            load_name="test_load2"
        )
        
        self.main1 = Main.objects.create(
            fastq_name=self.metadata1,
            study_set="test_study1",
            organism="test_organism1",
            library_prep_method="test_method1",
            alignment_status="COMPLETED",
            postqc_status="COMPLETED",
            ingest_status="COMPLETED"
        )
        
        self.main2 = Main.objects.create(
            fastq_name=self.metadata2,
            study_set="test_study2",
            organism="test_organism2",
            library_prep_method="test_method2",
            alignment_status="NOT COMPLETED",
            postqc_status="NOT COMPLETED",
            ingest_status="NOT COMPLETED"
        )

    def tearDown(self):
        # Clean up test data
        Main.objects.all().delete()
        Metadata.objects.all().delete()
        LoadAssociation.objects.all().delete()

    def test_study_set_filter(self):
        """Test filtering by study set"""
        response = self.client.get(reverse('viewer:main_list'), {'study_set': 'test_study1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_organism_filter(self):
        """Test filtering by organism"""
        response = self.client.get(reverse('viewer:main_list'), {'organism': 'test_organism1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_library_prep_method_filter(self):
        """Test filtering by library prep method"""
        response = self.client.get(reverse('viewer:main_list'), {'library_prep_method': 'test_method1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_alignment_status_filter(self):
        """Test filtering by alignment status"""
        response = self.client.get(reverse('viewer:main_list'), {'alignment_status': 'COMPLETED'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_postqc_status_filter(self):
        """Test filtering by postqc status"""
        response = self.client.get(reverse('viewer:main_list'), {'postqc_status': 'COMPLETED'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_ingest_status_filter(self):
        """Test filtering by ingest status"""
        response = self.client.get(reverse('viewer:main_list'), {'ingest_status': 'COMPLETED'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_multiple_filters(self):
        """Test applying multiple filters simultaneously"""
        response = self.client.get(reverse('viewer:main_list'), {
            'study_set': 'test_study1',
            'organism': 'test_organism1',
            'library_prep_method': 'test_method1',
            'alignment_status': 'COMPLETED'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")

    def test_clear_filters(self):
        """Test clearing all filters"""
        # First apply some filters
        response = self.client.get(reverse('viewer:main_list'), {
            'study_set': 'test_study1',
            'organism': 'test_organism1'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2")
        
        # Then clear filters
        response = self.client.get(reverse('viewer:main_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertContains(response, "test_fastq2")

    def test_empty_filter_values(self):
        """Test that empty filter values don't affect the results"""
        response = self.client.get(reverse('viewer:main_list'), {
            'study_set': '',
            'organism': '',
            'library_prep_method': '',
            'alignment_status': '',
            'postqc_status': '',
            'ingest_status': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq1")
        self.assertContains(response, "test_fastq2")

    def test_invalid_filter_values(self):
        """Test that invalid filter values don't break the application"""
        response = self.client.get(reverse('viewer:main_list'), {
            'study_set': 'invalid_study',
            'organism': 'invalid_organism',
            'library_prep_method': 'invalid_method',
            'alignment_status': 'invalid_status',
            'postqc_status': 'invalid_status',
            'ingest_status': 'invalid_status'
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "test_fastq1")
        self.assertNotContains(response, "test_fastq2") 