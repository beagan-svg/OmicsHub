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
                 'organism', 'ingest_status', 'alignment_status', 'postqc_status')
        attrs = {'class': 'table table-striped table-bordered'} 