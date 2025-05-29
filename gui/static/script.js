document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing UI');      
    
    // Loading screen management
    let omniParserReady = false;
    let uiZoomed = false;
    let systemReady = false;
    let loadingScreenHidden = false;
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    // Add a flag to ensure we don't hide too early
    let initializationStarted = false;
    
    console.log('Loading screen variables initialized:', {
        omniParserReady,
        uiZoomed, 
        systemReady,
        loadingScreenHidden,
        loadingOverlay: !!loadingOverlay
    });    function checkLoadingComplete() {
        console.log(`Loading status check: omniParserReady=${omniParserReady}, uiZoomed=${uiZoomed}, systemReady=${systemReady}, loadingScreenHidden=${loadingScreenHidden}`);
        
        if (loadingScreenHidden) {
            console.log('Loading screen already hidden, skipping...');
            return;
        }
        
        // STRICT REQUIREMENT: Both uiZoomed AND systemReady must be true
        const bothConditionsMet = uiZoomed && systemReady;
        console.log(`Both conditions met check: uiZoomed(${uiZoomed}) && systemReady(${systemReady}) = ${bothConditionsMet}`);
        
        // Hide loading screen only when both UI zoom and system initialization are complete
        if (bothConditionsMet && loadingOverlay) {
            console.log('✅ BOTH UI zoom and system initialization completed - hiding loading screen to reveal GUI...');
            loadingScreenHidden = true;
            loadingOverlay.classList.add('hidden');
            
            // Remove the loading overlay from DOM after transition
            setTimeout(() => {
                if (loadingOverlay && loadingOverlay.classList.contains('hidden')) {
                    loadingOverlay.remove();
                    console.log('Loading overlay removed from DOM');
                }
            }, 500); // Match the CSS transition duration
        } else {
            console.log(`❌ Still waiting: uiZoomed=${uiZoomed}, systemReady=${systemReady} - both must be true to hide loading screen`);
        }
    }
      function hideLoadingScreen(reason) {
        console.log(`⚠️ hideLoadingScreen called with reason: ${reason}`);
        console.log(`Current state: uiZoomed=${uiZoomed}, systemReady=${systemReady}, loadingScreenHidden=${loadingScreenHidden}`);
        
        // Only allow hiding if both conditions are met OR it's a timeout/emergency
        const emergencyReasons = ['30-second timeout reached', 'Escape key pressed'];
        const isEmergency = emergencyReasons.includes(reason);
        const bothConditionsMet = uiZoomed && systemReady;
        
        if (!loadingScreenHidden && loadingOverlay && (bothConditionsMet || isEmergency)) {
            console.log(`✅ Hiding loading screen: ${reason} (emergency: ${isEmergency}, conditions met: ${bothConditionsMet})`);
            loadingScreenHidden = true;
            loadingOverlay.classList.add('hidden');
            setTimeout(() => {
                if (loadingOverlay) {
                    loadingOverlay.remove();
                }
            }, 500);
        } else {
            console.log(`❌ Refusing to hide loading screen: ${reason} - conditions not met or already hidden`);
        }
    }    // Fallback timeout to hide loading screen after 30 seconds
    setTimeout(() => {
        hideLoadingScreen('30-second timeout reached');
    }, 30000);

    // Debug: Allow manual loading screen hide with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !loadingScreenHidden) {
            hideLoadingScreen('Escape key pressed');
        }
    });
      // Listen for custom events that indicate loading progress
    window.addEventListener('omniparser-ready', function() {
        console.log('OmniParser ready event received');
        omniParserReady = true;
        checkLoadingComplete();
    });    window.addEventListener('ui-zoomed', function() {
        console.log('UI zoom completion event received - zoom has been verified as applied!');
        uiZoomed = true;
        console.log(`After ui-zoomed: uiZoomed=${uiZoomed}, systemReady=${systemReady}`);
        checkLoadingComplete();
    });
    
    window.addEventListener('system-ready', function() {
        console.log('System ready event received - system initialization completed!');
        systemReady = true;
        console.log(`After system-ready: uiZoomed=${uiZoomed}, systemReady=${systemReady}`);
        checkLoadingComplete();
    });
    
    // Initial check for OmniParser status immediately
    setTimeout(() => {
        console.log('Performing initial OmniParser status check...');
        checkOmniParserStatus();
    }, 500);
    
    // Check OmniParser status more frequently during startup (every 2 seconds for first 30 seconds)
    let startupChecks = 0;
    const maxStartupChecks = 15; // 30 seconds / 2 seconds
    const startupInterval = setInterval(() => {
        startupChecks++;
        console.log(`Startup OmniParser check ${startupChecks}/${maxStartupChecks}`);
        checkOmniParserStatus();
        
        if (startupChecks >= maxStartupChecks || omniParserReady) {
            clearInterval(startupInterval);
            console.log('Startup OmniParser checking complete');
        }
    }, 2000);
    
    // Animated ellipsis for placeholder
    let ellipsisCount = 0;
    const placeholderEl = document.getElementById('screenshotPlaceholder');
    setInterval(() => {
        ellipsisCount = (ellipsisCount + 1) % 4;
        placeholderEl.textContent = 'Waiting for frame' + '.'.repeat(ellipsisCount);
    }, 500);    // Initial screenshot load 
    setTimeout(() => {
        console.log("Attempting initial screenshot load...");
        refreshScreenshot('raw');
    }, 1000); // Try loading a screenshot after 1 second
    
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
                }                if (visualAnalysisDisplay && data.current_visual_analysis) {
                    visualAnalysisDisplay.textContent = data.current_visual_analysis;
                }
                if (thinkingProcessDisplay && data.current_thinking_process) {
                    thinkingProcessDisplay.textContent = data.current_thinking_process;
                }
                if (stepsGeneratedDisplay && data.current_steps_generated) {
                    if (Array.isArray(data.current_steps_generated) && data.current_steps_generated.length > 0) {
                        stepsGeneratedDisplay.innerHTML = data.current_steps_generated.map(step => `<li>${escapeHtml(step.description || step)}</li>`).join('');
                    } else if (Array.isArray(data.current_steps_generated) && data.current_steps_generated.length === 0 && stepsGeneratedDisplay.innerHTML !== "<li>Waiting for steps...</li>") {
                        stepsGeneratedDisplay.innerHTML = "<li>No steps generated yet.</li>";
                    } else if (typeof data.current_steps_generated === 'string') { // Handle if it's a string by mistake
                        stepsGeneratedDisplay.innerHTML = `<li>${escapeHtml(data.current_steps_generated)}</li>`;
                    }
                }
                // Update for Operations Generated
                if (operationsGeneratedDisplay && data.current_operations_generated) {
                    // Assuming data.current_operations_generated will be a string (e.g., JSON string of the operation)
                    // If it's an object, you might want to JSON.stringify it here with indentation
                    if (typeof data.current_operations_generated === 'object') {
                        operationsGeneratedDisplay.textContent = JSON.stringify(data.current_operations_generated, null, 2);
                    } else {
                        operationsGeneratedDisplay.textContent = data.current_operations_generated;
                    }
                } else if (operationsGeneratedDisplay) {
                    // Clear or set to default if no operations data
                    operationsGeneratedDisplay.textContent = 'Waiting for operations...'; // Set a default message
                }
                  // LLM Query, Response, Execution Result, History Log - not explicitly in current HTML focus
                // if (llmQueryDisplay && data.llm_query) { ... }
                // if (llmResponseDisplay && data.llm_response) { ... }
                // if (executionResultDisplay && data.execution_result) { ... }
                // if (historyLogDisplay && data.history_log) { ... }                // Check if processed screenshot is available and switch to it
                if (data.processed_screenshot_available && data.processed_screenshot_available === true) {
                    const screenshotImg = document.getElementById('screenshotImage');
                    if (screenshotImg && !screenshotImg.src.includes('processed_screenshot.png')) {
                        console.log("Processed screenshot is available, switching display to processed screenshot");
                        refreshScreenshot('processed');
                    }
                } else {
                    // Debug: Log the state of processed_screenshot_available
                    console.log("Processed screenshot availability:", data.processed_screenshot_available);
                }

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
    */    // Function to refresh the screenshot
    function refreshScreenshot(type = 'raw') { // Added type parameter, default to 'raw'
        const timestamp = new Date().getTime();
        const screenshotImg = document.getElementById('screenshotImage');
        const placeholderEl = document.getElementById('screenshotPlaceholder');

        if (!screenshotImg) {
            console.error("Screenshot image element not found.");
            return;
        }

        if (type === 'processed') {
            // Try to load processed screenshot first
            const processedImageUrl = `/processed_screenshot.png?t=${timestamp}`;
            console.log("Refreshing processed screenshot from: ", processedImageUrl);
            screenshotImg.src = processedImageUrl;
            screenshotImg.style.display = 'block';
            if (placeholderEl) placeholderEl.style.display = 'none';
            screenshotImg.onload = () => console.log("Processed screenshot loaded successfully.");
            screenshotImg.onerror = () => {
                console.warn("Error loading processed screenshot, falling back to raw.");
                // Fallback to raw screenshot if processed fails
                refreshScreenshot('raw');
            };
        } else {
            // Load raw screenshot (default)
            const rawImageUrl = `/automoy_current.png?t=${timestamp}`;
            console.log("Refreshing raw screenshot from: ", rawImageUrl);
            screenshotImg.src = rawImageUrl;
            screenshotImg.style.display = 'block';
            if (placeholderEl) placeholderEl.style.display = 'none';
            screenshotImg.onload = () => console.log("Raw screenshot loaded successfully.");
            screenshotImg.onerror = () => {
                console.error("Error loading raw screenshot.");
                screenshotImg.style.display = 'none';
                if (placeholderEl) placeholderEl.style.display = 'flex';
            };
        }
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

    // Update operations generated list (newly added)
    if (data.operations_generated && data.operations_generated.operations) {
        const operationsList = document.getElementById('operations-generated-list');
        if (operationsList) {
            operationsList.innerHTML = ''; // Clear previous operations
            if (Array.isArray(data.operations_generated.operations)) {
                data.operations_generated.operations.forEach(op => {
                    const listItem = document.createElement('li');
                    listItem.textContent = `${op.type}: ${op.summary}`;
                    if (op.details) {
                        const detailsText = document.createElement('small');
                        detailsText.textContent = ` (${op.details})`;
                        listItem.appendChild(detailsText);
                    }
                    operationsList.appendChild(listItem);
                });
            } else {
                console.warn("data.operations_generated.operations is not an array:", data.operations_generated.operations);
            }
            // Update thinking process if available within operations_generated
            if (data.operations_generated.thinking_process) {
                document.getElementById('thinking-process-content').textContent = data.operations_generated.thinking_process;
            }
        } else {
            console.error('Operations generated list element not found.');
        }
    } else {
        // console.log("No operations_generated data or missing .operations property"); // Keep this for debugging if needed
        const operationsList = document.getElementById('operations-generated-list');
        if (operationsList) {
            operationsList.innerHTML = '<li>No operations generated yet.</li>';
        }
    }
}

