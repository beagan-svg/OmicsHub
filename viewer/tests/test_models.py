from django.test import TransactionTestCase
from django.db import IntegrityError
from django.utils import timezone
from viewer.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main

class MetadataModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_1",
            organism_name="mouse",
            library_prep_method_name="10x_v3",
            studies=["study1", "study2"],
            alignment_method="star",
            amplification_id=123,
            batch_name="batch1",
            cell_capture=1000
        )

    def test_metadata_creation(self):
        """Test metadata creation and field values"""
        self.assertEqual(self.metadata.fastq_name, "test_fastq_1")
        self.assertEqual(self.metadata.organism_name, "mouse")
        self.assertEqual(self.metadata.library_prep_method_name, "10x_v3")
        self.assertEqual(self.metadata.studies, ["study1", "study2"])
        self.assertEqual(self.metadata.cell_capture, 1000)

    def test_metadata_string_representation(self):
        """Test the string representation of metadata"""
        self.assertEqual(str(self.metadata), "test_fastq_1")

    def test_duplicate_fastq_name(self):
        """Test that duplicate fastq_names are not allowed"""
        with self.assertRaises(IntegrityError):
            Metadata.objects.create(
                fastq_name="test_fastq_1",
                organism_name="human"
            )

class AlignmentModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_2",
            organism_name="human"
        )
        self.alignment = Alignment.objects.create(
            fastq_name=self.metadata,
            status_id="RUNNING",
            start_time=timezone.now(),
            fid="align_123"
        )

    def test_alignment_creation(self):
        """Test alignment creation and field values"""
        self.assertEqual(self.alignment.fastq_name, self.metadata)
        self.assertEqual(self.alignment.status_id, "RUNNING")
        self.assertIsNotNone(self.alignment.start_time)
        self.assertEqual(self.alignment.fid, "align_123")

    def test_alignment_string_representation(self):
        """Test the string representation of alignment"""
        expected = f"{self.metadata} - RUNNING"
        self.assertEqual(str(self.alignment), expected)

    def test_cascade_delete(self):
        """Test that deleting metadata cascades to alignment"""
        self.metadata.delete()
        self.assertEqual(Alignment.objects.count(), 0)

class PostQCModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_3",
            organism_name="human"
        )
        self.postqc = PostQC.objects.create(
            fastq_name=self.metadata,
            status_id="COMPLETED",
            start_time=timezone.now(),
            end_time=timezone.now(),
            fid="qc_123"
        )

    def test_postqc_creation(self):
        """Test PostQC creation and field values"""
        self.assertEqual(self.postqc.fastq_name, self.metadata)
        self.assertEqual(self.postqc.status_id, "COMPLETED")
        self.assertIsNotNone(self.postqc.start_time)
        self.assertIsNotNone(self.postqc.end_time)

class IngestModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_4",
            organism_name="human"
        )
        self.ingest = Ingest.objects.create(
            fastq_name=self.metadata,
            status_id="PENDING",
            fid="ingest_123"
        )

    def test_ingest_creation(self):
        """Test Ingest creation and field values"""
        self.assertEqual(self.ingest.fastq_name, self.metadata)
        self.assertEqual(self.ingest.status_id, "PENDING")
        self.assertEqual(self.ingest.fid, "ingest_123")

class LoadAssociationModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_5",
            organism_name="human"
        )
        self.load_assoc = LoadAssociation.objects.create(
            fastq_name=self.metadata,
            load_name="load_123"
        )

    def test_load_association_creation(self):
        """Test LoadAssociation creation and field values"""
        self.assertEqual(self.load_assoc.fastq_name, self.metadata)
        self.assertEqual(self.load_assoc.load_name, "load_123")

    def test_unique_together_constraint(self):
        """Test that duplicate fastq_name and load_name combinations are not allowed"""
        with self.assertRaises(IntegrityError):
            LoadAssociation.objects.create(
                fastq_name=self.metadata,
                load_name="load_123"
            )

class MainModelTest(TransactionTestCase):
    def setUp(self):
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_6",
            organism_name="human",
            library_prep_method_name="10x_v3",
            studies=["study1"]
        )
        self.main = Main.objects.create(
            fastq_name=self.metadata,
            study_set="study_set_1",
            organism="human",
            library_prep_method="10x_v3",
            alignment_status="COMPLETED",
            postqc_status="RUNNING",
            ingest_status="PENDING"
        )

    def test_main_creation(self):
        """Test Main creation and field values"""
        self.assertEqual(self.main.fastq_name, self.metadata)
        self.assertEqual(self.main.study_set, "study_set_1")
        self.assertEqual(self.main.organism, "human")
        self.assertEqual(self.main.library_prep_method, "10x_v3")
        self.assertEqual(self.main.alignment_status, "COMPLETED")
        self.assertEqual(self.main.postqc_status, "RUNNING")
        self.assertEqual(self.main.ingest_status, "PENDING")

    def test_main_string_representation(self):
        """Test the string representation of main"""
        self.assertEqual(str(self.main), str(self.metadata))

class IntegrationTest(TransactionTestCase):
    def setUp(self):
        # Create base metadata
        self.metadata = Metadata.objects.create(
            fastq_name="test_fastq_7",
            organism_name="mouse",
            library_prep_method_name="10x_v3",
            studies=["study1", "study2"]
        )

        # Create related records
        self.alignment = Alignment.objects.create(
            fastq_name=self.metadata,
            status_id="COMPLETED"
        )

        self.postqc = PostQC.objects.create(
            fastq_name=self.metadata,
            status_id="RUNNING"
        )

        self.ingest = Ingest.objects.create(
            fastq_name=self.metadata,
            status_id="PENDING"
        )

        self.load_assoc = LoadAssociation.objects.create(
            fastq_name=self.metadata,
            load_name="load_123"
        )

        self.main = Main.objects.create(
            fastq_name=self.metadata,
            study_set="study_set_1",
            organism="mouse",
            library_prep_method="10x_v3",
            alignment_status="COMPLETED",
            postqc_status="RUNNING",
            ingest_status="PENDING"
        )

    def test_relationships(self):
        """Test all relationships are properly set up"""
        # Test forward relationships
        self.assertEqual(self.metadata.alignment, self.alignment)
        self.assertEqual(self.metadata.postqc, self.postqc)
        self.assertEqual(self.metadata.ingest, self.ingest)
        self.assertEqual(self.metadata.main, self.main)
        
        # Test reverse relationships
        self.assertEqual(list(self.metadata.loadassociation_set.all()), [self.load_assoc])

    def test_cascade_delete(self):
        """Test that deleting metadata cascades to all related records"""
        self.metadata.delete()
        
        self.assertEqual(Metadata.objects.count(), 0)
        self.assertEqual(Alignment.objects.count(), 0)
        self.assertEqual(PostQC.objects.count(), 0)
        self.assertEqual(Ingest.objects.count(), 0)
        self.assertEqual(LoadAssociation.objects.count(), 0)
        self.assertEqual(Main.objects.count(), 0) 