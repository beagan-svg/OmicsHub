"""Match the GEX and ATAC fastq samples in a multiome pair.

A multiome experiment is sequenced as two halves, a GEX library and an ATAC library,
that arrive as separate fastq entries under different batch names from the vendor (MTX-32013 and
ATX-36013, say). They are the same biological sample and are aligned together, so
submitting one without the other produces a run that cannot complete.

The two halves are matched on `load_name` and batch-name-from-vendor prefix (MTX/ATX), not on
library prep name , a vendor's naming for the two halves varies, so the prep name is
not a reliable signal, and load_name alone is not enough either (see MULTIOME_PREFIXES).
"""

from __future__ import annotations

from apps.sample_catalog.models import MULTIOME_PREFIXES, Sample


def with_multiome_partners(samples) -> tuple[list[Sample], list[Sample]]:
    """Return the expanded selection and the partners added to it.

    The second element lets the UI report which partners were added to the selection.
    """
    samples = list(samples)
    selected_names = {sample.fastq_name for sample in samples}

    # One query for the whole selection rather than one per sample. Only samples that are
    # half of a pair can contribute a partner, so anything else is filtered out first.
    wanted: set[tuple[str, str]] = set()
    for sample in samples:
        partner_prefix = sample.multiome_partner_prefix
        if partner_prefix and sample.load_name:
            wanted.add((sample.load_name, partner_prefix))

    if not wanted:
        return samples, []

    candidates = Sample.objects.filter(
        load_name__in={load_name for load_name, _ in wanted},
        batch_prefix__in=MULTIOME_PREFIXES,
    ).prefetch_related("stage_statuses")

    partners = [
        candidate
        for candidate in candidates
        if (candidate.load_name, candidate.batch_prefix) in wanted
        and candidate.fastq_name not in selected_names
    ]
    return samples + partners, partners
