// Global configuration variables
let omniparserPort = 8111; // Default value, will be updated by loadConfig
let omniParserReady = false;
let loadingScreenHidden = false;

// GLOBAL loading screen hide function (accessible from backend's direct call)
window.hideLoadingScreen = function(reason) {
    if (loadingScreenHidden) {
        console.log(`Loading screen already hidden, ignoring request: ${reason}`);
        return;
    }
    
    console.log(`🎯 HIDING LOADING SCREEN - Reason: ${reason}`);
    
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        console.log('Loading overlay found, applying hiding methods...');
        
        // CSS class method
        overlay.classList.add('hidden');
        
        // Direct style manipulation
        overlay.style.display = 'none';
        overlay.style.visibility = 'hidden';
        overlay.style.opacity = '0';
        
        // EXTRA DEFENSIVE: Remove from DOM completely to prevent re-appearance
        overlay.remove();
        
        console.log('Loading screen hidden successfully and removed from DOM');
    } else {
        console.warn('Loading overlay element not found!');
    }
    
    loadingScreenHidden = true;
    console.log('Loading screen hide complete');
    
    // DEFENSIVE: Prevent any future attempts to show loading screen
    window.loadingScreenPermanentlyHidden = true;
};

// SINGLE system-ready event listener (moved outside DOMContentLoaded for reliability)
console.log('🎯 SCRIPT: Registering MULTIPLE system-ready event listeners...');

// Primary event listener
window.addEventListener('system-ready', function(event) {
    console.log('✅ PRIMARY: System-ready event received - hiding loading screen');
    console.log('Event details:', event);
    window.hideLoadingScreen('System ready event received - PRIMARY');
});

// Backup event listener on document
document.addEventListener('system-ready', function(event) {
    console.log('✅ BACKUP: System-ready event received on document - hiding loading screen');
    console.log('Event details:', event);
    window.hideLoadingScreen('System ready event received - BACKUP');
});

console.log('🎯 SCRIPT: Multiple system-ready event listeners registered!');

// EMERGENCY: If loading screen is still visible after 8 seconds, force hide it
setTimeout(() => {
    if (!loadingScreenHidden) {
        console.warn('🚨 EMERGENCY: Loading screen still visible after 8 seconds - forcing hide');
        window.hideLoadingScreen('8-second emergency fallback');
    }
}, 8000);

