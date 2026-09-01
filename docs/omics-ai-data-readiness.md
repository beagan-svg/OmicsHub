# Omics AI Data-Product Readiness Assessment

**Assessment date:** September 1, 2026
**Scope:** OmicsHub, production OCS DynamoDB and S3 metadata, read-only LIMS PostgreSQL, and locally available STAR/taxonomy artifacts.

## 1. Executive conclusion

**Partially.**

The available systems contain enough data to build a meaningful, governed minimum viable product. They do not yet constitute a broadly distributable, AI-ready dataset.

The strongest evidence is:

- All **495,147** production DynamoDB FASTQ metadata records match a LIMS experiment component by exact `fastq_name`.
- LIMS provides specimen, donor, age, sex, and organism lineage for **100%** of those records, spanning **9,580 distinct donors**.
- LIMS has **1,022,897 STAR analysis runs** with alignment metrics and registered FASTQ, gene-count, TPM, and BAM outputs.
- Local STAR artifacts contain **199,131** experiment components, including **173,031** records that pass the saved STAR QC exclusion rule.
- A separate taxonomy artifact contains **56,104** cell-level annotations with **209 cluster labels** and **111 leaf labels**.
- Modern OCS storage contains **41,824** registered file stores totaling approximately **3.64 PB** of declared data, including raw FASTQ, BAM, count matrices, HDF5, H5AD, and QC outputs.

The primary blockers are not data volume. They are:

- No verified sample-level consent, data-use, redistribution-rights, or access-tier metadata.
- Biological labels use project-specific terms and have not been mapped consistently to external ontologies such as Cell Ontology, UBERON, EFO, or MONDO.
- Cell-level taxonomy labels are present for a subset, not the entire corpus.
- Data are split across OmicsHub, DynamoDB, LIMS, S3, and local analysis artifacts rather than represented as one versioned release.
- Registered files do not consistently expose immutable checksums through the audited metadata.
- OmicsHub's active catalog contains only **16,291 records**, or **3.29%** of the full DynamoDB metadata catalog, because synchronization is scoped to active workflow prefixes.

The practical decision is to build a controlled internal release first, validate rights and label quality, then decide which portions can become a multi-institution product.

### Coverage snapshot

```text
Full AWS metadata catalog     495,147  |██████████████████████████████| 100.00%
Current OmicsHub catalog       16,291  |█                             |   3.29%
Detailed taxonomy labels       56,104  |███                           |  11.33%*

*Shown against the full AWS catalog only to illustrate relative scale. The taxonomy
 cohort has different eligibility rules and should not be interpreted as missing labels
 for every other AWS record.
```

## 2. Data inventory

### OmicsHub

OmicsHub currently stores **16,291 samples** selected by active workflow prefixes. Its sample model includes:

- FASTQ name
- internal and vendor batch names
- sequencing vendor
- organism common and scientific names
- library-preparation method, name, and ID
- sample ID, names, and type
- cell-capture and cell-preparation type
- amplification ID and name
- load name
- alignment method
- studies
- synchronization timestamp

For each stage, OmicsHub stores the demand ID, execution ARN, raw OCS status, source update time, synchronization time, start time, duration, and file-store ID.

The UI exposes filtered CSV exports and authenticated downloads of registered S3 objects. The CSV export is a view of selected application columns, not a complete scientific metadata package. Some upstream fields, including `cellranger_multi_metadata`, are not represented in the local `Sample` model or normal CSV export.

### AWS and DynamoDB

The production OCS data model uses four principal DynamoDB tables:

| Table role | Primary identity | Purpose |
|---|---|---|
| FASTQ metadata | `fastq_name` | LIMS-derived sample and library metadata |
| FASTQ history | `fastq_name` + demand type/ID | Stage history and input/output file-store relationships |
| Demand registry | `demand_id` | Workflow request, status, execution, message, command, image, and timing |
| File store | `file_store_id` | S3 location, category, declared size, demand, and timestamps |

Production FASTQ metadata contains **495,147 records**. The largest vendor-batch families are approximately:

