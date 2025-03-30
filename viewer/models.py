from django.db import models

class Metadata(models.Model):
    fastq_name = models.CharField(max_length=255, primary_key=True)
    organism_name = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method_name = models.CharField(max_length=255, null=True, blank=True)
    studies = models.CharField(max_length=255, null=True, blank=True)
    alignment_method = models.CharField(max_length=255, null=True, blank=True)
    amplification_id = models.BigIntegerField(null=True, blank=True)
    amplification_name = models.CharField(max_length=255, null=True, blank=True)
    batch_name = models.CharField(max_length=255, null=True, blank=True)
    batch_name_from_vendor = models.CharField(max_length=255, null=True, blank=True)
    cell_capture = models.IntegerField(null=True, blank=True)
    cell_prep_type = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method_id = models.BigIntegerField(null=True, blank=True)
    library_prep_name = models.CharField(max_length=255, null=True, blank=True)
    organism_common_name = models.CharField(max_length=255, null=True, blank=True)
    sample_id = models.BigIntegerField(null=True, blank=True)
    sample_name = models.CharField(max_length=255, null=True, blank=True)
    sample_type = models.CharField(max_length=255, null=True, blank=True)
    sequencing_vendor = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'metadata'

    def __str__(self):
        return self.fastq_name

class Alignment(models.Model):
    fastq_name = models.ForeignKey(Metadata, on_delete=models.CASCADE)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'alignment'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class PostQC(models.Model):
    fastq_name = models.ForeignKey(Metadata, on_delete=models.CASCADE)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'postqc'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class Ingest(models.Model):
    fastq_name = models.ForeignKey(Metadata, on_delete=models.CASCADE)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'ingest'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class LoadAssociation(models.Model):
    fastq_name = models.ForeignKey(Metadata, on_delete=models.CASCADE)
    load_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'load_association'

    def __str__(self):
        return f"{self.fastq_name} - {self.load_name}"

class Main(models.Model):
    fastq_name = models.OneToOneField(Metadata, on_delete=models.CASCADE, primary_key=True, related_name='main')
    study_set = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method = models.CharField(max_length=255, null=True, blank=True)
    organism = models.CharField(max_length=255, null=True, blank=True)
    alignment_status = models.CharField(max_length=50, null=True, blank=True)
    postqc_status = models.CharField(max_length=50, null=True, blank=True)
    ingest_status = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'main'
        managed = False  # Prevent Django from trying to create/modify this table

    def __str__(self):
        return str(self.fastq_name)
        
    def batch_name(self):
        """
        Access batch_name from the related Metadata model
        """
        return self.fastq_name.batch_name
        
    def cell_capture(self):
        """
        Access cell_capture from the related Metadata model
        """
        return self.fastq_name.cell_capture

class UserPreferences(models.Model):
    session_key = models.CharField(max_length=40, primary_key=True)
    show_batch_name = models.BooleanField(default=True)
    show_cell_capture = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_preferences' 