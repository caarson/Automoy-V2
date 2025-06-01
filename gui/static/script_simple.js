document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing UI with SIMPLE loading screen logic');
    
    // Global configuration variables
    let omniparserPort = 8111;
    
    // Load configuration first
    loadConfig();
    
    // SUPER SIMPLE LOADING SCREEN MANAGEMENT
    let loadingScreenHidden = false;
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    console.log('Loading screen initialized:', {
        loadingScreenHidden,
        loadingOverlay: !!loadingOverlay
    });

    // Simple loading screen hide function
    function hideLoadingScreen(reason) {
        if (loadingScreenHidden) {
            console.log('Loading screen already hidden, skipping...');
            return;
        }
        
        console.log(`🎯 Hiding loading screen - Reason: ${reason}`);
        loadingScreenHidden = true;
        
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
            
            // Remove the loading overlay from DOM after transition
            setTimeout(() => {
                if (loadingOverlay && loadingOverlay.classList.contains('hidden')) {
                    loadingOverlay.remove();
                    console.log('Loading overlay removed from DOM');
                }
            }, 500);
        } else {
            console.warn('Loading overlay element not found!');
        }
    }

    // IMMEDIATE FALLBACK: Hide loading screen after 1 second - NO CONDITIONS REQUIRED
    setTimeout(() => {
        console.log('🚨 1-second IMMEDIATE fallback: Hiding loading screen now');
        hideLoadingScreen('1-second immediate fallback');
    }, 1000);

    // Secondary fallback in case the first one fails
    setTimeout(() => {
        console.log('🚨 3-second backup fallback');
        hideLoadingScreen('3-second backup fallback');
    }, 3000);

    // Manual override for testing
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !loadingScreenHidden) {
            hideLoadingScreen('Escape key pressed');
        }
    });

    // Animated ellipsis for placeholder
    let ellipsisCount = 0;
    const placeholderEl = document.getElementById('screenshotPlaceholder');
    if (placeholderEl) {
        setInterval(() => {
            ellipsisCount = (ellipsisCount + 1) % 4;
            placeholderEl.textContent = 'Waiting for frame' + '.'.repeat(ellipsisCount);
        }, 500);
    }

    // Initial screenshot load 
    setTimeout(() => {
        console.log("Attempting initial screenshot load...");
        refreshScreenshot('raw');
    }, 1000);

    const goalForm = document.getElementById('goalForm');
    const goalInput = document.getElementById('goalInput');
    const userGoalDisplay = document.getElementById('userGoalDisplay');
    const formulatedObjectiveDisplay = document.getElementById('formulatedObjectiveDisplay');
    
    const llmStreamContent = document.getElementById('llmStreamContent');
    const visualAnalysisDisplay = document.getElementById('visualAnalysisDisplay');
    const thinkingProcessDisplay = document.getElementById('thinkingProcessDisplay');
    const stepsGeneratedDisplay = document.getElementById('stepsGeneratedList');
    const operationsGeneratedDisplay = document.getElementById('operationsGeneratedText');
    const currentOperationDisplay = document.getElementById('currentOperationDisplay');
    const llmQueryDisplay = document.getElementById('llmQueryDisplay');
    const llmResponseDisplay = document.getElementById('llmResponseDisplay');
    const executionResultDisplay = document.getElementById('executionResultDisplay');
    const historyLogDisplay = document.getElementById('historyLogDisplay');
    
    const pauseButton = document.getElementById('pauseButton');
    const pauseIcon = document.getElementById('pauseIcon');
    let isPaused = false;

    if (goalForm && goalInput && userGoalDisplay && formulatedObjectiveDisplay) {
        goalForm.addEventListener('submit', function(e) {
            e.preventDefault(); 
            const goalValue = goalInput.value;

            fetch('/set_goal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal: goalValue })
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => { 
                        throw new Error(`Server error: ${response.status} - ${text || 'No error message'}`); 
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.goal) {
                    userGoalDisplay.textContent = data.goal;
                    console.log('Goal set to:', data.goal);
                }
                if (data.formulated_objective) {
                    formulatedObjectiveDisplay.textContent = data.formulated_objective;
                }
                goalInput.value = '';
            })
            .catch(error => {
                console.error('Error setting goal:', error);
                if(userGoalDisplay) userGoalDisplay.textContent = 'Error setting goal. Check console.';
            });
        });
    } else {
        console.error('Goal form elements not found. Check HTML IDs: goalForm, goalInput, userGoalDisplay, formulatedObjectiveDisplay.');
    }

    // SSE for LLM stream updates
    if (llmStreamContent) {
        const eventSourceLlmStream = new EventSource('/llm_stream_updates');
        eventSourceLlmStream.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.signal === '__STREAM_START__') {
                    llmStreamContent.textContent = '';
                    console.log("LLM Stream started.");
                } else if (data.signal === '__STREAM_END__') {
                    console.log("LLM Stream ended.");
                } else if (data.chunk) {
                    llmStreamContent.textContent += data.chunk;
                }
            } catch (e) {
                console.error("Error parsing LLM stream data: ", e, "Raw data:", event.data);
            }
        };
        eventSourceLlmStream.onerror = function(err) {
            console.error('LLM EventSource failed:', err);
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

                if (currentOperationDisplay && data.current_operation_display) {
                    if (isPaused && !data.current_operation_display.toLowerCase().includes('paused')) {
                        // Keep the 'Paused by user' message for immediate feedback
                    } else if (!isPaused) {
                        currentOperationDisplay.textContent = data.current_operation_display;
                    }
                }
                
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
                    } else if (typeof data.current_steps_generated === 'string') {
                        stepsGeneratedDisplay.innerHTML = `<li>${escapeHtml(data.current_steps_generated)}</li>`;
                    }
                }

                if (operationsGeneratedDisplay && data.current_operations_generated) {
                    if (typeof data.current_operations_generated === 'object') {
                        operationsGeneratedDisplay.textContent = JSON.stringify(data.current_operations_generated, null, 2);
                    } else {
                        operationsGeneratedDisplay.textContent = data.current_operations_generated;
                    }
                } else if (operationsGeneratedDisplay) {
                    operationsGeneratedDisplay.textContent = 'Waiting for operations...';
                }

                if (data.processed_screenshot_available && data.processed_screenshot_available === true) {
                    const screenshotImg = document.getElementById('screenshotImage');
                    if (screenshotImg && !screenshotImg.src.includes('processed_screenshot.png')) {
                        console.log("Processed screenshot is available, switching display to processed screenshot");
                        refreshScreenshot('processed');
                    }
                } else {
                    console.log("Processed screenshot availability:", data.processed_screenshot_available);
                }
            })
            .catch(error => console.error('Error fetching operator state:', error));
    }

    // Fetch initial state and then poll for updates
    fetchAndUpdateOperatorState();
    setInterval(fetchAndUpdateOperatorState, 1000);

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
                pauseIcon.src = '/static/imgs/play_icon.png';
                pauseIcon.alt = 'Resume';
                pauseButton.title = 'Resume Automoy';
            } else {
                pauseIcon.src = '/static/imgs/pause_button.png';
                pauseIcon.alt = 'Pause';
                pauseButton.title = 'Pause Automoy';
            }
        }
    } else {
        console.error('Pause button or icon element not found.');
    }

    // Function to refresh the screenshot
    function refreshScreenshot(type = 'raw') {
        const timestamp = new Date().getTime();
        const screenshotImg = document.getElementById('screenshotImage');
        const placeholderEl = document.getElementById('screenshotPlaceholder');

        if (!screenshotImg) {
            console.error("Screenshot image element not found.");
            return;
        }

        if (type === 'processed') {
            const processedImageUrl = `/processed_screenshot.png?t=${timestamp}`;
            console.log("Refreshing processed screenshot from: ", processedImageUrl);
            screenshotImg.src = processedImageUrl;
            screenshotImg.style.display = 'block';
            if (placeholderEl) placeholderEl.style.display = 'none';
            screenshotImg.onload = () => console.log("Processed screenshot loaded successfully.");
            screenshotImg.onerror = () => {
                console.warn("Error loading processed screenshot, falling back to raw.");
                refreshScreenshot('raw');
            };
        } else {
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

    // Expose refreshScreenshot to global scope
    window.refreshScreenshot = refreshScreenshot;

    // Escape HTML helper function
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // SSE for operational updates
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
    console.log("Updating operational state with data:", data);

    const userGoalElement = document.getElementById('userGoalDisplay');
    if (userGoalElement) {
        userGoalElement.textContent = data.user_goal || 'Enter your goal below and press Send.';
    }

    const aiObjectiveElement = document.getElementById('formulatedObjectiveDisplay');
    if (aiObjectiveElement) {
        aiObjectiveElement.textContent = data.formulated_objective || 'Waiting for AI...';
    }

    const visualAnalysisElement = document.getElementById('visualAnalysisDisplay');
    if (visualAnalysisElement) {
        visualAnalysisElement.textContent = data.visual_analysis_output || data.current_visual_analysis || 'Waiting for visual analysis...';
    }

    const thinkingProcessElement = document.getElementById('thinkingProcessDisplay');
    if (thinkingProcessElement) {
        thinkingProcessElement.textContent = data.thinking_process_output || data.current_thinking_process || 'Waiting for thinking process...';
    }

    const operationsElement = document.getElementById('operationsGeneratedText');
    if (operationsElement) {
        console.log('Raw current_operations_generated from backend:', data.current_operations_generated);
        if (data.current_operations_generated && Object.keys(data.current_operations_generated).length > 0) {
            operationsElement.textContent = JSON.stringify(data.current_operations_generated, null, 2);
        } else {
            operationsElement.textContent = 'Waiting for operations...';
        }
    }

    const currentOperationElement = document.getElementById('currentOperationDisplay');
    if (currentOperationElement) {
        currentOperationElement.textContent = data.current_operation_display || data.operator_status || 'Idle';
    }

    const pastOperationElement = document.getElementById('pastOperationDisplay');
    if (pastOperationElement) {
        pastOperationElement.textContent = data.past_operation_display || 'None';
    }

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

    const llmStreamElement = document.getElementById('llmStreamContent');
    if (llmStreamElement && data.llm_stream_content !== undefined) {
        llmStreamElement.textContent = data.llm_stream_content || 'No stream content.';
    }
}

// OmniParser status checking functionality
let omniParserEventDispatched = false;
let omniparserPort = 8111;

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
        console.log('Status elements not found in DOM yet');
        return;
    }

    fetch(`http://localhost:${omniparserPort}/probe/`)
        .then(response => {
            console.log(`OmniParser probe response: ${response.status}`);
            if (response.ok) {
                statusDot.className = 'status-dot ready';
                statusText.textContent = 'OmniParser Ready';
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

// Regular OmniParser status checking
setInterval(() => {
    checkOmniParserStatus();
}, 5000);
