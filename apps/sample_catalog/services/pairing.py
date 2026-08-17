"""Match the GEX and ATAC fastq samples in a multiome pair.

A multiome experiment is sequenced as two halves, a GEX library and an ATAC library.
that arrive as separate fastq entries under different vendor batches (MTX-32013 and
ATX-36013, say). They are the same biological sample and are aligned together, so
submitting one without the other produces a run that cannot complete.

The two halves are matched on `load_name`, which is the one field they share: batch name,
amplification name and fastq name all differ between them.
"""

from __future__ import annotations

from apps.sample_catalog.models import MULTIOME_PREPS, Sample


def with_multiome_partners(samples) -> tuple[list[Sample], list[Sample]]:
    """Return the selected samples, added partners, and the expanded selection.

    The second element is what the UI needs: telling someone their 4-sample selection
    became 8 is the difference between a helpful feature and a surprising one.
    """
    samples = list(samples)
    selected_names = {sample.fastq_name for sample in samples}

    # One query for the whole selection rather than one per sample. Only samples that are
    # half of a pair can contribute a partner, so anything else is filtered out first.
    wanted: set[tuple[str, str]] = set()
    for sample in samples:
        partner_prep = sample.multiome_partner_prep
        if partner_prep and sample.load_name:
            wanted.add((sample.load_name, partner_prep))

    if not wanted:
        return samples, []

    candidates = Sample.objects.filter(
        load_name__in={load_name for load_name, _ in wanted},
        library_prep_method_name__in=MULTIOME_PREPS,
    ).prefetch_related("stage_statuses")

    partners = [
        candidate
        for candidate in candidates
        if (candidate.load_name, candidate.library_prep_method_name) in wanted
        and candidate.fastq_name not in selected_names
    ]
    return samples + partners, partners