| Family | Records |
|---|---:|
| RSC | 474,285 |
| ATX | 5,814 |
| RTX | 5,230 |
| MTX | 5,138 |
| BT3 | 3,790 |
| RFX | 109 |

The metadata catalog includes 28 organism terms, 34 library-preparation methods, 1,959 vendor batches, and 251 studies. Important field coverage is:

| Field | Coverage |
|---|---:|
| Core FASTQ, batch, organism, library, sample, amplification, and alignment fields | 100% |
| Sample names | 99.997% |
| Studies | 92.319% |
| Cell-preparation type | 92.314% |
| Cell-capture | 15.688% |
| Load name | 6.325% |
| Cell Ranger multi metadata | 0.071% |

The demand registry contains **33,541 demands**, including 27,643 completed, 4,686 failed, 781 aborted, 427 in progress, and 4 awaiting. Failure and abort messages exist for 5,467 demands, but they are mostly unstructured operational messages rather than reviewed root-cause labels.

The modern file-store registry contains:

| Category | Files/stores | Declared size |
|---|---:|---:|
| Raw FASTQ | 18,124 | 2,027.74 TB |
| Alignment | 12,304 | 1,594.06 TB |
| QC/post-alignment | 11,343 | 21.61 TB |
| References and probes | 53 | 0.92 TB |

Representative registered outputs include FASTQ, BAM/BAI, count matrices, HDF5, H5AD, CSV metrics, HTML reports, PDF reports, and visualization files.

### LIMS PostgreSQL

The read-only connection was verified against database `lims2` with `transaction_read_only=on`. The database contains 602 public base tables and 50 annotation-schema tables.

The primary sequence lineage is:

```text
rseq_tube_sets
└── rseq_tubes
    └── rseq_experiments
        └── rseq_experiment_components
            ├── FACS well / cell-prep / specimen / donor lineage
            └── library-prep / amplification lineage
```

Relevant LIMS scale includes:

- 556,353 RNA-seq experiment components
- 833,756 FACS well templates
- 551,067 RNA-seq library preparations
- 549,724 RNA amplifications
- 1,154,657 analysis runs
- 1,026,985 experiment-component-to-STAR-run links

For the complete DynamoDB cohort, exact `fastq_name` matching found:

| LIMS lineage field | Coverage |
|---|---:|
| LIMS experiment component | 100% |
| Specimen | 100% |
| Donor | 100% |
| Age | 100% |
| Sex | 100% |
| Organism | 100% |
| External donor ID | 99.94% |
| Direct specimen structure | 6.11% |

The direct specimen structure field understates region information available through other LIMS paths. In the modern FACS-linked cohort, a controlled ROI structure is present for 99.92% of 18,062 FASTQ-to-well pairs. These two values must not be combined without a documented hierarchy and normalization rule.

Additional modern-cohort coverage includes genotype at 51.49%, medical condition at 22.43%, hemisphere at 27.37%, study at 99.99%, and injection metadata at approximately 2.07%.

LIMS stores sequencing and preparation measurements such as read counts, lane reads, PCR cycles, concentrations, library sizes, input quantities, indexes, failure flags, and STAR alignment metrics. Coverage varies by assay and era.

### Legacy STAR and taxonomy artifacts

Current LIMS contains **1,022,897 STAR analysis runs**. Registered STAR files include:

| Output type | Registered files | Runs represented |
|---|---:|---:|
| Forward-read FASTQ | 3,050,431 | 1,016,811 |
| Reverse-read FASTQ | 3,050,430 | 1,016,810 |
| TPM per gene | 1,016,830 | 1,016,830 |
| Gene-level counts | 1,016,810 | 1,016,810 |
| Genome-aligned BAM | 1,016,811 | 1,016,811 |
| ERCC-aligned BAM | 1,016,811 | 1,016,811 |
| E. coli-aligned BAM | 1,016,811 | 1,016,811 |

These registered STAR outputs total approximately **128.45 TB** by declared file size.

Separate local artifacts contain a 199,131-component sparse CPM corpus and 56,104 detailed cell annotations. One 9.48 GB expression Feather artifact is currently unreadable because its footer is incomplete. This does not invalidate the sparse CPM source, but it demonstrates why release validation and checksums are required.

