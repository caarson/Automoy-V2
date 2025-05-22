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
    
    // Setup form submission
    document.getElementById('objectiveForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const command = document.getElementById('objectiveInput').value;
        
        // Send command to backend
        fetch('/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'command': command
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Command sent:', data);
            document.getElementById('objectiveInput').value = '';
        })
        .catch(error => {
            console.error('Error sending command:', error);
        });
    });
    
    // Setup pause button
    document.getElementById('pauseBtn').addEventListener('click', function() {
        console.log('Pause button clicked');
        // Add pause functionality here
    });
    
    // Setup console polling
    setInterval(refreshConsole, 1000);
    
    // Initial console load
    refreshConsole();
    
    // Call operator state refresh periodically
    setInterval(refreshOperatorState, 1000);

    // Handle messages from Python backend
    window.handleWsMessage = function(messageString) {
        try {
            const message = JSON.parse(messageString);
            console.log('Received message from Python:', message);
            if (message.type === 'screenshot_processed') {
                console.log('Screenshot processed event received, refreshing screenshot.');
                refreshScreenshot();
            }
            // Add other message type handlers here if needed
            // For example, to update other parts of the UI based on backend state:
            if (message.type === 'operator_state_update') {
                // Assuming the message.data contains the same structure as /operator_state endpoint
                updateOperatorStateDisplay(message.data); 
            }
        } catch (error) {
            console.error('Error handling message from Python:', error);
        }
    };
});

// Function to refresh the screenshot from the processed_screenshot endpoint
function refreshScreenshot() {
    console.log('refreshScreenshot(): fetching /static/processed_screenshot.png');
    const imgElement = document.getElementById('screenshotImg');
    const placeholderEl = document.getElementById('screenshotPlaceholder');
    // Corrected path to /static/processed_screenshot.png
    fetch('/static/processed_screenshot.png?_=' + Date.now(), {cache: 'no-store'})
        .then(res => {
            if (!res.ok) throw new Error('No frame available');
            return res.blob();
        })
        .then(blob => {
            console.log('New frame fetched, updating image');
            if (imgElement.src.startsWith('blob:')) URL.revokeObjectURL(imgElement.src);
            imgElement.src = URL.createObjectURL(blob);
            imgElement.style.display = 'block';
            placeholderEl.style.display = 'none';
        })
        .catch(err => {
            console.log('Waiting for frame...', err.message);
            imgElement.style.display = 'none';
            placeholderEl.style.display = 'flex';
        });
}

// Function to refresh console output and update reasoning and operation text
function refreshConsole() {
    // This function is no longer needed as /operator_state provides all data.
    // We can remove its content or the function entirely if it's not used elsewhere.
    // For now, let's leave it empty to avoid breaking anything if it's called unexpectedly.
}

// Function to refresh operator state and update objective and coords
function refreshOperatorState() {
    fetch('/operator_state')
        .then(response => response.json())
        .then(data => {
            updateOperatorStateDisplay(data);
        })
        .catch(error => {
            console.error('Error fetching operator state:', error);
            // Optionally, update UI to show an error state
            const objEl = document.getElementById('objectiveDisplay');
            if (objEl) objEl.textContent = 'Error fetching state.';
            // Clear other fields or show error indicators
        });
}

// New function to consolidate UI updates from operator state
function updateOperatorStateDisplay(data) {
    // Update objective display
    const objEl = document.getElementById('objectiveDisplay');
    if (data.objective !== undefined && objEl) {
        objEl.textContent = 'Objective: ' + data.objective;
    } else if (objEl) {
        objEl.textContent = 'Awaiting Objective...';
    }

    // Update reasoning display
    const reasoningEl = document.getElementById('reasoningText');
    if (data.current_reasoning !== undefined && reasoningEl) {
        reasoningEl.textContent = data.current_reasoning;
    } else if (reasoningEl) {
        reasoningEl.textContent = 'Awaiting reasoning...';
    }

    // Update operation display
    const operationEl = document.getElementById('operationText');
    if (data.current_operation !== undefined && operationEl) {
        // Assuming current_operation is an object {command: "...", args: {...}}
        // You might want to format this nicely
        operationEl.textContent = JSON.stringify(data.current_operation, null, 2);
    } else if (operationEl) {
        operationEl.textContent = 'Awaiting operation...';
    }

    // Update coordinates display
    const coordsEl = document.getElementById('coordsDisplay');
    if (data.parsed_coords !== undefined && coordsEl) {
        coordsEl.textContent = `Coords: X: ${data.parsed_coords.x}, Y: ${data.parsed_coords.y}`;
    } else if (coordsEl) {
        coordsEl.textContent = 'Coords: N/A';
    }
}