// POLLING: Check every 2 seconds if backend is trying to hide the loading screen
let pollCount = 0;
const loadingPollInterval = setInterval(() => {
    pollCount++;
    console.log(`🔄 POLL ${pollCount}: Checking if loading screen should be hidden...`);
    
    if (loadingScreenHidden) {
        console.log('🔄 POLL: Loading screen already hidden, stopping poll');
        clearInterval(loadingPollInterval);
        return;
    }
    
    // After 6 polls (12 seconds), force hide
    if (pollCount >= 6) {
        console.warn('🔄 POLL: Reached maximum polls - forcing loading screen hide');
        window.hideLoadingScreen('Polling timeout fallback');
        clearInterval(loadingPollInterval);
    }
}, 2000);

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing UI');
    console.log('🎯 DOM: window.hideLoadingScreen available:', typeof window.hideLoadingScreen);
    
    // Load configuration first
    loadConfig();
    
    const loadingOverlay = document.getElementById('loadingOverlay');
    console.log('Loading screen variables initialized:', {
        omniParserReady,
        loadingScreenHidden,
        loadingOverlay: !!loadingOverlay
    });
    
    // PROPER loading screen management - wait for system-ready event
    console.log('⏳ Loading screen will remain visible until system-ready event is received');    // Safety fallback - hide after 20 seconds if no system-ready event
    setTimeout(() => {
        if (!loadingScreenHidden) {
            console.log('⚠️ Safety timeout - hiding loading screen after 20 seconds');
            window.hideLoadingScreen('20-second safety timeout');
        }
    }, 20000);

    // Debug: Allow manual loading screen hide with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !loadingScreenHidden) {
            window.hideLoadingScreen('Escape key pressed');
        }
    });
      
    // Simplified event listeners - no complex loading screen logic needed
    window.addEventListener('omniparser-ready', function() {
        console.log('OmniParser ready event received');
        omniParserReady = true;
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
    }, 2000);    // EMERGENCY FALLBACK: Force hide loading screen after 10 seconds if events don't fire
    setTimeout(() => {
        if (!loadingScreenHidden) {
            console.warn('🚨 EMERGENCY FALLBACK: Loading screen still visible after 10 seconds - forcing hide');
            console.log(`Current state: loadingScreenHidden=${loadingScreenHidden}`);
            hideLoadingScreen('Emergency timeout fallback');
        }
    }, 10000); // 10 second emergency fallback

    // Add manual override for testing (Ctrl+H to force hide)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'h' && !loadingScreenHidden) {
            console.log('🔧 MANUAL OVERRIDE: Ctrl+H pressed - forcing loading screen hide');
            hideLoadingScreen('Manual override (Ctrl+H)');
        }
    });
    
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
            
            // Prevent zoom interference with form submission
            console.log('Form submitted - preventing any zoom interference');
            
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
                
                // Ensure zoom stability after form submission
                console.log('Form submission completed - zoom should remain stable');
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
                }                // Update current operation display, but be mindful of pause state
                if (currentOperationDisplay && data.current_operation_display) {
                    if (isPaused && !data.current_operation_display.toLowerCase().includes('paused')) {
                        // If locally we think it's paused, but server says something else (and not already 'paused')
                        // We keep the 'Paused by user' message from the click handler for immediate feedback.
                        // Or, we can let the server state override:
                        // currentOperationDisplay.textContent = data.current_operation_display;
                    } else if (!isPaused) {
                        currentOperationDisplay.textContent = data.current_operation_display;
                    }
                }
                  // Update past operation display
                const pastOperationDisplay = document.getElementById('pastOperationDisplay');
                if (pastOperationDisplay && data.past_operation_display) {
                    pastOperationDisplay.textContent = data.past_operation_display;
                }
                
                if (visualAnalysisDisplay && data.current_visual_analysis) {
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
                }                // LLM Query, Response, Execution Result, History Log - not explicitly in current HTML focus
                // if (llmQueryDisplay && data.llm_query) { ... }
                // if (llmResponseDisplay && data.llm_response) { ... }
                // if (executionResultDisplay && data.execution_result) { ... }
                // if (historyLogDisplay && data.history_log) { ... }
                
                // Check if processed screenshot is available and switch to it
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
        console.error('EventSource failed:', error);        eventSource.close();
    };
    */
    
    // REMOVE refreshOperatorState and updateUIFromState as their functionality
    // is covered by fetchAndUpdateOperatorState and the new SSE stream logic.
    /*
    function refreshOperatorState() { ... }
    function updateUIFromState(state) { ... }
    */
    
    // Function to refresh the screenshot
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

    // Update User Goal - using correct element ID
    const userGoalElement = document.getElementById('userGoalDisplay');
    if (userGoalElement) {
        userGoalElement.textContent = data.user_goal || 'Enter your goal below and press Send.';
    }

    // Update AI Formulated Objective - using correct element ID
    const aiObjectiveElement = document.getElementById('formulatedObjectiveDisplay');
    if (aiObjectiveElement) {
        aiObjectiveElement.textContent = data.formulated_objective || 'Waiting for AI...';
    }

    // Update Visual Analysis - using correct element ID
    const visualAnalysisElement = document.getElementById('visualAnalysisDisplay');
    if (visualAnalysisElement) {
        visualAnalysisElement.textContent = data.visual_analysis_output || data.current_visual_analysis || 'Waiting for visual analysis...';
    }

    // Update Thinking Process - using correct element ID
    const thinkingProcessElement = document.getElementById('thinkingProcessDisplay');
    if (thinkingProcessElement) {
        thinkingProcessElement.textContent = data.thinking_process_output || data.current_thinking_process || 'Waiting for thinking process...';
    }

    // Update Operations Generated - using correct element ID
    const operationsElement = document.getElementById('operationsGeneratedText');
    if (operationsElement) {
        console.log('Raw current_operations_generated from backend:', data.current_operations_generated); // Specific log for operations
        if (data.current_operations_generated && Object.keys(data.current_operations_generated).length > 0) {
            operationsElement.textContent = JSON.stringify(data.current_operations_generated, null, 2);
        } else {
            operationsElement.textContent = 'Waiting for operations...';
        }
    }

    // Update Current Operation - using correct element ID
    const currentOperationElement = document.getElementById('currentOperationDisplay');
    if (currentOperationElement) {
        currentOperationElement.textContent = data.current_operation_display || data.operator_status || 'Idle';
    }

    // Update Past Operation - using correct element ID  
    const pastOperationElement = document.getElementById('pastOperationDisplay');
    if (pastOperationElement) {
        pastOperationElement.textContent = data.past_operation_display || 'None';
    }

    // Update Steps Generated List - using correct element ID
    const stepsListElement = document.getElementById('stepsGeneratedList');
    if (stepsListElement && data.current_steps_generated) {
        if (Array.isArray(data.current_steps_generated) && data.current_steps_generated.length > 0) {
            stepsListElement.innerHTML = data.current_steps_generated.map(step => 
                `<li>${escapeHtml(step.description || step)}</li>`
            ).join('');
        } else if (Array.isArray(data.current_steps_generated) && data.current_steps_generated.length === 0) {
            stepsListElement.innerHTML = "<li>No steps generated yet.</li>";
        } else if (typeof data.current_steps_generated === 'string') {
            stepsListElement.innerHTML = `<li>${escapeHtml(data.current_steps_generated)}</li>`;
        }
    }

    // Update LLM Stream Content - using correct element ID
    const llmStreamElement = document.getElementById('llmStreamContent');
    if (llmStreamElement && data.llm_stream_content !== undefined) {
        llmStreamElement.textContent = data.llm_stream_content || 'No stream content.';
    }
}
}