## 3. Per-sample metadata map

```text
Sample / FASTQ
├── source identity
│   ├── fastq_name                         LIMS → DynamoDB → OmicsHub
│   ├── vendor batch / internal batch      LIMS → DynamoDB → OmicsHub
│   └── sample_id and sample_type          LIMS → DynamoDB → OmicsHub
├── biological source
│   ├── specimen and donor                 LIMS
│   ├── organism, age, sex                 LIMS, with selected fields copied to DynamoDB
│   ├── genotype / medical condition       LIMS, partial coverage
│   └── region / ROI / hemisphere          LIMS, path and coverage vary by cohort
├── experiment
│   ├── study                              LIMS → DynamoDB → OmicsHub
│   ├── cell-preparation and capture       LIMS → DynamoDB → OmicsHub
│   ├── amplification and load             LIMS → DynamoDB → OmicsHub
│   └── library-preparation method         LIMS → DynamoDB → OmicsHub
├── sequencing and QC
│   ├── indexes, reads, concentrations      LIMS
│   ├── STAR metrics and exclusion          LIMS / analysis artifacts
│   └── modern assay QC                     S3 output files
├── processing provenance
│   ├── demand ID and workflow status       DynamoDB
│   ├── command, image, execution ARN       DynamoDB
│   └── stage duration and file-store ID    DynamoDB → OmicsHub
└── files
    ├── legacy STAR files                   LIMS well-known-file registry
    └── modern raw/align/QC files            DynamoDB file store → S3
```

Authoritative-source rules are essential. For example, `sample_id` can refer to different entity types depending on `sample_type`, and `load_name` is not globally safe as a biological-sample identity.

## 4. Cross-system lineage

The strongest confirmed join path is:

```text
LIMS rseq_experiment_components.name
    = DynamoDB fastq-metadata.fastq_name
    = DynamoDB fastq-history.fastq_name
        → demand_type_and_id
        → demand-registry.demand_id
        → file_store_id
        → file-store.s3_uri
        → downloadable scientific files
```

Evidence supporting this path:

- 495,147 of 495,147 production DynamoDB FASTQ names matched LIMS exactly.
- All 58,859 FASTQ-history rows refer to FASTQ names present in production metadata.
- All 41,824 file-store records match a demand-registry demand.
- In the current OmicsHub cohort, all 19,409 distinct local demand IDs matched the demand registry.
- All 47,024 local stage rows matched the registry demand and expected stage type.
- All 44,747 local stage/file-store references checked matched the expected demand and file category.

Known identity cautions:

- 234 current FASTQ records link to more than one FACS well, with as many as 26 links.
- 5,111 load groups contain the intended MTX/ATX pairing, but 281 load groups mix other prefixes. Pairing must therefore use assay-aware rules, not `load_name` alone.
- One demand can cover multiple FASTQ names. Alignment has 5,541 multi-sample demands, with up to eight FASTQs per demand.
- Scientific-name capitalization is not fully normalized, for example `Homo Sapiens` versus `Homo sapiens`.

## 5. Metadata completeness

### High coverage

- FASTQ identity and vendor/internal batch
- sample type and source-system identity
- organism
- specimen and donor lineage
- donor age and sex
- library-preparation method
- amplification identity
- processing demand, status, command, image, and timing for OCS-managed work
- S3 location and declared size for modern registered outputs
- STAR read and alignment metrics for the legacy STAR corpus

### Medium or cohort-dependent coverage

- study and project context
- external donor identity
- load name
- genotype
- hemisphere
- cell-level taxonomy labels
- modern post-alignment QC outputs
- experimental condition and injection metadata

### Low, inconsistent, or absent

- globally harmonized tissue and anatomical-region ontology terms
- globally harmonized cell-type ontology terms
- disease ontology and experimental-condition normalization
- explicit label confidence and human-review history
- sample-level consent group, redistribution right, license, and access tier
- immutable file checksums in the audited registries
- public accessions such as BioProject, BioSample, SRA experiment, and SRA run
- institution-independent protocol identifiers

