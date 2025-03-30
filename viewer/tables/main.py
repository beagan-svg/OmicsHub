import django_tables2 as tables
from viewer.models import Main, LoadAssociation
from django.db.models import Subquery, OuterRef
from django.utils.safestring import mark_safe

class MainTable(tables.Table):
    fastq_name = tables.Column(verbose_name='Fastq Name')
    study_set = tables.Column(verbose_name='Study Set', accessor='fastq_name.studies')
    load_name = tables.Column(verbose_name='Load Name', accessor='fastq_name.loadassociation_set.first.load_name')
    library_prep_method = tables.Column(verbose_name='Library Prep Method', accessor='fastq_name.library_prep_method_name')
    organism = tables.Column(verbose_name='Organism', accessor='fastq_name.organism_name')
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
    ingest_status = tables.Column(verbose_name='Ingest Status')
    alignment_status = tables.Column(verbose_name='Alignment Status')
    postqc_status = tables.Column(verbose_name='PostQC Status')

    def render_study_set(self, value):
        if value:
            return value
        return ''

    def render_load_name(self, record):
        try:
            load_assoc = record.fastq_name.loadassociation_set.first()
            return load_assoc.load_name if load_assoc else ''
        except Exception:
            return ''

    def render_ingest_status(self, value):
        status_class = 'status-completed' if value == 'COMPLETED' else 'status-not-completed'
        return mark_safe(f'<span class="status-badge {status_class}">{value}</span>')

    def render_alignment_status(self, value):
        status_class = 'status-completed' if value == 'COMPLETED' else 'status-not-completed'
        return mark_safe(f'<span class="status-badge {status_class}">{value}</span>')

    def render_postqc_status(self, value):
        status_class = 'status-completed' if value == 'COMPLETED' else 'status-not-completed'
        return mark_safe(f'<span class="status-badge {status_class}">{value}</span>')

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
                 'library_prep_method_id', 'library_prep_name', 'ingest_status', 
                 'alignment_status', 'postqc_status')
        attrs = {'class': 'table table-striped table-bordered'} 