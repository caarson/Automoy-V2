document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing UI');
    
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

// Function to refresh the screenshot from the latest processed image
function refreshScreenshot() {
    console.log('Refreshing screenshot...');
    fetch('/get_latest_screenshot')
        .then(response => {
            console.log('Screenshot response:', response);
            return response.json();
        })
        .then(data => {
            console.log('Screenshot data:', data);
            if (data.status === 'success') {
                const imgElement = document.getElementById('screenshotImg');
                imgElement.src = data.screenshotUrl;
                console.log('Screenshot refreshed:', data.screenshotUrl);
                // Force reload by setting a random parameter if image doesn't load
                imgElement.onerror = () => {
                    console.error('Image failed to load, trying with cache buster');
                    imgElement.src = data.screenshotUrl + '&nocache=' + new Date().getTime();
                };
            } else {
                console.error('Error refreshing screenshot:', data.message);
            }
        })
        .catch(error => {
            console.error('Error fetching screenshot:', error);
        });
}

// Function to refresh console output and update reasoning and operation text
function refreshConsole() {
    fetch('/console_output')
        .then(response => response.json())
        .then(data => {
            const lines = data.output || [];
            let thinking, visual, steps, pastOp, currOp;
            lines.forEach(line => {
                if (line.startsWith('Thinking:')) {
                    thinking = line.substring('Thinking:'.length).trim();
                } else if (line.startsWith('Visual:')) {
                    visual = line.substring('Visual:'.length).trim();
                } else if (line.startsWith('Steps:')) {
                    steps = line.substring('Steps:'.length).trim();
                } else if (line.startsWith('Past Operation:')) {
                    pastOp = line.substring('Past Operation:'.length).trim();
                } else if (line.startsWith('Current Operation:')) {
                    currOp = line.substring('Current Operation:'.length).trim();
                }
            });
            if (thinking) document.getElementById('thinkingText').textContent = thinking;
            if (visual) document.getElementById('visualText').textContent = visual;
            if (steps) document.getElementById('stepsText').textContent = steps;
            if (pastOp) document.getElementById('pastOperation').textContent = pastOp;
            if (currOp) document.getElementById('currentOperation').textContent = currOp;
        })
        .catch(error => console.error('Error refreshing console output:', error));
}

// Function to refresh operator state and update objective and coords
function refreshOperatorState() {
    fetch('/operator_state')
        .then(response => response.json())
        .then(data => {
            // Update objective display
            const objEl = document.getElementById('objectiveDisplay');
            if (data.objective !== undefined && objEl) {
                objEl.textContent = 'Objective: ' + data.objective;
            }
            // Update coords display
            const coordsEl = document.getElementById('coordsDisplay');
            if (data.coords !== undefined && coordsEl) {
                coordsEl.style.display = 'block';
                coordsEl.textContent = JSON.stringify(data.coords, null, 2);
            }
            // Update last action display
            const lastEl = document.getElementById('lastActionDisplay');
            if (data.last_action !== undefined && lastEl) {
                lastEl.style.display = 'block';
                lastEl.textContent = 'Last Action: ' + JSON.stringify(data.last_action);
            }
        })
        .catch(error => console.error('Error fetching operator state:', error));
}