### Metadata that can be derived reliably

- LIMS-to-DynamoDB-to-file lineage using `fastq_name`, demand ID, and file-store ID
- assay modality from validated library and vendor-batch rules
- intended MTX/ATX pairing from assay-aware load-name rules
- demand-level grouping of multiple FASTQ inputs
- stage-level operational outcomes and durations

### Metadata requiring normalization or review

- organism spelling and capitalization
- anatomical structures and ROI hierarchy
- cell taxonomy labels and mapping to Cell Ontology
- library-preparation names across versions
- QC pass/fail policy across assays and eras
- failure messages into a reviewed root-cause taxonomy
- consent text into data-use terms such as GA4GH DUO

## 6. AI-readiness gaps

1. **Rights and governance are unproven.** Human genomic and donor-linked data cannot be offered externally merely because files are technically retrievable. No sample-level consent or data-use field was confirmed in the audited schema.
2. **The release unit is undefined.** A product needs an immutable dataset version, inclusion criteria, schema version, checksums, and a manifest. Current records are operational state, not a release.
3. **Labels need provenance.** Detailed taxonomy labels exist, but a product must record taxonomy version, annotator or algorithm, confidence, and any manual correction.
4. **Ontologies are not harmonized.** Allen/LIMS structures and taxonomy labels are scientifically meaningful but not automatically interoperable with CELLxGENE or another institution.
5. **Files require validation.** The unreadable Feather file is direct evidence that existence and size are insufficient. Every release file needs an integrity check and content validation.
6. **Splitting can leak biology and batches.** Cells or FASTQs from the same donor, specimen, capture, load, demand, or study must remain in one partition.
7. **Operational failures are noisy labels.** A failed demand may reflect infrastructure, invalid input, software, or scientific QC. Those outcomes should not be combined without review.
8. **OmicsHub is a scoped operational view.** It cannot be treated as the complete catalog unless the product pipeline reads the full upstream metadata independently of submission workflow configuration.

## 7. Best product opportunities

| Rank | Product | Usefulness | Feasibility | Human annotation | Expected scale | Main risk |
|---:|---|---|---|---|---|---|
| 1 | Single-cell expression and taxonomy benchmark | High | Medium-high | Medium-high | Up to 56,104 detailed labels plus a larger weakly labeled corpus | Rights, ontology mapping, label versioning |
| 2 | Assay-aware sequencing QC benchmark | High | High internally, medium externally | Medium | 199,131 legacy records plus modern OCS outputs | QC policy differs by assay and institution |
| 3 | Metadata normalization and entity-resolution benchmark | High across institutions | High | Medium | 495,147 source records | Silver labels may encode Allen-specific rules |
| 4 | Paired RNA/ATAC raw-to-processed corpus | Very high | Medium | High | 5,111 confirmed MTX/ATX load groups covering 10,952 records | Human-data rights and incomplete multimodal standardization |
| 5 | Workflow failure-prediction benchmark | Medium | High internally | Medium | 33,541 demands with 5,467 failed/aborted messages | OCS/AWS-specific behavior may not generalize |

### 1. Single-cell expression and taxonomy benchmark

- **Input:** sparse gene-expression matrix and per-cell technical/biological metadata.
- **Target:** cluster or leaf label, plus the three-value class label where populated. The current subclass and broad-class exports contain only `ZZ_Missing` and are not usable targets.
- **Label source:** saved taxonomy artifacts tied by experiment-component name.
- **Cleaning:** intersect readable matrix columns with annotations, remove controls and excluded records, normalize genes and labels, map labels to external ontologies where possible.
- **Risk:** detailed labels may reflect one taxonomy and one institution's tissue focus.
- **Value:** scientifically interpretable model training and evaluation for cell-type annotation and out-of-distribution generalization.
- **Automation:** matrix and metadata assembly can be automated. Ontology mapping and ambiguous labels require expert review.

### 2. Assay-aware sequencing QC benchmark