// OmniParser status checking functionality
let omniParserEventDispatched = false;
function checkOmniParserStatus() {
    const statusDot = document.getElementById('omniparserStatusDot');
    const statusText = document.getElementById('omniparserStatusText');
    
    console.log('Checking OmniParser status...');
    
    if (!statusDot || !statusText) {
        console.log('Status elements not found in DOM yet');
        return;
    }
    
    // Try to ping OmniParser server directly
    fetch('http://localhost:8111/probe/')
        .then(response => {
            console.log(`OmniParser probe response: ${response.status}`);
            if (response.ok) {
                statusDot.className = 'status-dot ready';
                statusText.textContent = 'OmniParser Ready';
                
                // Dispatch custom event for loading screen management (only once)
                if (!omniParserEventDispatched) {
                    window.dispatchEvent(new CustomEvent('omniparser-ready'));
                    omniParserEventDispatched = true;
                    console.log('OmniParser ready event dispatched for the first time');
                }
            } else {
                statusDot.className = 'status-dot error';
                statusText.textContent = 'OmniParser Error';
                console.log('OmniParser returned error status');
            }
        })
        .catch(error => {
            statusDot.className = 'status-dot';
            statusText.textContent = 'OmniParser Offline';
            console.log('OmniParser connection failed:', error.message);
        });
}

// Regular OmniParser status checking (after startup period)
setInterval(() => {
    if (!omniParserReady) {
        checkOmniParserStatus();
    }
}, 5000);
