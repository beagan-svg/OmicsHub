// Generated on 2025-03-30 07:28:06.068429+00:00
// This file forces browser cache refresh

// Make sure toggleColumnVisibility uses the correct class selectors
function toggleColumnVisibility(fieldName, visible) {
    // Use the correct selector pattern
    const columnClass = `.column-${fieldName}`;
    console.log(`Toggle ${fieldName} to ${visible ? 'visible' : 'hidden'} (selector: ${columnClass})`);
    
    const columnElements = document.querySelectorAll(columnClass);
    console.log(`Found ${columnElements.length} elements with class ${columnClass}`);
    
    columnElements.forEach(element => {
        element.style.display = visible ? '' : 'none';
    });
}
