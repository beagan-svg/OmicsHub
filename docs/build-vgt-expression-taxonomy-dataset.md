# Build the VGT Expression and Taxonomy Dataset

This guide tells an LLM how to create a validated, model-ready dataset from the VGT expression matrices, taxonomy annotations, and optional LIMS metadata.

## Outcome

Produce one H5AD file where:

- each row is one cell,
- each column is one gene,
- `X` contains normalized CPM expression values,
- `obs` contains taxonomy labels and optional LIMS metadata, and
- every cell identifier was matched exactly once.

Example output record:

```text
Cell: AB-S40309_S001_E1-50
Expression: 8,401 genes with nonzero CPM
Cluster: L4_IT_VISp_Rspo1
Top leaf: L4_IT_VISp_Rspo1
Class: Glutamatergic
Taxonomy: AIT2.1.1
VGT code version: 1.4
LIMS lineage: specimen, donor, and organism found
```

## Inputs

```text
/Users/beagannguy/Desktop/Projects/vgt/input/fixed/other/
  220916_RSC-004-199_mouse_star2.7_cpm_sparse.Rdata

/Users/beagannguy/Desktop/Projects/vgt/input/dynamic/batch_260527_RSC-200-405/
  260527_RSC-200-405_mouse_star2.7_cpm_sparse.Rdata

/Users/beagannguy/Desktop/Projects/vgt/output/GT_Current/
  anno.feather
  memb.feather
  dend.RData
```

Do not use `data.feather`. Its current copy is incomplete and unreadable.

## Verified source behavior

The VGT pipeline joins expression to annotations using:

```text
colnames(cpmR) = anno.sample_id = LIMS rseq_experiment_components.name
```

The two expression matrices were tested on September 1, 2026:

| Check | Baseline | Current batch | Combined |
|---|---:|---:|---:|
| Matrix shape | 32,245 × 155,795 | 32,245 × 199,131 | Not combined until filtering |
| Annotated cells | 14,011 | 42,093 | 56,104 |
| Duplicate cell IDs between matrices | 0 | 0 | 0 |
| Annotated cells with nonzero expression | 14,011 | 42,093 | 56,104 |

Both matrices contain the same 32,245 unique genes in the same order. The ordered gene-list SHA-256 is:

```text
1b77a2bdc1c77db612bc343a26fe397fab35b48fcca5817735934df080fce8e0
```

`anno.feather` contains 56,104 unique, nonempty `sample_id` values. All 56,104 occur in exactly one expression matrix.

A four-cell H5AD smoke test was also completed using two cells from each matrix. The file reopened successfully with a sparse 4 × 32,245 expression matrix and retained the expected cluster and leaf labels. The temporary test file was removed afterward.

## Important label limitations

Use these fields:

- `cluster_label`: populated for 56,104 cells, 209 distinct values
- `cluster_detail_label`: populated for 56,104 cells, 209 distinct values
- `topLeaf_label`: populated for 56,104 cells, 111 distinct values
- `class_label`: populated for 29,433 cells, 3 distinct values
- `ref_version`: `AIT2.1.1`
- `code_version`: `1.4`

Do not use these fields as targets in the current export:

- `subclass_label`: every value is `ZZ_Missing`
- `broad_class_label`: every value is `ZZ_Missing`

These labels are VGT taxonomy assignments. Do not describe them as independently verified ground truth unless a scientist confirms how they were reviewed.

## Procedure

### 1. Work outside the source directories

Create a new output directory. Never overwrite the RData or Feather inputs.

Record the input paths, file sizes, and checksums in a manifest.

### 2. Validate the annotations

Read `anno.feather` with Python and PyArrow. Feather V1 support is required for the current file.

Confirm:

```text
rows = 56,104
unique sample_id = 56,104
empty sample_id = 0
ref_version = AIT2.1.1
code_version = 1.4
```

Stop if any count differs. Do not deduplicate automatically.

Keep at least:

```text
sample_id
cluster_label
cluster_detail_label
topLeaf_label
class_label
ref_version
code_version
```

