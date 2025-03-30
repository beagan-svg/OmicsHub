from django.test import TestCase, Client
from django.urls import reverse
from django.db import connection
from viewer.models import Metadata, LoadAssociation, Main

class ModelTests(TestCase):
    def setUp(self):
        # Create test tables if they don't exist
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS viewer_metadata (
                    fastq_name character varying(255) NOT NULL PRIMARY KEY,
                    organism_name character varying(255),
                    library_prep_method_name character varying(255),
                    studies jsonb,
                    batch_name character varying(255),
                    cell_capture integer
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS viewer_loadassociation (
                    id serial PRIMARY KEY,
                    fastq_name character varying(255) REFERENCES viewer_metadata(fastq_name),
                    load_name character varying(255) NOT NULL DEFAULT ''
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS viewer_main (
                    fastq_name character varying(255) NOT NULL PRIMARY KEY REFERENCES viewer_metadata(fastq_name),
                    study_set character varying(255),
                    organism character varying(255),
                    library_prep_method character varying(255),
                    alignment_status character varying(50),
                    postqc_status character varying(50),
                    ingest_status character varying(50)
                )
            """)

        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq",
            organism_name="test_organism",
            library_prep_method_name="test_method",
            studies=["test_study"],
            batch_name="test_batch",
            cell_capture=100
        )
        
        self.load_association = LoadAssociation.objects.create(
            fastq_name=self.metadata,
            load_name="test_load"
        )
        
        self.main = Main.objects.create(
            fastq_name=self.metadata,
            study_set="test_study",
            organism="test_organism",
            library_prep_method="test_method",
            alignment_status="NOT COMPLETED",
            postqc_status="NOT COMPLETED",
            ingest_status="NOT COMPLETED"
        )

    def test_metadata_str(self):
        self.assertEqual(str(self.metadata), "test_fastq")

    def test_load_association_str(self):
        self.assertEqual(str(self.load_association), "test_fastq - test_load")

    def test_main_str(self):
        self.assertEqual(str(self.main), "test_fastq")

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq",
            organism_name="test_organism",
            library_prep_method_name="test_method",
            studies=["test_study"]
        )
        
        self.main = Main.objects.create(
            fastq_name=self.metadata,
            study_set="test_study",
            organism="test_organism",
            library_prep_method="test_method",
            alignment_status="NOT COMPLETED",
            postqc_status="NOT COMPLETED",
            ingest_status="NOT COMPLETED"
        )

    def test_main_list_view(self):
        response = self.client.get(reverse('viewer:main_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'viewer/main_list.html')

    def test_filter_by_study_set(self):
        response = self.client.get(reverse('viewer:main_list'), {'study_set': 'test_study'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq")

    def test_filter_by_organism(self):
        response = self.client.get(reverse('viewer:main_list'), {'organism': 'test_organism'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_fastq") 