from django_tables2 import tables, Column
from django.utils.html import format_html
from django.db.models import OuterRef, Subquery
from .models import Main, LoadAssociation, Alignment, PostQC, Ingest
from django.utils import timezone
import datetime

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
    
    # Status columns
    alignment_status = Column(verbose_name='Alignment Status')
    alignment_time = Column(empty_values=(), verbose_name='Alignment Time', attrs={'th': {'class': 'column-alignment_time'}, 'td': {'class': 'field-alignment_time'}})
    
    postqc_status = Column(verbose_name='PostQC Status')
    postqc_time = Column(empty_values=(), verbose_name='PostQC Time', attrs={'th': {'class': 'column-postqc_time'}, 'td': {'class': 'field-postqc_time'}})
    
    ingest_status = Column(verbose_name='Ingest Status')
    ingest_time = Column(empty_values=(), verbose_name='Ingest Time', attrs={'th': {'class': 'column-ingest_time'}, 'td': {'class': 'field-ingest_time'}})
    
    class Meta:
        model = Main
        fields = ('fastq_name', 'load_name', 'study_set', 'organism', 'library_prep_method', 
                 'batch_name', 'cell_capture', 'sample_name', 'sample_type', 'amplification_name',
                 'cell_prep_type', 'sequencing_vendor', 
                 'alignment_status', 'alignment_time',
                 'postqc_status', 'postqc_time',
                 'ingest_status', 'ingest_time')
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

    def render_alignment_time(self, record):
        """Render alignment time information"""
        try:
            # First try to get the prefetched attribute
            if hasattr(record.fastq_name, 'alignment_info'):
                alignment = record.fastq_name.alignment_info
                if alignment:
                    return self._format_time_range(alignment.start_time, alignment.end_time)
                else:
                    return "—"
            else:
                # Fallback to database query if not prefetched
                alignment = Alignment.objects.get(fastq_name=record.fastq_name)
                return self._format_time_range(alignment.start_time, alignment.end_time)
        except Alignment.DoesNotExist:
            return "—"

    def render_postqc_time(self, record):
        """Render postqc time information"""
        try:
            # First try to get the prefetched attribute
            if hasattr(record.fastq_name, 'postqc_info'):
                postqc = record.fastq_name.postqc_info
                if postqc:
                    return self._format_time_range(postqc.start_time, postqc.end_time)
                else:
                    return "—"
            else:
                # Fallback to database query if not prefetched
                postqc = PostQC.objects.get(fastq_name=record.fastq_name)
                return self._format_time_range(postqc.start_time, postqc.end_time)
        except PostQC.DoesNotExist:
            return "—"

    def render_ingest_time(self, record):
        """Render ingest time information"""
        try:
            # First try to get the prefetched attribute
            if hasattr(record.fastq_name, 'ingest_info'):
                ingest = record.fastq_name.ingest_info
                if ingest:
                    return self._format_time_range(ingest.start_time, ingest.end_time)
                else:
                    return "—"
            else:
                # Fallback to database query if not prefetched
                ingest = Ingest.objects.get(fastq_name=record.fastq_name)
                return self._format_time_range(ingest.start_time, ingest.end_time)
        except Ingest.DoesNotExist:
            return "—"
    
    def _format_time_range(self, start_time, end_time):
        """Format start and end time to a readable format"""
        if not start_time:
            return "Not started"
            
        # Calculate duration if both start and end times are available
        if end_time:
            duration = end_time - start_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            
            if duration.days > 0:
                duration_str = f"{duration.days}d {hours}h {minutes}m"
            elif hours > 0:
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = f"{minutes}m"
                
            # Format the date
            start_date = start_time.strftime("%Y-%m-%d")
            
            return format_html('<span title="Started: {}, Duration: {}">{}...</span>', 
                              start_time.strftime("%Y-%m-%d %H:%M"), 
                              duration_str,
                              start_date)
        else:
            # If still running, calculate time since start
            now = timezone.now()
            elapsed = now - start_time
            hours = elapsed.seconds // 3600
            minutes = (elapsed.seconds % 3600) // 60
            
            if elapsed.days > 0:
                elapsed_str = f"{elapsed.days}d {hours}h {minutes}m"
            elif hours > 0:
                elapsed_str = f"{hours}h {minutes}m"
            else:
                elapsed_str = f"{minutes}m"
                
            start_date = start_time.strftime("%Y-%m-%d")
            
            return format_html('<span title="Started: {}, Running for: {}" class="text-primary">{}...</span>', 
                              start_time.strftime("%Y-%m-%d %H:%M"), 
                              elapsed_str,
                              start_date) 