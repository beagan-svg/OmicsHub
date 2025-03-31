/**
 * Table Column Classes
 * Adds the appropriate column classes to all table cells based on their header
 */

document.addEventListener('DOMContentLoaded', function() {
    // Find all tables
    const tables = document.querySelectorAll('table.table');
    
    tables.forEach(table => {
        // Get all headers
        const headerCells = table.querySelectorAll('thead th');
        const headerMapping = [];
        
        // Create mapping of column index to class name
        headerCells.forEach((th, index) => {
            // Get header text and convert to snake_case
            const headerText = th.textContent.trim().toLowerCase();
            const className = `column_${headerText.replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')}`;
            
            // Add column class to header
            th.classList.add(className);
            
            // Store the mapping
            headerMapping[index] = className;
        });
        
        // Get all rows in the table body
        const rows = table.querySelectorAll('tbody tr');
        
        // Add class to each cell based on its position
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            
            cells.forEach((cell, cellIndex) => {
                if (headerMapping[cellIndex]) {
                    cell.classList.add(headerMapping[cellIndex]);
                }
            });
        });
    });
}); 