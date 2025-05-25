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
    // setTimeout(refreshScreenshot, 500); // No longer needed, will be triggered by notification
    
    // Setup periodic refresh (every 3 seconds) - Keep this as a fallback or for general updates
    // setInterval(refreshScreenshot, 3000); // Commenting out to rely on notification primarily

    const goalForm = document.getElementById('goalForm'); // Changed from objectiveForm
    const goalInput = document.getElementById('goalInput'); // Changed from objectiveInput
    const userGoalDisplay = document.getElementById('userGoalDisplay'); // New display element
    const formulatedObjectiveDisplay = document.getElementById('formulatedObjectiveDisplay'); // New display element
    
    const llmStreamContent = document.getElementById('llmStreamContent');
    const visualAnalysisDisplay = document.getElementById('visualAnalysisDisplay'); // Added
    const thinkingProcessDisplay = document.getElementById('thinkingProcessDisplay'); // Added
    const stepsGeneratedDisplay = document.getElementById('stepsGeneratedList'); // Corrected ID
    const operationsGeneratedDisplay = document.getElementById('operationsGeneratedText'); // Added for new section
    const currentOperationDisplay = document.getElementById('currentOperationDisplay');
    const llmQueryDisplay = document.getElementById('llmQueryDisplay');
    const llmResponseDisplay = document.getElementById('llmResponseDisplay');
    const executionResultDisplay = document.getElementById('executionResultDisplay');
    const historyLogDisplay = document.getElementById('historyLogDisplay');
    
    const pauseButton = document.getElementById('pauseButton');
    const pauseIcon = document.getElementById('pauseIcon');
    let isPaused = false; // Local state to track pause status for UI updates

    if (goalForm && goalInput && userGoalDisplay && formulatedObjectiveDisplay) { // Updated condition
        goalForm.addEventListener('submit', function(e) {
            e.preventDefault(); 
            const goalValue = goalInput.value;

            fetch('/set_goal', { // Changed from /set_objective
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal: goalValue }) // Changed from objective
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => { 
                        throw new Error(`Server error: ${response.status} - ${text || 'No error message'}`); 
                    });
                }
                return response.json();
            })
            .then(data => { // Corrected syntax: added parentheses around data
                if (data.goal) {
                    userGoalDisplay.textContent = data.goal;
                    console.log('Goal set to:', data.goal);
                }
                if (data.formulated_objective) { // Update formulated objective display if available
                    formulatedObjectiveDisplay.textContent = data.formulated_objective;
                }
                goalInput.value = ''; // Clear input after submission
            })
            .catch(error => {
                console.error('Error setting goal:', error);
                if(userGoalDisplay) userGoalDisplay.textContent = 'Error setting goal. Check console.';
            });
        });
    } else {
        console.error('Goal form elements not found. Check HTML IDs: goalForm, goalInput, userGoalDisplay, formulatedObjectiveDisplay.');
        if (!goalForm) console.error('goalForm is missing.');
        if (!goalInput) console.error('goalInput is missing.');
        if (!userGoalDisplay) console.error('userGoalDisplay is missing.');
        if (!formulatedObjectiveDisplay) console.error('formulatedObjectiveDisplay is missing.');
    }

    // SSE for LLM stream updates
    if (llmStreamContent) {
        const eventSourceLlmStream = new EventSource('/llm_stream_updates');
        eventSourceLlmStream.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.signal === '__STREAM_START__') {
                    llmStreamContent.textContent = ''; // Clear content on new stream start
                    console.log("LLM Stream started.");
                } else if (data.signal === '__STREAM_END__') {
                    console.log("LLM Stream ended.");
                    // Optionally, do something on stream end, like re-enable a button or fetch final state.
                    // The current server-side implementation doesn't explicitly close the EventSource from server,
                    // but client can choose to close if needed, or server can send a specific "close" signal.
                } else if (data.chunk) {
                    llmStreamContent.textContent += data.chunk;
                    // Auto-scroll to bottom if content overflows
                    // llmStreamContent.scrollTop = llmStreamContent.scrollHeight; 
                }
            } catch (e) {
                console.error("Error parsing LLM stream data: ", e, "Raw data:", event.data);
                // Fallback for non-JSON data, though server should always send JSON
                // llmStreamContent.textContent += event.data;
            }
        };
        eventSourceLlmStream.onerror = function(err) {
            console.error('LLM EventSource failed:', err);
            // Consider closing and attempting to reconnect after a delay, or notifying the user.
            // eventSourceLlmStream.close(); 
        };
    } else {
        console.warn('llmStreamContent element not found in the DOM.');
    }

    // Function to fetch and display the entire operator state
    function fetchAndUpdateOperatorState() {
        fetch('/operator_state')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server error fetching state: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (userGoalDisplay && data.user_goal && userGoalDisplay.textContent !== data.user_goal) {
                    userGoalDisplay.textContent = data.user_goal;
                }
                if (formulatedObjectiveDisplay && data.formulated_objective && formulatedObjectiveDisplay.textContent !== data.formulated_objective) {
                    formulatedObjectiveDisplay.textContent = data.formulated_objective;
                }
                // Update current operation display, but be mindful of pause state
                if (currentOperationDisplay && data.current_operation) {
                    if (isPaused && !data.current_operation.toLowerCase().includes('paused')) {
                        // If locally we think it's paused, but server says something else (and not already 'paused')
                        // We keep the 'Paused by user' message from the click handler for immediate feedback.
                        // Or, we can let the server state override:
                        // currentOperationDisplay.textContent = data.current_operation;
                    } else if (!isPaused) {
                        currentOperationDisplay.textContent = data.current_operation;
                    }
                }

                if (visualAnalysisDisplay && data.visual_analysis_output) { // Corrected from data.current_visual_analysis
                    visualAnalysisDisplay.textContent = data.visual_analysis_output;
                }
                if (thinkingProcessDisplay && data.thinking_process_output) { // Corrected from data.current_thinking_process
                    thinkingProcessDisplay.textContent = data.thinking_process_output;
                }
                if (stepsGeneratedDisplay && data.steps_generated) { // Corrected from data.current_steps_generated
                    if (Array.isArray(data.steps_generated) && data.steps_generated.length > 0) {
                        stepsGeneratedDisplay.innerHTML = data.steps_generated.map(step => `<li>${escapeHtml(step)}</li>`).join('');
                    } else if (Array.isArray(data.steps_generated) && data.steps_generated.length === 0 && stepsGeneratedDisplay.innerHTML !== "<li>Waiting for steps...</li>") {
                        stepsGeneratedDisplay.innerHTML = "<li>No steps generated yet.</li>";
                    } else if (typeof data.steps_generated === 'string') { // Handle if it's a string by mistake
                        stepsGeneratedDisplay.innerHTML = `<li>${escapeHtml(data.steps_generated)}</li>`;
                    }
                }
                // Update for Operations Generated
                if (operationsGeneratedDisplay && data.operations_generated) { // Already corrected to data.operations_generated
                    // Assuming data.operations_generated will be a string (e.g., JSON string of the operation)
                    // If it's an object, you might want to JSON.stringify it here with indentation
                    if (typeof data.operations_generated === 'object') { // Corrected: Check data.operations_generated
                        operationsGeneratedDisplay.textContent = JSON.stringify(data.operations_generated, null, 2); // Corrected: Use data.operations_generated
                    } else {
                        operationsGeneratedDisplay.textContent = data.operations_generated; // Corrected: Use data.operations_generated
                    }
                } else if (operationsGeneratedDisplay) {
                    // Clear or set to default if no operations data
                    operationsGeneratedDisplay.textContent = 'Waiting for operations...'; // Set a default message
                }
                
                // LLM Query, Response, Execution Result, History Log - not explicitly in current HTML focus
                // if (llmQueryDisplay && data.llm_query) { ... }
                // if (llmResponseDisplay && data.llm_response) { ... }
                // if (executionResultDisplay && data.execution_result) { ... }
                // if (historyLogDisplay && data.history_log) { ... }

                // LLM Stream content is handled by SSE, but we can update from polling as a fallback
                // or if SSE is not active. However, this might cause jumpy text if SSE is also working.
                // For now, let SSE be the primary source for llmStreamContent.
                // if (llmStreamContent && data.llm_stream_content && llmStreamContent.textContent !== data.llm_stream_content) {
                //    llmStreamContent.textContent = data.llm_stream_content;
                // }
            })
            .catch(error => console.error('Error fetching operator state:', error));
    }

    // Fetch initial state and then poll for updates
    fetchAndUpdateOperatorState();
    setInterval(fetchAndUpdateOperatorState, 1000); // Poll every 1 second for general state

    // Pause Button Functionality
    if (pauseButton && pauseIcon) {
        pauseButton.addEventListener('click', function() {
            fetch('/control/toggle_pause', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        isPaused = data.is_paused;
                        updatePauseButtonIcon();
                        console.log('Pause state toggled to:', isPaused ? 'Paused' : 'Running');
                        // Optionally, update a status display elsewhere in the UI
                        if (currentOperationDisplay) {
                            currentOperationDisplay.textContent = isPaused ? 'Paused by user' : 'Running...';
                        }
                    } else {
                        console.error('Failed to toggle pause state:', data.message);
                    }
                })
                .catch(error => console.error('Error toggling pause state:', error));
        });

        function updatePauseButtonIcon() {
            if (isPaused) {
                pauseIcon.src = '/static/imgs/play_icon.png'; // Assuming you have a play_icon.png
                pauseIcon.alt = 'Resume';
                pauseButton.title = 'Resume Automoy';
            } else {
                pauseIcon.src = '/static/imgs/pause_button.png'; // Corrected to pause_button.png
                pauseIcon.alt = 'Pause';
                pauseButton.title = 'Pause Automoy';
            }
        }
        // Initial icon update based on fetched state (will be covered by polling fetchAndUpdateOperatorState)
    } else {
        console.error('Pause button or icon element not found.');
    }

    // REMOVE OLD EventSource for /stream_llm as it's replaced by /llm_stream_updates and polling
    /*
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
    */

    // REMOVE refreshOperatorState and updateUIFromState as their functionality
    // is covered by fetchAndUpdateOperatorState and the new SSE stream logic.
    /*
    function refreshOperatorState() { ... }
    function updateUIFromState(state) { ... }
    */

    // Function to refresh the screenshot
    function refreshScreenshot() {
        const imgElement = document.getElementById('screenshotImage');
        const placeholder = document.getElementById('screenshotPlaceholder');
        if (!imgElement || !placeholder) {
            console.error('Screenshot image element or placeholder not found.');
            return;
        }

        // Add a cache-busting query parameter
        const timestamp = new Date().getTime();
        // Corrected URL to point to the copied processed screenshot in the static directory
        const screenshotUrl = `/static/processed_screenshot.png?t=${timestamp}`; 
        console.log("Refreshing screenshot from:", screenshotUrl);

        imgElement.src = screenshotUrl; 

        imgElement.onload = () => {
            console.log("Screenshot loaded successfully.");
            imgElement.style.display = 'block';
            placeholder.style.display = 'none';
        };
        imgElement.onerror = () => {
            console.error("Error loading screenshot. It might not be available yet or path is incorrect.");
            imgElement.style.display = 'none';
            placeholder.style.display = 'block';
            placeholder.textContent = 'Error loading screenshot. Waiting for next update...';
        };
    }

    // Expose refreshScreenshot to global scope if not already (e.g., for pywebview evaluate_js)
    window.refreshScreenshot = refreshScreenshot;

    // Escape HTML helper function (keep if used, otherwise can be removed)
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // SSE for operational updates (newly added)
    const eventSourceOperational = new EventSource('/stream_operator_updates');
    eventSourceOperational.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Operational update:', data);
        updateOperationalState(data);
    };
    eventSourceOperational.onerror = function(error) {
        console.error('EventSource failed:', error);
        eventSourceOperational.close();
    };
});