- **Input:** pre-QC sequencing, library, organism, assay, and preparation metadata plus permitted summary features.
- **Target:** a versioned scientific QC outcome, not merely workflow completion.
- **Label source:** STAR exclusion and LIMS failure fields for legacy data, plus reviewed post-alignment metrics for modern assays.
- **Cleaning:** define assay-specific policies, normalize false-value variants, exclude information generated after the prediction point.
- **Risk:** post-QC fields can leak the target, and thresholds can be institution-specific.
- **Value:** useful for sequencing facilities and research institutes prioritizing reruns and diagnosing technical variation.

### 3. Metadata normalization and entity resolution

- **Input:** de-identified sample, library, batch, load, FASTQ, demand, and file records.
- **Target:** canonical entity links and duplicate/non-duplicate decisions.
- **Label source:** exact IDs plus validated MTX/ATX and demand-grouping rules.
- **Cleaning:** build hard negatives, hide identifiers that directly created the label, normalize names and types.
- **Risk:** automatic links are silver labels and may teach institution-specific naming conventions.
- **Value:** directly transferable to institutions struggling to reconcile LIMS, workflow, and object-storage records.

### 4. Paired RNA/ATAC corpus

- **Input:** paired raw FASTQ and processed matrices/H5AD, with assay and specimen lineage.
- **Target:** self-supervised cross-modal objectives, gene activity, or paired representation learning.
- **Label source:** assay-aware MTX/ATX pairing using shared load identity.
- **Cleaning:** verify one biological capture, normalize feature spaces, retain pairing through every split, confirm whether ATAC fragment files are available.
- **Risk:** high transfer cost, human-genomic governance, and incomplete standardization.
- **Value:** highest scientific upside if sharing authority can be established.

### 5. Workflow failure prediction

- **Input:** information known before submission or at a precisely defined execution cutoff.
- **Target:** reviewed failure category or terminal outcome.
- **Label source:** demand registry, logs, and human-reviewed root cause.
- **Cleaning:** remove terminal message, final duration, and output-existence leakage. Group related FASTQs by demand.
- **Risk:** predicts Allen/OCS infrastructure rather than general scientific failure.

## 8. Recommended annotation strategy

### Automate

- Preserve source identifiers and generate immutable product identifiers.
- Assemble donor → specimen → capture → library → FASTQ → demand → output lineage.
- Copy controlled LIMS terms without silently changing them.
- Derive assay and pairing only through tested, assay-aware rules.
- Extract QC metrics using versioned parsers for each output schema.
- Record missingness explicitly rather than substituting `unknown` for absent data.
- Generate candidate ontology mappings with source term, target term, mapping method, and confidence.

### Human review

- Approve consent groups, redistribution rights, access tiers, and commercial-use conditions.
- Review ontology mappings for anatomy, cell type, disease, assay, and developmental stage.
- Define assay-specific QC policies and adjudicate borderline cases.
- Review ambiguous entity links and construct hard negative examples.
- Classify failure messages into a small root-cause taxonomy.
- Validate benchmark tasks and test sets before labels are released.

Human review should concentrate on high-impact ambiguity. It should not manually transcribe metadata already joined reliably from LIMS.

## 9. Minimum viable dataset

### Recommended MVP: governed single-cell taxonomy benchmark

**Inclusion criteria**

- Cell or nucleus records, excluding controls.
- A readable sparse expression column tied to one experiment-component name.
- A detailed taxonomy annotation tied to the same identifier.
- No LIMS experiment-component failure.
- Not excluded by the versioned STAR QC rule.
- Specimen and donor lineage present.
- Data-use approval for the intended access tier.

**Expected scale**

All **56,104 annotated cells** match exactly one of the two readable sparse CPM matrices. The final release count may be lower after applying scientific QC and lineage requirements.

**Required fields**

- product cell ID and source experiment-component ID
- pseudonymous donor and specimen IDs
- source study
- organism, age/development stage, sex
- source region/ROI and reviewed ontology mapping
- library-preparation method and cell/nucleus type
- normalized CPM expression matrix with stable gene identifiers
- cluster and leaf labels, plus class where populated
- an explicit note that the current subclass and broad-class fields are unusable because every value is `ZZ_Missing`
- taxonomy and label-generation version
- STAR QC metrics and QC-policy version
- source file IDs, sizes, checksums, and lineage
- access tier and approved data-use statement
- fixed train, validation, and test assignment