Write the selected annotation table to Parquet and write the ordered `sample_id` values to a text file for R.

### 3. Load each sparse expression matrix correctly

Load the R `Matrix` package before loading or inspecting `cpmR`:

```r
suppressPackageStartupMessages(library(Matrix))
load("PATH_TO_CPM_RDATA")
stopifnot(inherits(cpmR, "dgCMatrix"))
```

Without `library(Matrix)`, row names may appear empty even though the sparse matrix contains gene identifiers.

For each matrix, confirm:

- 32,245 rows,
- unique, nonempty gene names,
- unique, nonempty cell names, and
- every selected cell has at least one nonzero expression value.

### 4. Verify genes before combining matrices

Require the two ordered gene lists to be identical:

```r
stopifnot(identical(rownames(baseline_cpm), rownames(current_cpm)))
```

Do not combine matrices by row position if this check fails. Reorder by exact gene name only after investigating the difference.

### 5. Join annotations to expression

Use exact cell-ID equality only. Do not use fuzzy matching, prefix matching, or fallback identifiers.

Expected matches:

```text
baseline matrix:      14,011 annotation IDs
current-batch matrix: 42,093 annotation IDs
combined:             56,104 unique annotation IDs
missing:                   0
matched twice:             0
```

Stop if the combined join does not cover all 56,104 annotation IDs exactly once.

Subset each sparse matrix to its matched cells, then combine the two matrices by columns.

### 6. Export the sparse matrix

From R, write:

- the filtered sparse matrix as Matrix Market,
- gene names in matrix row order, and
- cell IDs in matrix column order.

Do not convert the full matrix to a dense data frame.

The values are normalized CPM. Do not label them as raw counts.

### 7. Add taxonomy membership data if needed

`memb.feather` contains 56,104 unique `sample_id` values and matches the annotation ID set exactly.

Its remaining 212 columns are taxonomy-node membership values. Preserve their column names and taxonomy version. Do not call them probabilities or confidence scores until their statistical meaning is confirmed from the VGT method.

### 8. Add LIMS metadata

Use an approved read-only LIMS connection. Never place credentials in the guide, output, logs, or generated code.

Join:

```text
annotation.sample_id = rseq_experiment_components.name
```

Aggregate LIMS relationships to one row per `sample_id` before joining. Some experiment components can connect to multiple biological records, so a raw join can multiply cells.

Useful fields include:

- pseudonymous donor ID,
- specimen ID,
- organism,
- age,
- sex,
- brain region or ROI,
- study, and
- library-preparation method.

Report the match rate and all one-to-many relationships. Do not silently choose the first LIMS row.

### 9. Create the H5AD file

In Python:

1. Read the Matrix Market file as a sparse matrix.
2. Transpose it to cells × genes.
3. Read cell IDs and genes in their saved order.
4. Reindex annotations to the exact cell order.
5. Create `AnnData(X=expression, obs=annotations, var=genes)`.
6. Record `expression_unit = "CPM"`, taxonomy version, code version, input checksums, and creation date in `uns`.
7. Write a compressed H5AD file.

Do not populate `raw` unless raw counts are obtained and validated separately.

### 10. Validate the final file

Before accepting the output, require:

```text
cells = 56,104
genes = 32,245
unique obs names = 56,104
unique var names = 32,245
missing cluster_label = 0
missing topLeaf_label = 0
cells with zero total expression = 0
```

Also confirm:

- the expression matrix remains sparse,
- each `obs` row matches its original `sample_id`,
- the example cell retains the expected labels,
- no donor appears in more than one train/validation/test partition, and
- the H5AD file can be reopened after writing.

## Clear completion condition

The task is complete only when one H5AD file reopens successfully and contains 56,104 uniquely identified cells, 32,245 correctly ordered genes, CPM expression, usable cluster and leaf labels, and a validation report showing zero missing or duplicated joins.

If any required count changes, stop and explain the discrepancy. Do not add fallback matching logic to force the dataset to build.
