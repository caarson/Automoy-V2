document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing UI');
    
    // Animated ellipsis for placeholder
    let ellipsisCount = 0;
    const placeholderEl = document.getElementById('screenshotPlaceholder');
    setInterval(() => {
        ellipsisCount = (ellipsisCount + 1) % 4;
        placeholderEl.textContent = 'Waiting for frame' + '.'.repeat(ellipsisCount);
    }, 500);

    // Initial screenshot load 
    setTimeout(refreshScreenshot, 500); // Short delay to ensure everything is loaded
    
    // Setup periodic refresh (every 3 seconds)
    setInterval(refreshScreenshot, 3000);
    
    // Setup objective form submission (reverted from goal form)
    document.getElementById('objectiveForm').addEventListener('submit', function(e) { // Changed back to objectiveForm
        e.preventDefault();
        const objectiveValue = document.getElementById('objectiveInput').value.trim(); // Store user input value
        if (!objectiveValue) return;
        fetch('/set_objective', { // Changed back to /set_objective
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ objective: objectiveValue }) // Send as 'objective'
        })
        .then(response => response.json())
        .then(data => { // data here is {message: "...", objective: "..."}
            console.log('Objective set:', data);
            document.getElementById('objectiveInput').value = ''; // Clear input
            // Update UI immediately using the objective confirmed by the server
            const objectiveEl = document.getElementById('objectiveDisplay');
            if (objectiveEl && data.objective) { // Use data.objective from server response
                objectiveEl.textContent = 'Objective: ' + data.objective;
            }
            // refreshOperatorState(); // This can be uncommented if preferred over immediate update, but immediate is good UX.
        })
        .catch(error => {
            console.error('Error setting objective:', error);
        });
    });
    
    // Initialize EventSource for LLM stream updates
    const eventSource = new EventSource('/stream_llm');
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Streamed data:', data);
        // Update UI components based on streamed data
        if (data.screenshot) {
            const imgElement = document.getElementById('screenshotImage');
            imgElement.src = 'data:image/png;base64,' + data.screenshot;
            imgElement.style.display = 'block';
            placeholderEl.style.display = 'none';
        }
        if (data.objective) {
            const objectiveEl = document.getElementById('objectiveDisplay');
            objectiveEl.textContent = 'Objective: ' + data.objective;
        }
        // Update other UI elements as needed
    };
    eventSource.onerror = function(error) {
        console.error('EventSource failed:', error);
        eventSource.close();
    };

    // Function to refresh operator state and update objective and coords
    function refreshOperatorState() {
        fetch('/get_operator_state')
            .then(response => response.json())
            .then(data => {
                console.log('Operator state:', data);
                // Update objective display
                const objectiveEl = document.getElementById('objectiveDisplay');
                if (objectiveEl && data.objective) {
                    objectiveEl.textContent = 'Objective: ' + data.objective;
                }
                // Update coordinates display
                const coordsEl = document.getElementById('coordsDisplay');
                if (coordsEl && data.coords) {
                    coordsEl.textContent = 'Coords: ' + data.coords;
                }
                // Update other UI elements as needed
            })
            .catch(error => {
                console.error('Error refreshing operator state:', error);
            });
    }

    // New function to consolidate UI updates from operator state
    function updateUIFromState(state) {
        console.log('Updating UI from state:', state);
        // Objective update
        const objectiveEl = document.getElementById('objectiveDisplay');
        if (objectiveEl && state.objective) {
            objectiveEl.textContent = 'Objective: ' + state.objective;
        }
        // Coordinates update
        const coordsEl = document.getElementById('coordsDisplay');
        if (coordsEl && state.coords) {
            coordsEl.textContent = 'Coords: ' + state.coords;
        }
        // Screenshot update
        const imgElement = document.getElementById('screenshotImage');
        if (imgElement && state.screenshot) {
            imgElement.src = 'data:image/png;base64,' + state.screenshot;
            imgElement.style.display = 'block';
            const placeholderEl = document.getElementById('screenshotPlaceholder');
            placeholderEl.style.display = 'none';
        }
        // Update other UI elements as needed
    }

    // Escape HTML helper function
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