**Output format**

- CELLxGENE-compatible H5AD where feasible
- versioned JSON or Parquet manifest for file and lineage metadata
- SHA-256 checksum manifest
- machine-readable data card describing scope, exclusions, label provenance, missingness, rights, and known biases

**Splitting strategy**

- Keep all cells from one specimen in one partition.
- Keep all specimens from one donor in one partition.
- Keep technical replicates and derived files together.
- Use unseen donors for validation.
- Reserve one or more complete studies for the final test set where label balance permits.
- Do not use random cell-level splitting.

**Provenance requirements**

- immutable source and release identifiers
- matrix and annotation checksums
- LIMS query/revision date
- taxonomy version
- code revision and exact transformation parameters
- reference genome and gene-annotation version
- QC-policy version
- human-review decisions with reviewer role and reason

If rights cannot be established for expression data, the fallback MVP should be a de-identified entity-resolution benchmark containing no genomic measurements or direct donor identifiers.

## 10. Recommended next steps

1. **Run a formal governance inventory.** Assign consent group, access tier, redistribution right, and commercial-use status to every candidate study before exporting data.
2. **Build a read-only release manifest.** Join LIMS, DynamoDB, and file records without changing operational systems. Preserve authoritative source and timestamp for every field.
3. **Validate scientific eligibility.** The 56,104 expression-to-annotation joins are confirmed. Next confirm QC eligibility, biological label quality, donor grouping, and file integrity.
4. **Create a controlled-vocabulary mapping review.** Map organism, region, cell type, assay, disease, sex, and developmental stage to recognized ontologies while preserving original terms.
5. **Define and version QC policies.** Separate technical execution success from scientific quality and create assay-specific rules.
6. **Add release-grade file integrity.** Calculate checksums, validate expected schemas, and reject truncated or unreadable artifacts before publication.
7. **Produce a small internal release.** Use a fixed donor/study split, data card, lineage manifest, and reproducible build command. Have scientists review label quality and leakage.
8. **Test cross-institution portability.** Give the schema and a small de-identified sample to a partner institution. Measure how much custom mapping is required.
9. **Only then choose the commercial boundary.** The likely product is curated data plus schema mapping, QC policy, lineage, and expert review, not unrestricted access to raw genomic files.

## Method and limitations

The investigation was read-only. It traced current OmicsHub implementation, queried production DynamoDB and LIMS metadata, inspected representative S3 file listings and headers, and inspected existing STAR/taxonomy artifacts. LIMS connectivity was verified with a harmless query and every audit connection enforced PostgreSQL read-only mode.

Confirmed findings are separated from product recommendations. No production data or infrastructure was modified.

Important limitations:

- File contents were sampled rather than exhaustively downloaded.
- Registered path and size do not prove that every object remains readable.
- No legal or institutional data-governance authority approved external use during this audit.
- The detailed STAR/taxonomy artifact is a local analytical snapshot, not yet a versioned production release.
- The unreadable expression Feather file requires recovery or regeneration, although a separate sparse CPM artifact is available.
- Cross-institution generalization cannot be claimed until an external institution is held out and evaluated.

## Interoperability targets

A multi-institution release should align, where applicable, with:

- [CELLxGENE single-cell schema](https://chanzuckerberg.github.io/single-cell-curation/latest-schema.html)
- [AnnData](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html)
- [NCBI BioProject, BioSample, and SRA metadata model](https://www.ncbi.nlm.nih.gov/sra/docs/submitmeta/)
- [GA4GH Data Repository Service](https://ga4gh.github.io/data-repository-service-schemas/)
- [GA4GH Data Use Ontology](https://www.ga4gh.org/product/data-use-ontology-duo/)
- [Human Cell Atlas metadata schema](https://github.com/HumanCellAtlas/metadata-schema)
- [NIH Genomic Data Sharing policy](https://grants.nih.gov/policy-and-compliance/policy-topics/sharing-policies/gds)