// OmniParser status checking functionality
let omniParserEventDispatched = false;
let omniparserPort = 8111; // Default port

// Fetch configuration on page load
async function loadConfig() {
    try {
        const response = await fetch('/config');
        if (response.ok) {
            const config = await response.json();
            omniparserPort = config.OMNIPARSER_PORT || 8111;
            console.log(`Configuration loaded: OmniParser port ${omniparserPort}`);
        }
    } catch (error) {
        console.warn('Failed to load configuration, using defaults:', error);
    }
}

function checkOmniParserStatus() {
    const statusDot = document.getElementById('omniparserStatusDot');
    const statusText = document.getElementById('omniparserStatusText');
    
    console.log(`Checking OmniParser status on port ${omniparserPort}...`);
    
    if (!statusDot || !statusText) {
        console.log('Status elements not found in DOM yet');        return;
    }
    
    // Try to ping OmniParser server directly using the loaded configuration
    fetch(`http://localhost:${omniparserPort}/probe/`)
        .then(response => {
            console.log(`OmniParser probe response: ${response.status}`);
            if (response.ok) {
                statusDot.className = 'status-dot ready';
                statusText.textContent = 'OmniParser Ready';
                  // Set the flag but keep checking in case server goes down
                omniParserReady = true;
                
                // Hide loading screen once OmniParser is ready
                if (!loadingScreenHidden) {
                    hideLoadingScreen('OmniParser is ready');
                }
            } else {
                statusDot.className = 'status-dot error';                statusText.textContent = 'OmniParser Error';
                console.log('OmniParser returned error status');
            }
        })
        .catch(error => {
            statusDot.className = 'status-dot';
            statusText.textContent = 'OmniParser Offline';
            console.log('OmniParser connection failed:', error.message);
            omniParserReady = false; // Reset flag when connection fails
        });
}

// Regular OmniParser status checking - check continuously to handle server restarts/crashes
setInterval(() => {
    checkOmniParserStatus();
}, 5000);

    // Fallback: Hide loading screen after a maximum timeout even if events don't fire
setTimeout(() => {
    if (!loadingScreenHidden) {
        console.log('⚠️ Loading screen timeout reached - forcing loading screen to hide');
        hideLoadingScreen('Timeout fallback');
    }
}, 10000); // 10 second maximum timeout

// IMMEDIATE fallback based on page readiness - hide after 5 seconds if page is complete
if (document.readyState === 'complete') {
    setTimeout(() => {
        console.log('⚠️ Document complete fallback - 5 second timer');
        if (!loadingScreenHidden) {
            hideLoadingScreen('Document complete 5-second fallback');
        }
    }, 5000); // 5 seconds after document complete
} else {
    // If document isn't complete yet, add a listener
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            console.log('⚠️ DOMContentLoaded fallback - 5 second timer');
            if (!loadingScreenHidden) {
                hideLoadingScreen('DOMContentLoaded 5-second fallback');
            }
        }, 5000);
    });
}

}); // Closing brace for main DOMContentLoaded event listener
