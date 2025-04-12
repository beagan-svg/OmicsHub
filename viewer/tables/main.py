import django_tables2 as tables
from viewer.models import Main, LoadAssociation, Ingest, Alignment, PostQC
from django.db.models import Subquery, OuterRef
from django.utils.safestring import mark_safe

class MainTable(tables.Table):
    fastq_name = tables.Column(verbose_name='Fastq Name', attrs={'th': {'class': 'column-fastq_name'}, 'td': {'class': 'field-fastq_name'}})
    study_set = tables.Column(verbose_name='Study Set', accessor='fastq_name.studies', attrs={'th': {'class': 'column-study_set'}, 'td': {'class': 'field-study_set'}})
    load_name = tables.Column(verbose_name='Load Name', accessor='fastq_name.loadassociation_set.first.load_name', attrs={'th': {'class': 'column-load_name'}, 'td': {'class': 'field-load_name'}})
    library_prep_method = tables.Column(verbose_name='Library Prep Method', accessor='fastq_name.library_prep_method_name', attrs={'th': {'class': 'column-library_prep_method'}, 'td': {'class': 'field-library_prep_method'}})
    organism = tables.Column(verbose_name='Organism', accessor='fastq_name.organism_name', attrs={'th': {'class': 'column-organism'}, 'td': {'class': 'field-organism'}})
    organism_common_name = tables.Column(verbose_name='Organism Common Name', accessor='fastq_name.organism_common_name', attrs={'th': {'class': 'column-organism_common_name'}, 'td': {'class': 'field-organism_common_name'}})
    batch_name = tables.Column(verbose_name='Batch Name', accessor='fastq_name.batch_name', attrs={'th': {'class': 'column-batch_name'}, 'td': {'class': 'field-batch_name'}})
    batch_name_from_vendor = tables.Column(verbose_name='Batch Name From Vendor', accessor='fastq_name.batch_name_from_vendor', attrs={'th': {'class': 'column-batch_name_from_vendor'}, 'td': {'class': 'field-batch_name_from_vendor'}})
    cell_capture = tables.Column(verbose_name='Cell Capture', accessor='fastq_name.cell_capture', attrs={'th': {'class': 'column-cell_capture'}, 'td': {'class': 'field-cell_capture'}})
    sample_id = tables.Column(verbose_name='Sample ID', accessor='fastq_name.sample_id', attrs={'th': {'class': 'column-sample_id'}, 'td': {'class': 'field-sample_id'}})
    amplification_name = tables.Column(verbose_name='Amplification', accessor='fastq_name.amplification_name', attrs={'th': {'class': 'column-amplification_name'}, 'td': {'class': 'field-amplification_name'}})
    amplification_id = tables.Column(verbose_name='Amplification ID', accessor='fastq_name.amplification_id', attrs={'th': {'class': 'column-amplification_id'}, 'td': {'class': 'field-amplification_id'}})
    cell_prep_type = tables.Column(verbose_name='Cell Prep Type', accessor='fastq_name.cell_prep_type', attrs={'th': {'class': 'column-cell_prep_type'}, 'td': {'class': 'field-cell_prep_type'}})
    sequencing_vendor = tables.Column(verbose_name='Sequencing Vendor', accessor='fastq_name.sequencing_vendor', attrs={'th': {'class': 'column-sequencing_vendor'}, 'td': {'class': 'field-sequencing_vendor'}})
    alignment_method = tables.Column(verbose_name='Alignment Method', accessor='fastq_name.alignment_method', attrs={'th': {'class': 'column-alignment_method'}, 'td': {'class': 'field-alignment_method'}})
    library_prep_method_id = tables.Column(verbose_name='Library Prep Method ID', accessor='fastq_name.library_prep_method_id', attrs={'th': {'class': 'column-library_prep_method_id'}, 'td': {'class': 'field-library_prep_method_id'}})
    library_prep_name = tables.Column(verbose_name='Library Prep Name', accessor='fastq_name.library_prep_name', attrs={'th': {'class': 'column-library_prep_name'}, 'td': {'class': 'field-library_prep_name'}})
    ingest_status = tables.Column(
        accessor='ingest_status',
        verbose_name='Ingest Status',
        attrs={
            'td': {'class': 'status-column ingest-status'},
            'th': {'class': 'status-column ingest-status'}
        },
        empty_values=('', None)
    )
    ingest_fid = tables.Column(
        accessor='fastq_name__ingest__fid',
        verbose_name='Ingest FID',
        attrs={
            'td': {'class': 'fid-column ingest-fid'},
            'th': {'class': 'fid-column ingest-fid'}
        },
        empty_values=('', None)
    )
    ingest_start_time = tables.Column(verbose_name='Ingest Start', empty_values=(), attrs={'th': {'class': 'column-ingest_start_time'}, 'td': {'class': 'field-ingest_start_time'}})
    ingest_end_time = tables.Column(verbose_name='Ingest End', empty_values=(), attrs={'th': {'class': 'column-ingest_end_time'}, 'td': {'class': 'field-ingest_end_time'}})
    alignment_status = tables.Column(
        accessor='alignment_status',
        verbose_name='Alignment Status',
        attrs={
            'td': {'class': 'status-column alignment-status'},
            'th': {'class': 'status-column alignment-status'}
        },
        empty_values=('', None)
    )
    alignment_fid = tables.Column(
        accessor='fastq_name__alignment__fid',
        verbose_name='Alignment FID',
        attrs={
            'td': {'class': 'fid-column alignment-fid'},
            'th': {'class': 'fid-column alignment-fid'}
        },
        empty_values=('', None)
    )
    alignment_start_time = tables.Column(verbose_name='Alignment Start', empty_values=(), attrs={'th': {'class': 'column-alignment_start_time'}, 'td': {'class': 'field-alignment_start_time'}})
    alignment_end_time = tables.Column(verbose_name='Alignment End', empty_values=(), attrs={'th': {'class': 'column-alignment_end_time'}, 'td': {'class': 'field-alignment_end_time'}})
    postqc_status = tables.Column(
        accessor='postqc_status',
        verbose_name='PostQC Status',
        attrs={
            'td': {'class': 'status-column postqc-status'},
            'th': {'class': 'status-column postqc-status'}
        },
        empty_values=('', None)
    )
    postqc_fid = tables.Column(
        accessor='fastq_name__postqc__fid',
        verbose_name='PostQC FID',
        attrs={
            'td': {'class': 'fid-column postqc-fid'},
            'th': {'class': 'fid-column postqc-fid'}
        },
        empty_values=('', None)
    )
    postqc_start_time = tables.Column(verbose_name='PostQC Start', empty_values=(), attrs={'th': {'class': 'column-postqc_start_time'}, 'td': {'class': 'field-postqc_start_time'}})
    postqc_end_time = tables.Column(verbose_name='PostQC End', empty_values=(), attrs={'th': {'class': 'column-postqc_end_time'}, 'td': {'class': 'field-postqc_end_time'}})

    def render_study_set(self, value):
        if value:
            return value
        return '—'

    def render_load_name(self, record):
        try:
            load_assoc = record.fastq_name.loadassociation_set.first()
            return load_assoc.load_name if load_assoc else '—'
        except Exception:
            return '—'

    def render_library_prep_method(self, value):
        return value if value and value != 'NA' else '—'

    def render_organism(self, value):
        return value if value and value != 'NA' else '—'

    def render_organism_common_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_batch_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_batch_name_from_vendor(self, value):
        return value if value and value != 'NA' else '—'

    def render_cell_capture(self, value):
        return value if value and value != 'NA' else '—'

    def render_sample_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_amplification_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_amplification_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_cell_prep_type(self, value):
        return value if value and value != 'NA' else '—'

    def render_sequencing_vendor(self, value):
        return value if value and value != 'NA' else '—'

    def render_alignment_method(self, value):
        return value if value and value != 'NA' else '—'

    def render_library_prep_method_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_library_prep_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_ingest_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_alignment_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_postqc_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_ingest_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')

    def render_alignment_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')

    def render_postqc_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')
    
    def render_ingest_start_time(self, value, record):
        """Render Ingest start time"""
        try:
            ingest_record = Ingest.objects.get(fastq_name=record.fastq_name)
            if ingest_record.start_time:
                return ingest_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Ingest.DoesNotExist:
            pass
        return "—"
    
    def render_ingest_end_time(self, value, record):
        """Render Ingest end time"""
        try:
            ingest_record = Ingest.objects.get(fastq_name=record.fastq_name)
            if ingest_record.end_time:
                return ingest_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Ingest.DoesNotExist:
            pass
        return "—"
        
    def render_alignment_start_time(self, value, record):
        """Render Alignment start time"""
        try:
            alignment_record = Alignment.objects.get(fastq_name=record.fastq_name)
            if alignment_record.start_time:
                return alignment_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Alignment.DoesNotExist:
            pass
        return "—"
    
    def render_alignment_end_time(self, value, record):
        """Render Alignment end time"""
        try:
            alignment_record = Alignment.objects.get(fastq_name=record.fastq_name)
            if alignment_record.end_time:
                return alignment_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Alignment.DoesNotExist:
            pass
        return "—"
        
    def render_postqc_start_time(self, value, record):
        """Render PostQC start time"""
        try:
            postqc_record = PostQC.objects.get(fastq_name=record.fastq_name)
            if postqc_record.start_time:
                return postqc_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except PostQC.DoesNotExist:
            pass
        return "—"
    
    def render_postqc_end_time(self, value, record):
        """Render PostQC end time"""
        try:
            postqc_record = PostQC.objects.get(fastq_name=record.fastq_name)
            if postqc_record.end_time:
                return postqc_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except PostQC.DoesNotExist:
            pass
        return "—"

    def order_load_name(self, queryset, is_descending):
        queryset = queryset.annotate(
            load_name=Subquery(
                LoadAssociation.objects.filter(fastq_name=OuterRef('fastq_name'))
                .values('load_name')[:1]
            )
        ).order_by(('-' if is_descending else '') + 'load_name')
        return queryset, True

    class Meta:
        model = Main
        template_name = "django_tables2/bootstrap5.html"
        fields = ('fastq_name', 'study_set', 'load_name', 'library_prep_method', 
                 'organism', 'organism_common_name', 'batch_name', 'batch_name_from_vendor',
                 'cell_capture', 'sample_id', 'amplification_name', 'amplification_id', 
                 'cell_prep_type', 'sequencing_vendor', 'alignment_method', 
                 'library_prep_method_id', 'library_prep_name', 
                 'ingest_status', 'ingest_fid', 'ingest_start_time', 'ingest_end_time',
                 'alignment_status', 'alignment_fid', 'alignment_start_time', 'alignment_end_time', 
                 'postqc_status', 'postqc_fid', 'postqc_start_time', 'postqc_end_time')
        attrs = {'class': 'table table-striped table-bordered'} 