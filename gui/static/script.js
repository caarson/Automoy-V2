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
    
    // Setup objective form submission
    document.getElementById('objectiveForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const objective = document.getElementById('objectiveInput').value.trim();
        if (!objective) return;
        fetch('/set_objective', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ objective })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Objective set:', data);
            document.getElementById('objectiveInput').value = '';
            refreshOperatorState(); // update UI with new objective
        })
        .catch(error => {
            console.error('Error setting objective:', error);
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

    // Update LLM Stream Content Display
    const llmStreamEl = document.getElementById('llmStreamContent'); // Assuming you have an element with this ID
    if (data.llm_stream_content !== undefined && llmStreamEl) {
        // Sanitize HTML content before inserting, or use textContent if no HTML is expected.
        // For simplicity, using textContent here. If LLM can output HTML, use a sanitizer.
        llmStreamEl.textContent = data.llm_stream_content;
    } else if (llmStreamEl) {
        llmStreamEl.textContent = 'LLM Stream: Waiting for content...';
    }

    // Update Visual Analysis, Thinking Process, Steps, Current/Past Operations
    const visualEl = document.getElementById('visualText');
    if (data.visual_analysis !== undefined && visualEl) {
        visualEl.textContent = data.visual_analysis;
    } else if (visualEl) {
        visualEl.textContent = 'Waiting for visual analysis...';
    }

    const thinkingEl = document.getElementById('thinkingText');
    if (data.thinking_process !== undefined && thinkingEl) {
        thinkingEl.textContent = data.thinking_process;
    } else if (thinkingEl) {
        thinkingEl.textContent = 'Waiting for thinking process...';
    }

    const stepsEl = document.getElementById('stepsText');
    if (data.steps_generated && Array.isArray(data.steps_generated) && stepsEl) {
        if (data.steps_generated.length > 0) {
            stepsEl.innerHTML = data.steps_generated.map((step, index) => `${index + 1}. ${escapeHtml(step)}`).join('<br>');
        } else {
            stepsEl.textContent = 'No steps generated yet.';
        }
    } else if (stepsEl) {
        stepsEl.textContent = 'Waiting for steps...';
    }

    const currentOpEl = document.getElementById('currentOperation');
    if (data.current_operation !== undefined && currentOpEl) {
        currentOpEl.textContent = data.current_operation;
    } else if (currentOpEl) {
        currentOpEl.textContent = '{No current operation}';
    }

    const pastOpEl = document.getElementById('pastOperation');
    if (data.past_operation !== undefined && pastOpEl) {
        pastOpEl.textContent = data.past_operation;
    } else if (pastOpEl) {
        pastOpEl.textContent = '{No past operation}';
    }

    // Screenshot availability (already handled by refreshScreenshot, but can be synced here too)
    if (data.screenshot_available) {
        // refreshScreenshot(); // Call if direct refresh from state is desired
    } else {
        const imgElement = document.getElementById('screenshotImg');
        const placeholderEl = document.getElementById('screenshotPlaceholder');
        if (imgElement) imgElement.style.display = 'none';
        if (placeholderEl) placeholderEl.style.display = 'flex';
    }
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
 }
