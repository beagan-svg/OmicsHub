// Handle submit selected samples button click
document.getElementById('submit-action-btn').addEventListener('click', function () {
    // Get only the checked samples from the table
    const selectedRows = document.querySelectorAll('.sample-select:checked');
    const selectedSamples = [];

    selectedRows.forEach(checkbox => {
        const row = checkbox.closest('tr');
        if (row) {
            const sample = {
                fastq_name: row.querySelector('td:nth-child(2)').textContent.trim(),
                study_set: row.querySelector('td:nth-child(3)').textContent.trim(),
                load_name: row.querySelector('td:nth-child(4)').textContent.trim(),
                batch_name_from_vendor: row.querySelector('td:nth-child(5)').textContent.trim(),
                organism_common_name: row.querySelector('td:nth-child(6)').textContent.trim(),
                library_prep: row.querySelector('td:nth-child(7)').textContent.trim(),
                ingest_status: row.querySelector('td:nth-child(8)').textContent.trim(),
                alignment_status: row.querySelector('td:nth-child(9)').textContent.trim(),
                postqc_status: row.querySelector('td:nth-child(10)').textContent.trim()
            };
            selectedSamples.push(sample);
        }
    });

    if (selectedSamples.length === 0) {
        showToast('Please select at least one sample', 'warning');
        return;
    }

    // Prepare samples for submission and check for incomplete samples
    prepareSubmissionModal(selectedSamples);
});

// Function to prepare submission modal
function prepareSubmissionModal(selectedSamples) {
    const modal = new bootstrap.Modal(document.getElementById('submissionModal'));
    const samplesList = document.getElementById('submission-samples-list');
    const selectedCountElem = document.getElementById('selected-count');
    const incompleteWarning = document.getElementById('incomplete-samples-warning');
    const incompleteList = document.getElementById('incomplete-samples-list');
    const submitBtn = document.getElementById('submitSamplesBtn');
    const proceedBtn = document.getElementById('proceedWithValidBtn');

    // Reset modal
    samplesList.innerHTML = '';
    incompleteList.innerHTML = '';
    incompleteWarning.classList.add('d-none');
    submitBtn.style.display = 'block';
    proceedBtn.style.display = 'none';

    // Set selected count
    selectedCountElem.textContent = selectedSamples.length;

    // Check each sample for ingest status
    const incompleteSamples = [];
    const validSamples = [];

    selectedSamples.forEach(sample => {
        const ingestStatus = sample.ingest_status || 'Not Started';
        const isComplete = ingestStatus === 'Completed';

        if (!isComplete) {
            incompleteSamples.push(sample);
        } else {
            validSamples.push(sample);
        }

        // Create row for sample
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${sample.fastq_name}</td>
            <td>${determineWorkflow(sample.batch_name_from_vendor) || 'RTX (default)'}</td>
            <td><span class="badge ${isComplete ? 'bg-success' : 'bg-warning'}">${ingestStatus}</span></td>
            <td><code class="small">Generating...</code></td>
        `;

        // Add color coding for incomplete samples
        if (!isComplete) {
            row.classList.add('table-warning');
        }

        samplesList.appendChild(row);
    });

    // Show warning if there are incomplete samples
    if (incompleteSamples.length > 0) {
        incompleteWarning.classList.remove('d-none');
        submitBtn.style.display = 'none';
        proceedBtn.style.display = 'block';

        // Populate incomplete samples list
        incompleteSamples.forEach(sample => {
            const li = document.createElement('li');
            li.textContent = sample.fastq_name;
            incompleteList.appendChild(li);
        });

        // Handle proceed with valid samples button
        document.getElementById('proceedWithValidBtn').onclick = function () {
            if (validSamples.length === 0) {
                showToast('No valid samples to submit', 'warning');
                return;
            }
            submitSamples(validSamples);
        };
    } else {
        // All samples are valid
        document.getElementById('submitSamplesBtn').onclick = function () {
            submitSamples(selectedSamples);
        };
    }

    // Show the modal
    modal.show();

    // Fetch command previews for each sample
    selectedSamples.forEach(sample => {
        // Simulate command preview (in real implementation, fetch from server)
        setTimeout(() => {
            const workflow = determineWorkflow(sample.batch_name_from_vendor) || 'rtx';
            const rows = samplesList.querySelectorAll('tr');

            for (let row of rows) {
                if (row.cells[0].textContent === sample.fastq_name) {
                    const commandCell = row.cells[3].querySelector('code');
                    if (workflow === 'mtx') {
                        commandCell.textContent = `ocs fastqs align tenx-arc --reference-names "..." --load-names "${sample.load_name || '...'}"`;
                    } else {
                        commandCell.textContent = `ocs fastqs align tenx-rnaseq --reference-names "..." --load-names "${sample.load_name || '...'}"`;
                    }
                }
            }
        }, 500);
    });
}

// Helper function to determine workflow from batch name
function determineWorkflow(batchName) {
    if (!batchName) return null;

    const parts = batchName.split('-');
    if (!parts.length) return null;

    const prefix = parts[0].toUpperCase();

    if (prefix === 'MTX' || batchName.includes('ATX')) {
        return 'mtx';
    } else if (prefix === 'RTX') {
        return 'rtx';
    }

    return 'rtx'; // Default to RTX
}

// Function to submit samples
function submitSamples(samples) {
    const forceSubmit = document.getElementById('forceSubmitCheck').checked;
    const modal = bootstrap.Modal.getInstance(document.getElementById('submissionModal'));

    showToast('Submitting samples...', 'info');
    modal.hide();

    // Call API to submit samples
    fetch('/api/pipeline/submit-samples/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            samples: samples.map(s => s.fastq_name),
            force_submit: forceSubmit
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(`Successfully submitted ${data.submitted_count} samples`, 'success');
                if (data.skipped_count > 0) {
                    showToast(`Skipped ${data.skipped_count} samples due to errors`, 'warning');
                }
                // Clear selected samples that were successfully submitted
                const submitted = new Set(data.submitted || []);
                pipelineLocalData.clearSelectedSamples(s => submitted.has(s.fastq_name));
                updateSelectedCount();
            } else {
                showToast(`Error: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Failed to submit samples', 'danger');
        });
}

// Helper function to get CSRF token
function getCsrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
} 