function updateOperationalState(data) {
    if (!data) {
        console.warn("updateOperationalState called with no data.");
        return;
    }
    console.log("Updating operational state with data:", data); // General log

    // Update User Goal
    const userGoalElement = document.getElementById('user-goal-content');
    if (userGoalElement) {
        userGoalElement.textContent = data.user_goal || 'Not set';
    }

    // Update AI Formulated Objective
    const aiObjectiveElement = document.getElementById('ai-formulated-objective-content');
    if (aiObjectiveElement) {
        aiObjectiveElement.textContent = data.formulated_objective || 'Waiting for user goal...';
    }

    // Update Steps Generated (Visual Analysis Output)
    const visualAnalysisElement = document.getElementById('visual-analysis-content');
    if (visualAnalysisElement) {
        // Assuming visual_analysis_output contains the steps (plain text or pre-formatted)
        visualAnalysisElement.textContent = data.visual_analysis_output || 'No visual analysis yet.';
    }
    
    // Update Operations Generated
    const operationsElement = document.getElementById('operations-generated-content');
    if (operationsElement) {
        console.log('Raw operations_generated from backend:', data.operations_generated); // Specific log for operations
        const operationsContent = data.operations_generated && Object.keys(data.operations_generated).length > 0
            ? JSON.stringify(data.operations_generated, null, 2)
            : '{}'; // Default to '{}' string if empty or undefined
        operationsElement.textContent = escapeHtml(operationsContent);
    }

    // Update Thinking Process
    const thinkingProcessElement = document.getElementById('thinking-process-content');
    if (thinkingProcessElement) {
        thinkingProcessElement.textContent = data.thinking_process_output || 'No thinking process logged yet.';
    }

    // Update Operator Status
    const operatorStatusElement = document.getElementById('operator-status-content');
    if (operatorStatusElement) {
        operatorStatusElement.textContent = data.operator_status || 'Idle';
    }

    // Update current step display
    const currentStepDisplayElement = document.getElementById('current-step-display');
    if (currentStepDisplayElement) {
        if (data.current_step_description) {
            currentStepDisplayElement.innerHTML = `<strong>Current:</strong> ${escapeHtml(data.current_step_description)}`;
        } else {
            currentStepDisplayElement.innerHTML = '<strong>Current:</strong> Not started';
        }
    }
}
