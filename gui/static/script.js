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
});

// Function to refresh the screenshot from the processed_screenshot endpoint
function refreshScreenshot() {
    console.log('refreshScreenshot(): fetching processed_screenshot.png');
    const imgElement = document.getElementById('screenshotImg');
    const placeholderEl = document.getElementById('screenshotPlaceholder');
    fetch('/processed_screenshot.png?_=' + Date.now(), {cache: 'no-store'})
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
            // Update objective display
            const objEl = document.getElementById('objectiveDisplay');
            if (data.objective !== undefined && objEl) {
                // Display the main user-set objective
                objEl.textContent = 'Objective: ' + data.objective;
            } else if (objEl) {
                objEl.textContent = 'Awaiting Objective...';
            }

            // Update Visual Analysis
            const visualEl = document.getElementById('visualText');
            if (data.visual_analysis !== undefined && visualEl) {
                visualEl.textContent = data.visual_analysis;
            } else if (visualEl) {
                visualEl.textContent = '';
            }

            // Update Thinking Process
            const thinkingEl = document.getElementById('thinkingText');
            if (data.thinking_process !== undefined && thinkingEl) {
                thinkingEl.textContent = data.thinking_process;
            } else if (thinkingEl) {
                thinkingEl.textContent = '';
            }

            // Update Steps
            const stepsEl = document.getElementById('stepsText');
            if (data.steps !== undefined && stepsEl) {
                stepsEl.textContent = data.steps;
            } else if (stepsEl) {
                stepsEl.textContent = '';
            }

            // Update Past Operation
            const pastOpEl = document.getElementById('pastOperation');
            if (data.past_operation !== undefined && pastOpEl) {
                pastOpEl.textContent = data.past_operation;
            } else if (pastOpEl) {
                pastOpEl.textContent = '{No past operation}';
            }

            // Update Current Operation
            const currentOpEl = document.getElementById('currentOperation');
            if (data.current_operation !== undefined && currentOpEl) {
                currentOpEl.textContent = data.current_operation;
            } else if (currentOpEl) {
                currentOpEl.textContent = '{No current operation}';
            }
            
            // Update coords display (if still needed, or remove if not)
            const coordsEl = document.getElementById('coordsDisplay');
            if (data.coords !== undefined && coordsEl) {
                coordsEl.style.display = 'block';
                coordsEl.textContent = JSON.stringify(data.coords, null, 2);
            } else if (coordsEl) {
                coordsEl.style.display = 'none';
            }

            // Update last action display (if still needed, or remove if not)
            const lastEl = document.getElementById('lastActionDisplay');
            if (data.last_action !== undefined && lastEl) {
                lastEl.style.display = 'block';
                lastEl.textContent = 'Last Action: ' + JSON.stringify(data.last_action);
            } else if (lastEl) {
                lastEl.style.display = 'none';
            }
        })
        .catch(error => console.error('Error fetching operator state:', error));
}
