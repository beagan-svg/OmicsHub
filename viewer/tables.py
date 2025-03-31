from django_tables2 import tables, Column
from django.utils.html import format_html
from django.db.models import OuterRef, Subquery
from .models import Main, LoadAssociation

class MainTable(tables.Table):
    fastq_name = Column(accessor='fastq_name.fastq_name', verbose_name='Fastq Name')
    load_name = Column(verbose_name='Load Name', empty_values=())
    study_set = Column(verbose_name='Study Set')
    organism = Column(verbose_name='Organism')
    library_prep_method = Column(verbose_name='Library Prep Method')
    batch_name = Column(verbose_name='Batch Name', attrs={'th': {'class': 'column-batch_name'}, 'td': {'class': 'field-batch_name'}})
    cell_capture = Column(verbose_name='Cell Capture', attrs={'th': {'class': 'column-cell_capture'}, 'td': {'class': 'field-cell_capture'}})
    sample_name = Column(accessor='fastq_name.sample_name', verbose_name='Sample Name', attrs={'th': {'class': 'column-sample_name'}, 'td': {'class': 'field-sample_name'}})
    sample_type = Column(accessor='fastq_name.sample_type', verbose_name='Sample Type', attrs={'th': {'class': 'column-sample_type'}, 'td': {'class': 'field-sample_type'}})
    amplification_name = Column(accessor='fastq_name.amplification_name', verbose_name='Amplification', attrs={'th': {'class': 'column-amplification_name'}, 'td': {'class': 'field-amplification_name'}})
    cell_prep_type = Column(accessor='fastq_name.cell_prep_type', verbose_name='Cell Prep Type', attrs={'th': {'class': 'column-cell_prep_type'}, 'td': {'class': 'field-cell_prep_type'}})
    sequencing_vendor = Column(accessor='fastq_name.sequencing_vendor', verbose_name='Sequencing Vendor', attrs={'th': {'class': 'column-sequencing_vendor'}, 'td': {'class': 'field-sequencing_vendor'}})
    alignment_status = Column(verbose_name='Alignment Status')
    postqc_status = Column(verbose_name='PostQC Status')
    ingest_status = Column(verbose_name='Ingest Status')
    
    class Meta:
        model = Main
        fields = ('fastq_name', 'load_name', 'study_set', 'organism', 'library_prep_method', 
                 'batch_name', 'cell_capture', 'sample_name', 'sample_type', 'amplification_name',
                 'cell_prep_type', 'sequencing_vendor', 'alignment_status', 'postqc_status', 'ingest_status')
        attrs = {
            'class': 'table table-striped table-bordered',
            'thead': {'class': 'table-light'},
        }
        row_attrs = {
            'class': 'table-row',
        }
    
    def render_load_name(self, value, record):
        """
        Render load_name(s) for a given fastq_name
        """
        # Get all load associations for this fastq_name
        load_associations = LoadAssociation.objects.filter(fastq_name=record.fastq_name)
        
        if not load_associations.exists():
            return "—"  # Em dash for empty values
            
        # Return comma-separated load names if multiple exist
        load_names = [la.load_name for la in load_associations]
        return ", ".join(load_names)

    def render_study_set(self, value):
        """
        Render study_set without brackets and quotes
        """
        if not value:
            return "—"  # Em dash for empty values
        
        # If value is already a string (not a list representation), just return it
        if not (value.startswith('[') and value.endswith(']')):
            return value
            
        # Remove the brackets and quotes
        # This handles ['study_name'] format
        cleaned_value = value.strip('[]')
        # Remove quotes
        cleaned_value = cleaned_value.replace('"', '').replace("'", '')
        
        return cleaned_value

    def render_alignment_status(self, value):
        """Render alignment status with color coding"""
        if value == 'COMPLETED':
            status_class = 'text-success'
        elif value == 'NOT COMPLETED':
            status_class = 'text-warning'
        elif value == 'FAILED':
            status_class = 'text-danger'
        else:
            status_class = 'text-secondary'
            
        return format_html('<span class="{}">{}</span>', status_class, value or "—")

    def render_postqc_status(self, value):
        """Render PostQC status with color coding"""
        if value == 'COMPLETED':
            status_class = 'text-success'
        elif value == 'NOT COMPLETED':
            status_class = 'text-warning'
        elif value == 'FAILED':
            status_class = 'text-danger'
        else:
            status_class = 'text-secondary'
            
        return format_html('<span class="{}">{}</span>', status_class, value or "—")

    def render_ingest_status(self, value):
        """Render Ingest status with color coding"""
        if value == 'COMPLETED':
            status_class = 'text-success'
        elif value == 'NOT COMPLETED':
            status_class = 'text-warning'
        elif value == 'FAILED':
            status_class = 'text-danger'
        else:
            status_class = 'text-secondary'
            
        return format_html('<span class="{}">{}</span>', status_class, value or "—") 